import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import require_clinician, require_patient
from app.models.alert import Alert
from app.models.user import User
from app.schemas.alert import AlertOut

router = APIRouter(prefix="/alerts", tags=["Alerts"])


def _to_out(alert: Alert) -> AlertOut:
    data = AlertOut.model_validate(alert, from_attributes=True)
    data.patient_name = alert.patient.full_name if alert.patient else None
    return data


def _alerts_query(db: Session):
    # joinedload avoids one extra SELECT per alert when reading patient_name.
    return db.query(Alert).options(joinedload(Alert.patient)).order_by(Alert.created_at.desc())


@router.get("/me", response_model=list[AlertOut])
def get_my_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_patient),
):
    alerts = _alerts_query(db).filter(Alert.patient_id == current_user.user_id).all()
    return [_to_out(a) for a in alerts]


@router.get("", response_model=list[AlertOut])
def get_all_alerts(
    unacknowledged_only: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinician),
):
    query = _alerts_query(db)
    if unacknowledged_only:
        query = query.filter(Alert.acknowledged.is_(False))
    return [_to_out(a) for a in query.all()]


@router.get("/patient/{patient_id}", response_model=list[AlertOut])
def get_patient_alerts(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinician),
):
    alerts = _alerts_query(db).filter(Alert.patient_id == patient_id).all()
    return [_to_out(a) for a in alerts]


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_clinician),
):
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert.acknowledged = True
    alert.acknowledged_by = current_user.user_id
    db.commit()
    db.refresh(alert)
    return _to_out(alert)
