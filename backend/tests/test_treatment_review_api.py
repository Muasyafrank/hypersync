"""The clinician-only HTTP surface of the treatment-review flag."""

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.reading import BPReading
from app.models.user import PatientProfile, User, UserRole

PASSWORD = "correct-horse-battery"
CONTROLLED, ELEVATED, HIGH = (118, 76), (142, 88), (162, 100)


@pytest.fixture()
def clinician_headers(client):
    db = SessionLocal()
    try:
        db.add(
            User(
                full_name="Dr. Test Clinician",
                email="dr.test@example.com",
                password_hash=hash_password(PASSWORD),
                role=UserRole.clinician,
            )
        )
        db.commit()
    finally:
        db.close()
    token = client.post("/auth/login", data={"username": "dr.test@example.com", "password": PASSWORD}).json()
    return {"Authorization": f"Bearer {token['access_token']}", "X-Timezone": "UTC"}


@pytest.fixture()
def make_patient(client, register_and_login):
    """Create a patient with four weeks of readings (oldest week first). Returns (headers, user_id)."""

    def _make(email, weeks, per_week=7):
        headers = register_and_login(email)
        user_id = client.get("/auth/me", headers=headers).json()["user_id"]
        now = datetime.now(UTC)
        db = SessionLocal()
        try:
            for index, week in enumerate(reversed(weeks)):  # index 0 = most recent week
                for day in range(per_week):
                    for second in (1, 2):  # same clock time each day keeps every reading in its own local day
                        db.add(
                            BPReading(
                                patient_id=uuid.UUID(user_id),
                                systolic=week[0],
                                diastolic=week[1],
                                heart_rate=70,
                                recorded_at=now - timedelta(days=7 * index + day, seconds=second),
                            )
                        )
            db.commit()
        finally:
            db.close()
        return headers, user_id

    return _make


def log_meds(client, headers, taken, missed):
    for i, answer in enumerate([True] * taken + [False] * missed):
        day = (datetime.now(UTC).date() - timedelta(days=i)).isoformat()
        assert (
            client.post("/factors", json={"medication_taken": answer, "logged_date": day}, headers=headers).status_code
            == 201
        )


def review_url(patient_id, suffix=""):
    return f"/treatment-review/patients/{patient_id}{suffix}"


class TestAccess:
    def test_a_patient_can_never_see_it(self, client, make_patient):
        headers, user_id = make_patient("pat@example.com", [ELEVATED] * 4)
        assert client.get(review_url(user_id), headers=headers).status_code == 403
        assert client.post(review_url(user_id, "/reviewed"), json={}, headers=headers).status_code == 403

    def test_it_requires_a_login(self, client, make_patient):
        _, user_id = make_patient("pat@example.com", [ELEVATED] * 4)
        assert client.get(review_url(user_id)).status_code == 401

    def test_nothing_about_it_leaks_into_patient_responses(self, client, make_patient):
        headers, _ = make_patient("pat@example.com", [HIGH] * 4)
        log_meds(client, headers, 9, 1)
        everything = " ".join(
            client.get(path, headers=headers).text.lower()
            for path in (
                "/auth/me",
                "/readings/me/summary",
                "/readings/me/trend?period_days=30",
                "/recommendations/me",
                "/alerts/me",
            )
        )
        assert "treatment review" not in everything and "treatment_review" not in everything

    def test_unknown_or_non_patient_ids_are_404(self, client, clinician_headers):
        assert (
            client.get(review_url("00000000-0000-0000-0000-000000000000"), headers=clinician_headers).status_code == 404
        )
        me = client.get("/auth/me", headers=clinician_headers).json()["user_id"]
        assert client.get(review_url(me), headers=clinician_headers).status_code == 404  # a clinician is not a patient


class TestTheFlag:
    def test_a_clinician_sees_why_a_patient_is_flagged(self, client, clinician_headers, make_patient):
        headers, user_id = make_patient("pat@example.com", [CONTROLLED, ELEVATED, ELEVATED, ELEVATED])
        log_meds(client, headers, 9, 1)

        body = client.get(review_url(user_id), headers=clinician_headers).json()
        assert body["flagged"] and body["active"]
        assert body["kind"] == "sustained_elevated_high" and body["level"] == "routine"
        assert "does not rule out other causes" in body["headline"]
        assert [w["status"] for w in body["weeks"]] == ["controlled", "elevated", "elevated", "elevated"]
        assert body["adherence"] == {"answered": 10, "missed": 1, "status": "good"}
        assert [line.split(":")[0] for line in body["confirm_first"]] == [
            "Medication use",
            "Measurement",
            "Lifestyle",
        ]
        assert "does not recommend a drug or dose" in body["disclaimer"]

    def test_a_controlled_patient_is_not_flagged_but_still_gets_the_weekly_picture(
        self, client, clinician_headers, make_patient
    ):
        _, user_id = make_patient("pat@example.com", [CONTROLLED] * 4)
        body = client.get(review_url(user_id), headers=clinician_headers).json()
        assert not body["flagged"] and body["headline"] is None
        assert len(body["weeks"]) == 4

    def test_weekly_review_uses_the_patient_calendar_not_the_clinicians(self, client, clinician_headers, make_patient):
        _, user_id = make_patient("pat@example.com", [ELEVATED] * 4)
        now = datetime.now(UTC)
        # Choose a patient calendar whose date differs from the clinician's UTC
        # calendar at every hour of the day.
        patient_timezone = "Etc/GMT+12" if now.hour < 12 else "Pacific/Kiritimati"

        db = SessionLocal()
        try:
            profile = db.query(PatientProfile).filter(PatientProfile.user_id == uuid.UUID(user_id)).one()
            profile.timezone = patient_timezone
            db.commit()
        finally:
            db.close()

        body = client.get(review_url(user_id), headers=clinician_headers).json()
        patient_today = now.astimezone(ZoneInfo(patient_timezone)).date().isoformat()
        clinician_today = now.astimezone(ZoneInfo("UTC")).date().isoformat()
        assert body["weeks"][-1]["end"] == patient_today
        assert patient_today != clinician_today

    def test_the_patient_list_carries_a_badge_only_for_flagged_patients(self, client, clinician_headers, make_patient):
        make_patient("flagged@example.com", [HIGH] * 4)
        make_patient("fine@example.com", [CONTROLLED] * 4)
        rows = {r["email"]: r for r in client.get("/users/patients/summary", headers=clinician_headers).json()}
        assert rows["flagged@example.com"]["treatment_review"] == {
            "kind": "sustained_elevated_high",
            "level": "priority",
        }
        assert rows["fine@example.com"]["treatment_review"] is None


