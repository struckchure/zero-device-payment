"""Merchant-facing pages: login and a dashboard to collect payments by account ID."""
from __future__ import annotations

from flask import (Blueprint, flash, redirect, render_template, request,
                   url_for)

from .. import current_merchant, login_merchant, logout_user, merchant_required
from ..models import Merchant, Transaction, User

bp = Blueprint("merchant", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        merchant = Merchant.query.filter_by(username=username).first()
        if merchant is None or not merchant.check_password(password):
            flash("Invalid merchant username or password.", "error")
            return render_template("merchant_login.html", form=request.form)
        login_merchant(merchant)
        return redirect(request.args.get("next") or url_for("merchant.dashboard"))
    return render_template("merchant_login.html", form={})


@bp.route("/logout")
def logout():
    logout_user()  # clears the whole session (user or merchant)
    flash("Logged out.", "success")
    return redirect(url_for("merchant.login"))


@bp.route("/dashboard")
@merchant_required
def dashboard():
    merchant = current_merchant()
    txns = (Transaction.query.filter_by(merchant_id=merchant.id)
            .order_by(Transaction.created_at.desc()).limit(15).all())
    # Demo helper: list customer account numbers so testers know what to charge.
    customers = [u for u in User.query.order_by(User.username).all()
                 if u.account and not u.is_admin]
    return render_template("merchant_dashboard.html", merchant=merchant,
                           transactions=txns, customers=customers)
