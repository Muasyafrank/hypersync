from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.alert import Alert


def maybe_create_alert(db: Session, patient_id, trend_status: str, period_days: int) -> Alert | None:
    if trend_status not in ("elevated", "high"):
        return None

    alert_type = f"{trend_status}_trend"

    # Avoid duplicate alerts: skip if an unacknowledged alert of the same
    # type was already raised for this patient in the last 24 hours.
    recent_cutoff = datetime.now(UTC) - timedelta(hours=24)
    existing = (
        db.query(Alert)
        .filter(
            Alert.patient_id == patient_id,
            Alert.alert_type == alert_type,
            Alert.acknowledged == False,  # noqa: E712
            Alert.created_at >= recent_cutoff,
        )
        .first()
    )
    if existing:
        return None

    message = (
        f"Patient's average blood pressure over the last {period_days} days is {trend_status}. Review recommended."
    )
    alert = Alert(patient_id=patient_id, alert_type=alert_type, message=message)
    db.add(alert)
    db.flush()  # so it has an ID without requiring a separate commit here
    return alert
