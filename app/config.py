"""Application configuration, loaded from environment / .env.

Keeping all tunables here (and reading them from the environment) means secrets
never live in source and the mock-simulation parameters can be adjusted without
touching code.
"""
import base64
import hashlib
import os

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

# Load THIS project's .env (do not walk up the tree into unrelated .env files,
# which could inject e.g. a relative DATABASE_URL and break the DB path).
load_dotenv(os.path.join(BASE_DIR, ".env"))

INSTANCE_DIR = os.path.join(BASE_DIR, "instance")


def _resolve_database_uri() -> str:
    """Return an absolute SQLite URI, robust to relative/empty DATABASE_URL."""
    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        return f"sqlite:///{os.path.join(INSTANCE_DIR, 'payments.db')}"
    # Anchor relative sqlite paths (sqlite:///relative/x.db) to the project root.
    prefix = "sqlite:///"
    if raw.startswith(prefix):
        path = raw[len(prefix):]
        if not os.path.isabs(path):
            path = os.path.join(BASE_DIR, path)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        return f"{prefix}{path}"
    return raw


def _derive_demo_fernet_key(secret: str) -> str:
    """Derive a *deterministic* Fernet key from SECRET_KEY.

    This is a convenience for demos so the app runs with zero setup. A real
    deployment must supply a proper random BIOMETRIC_ENCRYPTION_KEY instead.
    """
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

    # Biometric-template encryption key (Fernet). Fall back to a derived demo key.
    BIOMETRIC_ENCRYPTION_KEY = (
        os.environ.get("BIOMETRIC_ENCRYPTION_KEY", "").strip()
        or _derive_demo_fernet_key(SECRET_KEY)
    )

    SQLALCHEMY_DATABASE_URI = _resolve_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session hardening (sensible security defaults).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Set True behind HTTPS in production.
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"

    # ---- Matching / fusion tunables ---------------------------------------
    # Similarity (0..1) a probe must reach to match an enrolled template.
    MATCH_THRESHOLD = float(os.environ.get("MATCH_THRESHOLD", "0.55"))
    # Minimum capture quality for the liveness/content check to pass.
    LIVENESS_MIN_QUALITY = float(os.environ.get("LIVENESS_MIN_QUALITY", "0.15"))
    # Weights used when authenticating with BOTH modalities.
    FUSION_WEIGHT_FACE = float(os.environ.get("FUSION_WEIGHT_FACE", "0.5"))
    FUSION_WEIGHT_FINGERPRINT = float(os.environ.get("FUSION_WEIGHT_FINGERPRINT", "0.5"))

    # Max upload size for captured images (base64 in JSON): 8 MB.
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
