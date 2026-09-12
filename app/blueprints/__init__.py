"""Blueprint registration for the CSV Explorer app."""

from flask import Flask

from app.blueprints.datasets import bp as datasets_bp
from app.blueprints.ingest import bp as ingest_bp
from app.blueprints.main import bp as main_bp


def register_blueprints(app: Flask) -> None:
    """Register the main, ingest, and datasets blueprints on `app`."""
    app.register_blueprint(main_bp)
    app.register_blueprint(ingest_bp)
    app.register_blueprint(datasets_bp)
