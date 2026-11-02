"""
Seeds the database from HyperSync_Test_Data.xlsx — the Kenyan test-data
workbook. Populates patients, clinicians, an admin, BP readings, lifestyle
factors, and (by replaying the same trend/alert logic the API uses) any
alerts that should exist as a result.

Usage (run from the backend/ directory, with the venv active):

    python -m scripts.seed_test_data [path/to/HyperSync_Test_Data.xlsx]

If no path is given, it uses backend/data/HyperSync_Test_Data.xlsx. Safe to re-run: any email that already exists is skipped rather
than duplicated.

Design note: dates in the workbook are formula-driven (relative to
TODAY()) so the sheet reads nicely whenever it's opened in Excel — but
this script does NOT rely on those cached formula values. It reads the
raw days_ago/hour/minute/logged-date-offset inputs directly and computes
every timestamp itself, using the current moment this script runs. That
way the seeded data lands in the right trend windows regardless of
whether the workbook was ever opened in a real spreadsheet app first.

Reading times are Kenyan local time (EAT, UTC+3). A reading for today whose
clock time is still in the future is clamped to one minute ago, so nothing
is ever future-dated.
"""

import sys
import os

sys.path.append(os.getcwd())

from datetime import datetime, timedelta, timezone, date
from pathlib import Path

import openpyxl

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.core.trend_analysis import compute_trend
from app.core.alert_engine import maybe_create_alert
from app.models.user import User, PatientProfile, UserRole, SexEnum
from app.models.reading import BPReading
from app.models.environmental_factor import EnvironmentalFactor, StressLevel, IntakeLevel

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "HyperSync_Test_Data.xlsx"

# The hour/minute columns are Kenyan clock times. Kenya has no daylight
# saving, so a fixed UTC+3 offset is exact.
EAT = timezone(timedelta(hours=3))


def get_or_create_user(db, full_name, email, password, role):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        print(f"  skip (already exists): {email}")
        return existing, False
    user = User(full_name=full_name, email=email, password_hash=hash_password(password), role=role)
    db.add(user)
    db.flush()
    return user, True


def seed_patients(db, ws):
    email_to_id = {}
    created = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        full_name, email, password, dob_str, sex, _age_formula, scenario = row
        if not email:
            continue
        user, is_new = get_or_create_user(db, full_name, email, password, UserRole.patient)
        email_to_id[email] = user.user_id
        if is_new:
            created += 1
            y, m, d = (int(p) for p in str(dob_str).split("-"))
            sex_enum = SexEnum.male if sex == "Male" else (SexEnum.female if sex == "Female" else SexEnum.other)
            db.add(PatientProfile(user_id=user.user_id, date_of_birth=date(y, m, d), sex=sex_enum))
            print(f"  created patient: {full_name} <{email}>  [{scenario}]")
    db.commit()
    print(f"Patients: {created} created, {len(email_to_id) - created} already existed.\n")
    return email_to_id


def seed_clinicians_and_admin(db, ws):
    """Reads exact row positions rather than scanning to the sheet's end,
    since the sheet also carries a free-text Note block below the data
    (a generic email-shaped/non-empty-row scan would wrongly try to
    treat that Note row as a user record)."""
    created = 0

    # Clinicians: header at row 2, data rows 3.. until a blank row.
    r = 3
    while True:
        full_name = ws.cell(row=r, column=1).value
        email = ws.cell(row=r, column=2).value
        password = ws.cell(row=r, column=3).value
        if not full_name or not email:
            break
        _user, is_new = get_or_create_user(db, full_name, email, password, UserRole.clinician)
        if is_new:
            created += 1
            print(f"  created clinician: {full_name} <{email}>")
        r += 1

    # Admin: header immediately follows the "Admin" label, data on the next row.
    admin_row = None
    for row_idx in range(1, ws.max_row + 1):
        if ws.cell(row=row_idx, column=1).value == "Admin":
            admin_row = row_idx + 2  # skip the "Admin" label row and the header row
            break
    if admin_row:
        full_name = ws.cell(row=admin_row, column=1).value
        email = ws.cell(row=admin_row, column=2).value
        password = ws.cell(row=admin_row, column=3).value
        if full_name and email:
            _user, is_new = get_or_create_user(db, full_name, email, password, UserRole.admin)
            if is_new:
                created += 1
                print(f"  created admin: {full_name} <{email}>")

    db.commit()
    print(f"Clinicians/Admin: {created} created.\n")


