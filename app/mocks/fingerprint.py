"""Fingerprint capture + matcher (real, OpenCV-based).

Capture supplies real image bytes from the browser (webcam or upload). The
template is an LBP histogram over the ridge image; matching compares it to the
enrolled template. No simulation.
"""
from __future__ import annotations

from .. import biometrics_engine as engine
from .interfaces import CaptureResult, FingerprintService, MatchResult


class OpenCVFingerprintService(FingerprintService):
    def __init__(self, settings: dict):
        self.settings = settings

    def extract(self, image_bytes: bytes, source: str = "upload") -> CaptureResult:
        try:
            template, quality, _ = engine.extract_fingerprint(image_bytes)
        except engine.ExtractionError as exc:
            return CaptureResult([], 0.0, source, ok=False, detail=str(exc))
        return CaptureResult(template, quality, source)

    def match(self, probe: CaptureResult, enrolled_embedding: list[float]) -> MatchResult:
        score = engine.compare(probe.embedding, enrolled_embedding)
        threshold = float(self.settings.get("match_threshold", 0.55))
        return MatchResult(score=round(score, 4), matched=score >= threshold, modality="fingerprint")
