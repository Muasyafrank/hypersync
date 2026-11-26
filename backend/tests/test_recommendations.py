"""What a patient is actually told, end to end: log habits and readings, read the advice back."""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import joblib
import pytest

from app.core.database import SessionLocal
from app.core.ml_recommendation_engine import _MODEL_PATH
from app.models.reading import BPReading

RISKY = dict(
    stress_level="high", sleep_hours=4.5, diet_adherence=False, medication_taken=False, salt_intake="high",
    caffeine_intake="high", alcohol_consumed=True, smoked=True, physical_activity_minutes=5,
)  # fmt: skip


def log_reading(client, headers, days_ago, systolic, diastolic, **conditions):
    when = (datetime.now(UTC) - timedelta(days=days_ago)).replace(microsecond=0)
    response = client.post(
        "/readings",
        json={
            "systolic": systolic,
            "diastolic": diastolic,
            "heart_rate": 70,
            "recorded_at": when.isoformat(),
            **conditions,
        },  # fmt: skip
        headers=headers,
    )
    assert response.status_code == 201, response.text


def log_factors(client, headers, days_ago, **answers):
    logged = (datetime.now(UTC).date() - timedelta(days=days_ago)).isoformat()
    response = client.post("/factors", json={**answers, "logged_date": logged}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def advice(client, headers):
    return [r for r in client.get("/recommendations/me", headers=headers).json() if r["source"] != "readings"][1:]


def texts(recs):
    return " ".join(r["message"] for r in recs).lower()


def test_the_population_estimate_has_distinct_provenance(client, patient_headers):
    for d in range(3):
        log_reading(client, patient_headers, d, 170, 100)

    recs = client.get("/recommendations/me", headers=patient_headers).json()
    assert recs[0]["source"] == "population_model"
    assert "using 2015 kenya steps survey data" in recs[0]["message"].lower()
    assert "the model estimates that about" in recs[0]["message"].lower()
    assert "population estimate and does not assess your blood pressure" in recs[0]["message"].lower()
    assert "brief versions of the survey questions" in recs[0]["message"].lower()
    assert "approximate comparison" in recs[0]["message"].lower()


def test_elevated_bp_keeps_smoking_visible_but_never_outputs_medication(client, patient_headers):
    for d in range(5):
        log_reading(client, patient_headers, d, 165, 100)
    log_factors(client, patient_headers, 0, **RISKY)

    said = texts(advice(client, patient_headers))
    assert "smoking" in said
    assert "medication" not in said
    assert "drug" not in said and "dose" not in said
    assert "also worth attention" in said  # whatever didn't fit is named
    # Naming a cut habit is not enough: its concrete action must still be shown.
    assert "aim for 7 to 9 hours" in said
    assert "five minutes of slow breathing" in said


def test_caffeine_is_advised_on(client, patient_headers):
    for d in range(5):
        log_reading(client, patient_headers, d, 165, 100)
    log_factors(client, patient_headers, 0, caffeine_intake="high")

    said = texts(advice(client, patient_headers))
    assert "coffee or tea" in said
    assert "after mid-afternoon" in said  # an action, not just a warning


def test_a_week_of_poor_sleep_is_not_hidden_by_one_good_night(client, patient_headers):
    for d in range(5):
        log_reading(client, patient_headers, d, 165, 100)
    for d in range(1, 6):
        log_factors(client, patient_headers, d, sleep_hours=4, stress_level="high")
    log_factors(client, patient_headers, 0, sleep_hours=8, stress_level="low")

    said = texts(advice(client, patient_headers))
    assert "under 6 hours of sleep" in said
    assert "high stress" in said


def test_controlled_bp_still_gets_preventive_advice_for_risky_habits(client, patient_headers):
    for d in range(5):
        log_reading(client, patient_headers, d, 118, 76)
    log_factors(client, patient_headers, 0, **RISKY)

    recs = client.get("/recommendations/me", headers=patient_headers).json()
    assert recs[0]["source"] == "system"
    assert "keep up your current routine" in recs[0]["message"].lower()
    said = texts(recs[1:])
    assert "smoking" in said or "alcohol" in said or "diet" in said
    assert len([r for r in recs if r["source"] in ("rule", "model", "pattern")]) <= 4  # kept short


def test_controlled_bp_with_healthy_habits_gets_no_nagging(client, patient_headers):
    for d in range(5):
        log_reading(client, patient_headers, d, 118, 76)
    log_factors(client, patient_headers, 0, sleep_hours=8, stress_level="low", smoked=False, medication_taken=True)

    recs = client.get("/recommendations/me", headers=patient_headers).json()
    assert {r["source"] for r in recs} <= {"system", "readings"}


def test_the_patients_own_readings_are_tied_to_the_habit_behind_them(client, patient_headers):
    for d in range(8):
        bad = d % 2 == 0
        log_reading(client, patient_headers, d, 168 if bad else 118, 102 if bad else 76)
        log_factors(client, patient_headers, d, sleep_hours=4 if bad else 8)

    recs = client.get("/recommendations/me", headers=patient_headers).json()
    [pattern] = [r for r in recs if r["source"] == "pattern"]
    assert "slept under 6 hours" in pattern["message"]
    assert "mmHg higher" in pattern["message"]
    assert "not proof of cause" in pattern["message"]


def test_healthy_habits_with_high_bp_say_so_instead_of_blaming_lifestyle(client, patient_headers):
    for d in range(5):
        log_reading(client, patient_headers, d, 165, 100)
    log_factors(client, patient_headers, 0, sleep_hours=8, stress_level="low", smoked=False, medication_taken=True)

    said = texts(client.get("/recommendations/me", headers=patient_headers).json())
    assert "no risky pattern is visible" in said
    assert "other factors may still matter" in said


def test_no_lifestyle_log_asks_the_patient_to_start_one(client, patient_headers):
    for d in range(5):
        log_reading(client, patient_headers, d, 165, 100)
    assert "lifestyle page" in texts(client.get("/recommendations/me", headers=patient_headers).json())


def test_cold_weather_and_noise_are_advised_on(client, patient_headers):
    for d in range(5):
        log_reading(client, patient_headers, d, 165, 100)
    log_factors(client, patient_headers, 0, temperature_feel="cold", noise_level="loud")

    said = texts(client.get("/recommendations/me", headers=patient_headers).json())
    assert "cold weather" in said and "warm layers" in said
    assert "loud day" in said and "quiet room" in said


def test_mild_weather_and_quiet_days_raise_nothing(client, patient_headers):
    for d in range(5):
        log_reading(client, patient_headers, d, 165, 100)
    log_factors(client, patient_headers, 0, temperature_feel="comfortable", noise_level="quiet")
    assert "cold weather" not in texts(client.get("/recommendations/me", headers=patient_headers).json())


def test_hurried_readings_are_called_out_with_how_much_higher_they_read(client, patient_headers):
    for d in range(3):  # rushed, straight after coffee
        log_reading(client, patient_headers, d, 152, 96, rested_before=False, stimulant_before=True)
    for d in range(3, 6):  # properly rested
        log_reading(client, patient_headers, d, 120, 78, rested_before=True, stimulant_before=False)

    recs = client.get("/recommendations/me", headers=patient_headers).json()
    [finding] = [r for r in recs if "without resting first" in r["message"]]
    assert finding["source"] == "pattern"
    assert "32 mmHg higher" in finding["message"]
    assert recs.index(finding) == 2  # right after the summary and the readings line: it affects everything else


def test_hurried_readings_without_a_comparison_still_get_technique_advice(client, patient_headers):
    for d in range(4):
        log_reading(client, patient_headers, d, 165, 100, rested_before=False)
    said = texts(client.get("/recommendations/me", headers=patient_headers).json())
    assert "4 of your 4 readings" in said


def test_controlled_readings_still_flag_hurried_measurement(client, patient_headers):
    for d in range(3):
        log_reading(client, patient_headers, d, 118, 76, rested_before=False, stimulant_before=True)

    said = texts(client.get("/recommendations/me", headers=patient_headers).json())
    assert "without resting first" in said
    assert "sit quietly with your back supported" in said


def test_no_technique_advice_when_readings_were_taken_properly(client, patient_headers):
    for d in range(4):
        log_reading(client, patient_headers, d, 165, 100, rested_before=True, stimulant_before=False)
    assert "without resting first" not in texts(client.get("/recommendations/me", headers=patient_headers).json())


def test_a_boundary_day_check_in_is_outside_the_seven_day_window(client, patient_headers):
    for d in range(3):
        log_reading(client, patient_headers, d, 165, 100)
    log_factors(client, patient_headers, 7, sleep_hours=4, stress_level="high")

    said = texts(client.get("/recommendations/me", headers=patient_headers).json())

    assert "under 6 hours of sleep" not in said
    assert "logged high stress" not in said


def test_a_sparse_logger_is_told_exactly_what_is_missing(client, patient_headers):
    for d in range(5):
        log_reading(client, patient_headers, d, 165, 100)
    log_factors(client, patient_headers, 0, sleep_hours=8, stress_level="low")

    said = texts(client.get("/recommendations/me", headers=patient_headers).json())
    assert "you have 1 so far" in said


def test_nobody_is_told_to_log_more_once_there_is_enough(client, patient_headers):
    for d in range(8):
        log_reading(client, patient_headers, d, 168 if d % 2 == 0 else 118, 100 if d % 2 == 0 else 76)
        log_factors(client, patient_headers, d, sleep_hours=4 if d % 2 == 0 else 8)
    assert "so far" not in texts(client.get("/recommendations/me", headers=patient_headers).json())


def test_low_bp_uses_safety_wording_and_never_attaches_lifestyle_advice(client, patient_headers):
    for d in range(3):
        log_reading(client, patient_headers, d, 85, 55)
    log_factors(
        client,
        patient_headers,
        0,
        smoked=True,
        medication_taken=False,
        sleep_hours=4,
    )

    recs = client.get("/recommendations/me", headers=patient_headers).json()
    said = texts(recs)
    assert "was low" in said
    assert "contact your clinician" in said
    assert "lifestyle advice is not shown for low readings" in said
    assert "ask your clinic about help to quit" not in said
    assert "aim for 7 to 9 hours" not in said
    assert "medication" not in said


def test_missing_profile_inputs_are_not_described_as_the_patients_own(client, patient_headers):
    for d in range(3):
        log_reading(client, patient_headers, d, 170, 100)

    said = texts(client.get("/recommendations/me", headers=patient_headers).json())
    assert "missing your age, sex," in said
    assert "smoking status" in said
    assert "alcohol use" in said
    assert "salt intake" in said
    assert "physical activity" in said
    assert "diet" in said
    assert "default values" in said
    assert "not fully personalised" in said


def test_a_partial_latest_check_in_does_not_erase_earlier_model_answers(client, patient_headers):
    for d in range(3):
        log_reading(client, patient_headers, d, 170, 100)
    log_factors(client, patient_headers, 1, smoked=False, alcohol_consumed=False, salt_intake="low")
    log_factors(client, patient_headers, 0, sleep_hours=8)

    recs = client.get("/recommendations/me", headers=patient_headers).json()
    model_message = next(item["message"] for item in recs if item["source"] == "population_model").lower()

    assert "missing your age, sex, physical activity and diet" in model_message
    assert "missing smoking status" not in model_message
    assert "missing alcohol use" not in model_message


def test_complete_model_inputs_do_not_claim_to_use_defaults(client):
    registration = client.post(
        "/auth/register",
        json={
            "full_name": "Complete Profile",
            "email": "complete.profile@example.com",
            "password": "correct-horse-battery",
            "date_of_birth": "2000-01-01",
            "sex": "Female",
        },
    )
    assert registration.status_code == 201, registration.text
    login = client.post(
        "/auth/login",
        data={"username": "complete.profile@example.com", "password": "correct-horse-battery"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    for d in range(3):
        log_reading(client, headers, d, 170, 100)
    log_factors(
        client,
        headers,
        0,
        smoked=False,
        alcohol_consumed=False,
        salt_intake="low",
        physical_activity_minutes=30,
        diet_adherence=True,
    )

    said = texts(client.get("/recommendations/me", headers=headers).json())
    assert "not fully personalised" not in said
    assert "default values" not in said
    assert "performance was only modest for your age group" in said


def test_an_age_outside_the_model_range_omits_the_population_estimate(client):
    registration = client.post(
        "/auth/register",
        json={
            "full_name": "Underage Patient",
            "email": "underage@example.com",
            "password": "correct-horse-battery",
            "date_of_birth": "2015-01-01",
            "sex": "Female",
        },
    )
    assert registration.status_code == 201, registration.text
    login = client.post(
        "/auth/login",
        data={"username": "underage@example.com", "password": "correct-horse-battery"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    for d in range(3):
        log_reading(client, headers, d, 170, 100)

    response = client.get("/recommendations/me", headers=headers)
    assert response.status_code == 200
    assert "outside the model's supported 18–69 range" in texts(response.json())
    assert response.json()[0]["source"] == "system"


def test_a_weakly_performed_age_band_withholds_the_population_estimate(client):
    registration = client.post(
        "/auth/register",
        json={
            "full_name": "Older Patient",
            "email": "older.patient@example.com",
            "password": "correct-horse-battery",
            "date_of_birth": "1990-01-01",
            "sex": "Female",
        },
    )
    assert registration.status_code == 201, registration.text
    login = client.post(
        "/auth/login",
        data={"username": "older.patient@example.com", "password": "correct-horse-battery"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    for d in range(3):
        log_reading(client, headers, d, 170, 100)

    response = client.get("/recommendations/me", headers=headers)
    assert response.status_code == 200
    assert response.json()[0]["source"] == "system"
    assert "locked test results were too weak for your age group" in texts(response.json())
    assert all(item["source"] != "population_model" for item in response.json())


def test_activity_above_the_model_cap_is_disclosed(client):
    registration = client.post(
        "/auth/register",
        json={
            "full_name": "Very Active Patient",
            "email": "very.active@example.com",
            "password": "correct-horse-battery",
            "date_of_birth": "2000-01-01",
            "sex": "Female",
        },
    )
    assert registration.status_code == 201, registration.text
    login = client.post(
        "/auth/login",
        data={"username": "very.active@example.com", "password": "correct-horse-battery"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    for d in range(3):
        log_reading(client, headers, d, 170, 100)
    log_factors(
        client,
        headers,
        0,
        smoked=False,
        alcohol_consumed=False,
        salt_intake="low",
        physical_activity_minutes=600,
        diet_adherence=True,
    )

    response = client.get("/recommendations/me", headers=headers)
    assert response.status_code == 200
    assert response.json()[0]["source"] == "population_model"
    assert "physical activity value is capped at 240 minutes per day" in texts(response.json())


def test_a_missing_model_degrades_the_population_estimate_without_failing(client, patient_headers, monkeypatch):
    monkeypatch.setattr("app.core.ml_recommendation_engine._MODEL_PATH", "/tmp/does-not-exist.joblib")
    monkeypatch.setattr("app.core.ml_recommendation_engine._bundle", None)
    monkeypatch.setattr("app.core.ml_recommendation_engine._model_load_attempted", False)
    for d in range(3):
        log_reading(client, patient_headers, d, 170, 100)

    response = client.get("/recommendations/me", headers=patient_headers)
    assert response.status_code == 200
    said = texts(response.json())
    assert "not available right now" not in said
    assert "survey-based population estimate" not in said
    assert "your average blood pressure" in said
    assert "lifestyle page" in said


def test_a_corrupt_model_degrades_the_population_estimate_without_failing(
    client, patient_headers, monkeypatch, tmp_path
):
    artifact = tmp_path / "corrupt.joblib"
    artifact.write_bytes(b"this is not a joblib artefact")
    monkeypatch.setattr("app.core.ml_recommendation_engine._MODEL_PATH", str(artifact))
    monkeypatch.setattr("app.core.ml_recommendation_engine._bundle", None)
    monkeypatch.setattr("app.core.ml_recommendation_engine._model_load_attempted", False)
    for d in range(3):
        log_reading(client, patient_headers, d, 170, 100)

    response = client.get("/recommendations/me", headers=patient_headers)
    assert response.status_code == 200
    said = texts(response.json())
    assert "not available right now" not in said
    assert "survey-based population estimate" not in said
    assert "your average blood pressure" in said


def test_an_incompatible_model_degrades_the_population_estimate_without_failing(
    client, patient_headers, monkeypatch, tmp_path
):
    artifact = tmp_path / "incompatible.joblib"
    joblib.dump({"unexpected": "bundle"}, artifact)
    monkeypatch.setattr("app.core.ml_recommendation_engine._MODEL_PATH", str(artifact))
    monkeypatch.setattr("app.core.ml_recommendation_engine._bundle", None)
    monkeypatch.setattr("app.core.ml_recommendation_engine._model_load_attempted", False)
    for d in range(3):
        log_reading(client, patient_headers, d, 170, 100)

    response = client.get("/recommendations/me", headers=patient_headers)
    assert response.status_code == 200
    said = texts(response.json())
    assert "not available right now" not in said
    assert "survey-based population estimate" not in said
    assert "your average blood pressure" in said


@pytest.mark.parametrize("malformation", ["default", "effects", "version"])
def test_a_malformed_published_model_fails_closed_without_a_500(
    client, patient_headers, monkeypatch, tmp_path, malformation
):
    bundle = joblib.load(_MODEL_PATH)
    if malformation == "default":
        bundle["feature_defaults"]["smoked"] = None
    elif malformation == "effects":
        bundle["effects"]["smoked"].pop("ci_high")
    else:
        bundle["version"] = "foreign-model"

    artifact = tmp_path / f"malformed-{malformation}.joblib"
    joblib.dump(bundle, artifact)
    monkeypatch.setattr("app.core.ml_recommendation_engine._MODEL_PATH", str(artifact))
    monkeypatch.setattr("app.core.ml_recommendation_engine._bundle", None)
    monkeypatch.setattr("app.core.ml_recommendation_engine._model_load_attempted", False)
    # Isolate bundle validation from the published-file digest check while
    # preserving the exact bytes that the loader will unpickle.
    monkeypatch.setattr(
        "app.core.ml_recommendation_engine._validate_model_file",
        lambda path: Path(path).read_bytes(),
    )
    for d in range(3):
        log_reading(client, patient_headers, d, 170, 100)

    response = client.get("/recommendations/me", headers=patient_headers)
    assert response.status_code == 200
    said = texts(response.json())
    assert "not available right now" not in said
    assert "survey-based population estimate" not in said
    assert "your average blood pressure" in said


def test_very_high_reading_uses_safety_wording_and_never_attaches_lifestyle_advice(client, patient_headers):
    log_reading(client, patient_headers, 0, 180, 110)
    log_reading(client, patient_headers, 1, 120, 78)
    log_factors(
        client,
        patient_headers,
        0,
        smoked=True,
        salt_intake="high",
        sleep_hours=4,
        medication_taken=False,
    )

    recs = client.get("/recommendations/me", headers=patient_headers).json()
    said = texts(recs)
    assert "was very high" in said
    assert "seek urgent medical care" in said
    assert "lifestyle advice is not shown for very high readings" in said
    assert "ask your clinic about help to quit" not in said
    assert "aim for 7 to 9 hours" not in said
    assert "model explanation" not in said


def test_a_future_timestamped_very_high_reading_uses_the_same_safety_route(client, patient_headers):
    for _ in range(3):
        log_reading(client, patient_headers, 0, 120, 78)

    future = (datetime.now(UTC) + timedelta(hours=1)).replace(microsecond=0)
    patient_id = uuid.UUID(client.get("/auth/me", headers=patient_headers).json()["user_id"])
    db = SessionLocal()
    try:
        db.add(
            BPReading(
                patient_id=patient_id,
                systolic=185,
                diastolic=115,
                heart_rate=70,
                recorded_at=future,
            )
        )
        db.commit()
    finally:
        db.close()

    recs = client.get("/recommendations/me", headers=patient_headers).json()
    said = texts(recs)
    assert len(recs) == 1
    assert "was very high" in said
    assert "seek urgent medical care" in said
    assert "lifestyle advice is not shown for very high readings" in said
    assert "model explanation" not in said


def test_one_low_reading_safety_route_wins_over_an_otherwise_normal_average(client, patient_headers):
    log_reading(client, patient_headers, 0, 85, 55)
    log_reading(client, patient_headers, 1, 125, 78)

    recs = client.get("/recommendations/me", headers=patient_headers).json()
    assert len(recs) == 1
    assert "was low" in texts(recs)
    assert "lifestyle advice is not shown" in texts(recs)


def test_the_patient_response_shape_is_unchanged(client, patient_headers):
    log_reading(client, patient_headers, 0, 170, 100)
    expected = {
        "recommendation_id",
        "message",
        "based_on_trend",
        "confidence",
        "source",
        "created_at",
    }
    for params in ({}, {"period_days": 30}):
        response = client.get("/recommendations/me", headers=patient_headers, params=params)
        assert response.status_code == 200
        assert all(set(item) == expected for item in response.json())


def test_before_and_after_profiles_get_different_uncertain_contribution_explanations(client, register_and_login):
    healthy_headers = register_and_login("healthy.model@example.com", "Healthy Model")
    risky_headers = register_and_login("risky.model@example.com", "Risky Model")
    for headers in (healthy_headers, risky_headers):
        for day in range(3):
            log_reading(client, headers, day, 170, 100)

    log_factors(
        client,
        healthy_headers,
        0,
        smoked=False,
        alcohol_consumed=False,
        salt_intake="none",
        physical_activity_minutes=90,
        diet_adherence=True,
    )
    log_factors(
        client,
        risky_headers,
        0,
        smoked=True,
        alcohol_consumed=True,
        salt_intake="high",
        physical_activity_minutes=0,
        diet_adherence=False,
    )

    healthy = client.get("/recommendations/me", headers=healthy_headers).json()[0]
    risky = client.get("/recommendations/me", headers=risky_headers).json()[0]
    assert "Model explanation:" in healthy["message"]
    assert "Model explanation:" in risky["message"]
    assert "95% range" in healthy["message"]
    assert healthy["message"] != risky["message"]
    assert healthy["confidence"] != risky["confidence"]


def test_patient_recommendations_never_include_diagnosis_or_treatment_content(client, patient_headers):
    for day in range(3):
        log_reading(client, patient_headers, day, 170, 100)
    log_factors(client, patient_headers, 0, **RISKY)

    said = texts(client.get("/recommendations/me", headers=patient_headers).json())
    for prohibited in (
        "diagnosis",
        "diagnostic",
        "medication",
        "medicine",
        "drug",
        "dose",
        "prescription",
        "treatment",
    ):
        assert prohibited not in said


@pytest.mark.parametrize(
    "readings",
    [
        pytest.param([], id="no-data"),
        pytest.param([(120, 78)], id="controlled"),
        pytest.param([(170, 100)], id="elevated-or-high"),
        pytest.param([(85, 55)], id="low"),
        pytest.param([(180, 110)], id="very-high"),
    ],
)
def test_every_recommendation_route_excludes_diagnosis_and_treatment_content(client, register_and_login, readings):
    headers = register_and_login(f"route-{uuid.uuid4().hex}@example.com", "Route Safety Patient")
    for systolic, diastolic in readings:
        log_reading(client, headers, 0, systolic, diastolic)

    said = texts(client.get("/recommendations/me", headers=headers).json())
    for prohibited in (
        "diagnosis",
        "diagnostic",
        "medication",
        "medicine",
        "drug",
        "dose",
        "prescription",
        "treatment",
    ):
        assert prohibited not in said
