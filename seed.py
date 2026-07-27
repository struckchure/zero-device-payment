"""Database setup + demo-data seeding script.

Usage:
    python seed.py            # create tables + seed demo users/merchants
    python seed.py --reset    # drop everything first, then recreate

Creates:
  * demo customers (alice, bob) funded to 50k (they enrol their own biometrics)
  * an admin user
  * demo merchants with login credentials + balances (they collect payments)

Biometrics are NOT pre-enrolled — matching is real, so each customer enrols a
face and/or fingerprint from a webcam or uploaded image after logging in.
"""
from __future__ import annotations

import secrets
import sys

from app import create_app
from app.extensions import db
from app.models import BankAccount, Merchant, User

# Customers are funded up to 50k by default.
DEMO_USERS = [
    # (username, full_name, email, password, balance, is_admin)
    ("alice", "Alice Anderson", "alice@example.com", "Password123", 50000.0, False),
    ("bob", "Bob Brown", "bob@example.com", "Password123", 50000.0, False),
    ("admin", "System Admin", "admin@example.com", "Admin12345", 0.0, True),
]

DEMO_MERCHANTS = [
    # (name, category, balance, username, email, password)
    ("Corner Coffee", "food", 200000.0, "coffee", "coffee@example.com", "Merchant123"),
    ("City Transit", "transport", 500000.0, "transit", "transit@example.com", "Merchant123"),
    ("BookNook", "retail", 80000.0, "booknook", "booknook@example.com", "Merchant123"),
]


def _account_number() -> str:
    return "ACC" + "".join(secrets.choice("0123456789") for _ in range(12))


def seed(reset: bool = False) -> None:
    app = create_app()
    with app.app_context():
        if reset:
            print("Dropping all tables…")
            db.drop_all()
        db.create_all()

        if User.query.first() or Merchant.query.first():
            print("Database already has data. Re-run with --reset to rebuild.")
            return

        # --- Users + biometric enrolment (via MOCK devices) ---
        for username, full_name, email, password, balance, is_admin in DEMO_USERS:
            user = User(username=username, full_name=full_name, email=email, is_admin=is_admin)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()  # assign id

            db.session.add(BankAccount(account_number=_account_number(), balance=balance, user=user))
            print(f"  + user {username} (balance NGN {balance:,.2f}, admin={is_admin})")

        # --- Merchants + accounts + login credentials ---
        for name, category, balance, username, email, password in DEMO_MERCHANTS:
            merchant = Merchant(name=name, category=category, username=username, email=email)
            merchant.set_password(password)
            db.session.add(merchant)
            db.session.flush()
            db.session.add(
                BankAccount(account_number=_account_number(), balance=balance, merchant=merchant)
            )
            print(f"  + merchant {name} (login {username}/{password}, balance NGN {balance:,.2f})")

        db.session.commit()
        print("\nSeed complete.")
        print("Customer logins:  alice/Password123  bob/Password123  admin/Admin12345")
        print("Merchant logins:  coffee/Merchant123  transit/Merchant123  booknook/Merchant123")
        print("Log in as a customer and enrol a face/fingerprint before paying.")


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
