
import sys, os
sys.path.append(os.getcwd())

import getpass
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole


def main():
    db = SessionLocal()
    try:
        full_name = input("Admin full name: ").strip()
        email = input("Admin email: ").strip().lower()

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

        admin = User(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.admin,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        print(f"\nAdmin account created successfully:")
        print(f"  Name:  {admin.full_name}")
        print(f"  Email: {admin.email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()