"""Application factory + shared request helpers.

`create_app()` wires config, the database, the mock registry and blueprints.
"""
from __future__ import annotations

import functools
import os

from flask import Flask, g, jsonify, redirect, request, session, url_for

from .config import INSTANCE_DIR, Config
from .extensions import db
from .mocks import init_mocks


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Make sure the SQLite directory exists (avoids "unable to open database file").
    os.makedirs(INSTANCE_DIR, exist_ok=True)

    db.init_app(app)
    init_mocks(app.config)

    # Register blueprints.
    from .routes.main import bp as main_bp
    from .routes.api import bp as api_bp
    from .routes.admin import bp as admin_bp
    from .routes.merchant import bp as merchant_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(merchant_bp, url_prefix="/merchant")

    # Format a numeric amount as Naira with thousands separators, e.g. ₦47,500.00.
    @app.template_filter("naira")
    def naira(value):
        try:
            return "₦{:,.2f}".format(float(value))
        except (TypeError, ValueError):
            return value

    # Expose the current user / merchant to every template.
    @app.context_processor
    def inject_identity():
        return {"current_user": current_user(), "current_merchant": current_merchant()}

    return app


# --- Session / auth helpers ---------------------------------------------------


def current_user():
    """Return the logged-in User (cached per request) or None."""
    from .models import User

    if "user" not in g:
        uid = session.get("user_id")
        g.user = db.session.get(User, uid) if uid else None
    return g.user


def current_merchant():
    """Return the logged-in Merchant (cached per request) or None."""
    from .models import Merchant

    if "merchant" not in g:
        mid = session.get("merchant_id")
        g.merchant = db.session.get(Merchant, mid) if mid else None
    return g.merchant


def login_user(user) -> None:
    session.clear()
    session["user_id"] = user.id


def login_merchant(merchant) -> None:
    session.clear()
    session["merchant_id"] = merchant.id


def logout_user() -> None:
    session.clear()


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("main.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def merchant_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if current_merchant() is None:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Merchant authentication required"}), 401
            return redirect(url_for("merchant.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return redirect(url_for("main.login", next=request.path))
        if not user.is_admin:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Admin privileges required"}), 403
            return "Forbidden: admin only", 403
        return view(*args, **kwargs)

    return wrapped
