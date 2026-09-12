"""Flask application factory for the CSV Explorer app."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from flask import Flask

from app.blueprints import register_blueprints
from app.config import Config
from app.container import init_services
from app.errors import register_error_handlers
from app.security import register_same_origin_check


def create_app(config_class: type = Config, overrides: Mapping[str, Any] | None = None) -> Flask:
    """Build and configure the Flask application.

    Configuration is applied in order: the config class, `CSV_EXPLORER_`
    prefixed environment variables, then explicit `overrides`. `CSV_DIR`
    and `DUCKDB_PATH` are coerced to `Path` and created if missing.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config.from_prefixed_env("CSV_EXPLORER")
    if overrides:
        app.config.from_mapping(overrides)

    app.config["CSV_DIR"] = Path(app.config["CSV_DIR"])
    app.config["DUCKDB_PATH"] = Path(app.config["DUCKDB_PATH"])

    app.config["CSV_DIR"].mkdir(parents=True, exist_ok=True)
    app.config["DUCKDB_PATH"].parent.mkdir(parents=True, exist_ok=True)

    init_services(app)
    register_error_handlers(app)
    register_same_origin_check(app)
    register_blueprints(app)

    return app
