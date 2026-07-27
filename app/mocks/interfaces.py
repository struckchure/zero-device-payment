"""Abstract interfaces defining the capture / matching / bank boundary.

Each biometric is accessed only through one of the abstract base classes below.
Capture sources (camera, upload) provide real image bytes from the browser; the
concrete services here do the real feature extraction + comparison. The bank and
the (disabled) external-device path remain stubs. To integrate real hardware or
a real bank, subclass the relevant interface and register it in
`app/mocks/__init__.py` — no calling code changes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


# --- Data contracts passed across the boundary --------------------------------


@dataclass
class CaptureResult:
    """A biometric template extracted from a captured image."""

    embedding: list[float]  # LBP-histogram feature vector
    quality: float          # 0..1 capture quality score
    source: str             # "camera" | "upload" | "external"
    ok: bool = True         # False when no usable biometric was found
    detail: str = ""        # human-readable reason when ok is False


@dataclass
class MatchResult:
    """Result of matching a probe capture against an enrolled template."""

    score: float            # 0..1 similarity
    matched: bool           # score >= modality threshold
    modality: str           # "face" | "fingerprint"


@dataclass
class LivenessResult:
    passed: bool
    score: float            # 0..1 confidence that the sample is a valid capture


@dataclass
class BankResult:
    """Result of a mock bank operation."""

    approved: bool
    status_code: str        # e.g. "00" approved, "51" insufficient funds
    reference: str
    message: str


# --- Interfaces ---------------------------------------------------------------


class FaceService(ABC):
    """Face capture + recognition boundary."""

    @abstractmethod
    def extract(self, image_bytes: bytes, source: str = "upload") -> CaptureResult:
        ...

    @abstractmethod
    def match(self, probe: CaptureResult, enrolled_embedding: list[float]) -> MatchResult:
        ...


class FingerprintService(ABC):
    """Fingerprint capture + matcher boundary."""

    @abstractmethod
    def extract(self, image_bytes: bytes, source: str = "upload") -> CaptureResult:
        ...

    @abstractmethod
    def match(self, probe: CaptureResult, enrolled_embedding: list[float]) -> MatchResult:
        ...


class LivenessService(ABC):
    """Presentation / liveness detection boundary."""

    @abstractmethod
    def check(self, capture: CaptureResult) -> LivenessResult:
        ...


class BankGateway(ABC):
    """Bank / payment-gateway boundary."""

    @abstractmethod
    def transfer(self, from_account: str, to_account: str, amount: float,
                 currency: str = "NGN") -> BankResult:
        ...
