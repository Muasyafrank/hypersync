import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.alert import Alert
from app.schemas.alert import AlertOut

router = APIRouter(prefix="/alerts", tags=["Alerts"])


def _to_out(alert: Alert) -> AlertOut:
    data = AlertOut.model_validate(alert, from_attributes=True)
    data.patient_name = alert.patient.full_name if alert.patient else None
    return data


@router.get("/me", response_model=List[AlertOut])
def get_my_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "patient":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only patients can view their own alerts")

    alerts = (
        db.query(Alert)
        .filter(Alert.patient_id == current_user.user_id)
        .order_by(Alert.created_at.desc())
        .all()
    )
    return [_to_out(a) for a in alerts]


@router.get("/", response_model=List[AlertOut])
def get_all_alerts(
    unacknowledged_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "clinician":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only clinicians can view the alert queue")

    query = db.query(Alert)
    if unacknowledged_only:
        query = query.filter(Alert.acknowledged == False)  # noqa: E712

    alerts = query.order_by(Alert.created_at.desc()).all()
    return [_to_out(a) for a in alerts]


@router.get("/patient/{patient_id}", response_model=List[AlertOut])
def get_patient_alerts(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "clinician":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only clinicians can view patient alerts")

    alerts = (
        db.query(Alert)
        .filter(Alert.patient_id == patient_id)
        .order_by(Alert.created_at.desc())
        .all()
    )
    return [_to_out(a) for a in alerts]


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "clinician":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only clinicians can acknowledge alerts")

    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert.acknowledged = True
    alert.acknowledged_by = current_user.user_id
    db.commit()
    db.refresh(alert)
    return _to_out(alert)