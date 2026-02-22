"""
Create a default admin user for local/dev. Run once after migrations:
  docker-compose exec api python scripts/create_admin.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from core.security import get_password_hash
from models import User

DEFAULT_EMAIL = "rk@admin.com"
DEFAULT_PASSWORD = "Admin123!"


def main():
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == DEFAULT_EMAIL).first()
        if existing:
            print(f"Admin user already exists: {DEFAULT_EMAIL}")
            print(f"Password: {DEFAULT_PASSWORD}")
            return
        user = User(
            email=DEFAULT_EMAIL,
            password_hash=get_password_hash(DEFAULT_PASSWORD),
            first_name="Admin",
            last_name="User",
            role="Admin",
            department="IT",
            status="active",
        )
        db.add(user)
        db.commit()
        print("Admin user created. Use these credentials to log in:")
        print(f"  Email:    {DEFAULT_EMAIL}")
        print(f"  Password: {DEFAULT_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
