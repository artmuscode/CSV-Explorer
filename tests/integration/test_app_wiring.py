"""Integration tests for the lazy service container and blueprint registry."""

import logging
from pathlib import Path

from flask import url_for

from app.container import get_services
from tests.fakes import FakeResponse


def test_create_app_does_not_open_duckdb_until_services_are_used(make_app):
    app = make_app()

    assert not Path(app.config["DUCKDB_PATH"]).exists()


def test_get_services_builds_container_once_and_caches_it(app):
    first = get_services(app)
    second = get_services(app)

    assert first is second


def test_services_ensure_metadata_schema_exists(app):
    services = get_services(app)

    assert services.metadata.list_all() == []


def test_first_service_use_scans_csv_dir_when_scan_on_startup_enabled(make_app):
    app = make_app(SCAN_ON_STARTUP=True)
    (app.config["CSV_DIR"] / "people.csv").write_text("id,name\n1,Ada\n")

    services = get_services(app)

    assert services.metadata.get("people") is not None


def test_startup_scan_skipped_when_disabled(app):
    (app.config["CSV_DIR"] / "people.csv").write_text("id,name\n1,Ada\n")

    services = get_services(app)

    assert services.metadata.get("people") is None


def test_startup_scan_logs_and_continues_when_files_fail(make_app, caplog):
    app = make_app(SCAN_ON_STARTUP=True)
    csv_dir = app.config["CSV_DIR"]
    (csv_dir / "bad.csv").write_bytes(b"")
    (csv_dir / "good.csv").write_text("id\n1\n")

    with caplog.at_level(logging.WARNING):
        services = get_services(app)

    assert services.metadata.get("good") is not None
    assert services.metadata.get("bad") is None
    assert any("bad.csv" in record.message for record in caplog.records)


def test_fake_network_fixture_routes_url_ingest_through_fake_session(app, fake_network):
    fake_network.dns["example.com"] = ["93.184.216.34"]
    fake_network.routes["http://example.com/data.csv"] = FakeResponse(
        status_code=200,
        body=b"id,name\n1,Ada\n",
        headers={"Content-Type": "text/csv"},
    )

    services = get_services(app)
    result = services.url_ingest_service.ingest("http://example.com/data.csv")

    assert result.dataset.name == "data"


def test_create_app_registers_main_ingest_and_datasets_blueprints(app):
    assert set(app.blueprints) == {"main", "ingest", "datasets"}


def test_all_final_endpoint_names_resolve_with_url_for(app):
    with app.test_request_context():
        assert url_for("main.index") == "/"
        assert url_for("main.delete", name="foo") == "/datasets/foo/delete"
        assert url_for("ingest.upload") == "/ingest/upload"
        assert url_for("ingest.from_url") == "/ingest/url"
        assert url_for("ingest.scan") == "/ingest/scan"
        assert url_for("datasets.show", name="foo") == "/datasets/foo"
        assert url_for("datasets.rows", name="foo") == "/api/datasets/foo/rows"
