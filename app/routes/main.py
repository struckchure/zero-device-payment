"""Server-rendered pages: landing, auth, dashboard, enrolment, payment."""
from __future__ import annotations

import secrets

from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)

from .. import current_user, login_required, login_user, logout_user
from ..extensions import db
from ..models import BankAccount, Merchant, Transaction, User, log_event

bp = Blueprint("main", __name__)


def _new_account_number() -> str:
    return "ACC" + "".join(secrets.choice("0123456789") for _ in range(12))


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")

        error = None
        if not username or not email or not password:
            error = "Username, email and password are required."
        elif User.query.filter_by(username=username).first():
            error = "That username is already taken."
        elif User.query.filter_by(email=email).first():
            error = "That email is already registered."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."

        if error:
            flash(error, "error")
            return render_template("register.html", form=request.form)

        user = User(username=username, email=email, full_name=full_name)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # assign user.id

        # Open a bank account with a demo starting balance.
        db.session.add(BankAccount(
            account_number=_new_account_number(), balance=50000.0, user=user
        ))

        log_event("INFO", "account", f"Registered user {username}")
        db.session.commit()

        login_user(user)
        flash("Account created. Enrol your face and/or fingerprint to start paying.", "success")
        return redirect(url_for("main.enrol"))

    return render_template("register.html", form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash("Invalid username or password.", "error")
            return render_template("login.html", form=request.form)
        login_user(user)
        nxt = request.args.get("next") or url_for("main.dashboard")
        return redirect(nxt)
    return render_template("login.html", form={})


@bp.route("/logout")
def logout():
    logout_user()
    flash("Logged out.", "success")
    return redirect(url_for("main.index"))


@bp.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    txns = (Transaction.query.filter_by(user_id=user.id)
            .order_by(Transaction.created_at.desc()).limit(10).all())
    merchants = Merchant.query.order_by(Merchant.name).all()
    return render_template("dashboard.html", user=user, transactions=txns, merchants=merchants)


@bp.route("/enrol")
@login_required
def enrol():
    # Enrolment itself is performed by POST /api/enrol from captured images.
    return render_template("enrol.html", user=current_user())


@bp.route("/pay")
@login_required
def pay():
    user = current_user()
    merchants = Merchant.query.order_by(Merchant.name).all()
    return render_template("pay.html", user=user, merchants=merchants)
