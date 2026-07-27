"""JSON API for the biometric-capture flows (enrol, authenticate, pay, collect)
and the metrics dashboard. Captured images arrive as base64 data URLs.
"""
from __future__ import annotations

import base64

from flask import Blueprint, jsonify, request

from .. import (admin_required, current_merchant, current_user, login_required,
                merchant_required)
from ..extensions import db
from ..models import BankAccount, Merchant, log_event
from ..mocks import face_service, fingerprint_service
from ..services import auth as auth_service
from ..services import biometrics
from ..services import metrics as metrics_service
from ..services import payments as payment_service

bp = Blueprint("api", __name__)

VALID_MODALITIES = ("face", "fingerprint", "both")


def _modality(data: dict) -> str:
    m = (data.get("modality") or "both").lower()
    return m if m in VALID_MODALITIES else "both"


def _decode_image(data_url) -> bytes | None:
    """Decode a base64 data URL (or raw base64) into image bytes."""
    if not data_url or not isinstance(data_url, str):
        return None
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    try:
        return base64.b64decode(data_url)
    except Exception:
        return None


@bp.post("/enrol")
@login_required
def enrol():
    """Enrol/replace the current user's face and/or fingerprint from real images."""
    data = request.get_json(silent=True) or {}
    user = current_user()
    face_bytes = _decode_image(data.get("face_image"))
    fp_bytes = _decode_image(data.get("fingerprint_image"))
    if not face_bytes and not fp_bytes:
        return jsonify({"error": "Capture a face or fingerprint image to enrol."}), 400

    enrolled, errors = [], []
    if face_bytes:
        cap = face_service().extract(face_bytes, source="enrol")
        if cap.ok:
            biometrics.enrol_template(user, "face", cap.embedding)
            enrolled.append("face")
        else:
            errors.append(cap.detail)
    if fp_bytes:
        cap = fingerprint_service().extract(fp_bytes, source="enrol")
        if cap.ok:
            biometrics.enrol_template(user, "fingerprint", cap.embedding)
            enrolled.append("fingerprint")
        else:
            errors.append(cap.detail)

    if enrolled:
        log_event("INFO", "account", f"Enrolled {'+'.join(enrolled)} for {user.username}")
        db.session.commit()
    return jsonify({
        "enrolled": enrolled,
        "errors": errors,
        "enrolled_modalities": user.enrolled_modalities,
    }), (200 if enrolled else 422)


@bp.post("/authenticate")
@login_required
def authenticate():
    """Run a standalone auth check (face, fingerprint, or both) for the user."""
    data = request.get_json(silent=True) or {}
    outcome = auth_service.authenticate(
        current_user(), modality=_modality(data),
        face_image=_decode_image(data.get("face_image")),
        fingerprint_image=_decode_image(data.get("fingerprint_image")),
        attempt_type="live",
    )
    d = outcome.decision
    return jsonify({
        "accepted": outcome.accepted,
        "modality": d.modality,
        "face_score": round(d.face_score, 4),
        "fingerprint_score": round(d.fingerprint_score, 4),
        "liveness_passed": d.liveness_passed,
        "fused_score": d.fused_score,
        "threshold": d.threshold,
        "reason": d.reason,
        "response_ms": round(outcome.response_ms, 2),
    })


@bp.post("/pay")
@login_required
def pay():
    """Authorize + settle a payment to a merchant using biometric auth."""
    data = request.get_json(silent=True) or {}
    try:
        merchant_id = int(data.get("merchant_id"))
        amount = round(float(data.get("amount")), 2)
    except (TypeError, ValueError):
        return jsonify({"error": "merchant_id and a numeric amount are required."}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be positive."}), 400

    merchant = db.session.get(Merchant, merchant_id)
    if merchant is None:
        return jsonify({"error": "Unknown merchant."}), 404

    result = payment_service.authorize_payment(
        current_user(), merchant, amount, modality=_modality(data),
        face_image=_decode_image(data.get("face_image")),
        fingerprint_image=_decode_image(data.get("fingerprint_image")),
    )
    user = current_user()
    return jsonify({
        "ok": result.ok,
        "status": result.status,
        "reference": result.reference,
        "message": result.message,
        "amount": amount,
        "merchant": merchant.name,
        "new_balance": user.account.balance if user.account else None,
        "transaction": result.transaction.to_dict() if result.transaction else None,
    }), (200 if result.ok else 402)


@bp.post("/collect")
@merchant_required
def collect():
    """Merchant collects a payment from a customer identified by account ID.

    The customer authorizes with a biometric (face or fingerprint) captured at
    the merchant — the 'zero-device' point of sale. Funds move customer -> merchant.
    """
    data = request.get_json(silent=True) or {}
    account_id = (data.get("account_id") or "").strip()
    try:
        amount = round(float(data.get("amount")), 2)
    except (TypeError, ValueError):
        return jsonify({"error": "A numeric amount is required."}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be positive."}), 400
    if not account_id:
        return jsonify({"error": "Customer account ID is required."}), 400

    account = BankAccount.query.filter_by(account_number=account_id).first()
    if account is None or account.user is None:
        return jsonify({"error": "No customer account with that ID."}), 404

    merchant = current_merchant()
    result = payment_service.authorize_payment(
        account.user, merchant, amount, modality=_modality(data),
        face_image=_decode_image(data.get("face_image")),
        fingerprint_image=_decode_image(data.get("fingerprint_image")),
    )
    return jsonify({
        "ok": result.ok,
        "status": result.status,
        "reference": result.reference,
        "message": result.message,
        "amount": amount,
        "customer": account.user.username,
        "new_balance": merchant.account.balance if merchant.account else None,
        "transaction": result.transaction.to_dict() if result.transaction else None,
    }), (200 if result.ok else 402)


@bp.post("/metrics/run")
@admin_required
def run_metrics():
    return jsonify(metrics_service.compute())


@bp.get("/metrics/history")
@login_required
def metrics_history():
    return jsonify(metrics_service.compute())
