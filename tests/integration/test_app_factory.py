from pathlib import Path

from flask import Flask

from app import create_app
from app.config import TestConfig


def test_create_app_returns_flask_app_instance(app):
    assert isinstance(app, Flask)


def test_create_app_applies_test_config_testing_flag(app):
    assert app.config["TESTING"] is True


def test_create_app_applies_overrides_after_config_class(make_app):
    app = make_app(PAGE_SIZE=5)
    assert app.config["PAGE_SIZE"] == 5


def test_create_app_reads_csv_explorer_prefixed_environment_variables(monkeypatch, tmp_path):
    monkeypatch.setenv("CSV_EXPLORER_PAGE_SIZE", "7")
    app = create_app(
        TestConfig,
        overrides={"CSV_DIR": tmp_path / "csv", "DUCKDB_PATH": tmp_path / "test.duckdb"},
    )
    assert app.config["PAGE_SIZE"] == 7


def test_create_app_creates_csv_dir_when_missing(app):
    assert Path(app.config["CSV_DIR"]).is_dir()
