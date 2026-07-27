"""Performance-metrics module (real templates, no simulation).

Computes biometric accuracy metrics by comparing the *real* enrolled templates
against each other:

  * genuine comparison  = a user's template against itself (exact self-match).
  * impostor comparison = one user's template against every other user's.

From the resulting similarity scores and the current match threshold we report:

  * FAR (False Acceptance Rate) = impostor pairs scoring >= threshold / all impostor
  * FRR (False Rejection Rate)  = genuine pairs scoring <  threshold / all genuine
  * Accuracy = correct decisions / all decisions
  * Average comparison time (ms)

Because only one template is stored per user/modality, genuine self-matches are
exact (FRR is 0); the informative figure is impostor separation (FAR), which
needs at least two enrolled users of the same modality.
"""
from __future__ import annotations

import time

from ..biometrics_engine import compare
from ..models import User
from ..mocks import settings as mock_settings
from . import biometrics

MODALITIES = ("face", "fingerprint")


def compute() -> dict:
    """Return a metrics summary from pairwise comparison of enrolled templates."""
    users = User.query.all()
    threshold = float(mock_settings.get("match_threshold", 0.55))

    genuine_scores: list[float] = []
    impostor_scores: list[float] = []
    enrolled_ids: set[int] = set()

    started = time.perf_counter()
    n_compare = 0
    for modality in MODALITIES:
        templates = []
        for u in users:
            emb = biometrics.get_enrolled_embedding(u, modality)
            if emb:
                templates.append(emb)
                enrolled_ids.add(u.id)
        for i, ti in enumerate(templates):
            genuine_scores.append(compare(ti, ti))
            n_compare += 1
            for j, tj in enumerate(templates):
                if i != j:
                    impostor_scores.append(compare(ti, tj))
                    n_compare += 1
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    if not enrolled_ids:
        return {"error": "No enrolled biometric templates yet — enrol a user first."}

    false_accepts = sum(1 for s in impostor_scores if s >= threshold)
    false_rejects = sum(1 for s in genuine_scores if s < threshold)
    n_gen, n_imp = len(genuine_scores), len(impostor_scores)
    total = n_gen + n_imp
    correct = (n_gen - false_rejects) + (n_imp - false_accepts)

    return {
        "users_tested": len(enrolled_ids),
        "genuine_attempts": n_gen,
        "impostor_attempts": n_imp,
        "true_accepts": n_gen - false_rejects,
        "true_rejects": n_imp - false_accepts,
        "false_accepts": false_accepts,
        "false_rejects": false_rejects,
        "threshold": round(threshold, 4),
        "FAR": _rate(false_accepts, n_imp),
        "FRR": _rate(false_rejects, n_gen),
        "accuracy": _rate(correct, total),
        "avg_genuine_score": _avg(genuine_scores),
        "avg_impostor_score": _avg(impostor_scores),
        "avg_response_ms": round(elapsed_ms / n_compare, 4) if n_compare else 0.0,
        "note": None if n_imp else "Enrol a second user to measure FAR (impostor separation).",
    }


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0
