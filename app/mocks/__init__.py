"""Service registry — wires the concrete capture/matching + bank implementations.

The rest of the app asks this registry for a FaceService / FingerprintService /
LivenessService / BankGateway and never imports concrete classes directly.

Face + fingerprint matching is real (OpenCV/LBP). The bank is still a mock, and
an external capture device is a disabled future option. `settings` is a
process-wide, mutable dict of tunables the admin panel can adjust at runtime
(currently the match threshold and liveness minimum quality).
"""
from __future__ import annotations

from .bank import MockBankGateway
from .camera import OpenCVFaceService
from .fingerprint import OpenCVFingerprintService
from .interfaces import BankGateway, FaceService, FingerprintService, LivenessService
from .liveness import ContentLivenessService

# Runtime-tunable settings (populated by init_mocks()).
settings: dict = {}

_registry: dict = {}


def init_mocks(config) -> None:
    """Instantiate services from app config. Called once by the app factory."""
    settings.clear()
    settings.update(
        {
            "match_threshold": config["MATCH_THRESHOLD"],
            "liveness_min_quality": config["LIVENESS_MIN_QUALITY"],
        }
    )

    _registry["face"] = OpenCVFaceService(settings)
    _registry["fingerprint"] = OpenCVFingerprintService(settings)
    _registry["liveness"] = ContentLivenessService(settings)
    # --- SWAP POINT: replace with a real bank/payment-gateway client here. ---
    _registry["bank"] = MockBankGateway()


def face_service() -> FaceService:
    return _registry["face"]


def fingerprint_service() -> FingerprintService:
    return _registry["fingerprint"]


def liveness_service() -> LivenessService:
    return _registry["liveness"]


def bank_gateway() -> BankGateway:
    return _registry["bank"]
