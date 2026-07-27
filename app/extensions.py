"""Shared Flask extension instances.

Isolated in their own module to avoid circular imports between the app factory
and the models/services.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
