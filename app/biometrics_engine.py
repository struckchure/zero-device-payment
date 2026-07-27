"""Real image-based biometric feature extraction & comparison (OpenCV + numpy).

A biometric *template* is a spatial Local Binary Pattern (LBP) histogram computed
from the actual captured image — the classic pre-deep-learning face/texture
recognition method, with no model downloads. Two templates are compared with
histogram intersection, giving a 0..1 similarity that is 1.0 for identical
captures and lower for different ones.

  * Face:        detect the face (Haar cascade), crop, then LBP histogram.
  * Fingerprint: LBP histogram over the whole ridge image.

This module does the genuine comparison; the browser (webcam/upload) supplies
the real image bytes.
"""
from __future__ import annotations

import numpy as np

try:  # OpenCV is required for real matching; degrade with a clear error if absent.
    import cv2

    _HAAR = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
except Exception:  # pragma: no cover - only if cv2 missing/broken
    cv2 = None
    _HAAR = None

CROP = 128          # face/finger crop is resized to CROP x CROP
CELLS = 8           # spatial grid: CELLS x CELLS cells


class ExtractionError(Exception):
    """Raised when an image cannot be decoded / no usable biometric is found."""


# --- Uniform-LBP bin mapping (59 bins: 58 uniform codes + 1 non-uniform) ------

def _build_uniform_table():
    mapping, idx = {}, 0
    for code in range(256):
        bits = [(code >> i) & 1 for i in range(8)]
        transitions = sum(bits[i] != bits[(i + 1) % 8] for i in range(8))
        if transitions <= 2:
            mapping[code] = idx
            idx += 1
    non_uniform = idx
    table = np.array([mapping.get(c, non_uniform) for c in range(256)], dtype=np.int32)
    return table, non_uniform + 1


_UNIFORM_TABLE, _N_BINS = _build_uniform_table()


def _decode_gray(image_bytes: bytes) -> np.ndarray:
    if cv2 is None:
        raise ExtractionError("OpenCV is not available for image matching.")
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None or img.size == 0:
        raise ExtractionError("Could not decode the captured image.")
    return img


def _detect_face(gray: np.ndarray):
    if _HAAR is None:
        return None
    faces = _HAAR.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])  # largest face
    return gray[y:y + h, x:x + w]


def _lbp_codes(gray: np.ndarray) -> np.ndarray:
    g = gray.astype(np.int16)
    padded = np.pad(g, 1, mode="edge")
    codes = np.zeros(g.shape, dtype=np.uint8)
    # 8 neighbours (clockwise from top-left).
    offsets = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]
    for i, (dy, dx) in enumerate(offsets):
        neigh = padded[1 + dy:1 + dy + g.shape[0], 1 + dx:1 + dx + g.shape[1]]
        codes |= ((neigh >= g).astype(np.uint8) << i)
    return codes


def _spatial_lbp_histogram(gray: np.ndarray) -> list[float]:
    gray = cv2.resize(gray, (CROP, CROP))
    gray = cv2.equalizeHist(gray)  # normalise lighting
    mapped = _UNIFORM_TABLE[_lbp_codes(gray)]
    step = CROP // CELLS
    feats = []
    for cy in range(CELLS):
        for cx in range(CELLS):
            cell = mapped[cy * step:(cy + 1) * step, cx * step:(cx + 1) * step]
            hist = np.bincount(cell.ravel(), minlength=_N_BINS)[:_N_BINS].astype(np.float64)
            total = hist.sum()
            if total:
                hist /= total
            feats.append(hist)
    vec = np.concatenate(feats)
    total = vec.sum()
    return (vec / total).tolist() if total else vec.tolist()


def _quality(gray: np.ndarray, face_detected: bool) -> float:
    """Crude capture-quality score from contrast (and face presence)."""
    q = min(1.0, float(np.std(gray)) / 64.0)
    if not face_detected:
        q *= 0.5
    return round(q, 3)


def extract_face(image_bytes: bytes) -> tuple[list[float], float, bool]:
    """Return (template, quality, face_detected) for a face image.

    If no face is detected we fall back to the whole frame so the pipeline still
    produces a real template, but flag it (lower quality) — a real device would
    reject the capture here.
    """
    gray = _decode_gray(image_bytes)
    face = _detect_face(gray)
    region = face if face is not None else gray
    return _spatial_lbp_histogram(region), _quality(region, face is not None), face is not None


def extract_fingerprint(image_bytes: bytes) -> tuple[list[float], float, bool]:
    """Return (template, quality, True) for a fingerprint image."""
    gray = _decode_gray(image_bytes)
    return _spatial_lbp_histogram(gray), _quality(gray, True), True


def compare(a: list[float], b: list[float]) -> float:
    """Histogram intersection of two templates -> similarity in [0, 1]."""
    va, vb = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if va.shape != vb.shape or va.size == 0:
        return 0.0
    return max(0.0, min(1.0, float(np.minimum(va, vb).sum())))
