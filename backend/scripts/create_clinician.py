
import sys
import os
sys.path.append(os.getcwd())

import getpass
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole


def main():
    db = SessionLocal()
    try:
        full_name = input("Clinician full name: ").strip()
        email = input("Clinician email: ").strip().lower()

        existing = db.query(User).filter(User.email == email).first()
        if existing:
            print(f"A user with email '{email}' already exists (role: {existing.role.value}).")
            return

        password = getpass.getpass("Password (min 8 characters): ")
        if len(password) < 8:
            print("Password must be at least 8 characters.")
            return

        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.")
            return

        clinician = User(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.clinician,
        )
        db.add(clinician)
        db.commit()
        db.refresh(clinician)

        print(f"\nClinician account created successfully:")
        print(f"  Name:  {clinician.full_name}")
        print(f"  Email: {clinician.email}")
        print(f"  Role:  {clinician.role.value}")
    finally:
        db.close()


if __name__ == "__main__":
    main()