def seed_readings(db, ws, email_to_id):
    now = datetime.now(EAT)
    already_have_readings = {
        pid
        for (pid,) in db.query(BPReading.patient_id).filter(BPReading.patient_id.in_(email_to_id.values())).distinct()
    }
    count = 0
    skipped_patients = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        email, days_ago, hour, minute, systolic, diastolic, heart_rate, notes, _formula = row
        if not email or email not in email_to_id:
            continue
        patient_id = email_to_id[email]
        if patient_id in already_have_readings:
            skipped_patients.add(email)
            continue
        recorded_at = (now - timedelta(days=int(days_ago))).replace(
            hour=int(hour), minute=int(minute), second=0, microsecond=0
        )
        # A "today" reading whose clock time hasn't happened yet would be
        # future-dated, which the API itself rejects. Pull it back to just now.
        if recorded_at > now:
            recorded_at = now - timedelta(minutes=1)
        db.add(
            BPReading(
                patient_id=patient_id,
                systolic=systolic,
                diastolic=diastolic,
                heart_rate=heart_rate,
                recorded_at=recorded_at,
                notes=notes,
            )
        )
        count += 1
    db.commit()
    for email in sorted(skipped_patients):
        print(f"  skip (already has readings): {email}")
    print(f"BP Readings: {count} rows inserted.\n")


def seed_factors(db, ws, email_to_id):
    already_have_factors = {
        pid
        for (pid,) in db.query(EnvironmentalFactor.patient_id)
        .filter(EnvironmentalFactor.patient_id.in_(email_to_id.values()))
        .distinct()
    }
    count = 0
    skipped_patients = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        (email, days_ago, stress, sleep, diet, meds, salt, caffeine, alcohol, smoked, activity, _formula) = row
        if not email or email not in email_to_id:
            continue
        patient_id = email_to_id[email]
        if patient_id in already_have_factors:
            skipped_patients.add(email)
            continue
        logged = date.today() - timedelta(days=int(days_ago))
        db.add(
            EnvironmentalFactor(
                patient_id=patient_id,
                logged_date=logged,
                stress_level=StressLevel(stress) if stress else None,
                sleep_hours=sleep,
                diet_adherence=diet,
                medication_taken=meds,
                salt_intake=IntakeLevel(salt) if salt else None,
                caffeine_intake=IntakeLevel(caffeine) if caffeine else None,
                alcohol_consumed=alcohol,
                smoked=smoked,
                physical_activity_minutes=activity,
            )
        )
        count += 1
    db.commit()
    for email in sorted(skipped_patients):
        print(f"  skip (already has lifestyle entries): {email}")
    print(f"Lifestyle Factors: {count} rows inserted.\n")


def raise_alerts(db, email_to_id):
    """Replays the same trend-check the API runs after every reading, so
    patients whose 7-day trend is elevated/high end up with a real alert
    — exactly as if the readings had come in through the API one by one."""
    raised = 0
    for patient_id in email_to_id.values():
        trend = compute_trend(db, patient_id, period_days=7)
        alert = maybe_create_alert(db, patient_id, trend.status, period_days=7)
        if alert:
            raised += 1
    db.commit()
    print(f"Alerts: {raised} raised from current trends.\n")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    if not os.path.exists(path):
        print(f"Workbook not found: {path}")
        print(f"Usage: python -m scripts.seed_test_data [path/to/{DEFAULT_PATH.name}]")
        return

    wb = openpyxl.load_workbook(path, data_only=True)
    db = SessionLocal()
    try:
        print(f"Seeding from {path}\n")

        print("Patients:")
        email_to_id = seed_patients(db, wb["Patients"])

        print("Clinicians & Admin:")
        seed_clinicians_and_admin(db, wb["Clinicians & Admin"])

        print("BP Readings:")
        seed_readings(db, wb["BP Readings"], email_to_id)

        print("Lifestyle Factors:")
        seed_factors(db, wb["Lifestyle Factors"], email_to_id)

        print("Checking trends for alerts:")
        raise_alerts(db, email_to_id)

        print("Done. Every account uses the password shown in the workbook (Test@1234 by default).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
