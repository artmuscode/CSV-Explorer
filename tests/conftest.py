from pathlib import Path

import pytest
from flask import Flask

from app import create_app
from app.config import TestConfig
from app.container import build_container, close_services, get_services, set_services
from tests.fakes import FakeSession, static_resolver


@pytest.fixture
def make_app(tmp_path):
    """Return a factory that builds a Flask app configured for tests.

    Every call gets its own CSV directory and DuckDB path under tmp_path, so
    parallel test workers never collide on `data/`. Every app it builds gets
    its container closed at teardown, if one was ever built.
    """
    created: list[Flask] = []

    def _make_app(**overrides) -> Flask:
        app = create_app(
            TestConfig,
            overrides={
                "CSV_DIR": tmp_path / "csv",
                "DUCKDB_PATH": tmp_path / "test.duckdb",
                **overrides,
            },
        )
        created.append(app)
        return app

    yield _make_app

    for app in created:
        close_services(app)


@pytest.fixture
def app(make_app):
    return make_app()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def services(app):
    return get_services(app)


@pytest.fixture
def write_csv(app):
    """Return a factory that writes `filename` into `CSV_DIR` and returns its path."""

    def _write_csv(filename: str, content: str | bytes) -> Path:
        path = app.config["CSV_DIR"] / filename
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content)
        return path

    return _write_csv


@pytest.fixture
def ingested(services, write_csv):
    """Return a factory that writes a CSV and ingests it, returning its `Dataset`."""

    def _ingested(filename: str, text: str):
        path = write_csv(filename, text)
        return services.ingest_service.ingest_file(path).dataset

    return _ingested


class FakeNetwork:
    """A fake network fixture built on `FakeSession`/`static_resolver`.

    `routes` and `dns` are shared by reference with the container's
    `CsvDownloader`/`UrlGuard`, so tests can add routes and DNS entries
    after the fixture is created.
    """

    def __init__(self, routes: dict, dns: dict) -> None:
        self.routes = routes
        self.dns = dns


@pytest.fixture
def fake_network(app):
    routes: dict = {}
    dns: dict = {}
    container = build_container(
        app.config,
        session=FakeSession(routes),
        resolver=static_resolver(dns),
    )
    set_services(app, container)
    return FakeNetwork(routes, dns)
