"""
Seeds 30 days of realistic readings and lifestyle logs for six demo patients
(plus one clinician), each built to show a different part of the system.

    python -m scripts.seed_demo_30_days            # write to the database
    python -m scripts.seed_demo_30_days --csv out  # also write CSV copies to ./out

Run from backend/ with the venv active.

Dates are relative to the moment you run it, so the last 30 days are always
"the last 30 days": re-run it any time to refresh them. Only the demo accounts
below (all @example.com) are touched: if they already exist they are deleted
and re-created. Nobody else's data is changed.

Reading times are Kenyan local time (EAT, UTC+3), as in the other seed script.
The data is deterministic (fixed random seeds), so every run gives the same
values, shifted to the current dates.
"""

import argparse
import csv
import os
import random
import sys

sys.path.append(os.getcwd())

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.core.alert_engine import maybe_create_alert
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.core.trend_analysis import compute_trend
from app.models.alert import Alert
from app.models.environmental_factor import (
    EnvironmentalFactor,
    IntakeLevel,
    NoiseLevel,
    StressLevel,
    TemperatureFeel,
)
from app.models.reading import BPReading
from app.models.recommendation import Recommendation
from app.models.token import RefreshToken
from app.models.user import PatientProfile, SexEnum, User, UserRole

EAT = timezone(timedelta(hours=3))  # Kenya has no daylight saving
DAYS = 30
DEMO_PASSWORD = "DemoPass#2026"
CLINICIAN_EMAIL = "demo.clinician@example.com"


# --------------------------------------------------------------------------
# Data shapes
# --------------------------------------------------------------------------


@dataclass
class ReadingRow:
    days_ago: int
    hour: int
    minute: int
    systolic: int
    diastolic: int
    heart_rate: int | None = None
    notes: str | None = None
    rested_before: bool | None = None
    stimulant_before: bool | None = None


@dataclass
class FactorRow:
    days_ago: int
    stress_level: str | None = None
    sleep_hours: float | None = None
    diet_adherence: bool | None = None
    medication_taken: bool | None = None
    salt_intake: str | None = None
    caffeine_intake: str | None = None
    alcohol_consumed: bool | None = None
    smoked: bool | None = None
    physical_activity_minutes: int | None = None
    temperature_feel: str | None = None
    noise_level: str | None = None


@dataclass
class Persona:
    email: str
    full_name: str
    sex: str
    birth_year: int
    story: str  # what this patient's data is like
    expect: str  # what the system should show for them
    readings: list[ReadingRow] = field(default_factory=list)
    factors: list[FactorRow] = field(default_factory=list)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _bp(rng, systolic, diastolic, systolic_sd=4.0, diastolic_sd=3.0):
    s = round(rng.gauss(systolic, systolic_sd))
    d = round(rng.gauss(diastolic, diastolic_sd))
    return s, min(d, s - 25)  # keep the pulse pressure physiologically sensible


def _hr(rng, mean=72):
    return round(rng.gauss(mean, 6))


def _morning(rng, d, systolic, diastolic, systolic_sd=4.0, diastolic_sd=3.0, **kw):
    s, dia = _bp(rng, systolic, diastolic, systolic_sd, diastolic_sd)
    return ReadingRow(d, 7, rng.randint(0, 45), s, dia, _hr(rng), **kw)


def _evening(rng, d, systolic, diastolic, systolic_sd=4.0, diastolic_sd=3.0, **kw):
    s, dia = _bp(rng, systolic, diastolic, systolic_sd, diastolic_sd)
    return ReadingRow(d, 19, rng.randint(0, 50), s, dia, _hr(rng, 70), **kw)


PROPER = {"rested_before": True, "stimulant_before": False}
HEALTHY = {
    "stress_level": "low",
    "sleep_hours": 7.5,
    "diet_adherence": True,
    "medication_taken": True,
    "salt_intake": "low",
    "caffeine_intake": "low",
    "alcohol_consumed": False,
    "smoked": False,
    "physical_activity_minutes": 40,
    "temperature_feel": "comfortable",
    "noise_level": "quiet",
}


def _days():
    return range(DAYS - 1, -1, -1)  # oldest first; 0 = today


# --------------------------------------------------------------------------
# The six patients
# --------------------------------------------------------------------------


