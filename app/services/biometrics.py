"""Biometric enrolment, encrypted-template storage, and multimodal fusion.

Templates are encrypted at rest with Fernet (AES-128-CBC + HMAC). Plaintext
embeddings exist only transiently in memory during enrolment and matching.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from cryptography.fernet import Fernet
from flask import current_app

from ..extensions import db
from ..models import BiometricTemplate, User


def _fernet() -> Fernet:
    return Fernet(current_app.config["BIOMETRIC_ENCRYPTION_KEY"].encode("utf-8"))


def encrypt_embedding(embedding: list[float]) -> bytes:
    """Serialize + encrypt an embedding into Fernet ciphertext for storage."""
    plaintext = json.dumps(embedding).encode("utf-8")
    return _fernet().encrypt(plaintext)


def decrypt_embedding(ciphertext: bytes) -> list[float]:
    """Decrypt stored ciphertext back into an embedding (in memory only)."""
    plaintext = _fernet().decrypt(bytes(ciphertext))
    return json.loads(plaintext.decode("utf-8"))


def enrol_template(user: User, modality: str, embedding: list[float]) -> BiometricTemplate:
    """Create or replace a user's encrypted template for a modality."""
    existing = BiometricTemplate.query.filter_by(user_id=user.id, modality=modality).first()
    ciphertext = encrypt_embedding(embedding)
    if existing:
        existing.encrypted_template = ciphertext
        return existing
    tmpl = BiometricTemplate(user_id=user.id, modality=modality, encrypted_template=ciphertext)
    db.session.add(tmpl)
    return tmpl


def get_enrolled_embedding(user: User, modality: str) -> list[float] | None:
    tmpl = BiometricTemplate.query.filter_by(user_id=user.id, modality=modality).first()
    if tmpl is None:
        return None
    return decrypt_embedding(tmpl.encrypted_template)


# --- Multimodal fusion --------------------------------------------------------


@dataclass
class FusionDecision:
    """Outcome of scoring one or both modalities under a liveness gate."""

    face_score: float
    fingerprint_score: float
    liveness_passed: bool
    fused_score: float
    threshold: float
    accepted: bool
    reason: str
    modality: str = "both"


def fuse(face_score: float, fingerprint_score: float, liveness_passed: bool,
         modality: str = "both") -> FusionDecision:
    """Decision rule with a hard liveness gate.

    * modality "both"        -> weighted-sum fusion: w_face*face + w_fp*fingerprint
    * modality "face"        -> face score alone
    * modality "fingerprint" -> fingerprint score alone

    The chosen score must reach the threshold AND liveness must pass (a spoof
    fails outright). Weights/threshold come from config so they can be tuned.
    """
    cfg = current_app.config
    from ..mocks import settings as mock_settings
    threshold = float(mock_settings.get("match_threshold", cfg["MATCH_THRESHOLD"]))

    if modality == "face":
        score, label = round(face_score, 4), "Face score"
    elif modality == "fingerprint":
        score, label = round(fingerprint_score, 4), "Fingerprint score"
    else:
        modality = "both"
        w_face, w_fp = cfg["FUSION_WEIGHT_FACE"], cfg["FUSION_WEIGHT_FINGERPRINT"]
        score, label = round(w_face * face_score + w_fp * fingerprint_score, 4), "Fused score"

    if not liveness_passed:
        return FusionDecision(face_score, fingerprint_score, False, score, threshold,
                              accepted=False, reason="Liveness check failed", modality=modality)

    accepted = score >= threshold
    reason = "Accepted" if accepted else f"{label} {score:.3f} below threshold {threshold:.3f}"
    return FusionDecision(face_score, fingerprint_score, True, score, threshold, accepted,
                          reason, modality=modality)
