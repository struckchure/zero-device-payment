"""Authentication orchestration.

Takes real captured images (webcam or upload), extracts templates, compares them
to the user's enrolled templates, applies a liveness/content check and the
decision rule, and records an AuthAttempt for every attempt.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from ..extensions import db
from ..models import AuthAttempt, User, log_event
from ..mocks import face_service, fingerprint_service, liveness_service, settings as mock_settings
from . import biometrics


@dataclass
class AuthOutcome:
    accepted: bool
    decision: biometrics.FusionDecision
    response_ms: float
    detail: str


def authenticate(
    user: User,
    *,
    modality: str = "both",
    face_image: bytes | None = None,
    fingerprint_image: bytes | None = None,
    attempt_type: str = "live",
    persist: bool = True,
) -> AuthOutcome:
    """Authenticate `user` with a real face and/or fingerprint capture.

    * modality: "face" | "fingerprint" | "both".
    * face_image / fingerprint_image: raw image bytes captured at the client.
    Returns an AuthOutcome and records an AuthAttempt.
    """
    started = time.perf_counter()
    use_face = modality in ("face", "both")
    use_fp = modality in ("fingerprint", "both")
    threshold = float(mock_settings.get("match_threshold", 0.55))

    enrolled_face = biometrics.get_enrolled_embedding(user, "face")
    enrolled_fp = biometrics.get_enrolled_embedding(user, "fingerprint")

    face_score = fp_score = 0.0
    face_probe = fp_probe = None
    error = None

    if use_face:
        if not enrolled_face:
            error = "Face is not enrolled for this account."
        elif not face_image:
            error = "No face capture was provided."
        else:
            face_probe = face_service().extract(face_image, source="capture")
            if not face_probe.ok:
                error = face_probe.detail
            else:
                face_score = face_service().match(face_probe, enrolled_face).score

    if error is None and use_fp:
        if not enrolled_fp:
            error = "Fingerprint is not enrolled for this account."
        elif not fingerprint_image:
            error = "No fingerprint capture was provided."
        else:
            fp_probe = fingerprint_service().extract(fingerprint_image, source="capture")
            if not fp_probe.ok:
                error = fp_probe.detail
            else:
                fp_score = fingerprint_service().match(fp_probe, enrolled_fp).score

    if error is not None:
        decision = biometrics.FusionDecision(
            face_score, fp_score, liveness_passed=False, fused_score=0.0,
            threshold=threshold, accepted=False, reason=error, modality=modality)
        liveness_passed = False
    else:
        liveness = liveness_service().check(face_probe or fp_probe)
        liveness_passed = liveness.passed
        decision = biometrics.fuse(face_score, fp_score, liveness_passed, modality=modality)

    response_ms = (time.perf_counter() - started) * 1000.0

    attempt = AuthAttempt(
        user_id=user.id,
        claimed_username=user.username,
        attempt_type=attempt_type,
        modality=decision.modality,
        face_score=face_score,
        fingerprint_score=fp_score,
        liveness_passed=liveness_passed,
        fused_score=decision.fused_score,
        threshold=decision.threshold,
        accepted=decision.accepted,
        response_ms=response_ms,
        detail=decision.reason,
    )
    db.session.add(attempt)
    if persist:
        log_event(
            "INFO" if decision.accepted else "WARN", "auth",
            f"Auth {'ACCEPTED' if decision.accepted else 'REJECTED'} [{decision.modality}] for "
            f"{user.username}: {decision.reason} (score={decision.fused_score:.3f})",
        )
        db.session.commit()

    return AuthOutcome(decision.accepted, decision, response_ms, decision.reason)