def grace(today: date) -> Persona:
    """Well controlled with good habits: the system should stay quiet."""
    rng = random.Random("grace")
    p = Persona(
        "demo.grace@example.com", "Grace Wanjiku", "Female", 1971,
        story="Well-controlled pressure (about 121/78), healthy habits, logs every day.",
        expect="'Controlled, keep up your routine' and no habit advice: no nagging.",
    )  # fmt: skip
    for d in _days():
        p.readings.append(_morning(rng, d, 121, 78, **PROPER))
        if rng.random() < 0.6:
            p.readings.append(_evening(rng, d, 124, 80, **PROPER))
        p.factors.append(
            FactorRow(
                d,
                **{
                    **HEALTHY,
                    "stress_level": rng.choice(["low", "low", "moderate"]),
                    "sleep_hours": rng.choice([7, 7.5, 8, 8.5]),
                    "caffeine_intake": rng.choice(["low", "moderate"]),
                    "physical_activity_minutes": rng.choice([30, 40, 45, 60]),
                    "noise_level": rng.choice(["quiet", "moderate"]),
                },
            )
        )
    return p


def peter(today: date) -> Persona:
    """Pressure rises on poor-sleep days and on high-salt days (different days)."""
    rng = random.Random("peter")
    p = Persona(
        "demo.peter@example.com", "Peter Otieno", "Male", 1966,
        story="Pressure jumps on nights of under 6 hours' sleep and again on high-salt days. "
        "The two habits fall on different days.",
        expect="Elevated. Two own-data findings, one for sleep and one for salt, each with the "
        "mmHg difference. Both properly measured.",
    )  # fmt: skip
    for d in _days():
        bad_sleep, high_salt = d % 3 == 0, d % 4 == 1
        s_mean = 124 + 26 * bad_sleep + 16 * high_salt
        d_mean = 80 + 14 * bad_sleep + 9 * high_salt
        p.readings.append(_morning(rng, d, s_mean, d_mean, **PROPER))
        p.readings.append(_evening(rng, d, s_mean + 2, d_mean + 1, **PROPER))
        p.factors.append(
            FactorRow(
                d,
                **{
                    **HEALTHY,
                    "sleep_hours": rng.choice([4.5, 5, 5.5]) if bad_sleep else rng.choice([7, 7.5, 8]),
                    "salt_intake": "high" if high_salt else "low",
                    "stress_level": rng.choice(["low", "moderate"]),
                },
            )
        )
    return p


def mary(today: date) -> Persona:
    """Normal when measured properly, high when rushed or straight after tea."""
    rng = random.Random("mary")
    p = Persona(
        "demo.mary@example.com", "Mary Achieng", "Female", 1980,
        story="Calm morning readings are normal (about 121/78). On every other day she also "
        "measures in a hurry, straight after tea or climbing stairs, and those read about 45 mmHg higher.",
        expect="Elevated average, but the FIRST advice is about measurement technique, showing "
        "the hurried readings read ~45 mmHg higher than properly rested ones.",
    )  # fmt: skip
    rushed_notes = ["Rushed, had just finished tea", "Measured right after climbing stairs", "In a hurry before work"]
    for d in _days():
        p.readings.append(_morning(rng, d, 121, 78, **PROPER))
        if d % 2 == 0:
            s, dia = _bp(rng, 168, 102, 5, 3)
            p.readings.append(
                ReadingRow(
                    d, 13, rng.randint(0, 40), s, dia, _hr(rng, 84), rng.choice(rushed_notes),
                    rested_before=False, stimulant_before=True,
                )
            )  # fmt: skip
        p.factors.append(FactorRow(d, **{**HEALTHY, "caffeine_intake": "moderate", "stress_level": "moderate"}))
    return p


def james(today: date) -> Persona:
    """Higher on loud weekdays and on cold mornings."""
    rng = random.Random("james")
    p = Persona(
        "demo.james@example.com", "James Kamau", "Male", 1975,
        story="Works somewhere loud Monday to Friday; quiet weekends. Also has cold days every third day. "
        "Pressure is higher on both.",
        expect="Elevated. Own-data findings for noise and for cold weather, each with its mmHg gap.",
    )  # fmt: skip
    for d in _days():
        day = today - timedelta(days=d)
        loud, cold = day.weekday() < 5, d % 3 == 1
        s_mean = 122 + 20 * loud + 14 * cold
        d_mean = 78 + 10 * loud + 8 * cold
        p.readings.append(_morning(rng, d, s_mean, d_mean, **PROPER))
        p.readings.append(_evening(rng, d, s_mean + 2, d_mean + 1, **PROPER))
        p.factors.append(
            FactorRow(
                d,
                **{
                    **HEALTHY,
                    "noise_level": "loud" if loud else "quiet",
                    "temperature_feel": "cold" if cold else "comfortable",
                    "stress_level": "moderate",
                },
            )
        )
    return p