class TestMarkingAsReviewed:
    def test_it_records_the_review_and_pauses_the_flag(self, client, clinician_headers, make_patient):
        _, user_id = make_patient("pat@example.com", [ELEVATED] * 4)

        reviewed = client.post(
            review_url(user_id, "/reviewed"),
            json={"note": "  Discussed; recheck in 4 weeks  "},
            headers=clinician_headers,
        )
        assert reviewed.status_code == 201
        body = reviewed.json()
        assert body["flagged"] and not body["active"]  # the facts remain, the nudge pauses
        assert body["snoozed_until"] is not None
        [record] = body["recent_reviews"]
        assert record["note"] == "Discussed; recheck in 4 weeks"
        assert record["clinician_name"] == "Dr. Test Clinician"
        assert record["flag_kind"] == "sustained_elevated_high"
        assert record["flag_level"] == "routine"

    def test_the_reviewer_name_is_an_immutable_snapshot(self, client, clinician_headers, make_patient):
        _, user_id = make_patient("pat@example.com", [ELEVATED] * 4)
        client.post(review_url(user_id, "/reviewed"), json={}, headers=clinician_headers)

        db = SessionLocal()
        try:
            clinician = db.query(User).filter(User.email == "dr.test@example.com").one()
            clinician.full_name = "Dr. Renamed Later"
            db.commit()
        finally:
            db.close()

        [record] = client.get(review_url(user_id), headers=clinician_headers).json()["recent_reviews"]
        assert record["clinician_name"] == "Dr. Test Clinician"

    def test_the_badge_disappears_after_a_review(self, client, clinician_headers, make_patient):
        _, user_id = make_patient("pat@example.com", [HIGH] * 4)
        client.post(review_url(user_id, "/reviewed"), json={}, headers=clinician_headers)
        [row] = client.get("/users/patients/summary", headers=clinician_headers).json()
        assert row["treatment_review"] is None

    def test_a_review_only_pauses_the_same_flag_kind(self, client, clinician_headers, make_patient):
        _, user_id = make_patient("pat@example.com", [HIGH] * 4)
        client.post(review_url(user_id, "/reviewed"), json={}, headers=clinician_headers)

        db = SessionLocal()
        try:
            readings = db.query(BPReading).filter(BPReading.patient_id == uuid.UUID(user_id)).all()
            for reading in readings:
                reading.systolic = 86
                reading.diastolic = 54
            db.commit()
        finally:
            db.close()

        body = client.get(review_url(user_id), headers=clinician_headers).json()
        assert body["kind"] == "sustained_low"
        assert body["active"]
        assert body["snoozed_until"] is None

    def test_an_unflagged_review_does_not_pause_a_later_flag(self, client, clinician_headers, make_patient):
        _, user_id = make_patient("pat@example.com", [CONTROLLED] * 4)
        client.post(review_url(user_id, "/reviewed"), json={}, headers=clinician_headers)

        db = SessionLocal()
        try:
            readings = db.query(BPReading).filter(BPReading.patient_id == uuid.UUID(user_id)).all()
            for reading in readings:
                reading.systolic = 142
                reading.diastolic = 88
            db.commit()
        finally:
            db.close()

        body = client.get(review_url(user_id), headers=clinician_headers).json()
        assert body["kind"] == "sustained_elevated_high"
        assert body["active"]
        assert body["snoozed_until"] is None

    def test_a_note_is_optional_and_bounded(self, client, clinician_headers, make_patient):
        _, user_id = make_patient("pat@example.com", [ELEVATED] * 4)
        assert client.post(review_url(user_id, "/reviewed"), json={}, headers=clinician_headers).status_code == 201
        too_long = {"note": "x" * 501}
        assert (
            client.post(review_url(user_id, "/reviewed"), json=too_long, headers=clinician_headers).status_code == 422
        )

    def test_reviewing_an_unflagged_patient_is_allowed_and_records_no_flag(
        self, client, clinician_headers, make_patient
    ):
        _, user_id = make_patient("pat@example.com", [CONTROLLED] * 4)
        body = client.post(
            review_url(user_id, "/reviewed"), json={"note": "Routine check"}, headers=clinician_headers
        ).json()
        assert body["recent_reviews"][0]["flag_kind"] is None

    def test_the_history_is_newest_first(self, client, clinician_headers, make_patient):
        _, user_id = make_patient("pat@example.com", [ELEVATED] * 4)
        for note in ("first", "second"):
            client.post(review_url(user_id, "/reviewed"), json={"note": note}, headers=clinician_headers)
        notes = [r["note"] for r in client.get(review_url(user_id), headers=clinician_headers).json()["recent_reviews"]]
        assert notes == ["second", "first"]
