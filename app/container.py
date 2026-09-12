"""Lazy service container for the CSV Explorer app.

`create_app` never opens DuckDB itself. Flask's development server loads the
app in both the reloader's parent process and the child that actually serves
requests (`flask run` calls `info.load_app()` before `run_simple`), so eager
construction would make the parent hold DuckDB's exclusive file lock and the
child would fail with `IO Error: Could not set lock on file`. Building the
container on first use means the reloader parent, which never handles a
request, never touches the database.
"""

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import requests
from flask import Flask, current_app

from app.repositories.duckdb_repository import DuckDBRepository
from app.repositories.metadata_repository import MetadataRepository
from app.services.csv_downloader import CsvDownloader
from app.services.csv_ingest_service import CsvIngestService
from app.services.dataset_service import DatasetService
from app.services.url_guard import UrlGuard
from app.services.url_ingest_service import UrlIngestService

_EXTENSION_KEY = "csv_explorer"


@dataclass(slots=True)
class ServiceContainer:
    """Holds the one instance of every repository and service for a process."""

    connection: duckdb.DuckDBPyConnection
    repository: DuckDBRepository
    metadata: MetadataRepository
    url_guard: UrlGuard
    downloader: CsvDownloader
    ingest_service: CsvIngestService
    url_ingest_service: UrlIngestService
    dataset_service: DatasetService

    def close(self) -> None:
        """Close the DuckDB connection backing every service in this container."""
        self.connection.close()


@dataclass(slots=True)
class _ServiceHolder:
    """The mutable, per-app slot that `ServiceContainer` gets built into."""

    container: ServiceContainer | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


def build_container(
    config: Mapping[str, Any],
    *,
    session: requests.Session | None = None,
    resolver: Callable[[str], list[str]] | None = None,
) -> ServiceContainer:
    """Build a fully wired `ServiceContainer` from `config`.

    `session` and `resolver` are the only seam tests use to fake the
    network: they're threaded through to `CsvDownloader` and `UrlGuard`
    respectively.
    """
    csv_dir: Path = config["CSV_DIR"]
    connection = duckdb.connect(str(config["DUCKDB_PATH"]))

    repository = DuckDBRepository(connection)
    metadata = MetadataRepository(connection)
    metadata.ensure_schema()

    url_guard = UrlGuard(config["ALLOW_PRIVATE_URLS"], resolver=resolver)
    downloader = CsvDownloader(
        csv_dir,
        url_guard,
        config["MAX_DOWNLOAD_BYTES"],
        config["DOWNLOAD_TIMEOUT"],
        session=session,
    )
    ingest_service = CsvIngestService(repository, metadata, csv_dir)
    url_ingest_service = UrlIngestService(downloader, ingest_service)
    dataset_service = DatasetService(
        repository, metadata, config["PAGE_SIZE"], config["MAX_PAGE_SIZE"]
    )

    return ServiceContainer(
        connection=connection,
        repository=repository,
        metadata=metadata,
        url_guard=url_guard,
        downloader=downloader,
        ingest_service=ingest_service,
        url_ingest_service=url_ingest_service,
        dataset_service=dataset_service,
    )


def init_services(app: Flask) -> None:
    """Register an empty service holder on `app`. Opens nothing.

    The container is built lazily by `get_services` on first use.
    """
    app.extensions[_EXTENSION_KEY] = _ServiceHolder()


def get_services(app: Flask) -> ServiceContainer:
    """Return `app`'s `ServiceContainer`, building it on first use.

    The first call builds the container (opening the DuckDB connection,
    ensuring the metadata schema exists) and, if `SCAN_ON_STARTUP` is
    enabled, scans the CSV drop folder. "Startup scan" therefore really
    means "on first use in the serving process", which in practice is the
    first page load, not app construction. Later calls return the cached
    instance.
    """
    holder: _ServiceHolder = app.extensions[_EXTENSION_KEY]
    if holder.container is not None:
        return holder.container

    with holder.lock:
        if holder.container is None:
            container = build_container(app.config)
            if app.config.get("SCAN_ON_STARTUP"):
                _run_startup_scan(app, container)
            holder.container = container

    return holder.container


def set_services(app: Flask, container: ServiceContainer) -> None:
    """Install a pre-built `container` on `app`. No startup scan runs.

    Used by tests to inject fakes (a fake network session/resolver) before
    any route touches the services.
    """
    holder: _ServiceHolder = app.extensions[_EXTENSION_KEY]
    holder.container = container


def close_services(app: Flask) -> None:
    """Close and clear `app`'s container if one was built.

    Safe to call even if no container was ever built; used by test teardown
    so every test leaves the DuckDB connection it opened closed.
    """
    holder: _ServiceHolder | None = app.extensions.get(_EXTENSION_KEY)
    if holder is None or holder.container is None:
        return
    holder.container.close()
    holder.container = None


def current_services() -> ServiceContainer:
    """Return the current app's `ServiceContainer`, building it if needed."""
    return get_services(current_app._get_current_object())


def _run_startup_scan(app: Flask, container: ServiceContainer) -> None:
    try:
        result = container.ingest_service.scan_folder()
    except Exception:
        app.logger.exception("Unexpected error during startup CSV scan")
        return

    for filename, message in result.errors.items():
        app.logger.warning("Startup scan skipped %s: %s", filename, message)
