"""Patient-owned context used when staff review a patient's records."""

from sqlalchemy.orm import Session

from app.core.localtime import resolve_timezone
from app.models.user import PatientProfile


def patient_timezones(db: Session, patient_ids) -> dict:
    """Return each patient's stored IANA timezone, with a safe default."""
    patient_ids = list(patient_ids)
    if not patient_ids:
        return {}
    stored = dict(
        db.query(PatientProfile.user_id, PatientProfile.timezone).filter(PatientProfile.user_id.in_(patient_ids)).all()
    )
    return {patient_id: resolve_timezone(stored.get(patient_id)) for patient_id in patient_ids}


def patient_timezone(db: Session, patient_id) -> object:
    """The timezone used to group one patient's readings into calendar days."""
    return patient_timezones(db, [patient_id])[patient_id]