def amina(today: date) -> Persona:
    """High pressure every day but almost no lifestyle logging."""
    rng = random.Random("amina")
    p = Persona(
        "demo.amina@example.com", "Amina Hassan", "Female", 1958,
        story="Consistently high (about 166/102) and measures twice a day, but has logged her "
        "lifestyle only twice in 30 days (one entry says she missed her medicine).",
        expect="High, with a high-trend alert. Missed-medication advice, plus a message saying "
        "exactly how many more days of logging are needed ('You have 2 so far').",
    )  # fmt: skip
    for d in _days():
        p.readings.append(_morning(rng, d, 166, 102, 5, 3))
        p.readings.append(_evening(rng, d, 168, 103, 5, 3))
    p.factors.append(FactorRow(12, stress_level="high", sleep_hours=8, smoked=False))
    p.factors.append(FactorRow(0, sleep_hours=5, salt_intake="high", medication_taken=False, diet_adherence=False))
    return p


def daniel(today: date) -> Persona:
    """Many risky habits at once: tests the cap, the priority order and the 'also worth attention' line."""
    rng = random.Random("daniel")
    p = Persona(
        "demo.daniel@example.com", "Daniel Mutua", "Male", 1969,
        story="High pressure (about 160/98) every day and nearly every habit is risky: smoking, "
        "alcohol at weekends, high salt, little sleep or activity, missed doses.",
        expect="High. Smoking and missed medicine always appear; a closing line names whatever "
        "didn't fit. No own-data findings, because there are no good days to compare with.",
    )  # fmt: skip
    for d in _days():
        day = today - timedelta(days=d)
        p.readings.append(_morning(rng, d, 160, 98, 6, 4))
        p.readings.append(_evening(rng, d, 162, 99, 6, 4))
        p.factors.append(
            FactorRow(
                d,
                stress_level="high",
                sleep_hours=rng.choice([4.5, 5, 5.5]),
                diet_adherence=False,
                medication_taken=d % 7 not in (1, 3, 5),
                salt_intake="high",
                caffeine_intake="high",
                alcohol_consumed=day.weekday() >= 5,
                smoked=True,
                physical_activity_minutes=rng.choice([0, 5, 10]),
                temperature_feel="comfortable",
                noise_level="moderate",
            )
        )
    return p


def build_demo_data(today: date | None = None) -> list[Persona]:
    """The six patients, with every row expressed as 'days ago' (no database needed)."""
    today = today or datetime.now(EAT).date()
    return [grace(today), peter(today), mary(today), james(today), amina(today), daniel(today)]


# --------------------------------------------------------------------------
# Writing to the database
# --------------------------------------------------------------------------


def reading_time(row: ReadingRow, now: datetime) -> datetime:
    when = (now - timedelta(days=row.days_ago)).replace(hour=row.hour, minute=row.minute, second=0, microsecond=0)
    # A reading for "today" whose clock time hasn't happened yet would be in the future.
    return min(when, now - timedelta(minutes=1))


def _delete_demo_user(db, user):
    for model, column in (
        (Recommendation, "patient_id"),
        (Alert, "patient_id"),
        (EnvironmentalFactor, "patient_id"),
        (BPReading, "patient_id"),
        (RefreshToken, "user_id"),
        (PatientProfile, "user_id"),
    ):
        db.query(model).filter(getattr(model, column) == user.user_id).delete()
    db.delete(user)


def seed(db, personas: list[Persona], now: datetime | None = None) -> dict[str, User]:
    """Create (or re-create) the demo accounts and all their data. Returns email -> User."""
    now = now or datetime.now(EAT)
    emails = [p.email for p in personas] + [CLINICIAN_EMAIL]

    for existing in db.query(User).filter(User.email.in_(emails)).all():
        _delete_demo_user(db, existing)
    db.flush()

    password_hash = hash_password(DEMO_PASSWORD)
    users: dict[str, User] = {}

    clinician = User(
        full_name="Dr. Wambui Njoroge", email=CLINICIAN_EMAIL, password_hash=password_hash, role=UserRole.clinician
    )
    db.add(clinician)
    users[CLINICIAN_EMAIL] = clinician

    for p in personas:
        user = User(full_name=p.full_name, email=p.email, password_hash=password_hash, role=UserRole.patient)
        db.add(user)
        db.flush()
        db.add(
            PatientProfile(
                user_id=user.user_id,
                date_of_birth=date(p.birth_year, 6, 15),
                sex=SexEnum(p.sex),
            )
        )
        for r in p.readings:
            db.add(
                BPReading(
                    patient_id=user.user_id,
                    systolic=r.systolic,
                    diastolic=r.diastolic,
                    heart_rate=r.heart_rate,
                    recorded_at=reading_time(r, now),
                    notes=r.notes,
                    rested_before=r.rested_before,
                    stimulant_before=r.stimulant_before,
                )
            )
        for f in p.factors:
            db.add(
                EnvironmentalFactor(
                    patient_id=user.user_id,
                    logged_date=now.date() - timedelta(days=f.days_ago),
                    stress_level=StressLevel(f.stress_level) if f.stress_level else None,
                    sleep_hours=f.sleep_hours,
                    diet_adherence=f.diet_adherence,
                    medication_taken=f.medication_taken,
                    salt_intake=IntakeLevel(f.salt_intake) if f.salt_intake else None,
                    caffeine_intake=IntakeLevel(f.caffeine_intake) if f.caffeine_intake else None,
                    alcohol_consumed=f.alcohol_consumed,
                    smoked=f.smoked,
                    physical_activity_minutes=f.physical_activity_minutes,
                    temperature_feel=TemperatureFeel(f.temperature_feel) if f.temperature_feel else None,
                    noise_level=NoiseLevel(f.noise_level) if f.noise_level else None,
                )
            )
        users[p.email] = user
    db.flush()

    # Replay the alert check the API runs after each reading, so patients whose
    # 7-day trend is elevated/high have the alert a clinician would see.
    for p in personas:
        uid = users[p.email].user_id
        trend = compute_trend(db, uid, period_days=7)
        maybe_create_alert(db, uid, trend.status, period_days=7)
    db.commit()
    return users


