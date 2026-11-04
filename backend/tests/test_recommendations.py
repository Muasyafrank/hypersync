"""What a patient is actually told, end to end: log habits and readings, read the advice back."""

from datetime import UTC, date, datetime, timedelta

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
    logged = (date.today() - timedelta(days=days_ago)).isoformat()
    assert client.post("/factors", json={**answers, "logged_date": logged}, headers=headers).status_code == 201


def advice(client, headers):
    return [r for r in client.get("/recommendations/me", headers=headers).json() if r["source"] != "readings"][1:]


def texts(recs):
    return " ".join(r["message"] for r in recs).lower()


def test_elevated_bp_with_every_habit_logged_never_hides_smoking_or_medication(client, patient_headers):
    for d in range(5):
        log_reading(client, patient_headers, d, 165, 100)
    log_factors(client, patient_headers, 0, **RISKY)

    said = texts(advice(client, patient_headers))
    assert "smoking" in said
    assert "medication" in said
    assert "also worth attention" in said  # whatever didn't fit is named


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
    assert "smoking" in said or "alcohol" in said or "medication" in said
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

    assert "look healthy" in texts(client.get("/recommendations/me", headers=patient_headers).json())


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


def test_no_technique_advice_when_readings_were_taken_properly(client, patient_headers):
    for d in range(4):
        log_reading(client, patient_headers, d, 165, 100, rested_before=True, stimulant_before=False)
    assert "without resting first" not in texts(client.get("/recommendations/me", headers=patient_headers).json())


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
