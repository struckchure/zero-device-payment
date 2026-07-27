"""SQLAlchemy models — the relational schema for the payment system.

All access goes through SQLAlchemy's ORM, which uses parameterized queries under
the hood (protection against SQL injection). Passwords are stored hashed and
biometric templates are stored encrypted (see app/services/biometrics.py).
"""
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class User(db.Model):
    """A person who can enrol biometrics and authorize payments."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False, default="")
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # One bank account per user (demo simplification).
    account = db.relationship(
        "BankAccount", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    templates = db.relationship(
        "BiometricTemplate", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        # werkzeug uses a salted PBKDF2 hash by default.
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def enrolled_modalities(self) -> list[str]:
        return sorted({t.modality for t in self.templates})

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat(),
            "enrolled_modalities": self.enrolled_modalities,
            "balance": self.account.balance if self.account else None,
            "account_number": self.account.account_number if self.account else None,
        }


class Merchant(db.Model):
    """A payee that can receive transfers (shop, service, etc.)."""

    __tablename__ = "merchants"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    category = db.Column(db.String(80), nullable=False, default="general")
    # Login credentials so a merchant can sign in and collect payments.
    username = db.Column(db.String(80), unique=True, nullable=True, index=True)
    email = db.Column(db.String(255), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    account = db.relationship(
        "BankAccount", back_populates="merchant", uselist=False, cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return bool(self.password_hash) and check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "username": self.username,
            "balance": self.account.balance if self.account else None,
            "account_number": self.account.account_number if self.account else None,
        }


class BankAccount(db.Model):
    """A balance held by the MOCK bank. Exactly one owner (user XOR merchant)."""

    __tablename__ = "bank_accounts"

    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(24), unique=True, nullable=False, index=True)
    balance = db.Column(db.Float, nullable=False, default=0.0)
    currency = db.Column(db.String(3), nullable=False, default="NGN")

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey("merchants.id"), nullable=True)

    user = db.relationship("User", back_populates="account")
    merchant = db.relationship("Merchant", back_populates="account")


class BiometricTemplate(db.Model):
    """An ENCRYPTED biometric template (face embedding or fingerprint template).

    The `encrypted_template` column holds Fernet ciphertext — never raw
    biometric data. Decryption happens only in memory during matching.
    """

    __tablename__ = "biometric_templates"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    modality = db.Column(db.String(20), nullable=False)  # "face" | "fingerprint"
    encrypted_template = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="templates")

    __table_args__ = (
        db.UniqueConstraint("user_id", "modality", name="uq_user_modality"),
    )


class Transaction(db.Model):
    """A payment attempt from a user to a merchant (persisted regardless of outcome)."""

    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(32), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey("merchants.id"), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="NGN")
    status = db.Column(db.String(24), nullable=False)  # APPROVED | DECLINED | AUTH_FAILED
    status_code = db.Column(db.String(8), nullable=False, default="")
    auth_method = db.Column(db.String(40), nullable=False, default="face+fingerprint")
    detail = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User")
    merchant = db.relationship("Merchant")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "reference": self.reference,
            "user": self.user.username if self.user else None,
            "merchant": self.merchant.name if self.merchant else None,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status,
            "status_code": self.status_code,
            "auth_method": self.auth_method,
            "detail": self.detail,
            "created_at": self.created_at.isoformat(),
        }


class AuthAttempt(db.Model):
    """Every authentication attempt — the core audit + metrics record.

    `attempt_type` distinguishes real user activity ("live") from the synthetic
    genuine/impostor pairs generated by the metrics batch, so FAR/FRR can be
    computed against a labelled ground truth.
    """

    __tablename__ = "auth_attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    claimed_username = db.Column(db.String(80), nullable=False, default="")
    attempt_type = db.Column(db.String(16), nullable=False, default="live")  # live|genuine|impostor
    modality = db.Column(db.String(20), nullable=False, default="both")  # face|fingerprint|both
    face_score = db.Column(db.Float, nullable=True)
    fingerprint_score = db.Column(db.Float, nullable=True)
    liveness_passed = db.Column(db.Boolean, nullable=True)
    fused_score = db.Column(db.Float, nullable=True)
    threshold = db.Column(db.Float, nullable=True)
    accepted = db.Column(db.Boolean, nullable=False, default=False)
    response_ms = db.Column(db.Float, nullable=False, default=0.0)
    detail = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user": self.user.username if self.user else self.claimed_username,
            "attempt_type": self.attempt_type,
            "modality": self.modality,
            "face_score": self.face_score,
            "fingerprint_score": self.fingerprint_score,
            "liveness_passed": self.liveness_passed,
            "fused_score": self.fused_score,
            "threshold": self.threshold,
            "accepted": self.accepted,
            "response_ms": round(self.response_ms, 2),
            "detail": self.detail,
            "created_at": self.created_at.isoformat(),
        }


class SystemLog(db.Model):
    """Generic append-only system/audit log surfaced in the admin panel."""

    __tablename__ = "system_logs"

    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.String(10), nullable=False, default="INFO")
    category = db.Column(db.String(40), nullable=False, default="general")
    message = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "level": self.level,
            "category": self.category,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
        }


def log_event(level: str, category: str, message: str) -> None:
    """Convenience helper to append a SystemLog row (caller commits)."""
    db.session.add(SystemLog(level=level, category=category, message=message))
