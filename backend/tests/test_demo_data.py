"""The 30-day demo data must keep producing the behaviour each patient was built to show."""

import csv
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from app.core.database import SessionLocal
from app.models.reading import BPReading
from app.models.user import User
from scripts.seed_demo_30_days import (
    CLINICIAN_EMAIL,
    DAYS,
    DEMO_PASSWORD,
    build_demo_data,
    reading_time,
    seed,
    write_csvs,
)

EAT = timezone(timedelta(hours=3))
TODAY = date(2026, 11, 4)


def by_name(personas):
    return {p.email.split(".")[1].split("@")[0]: p for p in personas}


class TestTheData:
    def test_it_is_deterministic(self):
        assert build_demo_data(TODAY) == build_demo_data(TODAY)

    def test_six_patients_with_unique_accounts(self):
        personas = build_demo_data(TODAY)
        assert len(personas) == 6
        assert len({p.email for p in personas}) == 6

    def test_every_patient_has_a_reading_on_each_of_the_30_days(self):
        for p in build_demo_data(TODAY):
            assert {r.days_ago for r in p.readings} == set(range(DAYS)), p.email

    def test_values_are_physiologically_sensible(self):
        for p in build_demo_data(TODAY):
            for r in p.readings:
                assert 90 <= r.systolic <= 220, (p.email, r)
                assert 50 <= r.diastolic <= 130 and r.diastolic <= r.systolic - 25, (p.email, r)
                assert r.heart_rate is None or 40 <= r.heart_rate <= 120

    @pytest.mark.parametrize("hour", [0, 3, 7, 13, 23])
    def test_nothing_is_ever_future_dated(self, hour):
        now = datetime(2026, 11, 4, hour, 30, tzinfo=EAT)
        for p in build_demo_data(TODAY):
            for r in p.readings:
                assert reading_time(r, now) < now

    def test_only_the_sparse_logger_skips_lifestyle_days(self):
        for name, p in by_name(build_demo_data(TODAY)).items():
            logged = {f.days_ago for f in p.factors}
            assert (len(logged) == 2) if name == "amina" else (logged == set(range(DAYS))), name


@pytest.fixture()
def demo(client):
    """The demo seeded into the test database; returns a function giving each patient's auth headers."""
    personas = build_demo_data(datetime.now(EAT).date())
    db = SessionLocal()
    try:
        seed(db, personas)
    finally:
        db.close()

    def headers_for(email):
        token = client.post("/auth/login", data={"username": email, "password": DEMO_PASSWORD}).json()["access_token"]
        # The browser sends its timezone; the demo times are Nairobi times.
        return {"Authorization": f"Bearer {token}", "X-Timezone": "Africa/Nairobi"}

    return by_name(personas), headers_for


def advice_for(client, headers):
    return client.get("/recommendations/me", headers=headers).json()


def status_for(client, headers):
    return client.get("/readings/me/trend?period_days=7", headers=headers).json()["status"]


def text(recs):
    return " ".join(r["message"] for r in recs).lower()


class TestWhatEachPatientSees:
    def test_grace_controlled_gets_no_nagging(self, client, demo):
        people, headers_for = demo
        h = headers_for(people["grace"].email)
        assert status_for(client, h) == "controlled"
        assert {r["source"] for r in advice_for(client, h)} <= {"system", "readings"}
        assert client.get("/alerts/me", headers=h).json() == []

    def test_peter_gets_separate_sleep_and_salt_findings(self, client, demo):
        people, headers_for = demo
        h = headers_for(people["peter"].email)
        assert status_for(client, h) == "elevated"
        patterns = [r["message"] for r in advice_for(client, h) if r["source"] == "pattern"]
        assert len(patterns) == 2
        assert any("slept under 6 hours" in m for m in patterns)
        assert any("salt" in m for m in patterns)
        assert all("mmHg higher" in m and "not proof of cause" in m for m in patterns)

    def test_mary_is_told_her_hurried_readings_read_high(self, client, demo):
        people, headers_for = demo
        h = headers_for(people["mary"].email)
        assert status_for(client, h) == "elevated"
        recs = advice_for(client, h)
        [finding] = [r for r in recs if "without resting first" in r["message"]]
        assert finding["source"] == "pattern"
        assert "higher than the" in finding["message"]
        assert recs.index(finding) == 2  # straight after the summary and readings lines
        assert "look healthy" in text(recs)  # her habits are not the explanation

    def test_james_gets_noise_and_cold_findings(self, client, demo):
        people, headers_for = demo
        h = headers_for(people["james"].email)
        assert status_for(client, h) == "elevated"
        said = text([r for r in advice_for(client, h) if r["source"] == "pattern"])
        assert "had a loud day" in said and "logged cold weather" in said

    def test_amina_gets_an_alert_medication_advice_and_a_logging_target(self, client, demo):
        people, headers_for = demo
        h = headers_for(people["amina"].email)
        assert status_for(client, h) == "high"
        assert [a["alert_type"] for a in client.get("/alerts/me", headers=h).json()] == ["high_trend"]
        said = text(advice_for(client, h))
        assert "missed medication" in said
        assert "you have 2 so far" in said

    def test_daniel_never_loses_smoking_or_medication_to_the_cap(self, client, demo):
        people, headers_for = demo
        h = headers_for(people["daniel"].email)
        recs = advice_for(client, h)
        said = text(recs)
        assert status_for(client, h) == "high"
        assert "smoking" in said and "missed medication" in said
        assert "also worth attention" in said
        assert not [r for r in recs if r["source"] == "pattern"]  # no good days to compare with

    def test_the_clinician_sees_all_six_patients(self, client, demo):
        _, headers_for = demo
        patients = client.get("/users/patients/summary", headers=headers_for(CLINICIAN_EMAIL)).json()
        assert len(patients) >= 6


class TestSeeding:
    def test_running_it_twice_replaces_rather_than_duplicates(self, client):
        personas = build_demo_data(datetime.now(EAT).date())
        db = SessionLocal()
        try:
            seed(db, personas)
            first = db.query(BPReading).count(), db.query(User).count()
            seed(db, personas)
            assert (db.query(BPReading).count(), db.query(User).count()) == first
        finally:
            db.close()

    def test_every_reading_falls_inside_the_last_30_days(self, client):
        db = SessionLocal()
        try:
            seed(db, build_demo_data(datetime.now(EAT).date()))
            oldest = min(r.recorded_at for r in db.query(BPReading).all())
            if oldest.tzinfo is None:
                oldest = oldest.replace(tzinfo=UTC)
            assert datetime.now(UTC) - oldest <= timedelta(days=DAYS + 1)
        finally:
            db.close()


def test_csv_export_matches_the_data(tmp_path):
    personas = build_demo_data(TODAY)
    readings, lifestyle, guide = write_csvs(personas, tmp_path, datetime(2026, 11, 4, 23, 0, tzinfo=EAT))

    with readings.open(encoding="utf-8") as fh:
        assert len(list(csv.DictReader(fh))) == sum(len(p.readings) for p in personas)
    with lifestyle.open(encoding="utf-8") as fh:
        assert len(list(csv.DictReader(fh))) == sum(len(p.factors) for p in personas)
    with guide.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 7 and {r["password"] for r in rows} == {DEMO_PASSWORD}
