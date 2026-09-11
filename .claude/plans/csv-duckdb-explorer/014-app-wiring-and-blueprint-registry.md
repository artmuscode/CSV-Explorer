# Task 014: App Wiring — Service Container, Startup Scan, Blueprint Registry

**Status**: pending
**Depends on**: 001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 012, 013, 020, 021, 022
**Retry count**: 0

## Description
Wire everything together. `create_app` registers a **lazily built** `ServiceContainer`: the first time services are used in a process, it opens the DuckDB connection, builds the repositories and services, makes sure the metadata schema exists, and optionally scans the drop folder. `create_app` also registers the three blueprints as stubs, so tasks 015–017 can fill them in parallel, and adds shared test fixtures, including a fake network.

## Context
- Related files (new):
  - `app/container.py`
  - `app/blueprints/__init__.py` (`register_blueprints(app)`)
  - stub blueprints `app/blueprints/main.py` (`bp = Blueprint("main", __name__)`), `app/blueprints/ingest.py` (`url_prefix="/ingest"`) and `app/blueprints/datasets.py`
  - `tests/integration/test_app_wiring.py`
- Related files (modify): `app/__init__.py`, `tests/conftest.py`

### Why lazy (critical)
Flask 3.x `flask run` loads the app in **both** the reloader parent process and the serving child (`flask/cli.py::run_command` calls `info.load_app()` before `run_simple`). If `create_app` opened `data/app.duckdb` eagerly, the parent would hold DuckDB's exclusive file lock and the child would crash with `IO Error: Could not set lock on file`. `uv run flask --app app run --debug` is the documented dev command, so it would fail every time. The earlier idea of skipping the build when `debug` is on and `WERKZEUG_RUN_MAIN` is unset also breaks `flask run --debug --no-reload`, where that same process serves requests. Building on first use avoids both problems, because the reloader parent never handles a request.

### `app/container.py`
- `ServiceContainer`: a `@dataclass(slots=True)` with `connection`, `repository`, `metadata`, `url_guard`, `downloader`, `ingest_service`, `url_ingest_service` and `dataset_service`, plus `close() -> None`, which closes the connection.
- `build_container(config: Mapping[str, Any], *, session: requests.Session | None = None, resolver: Callable[[str], list[str]] | None = None) -> ServiceContainer`:
  - connection: `duckdb.connect(str(DUCKDB_PATH))`
  - `DuckDBRepository(conn)`, `MetadataRepository(conn)` followed by `ensure_schema()`
  - `UrlGuard(ALLOW_PRIVATE_URLS, resolver=resolver)`
  - `CsvDownloader(CSV_DIR, guard, MAX_DOWNLOAD_BYTES, DOWNLOAD_TIMEOUT, session=session)`
  - `CsvIngestService(repo, metadata, CSV_DIR)`. It takes no downloader; URL ingest is the separate `UrlIngestService` (task 021).
  - `UrlIngestService(downloader, ingest_service)`
  - `DatasetService(repo, metadata, PAGE_SIZE, MAX_PAGE_SIZE)`
  - The `session` and `resolver` keyword arguments are the **only** seam integration tests use to fake the network. Don't make tests reach into private attributes such as `url_ingest_service._downloader`.
- `create_app` already calls `register_same_origin_check(app)` (task 022). Keep that call when editing `app/__init__.py`.
- `init_services(app) -> None`: stores a small holder (the container or `None`, plus a `threading.Lock`) at `app.extensions["csv_explorer"]`. It opens **nothing**.
- `get_services(app) -> ServiceContainer`: on first call, under the lock, runs `build_container(app.config)`. Then, if `SCAN_ON_STARTUP` is set, it runs `ingest_service.scan_folder()`, logging each entry of `ScanResult.errors` with `app.logger.warning` and catching and logging (`app.logger.exception`) any unexpected exception so the scan never crashes the app. It caches and returns the container, so later calls return the same instance.
- `set_services(app, container) -> None`: installs a pre-built container (for tests). No startup scan runs.
- `current_services() -> ServiceContainer`: `get_services(current_app._get_current_object())`.
- "Startup scan" therefore means "on first use in the serving process", which in practice is the first page load. Write this in the docstring. Task 019 documents it in the README.

### `create_app` order
config (from task 001) → `init_services(app)` → `register_error_handlers(app)` (already added in 004) → `register_same_origin_check(app)` (already added in 022) → `register_blueprints(app)`. Keep the connection for the process lifetime and don't close it on request teardown.

### Stub routes (required)
Tasks 015, 016 and 017 run in parallel, and each owns exactly one blueprint module. Create every endpoint now as a one-line stub returning `"Not implemented", 501`, using the **final endpoint names and URLs**, so `url_for` resolves everywhere:
- `main.index` → `GET /`
- `main.delete` → `POST /datasets/<name>/delete`
- `ingest.upload` → `POST /ingest/upload`
- `ingest.from_url` → `POST /ingest/url`
- `ingest.scan` → `POST /ingest/scan`
- `datasets.show` → `GET /datasets/<name>`
- `datasets.rows` → `GET /api/datasets/<name>/rows`

### `tests/conftest.py` additions
Keep `make_app` / `app` / `client` from task 001.
- Change `app` (and apps created through `make_app`) to close their container at teardown if one was built: a yield fixture that tracks the created apps and calls `container.close()`. Without this, every integration test leaves an open DuckDB instance, with its own buffer pool and worker threads, alive in the xdist worker.
- `services(app)` → `get_services(app)`
- `write_csv(app)` → a factory `(filename, text_or_bytes) -> Path` that writes into `CSV_DIR`
- `ingested(services, write_csv)` → a factory `(filename, text) -> Dataset` that writes the file and calls `ingest_file`
- `fake_network(app)` → a `FakeNetwork` helper built on `tests/fakes.py` (task 010):
  - `routes: dict[str, FakeResponse | Exception]` and `dns: dict[str, list[str]]`. Unknown hosts resolve to a public IP by default.
  - On creation it calls `set_services(app, build_container(app.config, session=FakeSession(routes), resolver=static_resolver(dns)))`. The dicts are shared by reference, so tests can add routes afterwards.
  - Tasks 016 and 019 use this fixture for every URL-ingest test.

## Requirements (Test Descriptions)
- [ ] `test_create_app_does_not_open_duckdb_until_services_are_used` (after `make_app()`, `DUCKDB_PATH` doesn't exist yet)
- [ ] `test_get_services_builds_container_once_and_caches_it`
- [ ] `test_services_ensure_metadata_schema_exists`
- [ ] `test_first_service_use_scans_csv_dir_when_scan_on_startup_enabled`
- [ ] `test_startup_scan_skipped_when_disabled`
- [ ] `test_startup_scan_logs_and_continues_when_files_fail`
- [ ] `test_fake_network_fixture_routes_url_ingest_through_fake_session`
- [ ] `test_create_app_registers_main_ingest_and_datasets_blueprints`
- [ ] `test_all_final_endpoint_names_resolve_with_url_for`

## Acceptance Criteria
- All requirements have passing tests
- If you can run a background process: `uv run flask --app app run --debug --port 5055` starts, `curl -s -o /dev/null -w '%{http_code}' localhost:5055/` returns `501` (the stub), and the log has **no DuckDB lock error**. Stop the server afterwards. If you can't run it, write "manual check pending for user" in Implementation Notes. Don't mark the task blocked over this.
- Code follows code standards

## Implementation Notes
(Left blank - filled in by programmer during implementation)
