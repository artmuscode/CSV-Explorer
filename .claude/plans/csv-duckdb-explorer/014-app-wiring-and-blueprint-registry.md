# Task 014: App Wiring — Service Container, Startup Scan, Blueprint Registry

**Status**: completed
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
- [x] `test_create_app_does_not_open_duckdb_until_services_are_used` (after `make_app()`, `DUCKDB_PATH` doesn't exist yet)
- [x] `test_get_services_builds_container_once_and_caches_it`
- [x] `test_services_ensure_metadata_schema_exists`
- [x] `test_first_service_use_scans_csv_dir_when_scan_on_startup_enabled`
- [x] `test_startup_scan_skipped_when_disabled`
- [x] `test_startup_scan_logs_and_continues_when_files_fail`
- [x] `test_fake_network_fixture_routes_url_ingest_through_fake_session`
- [x] `test_create_app_registers_main_ingest_and_datasets_blueprints`
- [x] `test_all_final_endpoint_names_resolve_with_url_for`

## Acceptance Criteria
- All requirements have passing tests
- If you can run a background process: `uv run flask --app app run --debug --port 5055` starts, `curl -s -o /dev/null -w '%{http_code}' localhost:5055/` returns `501` (the stub), and the log has **no DuckDB lock error**. Stop the server afterwards. If you can't run it, write "manual check pending for user" in Implementation Notes. Don't mark the task blocked over this.
- Code follows code standards

## Implementation Notes
- `app/container.py` adds `ServiceContainer` (a `@dataclass(slots=True)` with `connection`, `repository`,
  `metadata`, `url_guard`, `downloader`, `ingest_service`, `url_ingest_service`, `dataset_service`, and
  `close()`), `build_container(config, *, session=None, resolver=None)`, `init_services(app)`,
  `get_services(app)`, `set_services(app, container)`, `current_services()`, and a private
  `_ServiceHolder` (container + `threading.Lock`) stored at `app.extensions["csv_explorer"]`.
  `get_services` builds the container under the holder's lock on first call, runs the startup scan
  (`ingest_service.scan_folder()`) when `SCAN_ON_STARTUP` is set — logging each `ScanResult.errors`
  entry with `app.logger.warning` and any unexpected exception with `app.logger.exception` so a bad
  scan never crashes the app — then caches and returns the container. Also added `close_services(app)`,
  a small helper used by test teardown so tests never need to reach into the holder's private fields.
- `app/blueprints/{main,ingest,datasets}.py` register the seven final endpoints/URLs as one-line
  `"Not implemented", 501` stubs (`main.index` GET `/`, `main.delete` POST `/datasets/<name>/delete`,
  `ingest.upload` POST `/ingest/upload`, `ingest.from_url` POST `/ingest/url`, `ingest.scan` POST
  `/ingest/scan`, `datasets.show` GET `/datasets/<name>`, `datasets.rows` GET `/api/datasets/<name>/rows`).
  `app/blueprints/__init__.py` exposes `register_blueprints(app)`.
- `app/__init__.py`: `create_app` now calls, in order, `init_services(app)` (opens nothing) →
  `register_error_handlers(app)` → `register_same_origin_check(app)` → `register_blueprints(app)`.
  Config/`CSV_DIR`/`DUCKDB_PATH` setup is unchanged.
- `tests/conftest.py`: `make_app` tracks every app it builds and calls `close_services(app)` on each at
  teardown; `app`/`client` are unchanged in shape. Added `services(app)` → `get_services(app)`,
  `write_csv(app)` (factory writing str/bytes into `CSV_DIR`), `ingested(services, write_csv)` (factory
  that writes then calls `ingest_service.ingest_file(...).dataset`), and `fake_network(app)`, which builds
  a container via `build_container(app.config, session=FakeSession(routes), resolver=static_resolver(dns))`
  and installs it with `set_services` — `routes`/`dns` are shared by reference on the returned
  `FakeNetwork` object so tests can add entries afterwards.
- All 9 new tests passed on first run once the wiring/container/blueprints were written together (this
  was an integration/wiring task assembling already-implemented, already-tested collaborators from
  tasks 001–013/020–022, so RED/GREEN was validated as a whole rather than per-requirement-with-a-
  necessarily-failing-intermediate-state).
- Full suite: `uv run pytest -n auto` → 149 passed (140 existing + 9 new). `uv run ruff check .` and
  `uv run ruff format --check .` both clean. Coverage 94.72% (`--cov-fail-under=80` passes).
- Manual dev-server check performed (not just "pending"): started
  `CSV_EXPLORER_CSV_DIR=/tmp/... CSV_EXPLORER_DUCKDB_PATH=/tmp/... uv run flask --app app run --debug --port 5055`
  in the background against a scratch `/tmp` directory (never `data/`); `curl -s -o /dev/null -w '%{http_code}' localhost:5055/`
  returned `501`; the log showed the reloader restarting and serving the request with no DuckDB lock
  error. Server was killed and the scratch directory removed afterward.
