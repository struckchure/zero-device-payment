"""Face capture + recognition (real, OpenCV-based).

Capture supplies real image bytes from the browser (webcam or upload). Feature
extraction detects the face and builds an LBP template; matching compares it to
the enrolled template. No simulation.
"""
from __future__ import annotations

from .. import biometrics_engine as engine
from .interfaces import CaptureResult, FaceService, MatchResult


class OpenCVFaceService(FaceService):
    def __init__(self, settings: dict):
        self.settings = settings  # shared, admin-tunable (match threshold)

    def extract(self, image_bytes: bytes, source: str = "upload") -> CaptureResult:
        try:
            template, quality, detected = engine.extract_face(image_bytes)
        except engine.ExtractionError as exc:
            return CaptureResult([], 0.0, source, ok=False, detail=str(exc))
        if not detected:
            return CaptureResult(template, quality, source, ok=False,
                                 detail="No face detected in the image.")
        return CaptureResult(template, quality, source)

    def match(self, probe: CaptureResult, enrolled_embedding: list[float]) -> MatchResult:
        score = engine.compare(probe.embedding, enrolled_embedding)
        threshold = float(self.settings.get("match_threshold", 0.55))
        return MatchResult(score=round(score, 4), matched=score >= threshold, modality="face")
