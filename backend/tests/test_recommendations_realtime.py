"""Recommendations follow the data immediately: no waiting for a cache to expire."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.database import SessionLocal
from app.models.environmental_factor import EnvironmentalFactor
from app.models.recommendation import Recommendation
from app.routers.recommendations import _signature


def add_reading(client, headers, systolic, diastolic, days_ago=0):
    when = (datetime.now(UTC) - timedelta(days=days_ago, seconds=5)).replace(microsecond=0)
    response = client.post(
        "/readings",
        json={"systolic": systolic, "diastolic": diastolic, "heart_rate": 70, "recorded_at": when.isoformat()},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_factors(client, headers, **answers):
    logged_date = datetime.now(UTC).date().isoformat()
    response = client.post("/factors", json={**answers, "logged_date": logged_date}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def recs(client, headers, **params):
    response = client.get("/recommendations/me", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def said(items):
    return " ".join(r["message"] for r in items).lower()


def stored_rows(patient_email_headers=None):
    db = SessionLocal()
    try:
        return db.query(Recommendation).count()
    finally:
        db.close()


class TestFollowsTheData:
    def test_a_first_reading_changes_the_advice_at_once(self, client, patient_headers):
        assert "haven't logged any readings" in said(recs(client, patient_headers))
        add_reading(client, patient_headers, 118, 76)
        after = said(recs(client, patient_headers))
        assert "haven't logged any readings" not in after
        assert "controlled" in after

    def test_a_high_reading_moves_the_summary_without_waiting(self, client, patient_headers):
        add_reading(client, patient_headers, 118, 76)
        assert "controlled" in said(recs(client, patient_headers))
        for _ in range(4):
            add_reading(client, patient_headers, 170, 104)
        assert "high" in recs(client, patient_headers)[0]["message"].lower()

    def test_a_new_lifestyle_entry_is_reflected_immediately(self, client, patient_headers):
        for d in range(4):
            add_reading(client, patient_headers, 165, 100, days_ago=d)
        before = said(recs(client, patient_headers))
        assert "lifestyle page" in before and "smoked" not in before

        add_factors(client, patient_headers, smoked=True, caffeine_intake="high")
        after = said(recs(client, patient_headers))
        assert "smok" in after and "coffee or tea" in after
        assert "log your stress, sleep, diet" not in after  # the "start logging" nudge is gone

    def test_deleting_a_reading_updates_the_advice(self, client, patient_headers):
        reading = add_reading(client, patient_headers, 118, 76)
        assert "controlled" in said(recs(client, patient_headers))
        assert client.delete(f"/readings/{reading['reading_id']}", headers=patient_headers).status_code == 204
        assert "haven't logged any readings" in said(recs(client, patient_headers))

    def test_deleting_a_lifestyle_entry_removes_its_advice(self, client, patient_headers):
        for d in range(4):
            add_reading(client, patient_headers, 165, 100, days_ago=d)
        entry = add_factors(client, patient_headers, smoked=True)
        assert "ask your clinic about help to quit" in said(recs(client, patient_headers))
        assert client.delete(f"/factors/{entry['factor_id']}", headers=patient_headers).status_code == 204
        assert "ask your clinic about help to quit" not in said(recs(client, patient_headers))

    def test_a_legacy_future_dated_check_in_is_not_used_as_evidence(self, client, patient_headers):
        for d in range(4):
            add_reading(client, patient_headers, 165, 100, days_ago=d)

        patient_id = uuid.UUID(client.get("/auth/me", headers=patient_headers).json()["user_id"])
        db = SessionLocal()
        try:
            db.add(
                EnvironmentalFactor(
                    patient_id=patient_id,
                    logged_date=date.today() + timedelta(days=7),
                    smoked=True,
                )
            )
            db.commit()
        finally:
            db.close()

        advice = said(recs(client, patient_headers))
        assert "help to quit" not in advice
        assert "you smoked" not in advice

    def test_one_patients_data_never_changes_anothers_advice(self, client, register_and_login):
        mine, other = register_and_login("mine@example.com"), register_and_login("other@example.com")
        before = said(recs(client, other))
        for d in range(4):
            add_reading(client, mine, 165, 100, days_ago=d)
        add_factors(client, mine, smoked=True)
        assert said(recs(client, other)) == before


class TestTheRequestItself:
    def test_responses_must_not_be_reused_by_browsers_or_proxies(self, client, patient_headers):
        response = client.get("/recommendations/me", headers=patient_headers)
        assert response.headers["cache-control"] == "no-store"

    def test_the_requested_period_is_respected(self, client, patient_headers):
        add_reading(client, patient_headers, 118, 76)
        seven = said(recs(client, patient_headers, period_days=7))
        thirty = said(recs(client, patient_headers, period_days=30))
        assert "7 days" in seven and "30 days" in thirty

    def test_the_order_is_the_order_it_was_generated_in_every_time(self, client, patient_headers):
        for d in range(4):
            add_reading(client, patient_headers, 165, 100, days_ago=d)
        add_factors(client, patient_headers, smoked=True, sleep_hours=4, stress_level="high")
        first = [r["message"] for r in recs(client, patient_headers)]
        for _ in range(3):
            assert [r["message"] for r in recs(client, patient_headers)] == first  # served from storage, same order
        assert first[0].lower().startswith("your average blood pressure")  # the summary always leads


class TestHistory:
    def test_a_changed_confidence_is_a_changed_batch(self):
        base = {
            "message": "The same patient-facing estimate.",
            "based_on_trend": "high",
            "source": "model",
        }

        assert _signature([{**base, "confidence": 0.41}]) != _signature([{**base, "confidence": 0.42}])

    def test_unchanged_advice_is_not_written_again(self, client, patient_headers):
        # A large batch (summary, readings line and several habits) so a scrambled order can't match by chance.
        for d in range(4):
            add_reading(client, patient_headers, 165, 100, days_ago=d)
        add_factors(client, patient_headers, smoked=True, sleep_hours=4, stress_level="high", caffeine_intake="high")
        first = recs(client, patient_headers)
        assert len(first) >= 5
        rows = stored_rows()
        for _ in range(3):
            again = recs(client, patient_headers)
            assert [r["recommendation_id"] for r in again] == [r["recommendation_id"] for r in first]
        assert stored_rows() == rows

    def test_changed_advice_adds_a_batch_and_keeps_the_old_one_as_history(self, client, patient_headers):
        add_reading(client, patient_headers, 118, 76)
        first = recs(client, patient_headers)
        add_reading(client, patient_headers, 120, 78)
        second = recs(client, patient_headers)

        assert {r["recommendation_id"] for r in first}.isdisjoint({r["recommendation_id"] for r in second})
        assert stored_rows() == len(first) + len(second)
        assert said(second) != said(first)

    def test_only_the_most_recent_batches_are_kept(self, client, patient_headers, monkeypatch):
        monkeypatch.setattr("app.routers.recommendations.MAX_HISTORY_BATCHES", 3)
        latest = None
        for i in range(6):
            add_reading(client, patient_headers, 118 + i, 76)  # each reading changes the averages, so the advice
            latest = recs(client, patient_headers)
        db = SessionLocal()
        try:
            batches = db.query(Recommendation.created_at).distinct().count()
        finally:
            db.close()
        assert batches <= 4  # the limit plus the batch just written
        assert recs(client, patient_headers)[0]["message"] == latest[0]["message"]

    def test_other_periods_are_answered_but_never_stored(self, client, patient_headers):
        add_reading(client, patient_headers, 118, 76)
        recs(client, patient_headers, period_days=30)
        assert stored_rows() == 0


@pytest.mark.parametrize("path", ["/recommendations/me"])
def test_clinicians_cannot_use_the_patient_endpoint(client, path):
    assert client.get(path).status_code == 401