# --------------------------------------------------------------------------
# CSV export
# --------------------------------------------------------------------------


def write_csvs(personas: list[Persona], directory: Path, now: datetime | None = None) -> list[Path]:
    now = now or datetime.now(EAT)
    directory.mkdir(parents=True, exist_ok=True)

    readings_path = directory / "demo_bp_readings_30_days.csv"
    with readings_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["patient_email", "patient", "date", "time_eat", "days_ago", "systolic", "diastolic",
                    "heart_rate", "rested_before", "stimulant_before", "notes"])  # fmt: skip
        for p in personas:
            for r in sorted(p.readings, key=lambda x: (-x.days_ago, x.hour, x.minute)):
                when = reading_time(r, now)
                w.writerow([p.email, p.full_name, when.date().isoformat(), when.strftime("%H:%M"), r.days_ago,
                            r.systolic, r.diastolic, r.heart_rate if r.heart_rate is not None else "",
                            "" if r.rested_before is None else int(r.rested_before),
                            "" if r.stimulant_before is None else int(r.stimulant_before), r.notes or ""])  # fmt: skip

    lifestyle_path = directory / "demo_lifestyle_30_days.csv"
    columns = [k for k in asdict(FactorRow(0)) if k != "days_ago"]
    with lifestyle_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["patient_email", "patient", "date", "days_ago", *columns])
        for p in personas:
            for f in sorted(p.factors, key=lambda x: -x.days_ago):
                row = asdict(f)
                w.writerow([p.email, p.full_name, (now.date() - timedelta(days=f.days_ago)).isoformat(), f.days_ago]
                           + ["" if row[c] is None else row[c] for c in columns])  # fmt: skip

    guide_path = directory / "demo_accounts_and_expected_results.csv"
    with guide_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["email", "password", "patient", "what_the_data_is_like", "what_the_system_should_show"])
        for p in personas:
            w.writerow([p.email, DEMO_PASSWORD, p.full_name, p.story, p.expect])
        w.writerow([CLINICIAN_EMAIL, DEMO_PASSWORD, "Dr. Wambui Njoroge", "Clinician account for reviewing the six patients.",
                    "Sees every patient, every logged habit, the alerts queue and flagged readings."])  # fmt: skip
    return [readings_path, lifestyle_path, guide_path]


# --------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Seed 30 days of demo data.")
    parser.add_argument("--csv", metavar="DIR", help="also write CSV copies of the data to this directory")
    args = parser.parse_args()

    now = datetime.now(EAT)
    personas = build_demo_data(now.date())

    db = SessionLocal()
    try:
        seed(db, personas, now)
    finally:
        db.close()

    print(f"Seeded {len(personas)} demo patients + 1 clinician with {DAYS} days of data.\n")
    print(f"Password for every demo account: {DEMO_PASSWORD}\n")
    for p in personas:
        n_readings, n_logs = len(p.readings), len(p.factors)
        print(
            f"{p.full_name:16} {p.email}\n    {p.story}\n    Expect: {p.expect}\n    ({n_readings} readings, {n_logs} lifestyle logs)\n"
        )
    print(f"Clinician        {CLINICIAN_EMAIL}")

    if args.csv:
        for path in write_csvs(personas, Path(args.csv), now):
            print(f"Wrote {path}")


if __name__ == "__main__":
    main()
