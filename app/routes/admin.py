"""Admin panel: users, transactions, system logs, matching controls, and the
performance-metrics dashboard.
"""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import admin_required
from ..models import AuthAttempt, Merchant, SystemLog, Transaction, User
from ..mocks import settings as match_settings
from ..services import metrics as metrics_service

bp = Blueprint("admin", __name__)


@bp.route("/")
@admin_required
def dashboard():
    users = User.query.order_by(User.created_at).all()
    merchants = Merchant.query.order_by(Merchant.name).all()
    txns = Transaction.query.order_by(Transaction.created_at.desc()).limit(25).all()
    attempts = (AuthAttempt.query.filter_by(attempt_type="live")
                .order_by(AuthAttempt.created_at.desc()).limit(25).all())
    logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(40).all()
    history = metrics_service.compute()
    return render_template(
        "admin.html", users=users, merchants=merchants, transactions=txns,
        attempts=attempts, logs=logs, settings=match_settings, history=history,
    )


@bp.post("/settings")
@admin_required
def update_settings():
    """Adjust the runtime matching thresholds."""
    match_settings["match_threshold"] = _as_float(
        request.form.get("match_threshold"), match_settings["match_threshold"], 0.0, 1.0)
    match_settings["liveness_min_quality"] = _as_float(
        request.form.get("liveness_min_quality"), match_settings["liveness_min_quality"], 0.0, 1.0)
    flash("Matching settings updated.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.post("/metrics/run")
@admin_required
def run_metrics():
    result = metrics_service.compute()
    if "error" in result:
        flash(result["error"], "error")
    else:
        flash(
            f"Metrics: FAR={result['FAR']:.3f}, FRR={result['FRR']:.3f}, "
            f"accuracy={result['accuracy']:.3f} at threshold {result['threshold']:.2f}",
            "success",
        )
    return render_template("metrics.html", result=result)


def _as_float(raw, default, lo, hi):
    try:
        return max(lo, min(hi, float(raw)))
    except (TypeError, ValueError):
        return default
