"""Liveness / presentation check.

Full anti-spoofing needs dedicated hardware or a trained model (this is where a
real external device would plug in). As a content-based stand-in we accept a
capture only when a usable biometric was actually found and the image has enough
contrast — this rejects blank/garbage frames rather than sampling a probability.
"""
from __future__ import annotations

from .interfaces import CaptureResult, LivenessResult, LivenessService


class ContentLivenessService(LivenessService):
    def __init__(self, settings: dict):
        self.settings = settings

    def check(self, capture: CaptureResult) -> LivenessResult:
        min_quality = float(self.settings.get("liveness_min_quality", 0.15))
        passed = bool(capture and capture.ok and capture.quality >= min_quality)
        return LivenessResult(passed=passed, score=capture.quality if capture else 0.0)
