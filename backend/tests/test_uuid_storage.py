"""UUID columns must remain UUID values on every supported database backend."""

import uuid

from app.core.database import SessionLocal
from app.models.user import User, UserRole


def test_a_numeric_only_uuid_survives_the_sqlite_round_trip():
    """SQLite must not coerce an all-digit UUID into a floating-point value."""
    numeric_only_id = uuid.UUID(int=12345678901234567890123456789012)
    db = SessionLocal()
    try:
        db.add(
            User(
                user_id=numeric_only_id,
                full_name="Numeric UUID Patient",
                email="numeric-uuid@example.com",
                password_hash="not-used-in-this-test",
                role=UserRole.patient,
            )
        )
        db.commit()
        db.expire_all()

        stored = db.query(User).filter(User.email == "numeric-uuid@example.com").one()
        assert stored.user_id == numeric_only_id
        assert isinstance(stored.user_id, uuid.UUID)
    finally:
        db.close()
