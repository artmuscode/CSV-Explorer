# Plan: CSV → DuckDB Explorer

## Created
2026-09-10

## Status
completed

## Objective
Turn the Flask starter into a layered OOP app that ingests CSVs (drop folder, browser upload, or URL download) into DuckDB tables and shows each dataset as a server-side paginated, searchable, filterable, sortable table, built with Alpine.js and Tailwind CSS 4.

## Related Issues
none

## Discovery Notes
- **Greenfield.** The existing code is a starter `main.py` with a module-level `app` and `/` + `/about` routes. It points `static_folder` at a folder that doesn't exist, and `templates/base.html` loads `js/script.js`, which doesn't match `assets/js/scripts.js`. There are also trivial templates (`base`, `header`, `footer`, `index`, `about`). All of this is replaced by the `app/` package and removed in task 001. `main.py` isn't ruff-formatted, so keeping it until task 004 would fail task 001's `ruff format --check`.
- The existing `venv/` only has Flask 3.1.2, and there's no dependency manifest. The project is moving to **uv + `pyproject.toml`**. `uv` must be installed on the machine (`brew install uv`) before execution.
- The Tailwind v4 **standalone CLI** binary (macOS arm64) is downloaded to `bin/tailwindcss` (gitignored).
- Project config (`CLAUDE.md`, `.claude/*.md`) defines the layering: blueprints → services → repositories → DuckDB.
- Decisions resolved during clarification:
  - **Re-ingest** of a same-named CSV **replaces** the table (`CREATE OR REPLACE`) and updates its metadata row.
  - **Drop folder** is scanned **on app startup** (`SCAN_ON_STARTUP`) and from a **"Scan folder" button**. Only new or changed files are ingested, judged by file size + mtime.
  - **Table UI**: global search, a per-column "contains" filter, click-to-sort headers. All of it runs **server-side**.
  - **URL ingest** blocks private/loopback/link-local addresses **unless `ALLOW_PRIVATE_URLS=True`**. Every redirect hop is re-validated.
- Post-review decisions (from the user):
  - **Remember deletions**: delete drops the table and sets `_datasets.deleted_at`, keeping the CSV file. The scan skips a deleted file while it's unchanged, and re-ingesting clears the marker (tasks 002, 007, 011, 012, 013).
  - **Same-origin check** on POST/PUT/PATCH/DELETE, plus a `SameSite=Lax` session cookie (task 022)
  - **`data/csv/` gitignored** (with `.gitkeep`)
  - **Latin-1 fallback** when UTF-8 decoding fails (task 005). The canonical unloadable test CSV is therefore a **0-byte file**.
  - **Hardening**: cap `page` at 1,000,000 (013); reject 0-byte CSVs and glob characters in file names (005, 012); filter `information_schema` by `table_schema = 'main'` (005); pin the Tailwind release in `.tailwind-version` (004); handle a user column named `rowid` (006)
  - **SRI** hash on the pinned Alpine CDN script (004)
  - **Split** the downloader (010 → 010 + 020) and move URL ingest into its own `UrlIngestService` (012 → 012 scan + 021 URL)
- Defaults accepted:
  - a `_datasets` metadata table in DuckDB
  - browser upload in addition to the drop folder
  - a delete-dataset action that drops the table but keeps the CSV file (see "remember deletions" above)
  - page size 25, with a 10/25/50/100 selector and max 100
  - `requests`, streamed, 30s timeout, 50 MB cap
  - no auth (single-user local tool)

## Scope

### In Scope
- `pyproject.toml` (uv), ruff + pytest config, `Config`/`TestConfig`, and a `create_app` factory that reads env overrides via the `CSV_EXPLORER_` prefix
- Dataclass DTOs (`Column`, `Dataset`, `RowQuery`, `Page`, `IngestResult`, `ScanResult`) and domain exceptions
- `DuckDBRepository` (tables, paged/filtered/sorted reads), `RowQueryBuilder` (safe SQL) and `MetadataRepository` (`_datasets`)
- `UrlGuard` (SSRF protection), `CsvDownloader` (streamed, capped, redirect-safe), `CsvIngestService` (file, upload, folder scan), `UrlIngestService` (URL) and `DatasetService`
- Same-origin protection for state-changing requests (CSRF) and a `SameSite=Lax` session cookie
- Blueprints: `main` (dataset list + delete), `ingest` (upload / URL / scan), `datasets` (table page + JSON rows API)
- Tailwind v4 layout, error pages, flash messages, and an Alpine.js `datasetTable` component
- README rewrite and end-to-end integration tests

### Out of Scope
- Authentication, multi-user support, token-based CSRF (the same-origin check covers the local single-user threat model)
- Live filesystem watcher (watchdog)
- Type-aware filters (numeric/date ranges), exporting data, editing rows
- Appending to or versioning datasets (re-ingest always replaces)
- Recursive folder scanning, non-CSV formats (Excel, Parquet, JSON)
- Syncing filter state into the browser URL; JS unit-test runner (the Alpine component is covered by integration tests plus a manual browser check)

## Success Criteria
- [ ] Dropping a CSV into `data/csv/` and restarting (or clicking "Scan folder") creates a dataset
- [ ] Uploading a CSV, or submitting a public CSV URL, creates a dataset and redirects to its table
- [ ] Submitting `http://127.0.0.1/...` or `http://169.254.169.254/...` is rejected, unless `ALLOW_PRIVATE_URLS` is on
- [ ] The table view paginates server-side, and search, column filters and sort apply across the whole dataset
- [ ] CSV header or cell content can't inject HTML, JS or SQL (covered by tests)
- [ ] Re-ingesting a same-named CSV replaces the table's rows
- [ ] A deleted dataset doesn't reappear after a restart or scan unless its file changes
- [ ] A cross-origin POST (e.g. a hidden form on another site) is rejected with a 403
- [ ] `uv run pytest -n auto --cov=app --cov-fail-under=80` passes
- [ ] `uv run ruff check .` and `uv run ruff format --check .` are clean
- [ ] Code follows project standards (`.claude/code-standards.md`)

## Task Overview
| Task | Description | Depends On | Status |
|------|-------------|------------|--------|
| 001 | Bootstrap tooling, config & app factory skeleton, `make_app` fixture, legacy cleanup | - | completed |
| 002 | Domain models (dataclass DTOs) & exceptions | 001 | completed |
| 003 | SQL identifier & table-naming helpers | 001 | completed |
| 004 | Frontend foundation: Tailwind, base layout, error pages | 001 | completed |
| 005 | DuckDBRepository: table operations | 001, 002, 003 | completed |
| 006 | RowQueryBuilder: search / filter / sort SQL | 001, 002, 003 | completed |
| 007 | MetadataRepository (`_datasets`) | 001, 002, 003 | completed |
| 008 | UrlGuard (SSRF protection) | 001, 002 | completed |
| 009 | DuckDBRepository.fetch_page | 001, 002, 003, 005, 006 | completed |
| 010 | CsvDownloader core: staging, redirects, filenames + shared `tests/fakes.py` | 001, 002, 008 | completed |
| 011 | CsvIngestService: files & uploads (public `install_and_ingest` with rollback) | 001, 002, 003, 005, 007 | completed |
| 012 | CsvIngestService: folder scan (deletion-aware, collisions, glob chars) | 001, 002, 003, 005, 007, 011 | completed |
| 013 | DatasetService (deletion marker, page cap) | 001, 002, 003, 005, 006, 007, 009 | completed |
| 014 | App wiring: lazy service container, startup scan, blueprint registry, `fake_network` fixture | 001–013, 020–022 | completed |
| 015 | Main blueprint: dataset list & delete | 001–014, 020–022 | completed |
| 016 | Ingest blueprint: upload, URL, scan | 001–014, 020–022 | completed |
| 017 | Datasets blueprint: table page & rows JSON API | 001–014, 020–022 | completed |
| 018 | Alpine.js datasetTable component | 001–014, 017, 020–022 | completed |
| 019 | End-to-end tests, README & final verification | 001–018, 020–022 | completed |
| 020 | CsvDownloader: limits, deadlines & failure cleanup | 001, 002, 008, 010 | completed |
| 021 | UrlIngestService (URL → staged download → `install_and_ingest`) | 001, 002, 003, 005, 007, 010, 011 | completed |
| 022 | Same-origin protection for POSTs (CSRF) + SameSite cookie | 001, 004 | completed |

Task numbers 020–022 were added after the review. Execution order follows **Depends on**, not the number. Batches: B1 001 · B2 002, 003, 004 · B3 005, 006, 007, 008, 022 · B4 009, 010, 011 · B5 012, 013, 020, 021 · B6 014 · B7 015, 016, 017 · B8 018 · B9 019.

## Architecture Notes
- **Layering**: blueprints → services → repositories → DuckDB. SQL lives only in `app/repositories/`. Services and repositories never import Flask. `werkzeug.utils.secure_filename` is allowed because it isn't Flask.
- **Connection**: one `duckdb.connect(DUCKDB_PATH)` per app, created in `create_app`. Every repository method runs on `self._conn.cursor()` so threaded requests are safe.
- **Container (lazy)**: `ServiceContainer` (dataclass) holds the connection, repositories and services. `create_app` only registers a holder at `app.extensions["csv_explorer"]`. The container, the DuckDB connection and the startup scan are built on first use (`get_services(app)` / `current_services()`, guarded by a lock). This is required: `flask run --debug` loads the app in both the reloader parent and the child, and an eager connection in the parent holds DuckDB's exclusive file lock, so the child can't open the database. `build_container(config, *, session=None, resolver=None)` is the only network seam for tests (see the `fake_network` fixture in task 014).
- **Connection shorthand**: wherever this plan says the connection is created "in `create_app`", read it as "on first use of services in the serving process".
- **Blueprint registry**: task 014 creates `app/blueprints/__init__.py::register_blueprints`, plus `main`/`ingest`/`datasets` blueprints where **every final endpoint exists as a 501 stub**. Tasks 015–017 each own exactly one blueprint module and its templates, so they run in parallel without touching shared files.
- **Metadata**: the `_datasets` table has columns `name` PK, `original_filename`, `source`, `source_url`, `row_count`, `file_size`, `file_mtime`, `ingested_at`, `deleted_at` (the deletion marker; `list_all` hides marked rows, and `get` returns them so the scan can compare file size and mtime). User tables can never start with `_`, because `table_name_from_filename` strips leading underscores, so they can't collide with it.
- **Stable pagination**: default `ORDER BY rowid`. When the user sorts, it becomes `ORDER BY "col" <dir> NULLS LAST, rowid`.
- **Filtering**: `CAST("col" AS VARCHAR) ILIKE ? ESCAPE '\'`, with `%`, `_` and `\` escaped in user input. Global search ORs across all columns and column filters are ANDed together. Unknown filter or sort columns raise `InvalidQueryError`.
- **JSON safety**: `fetch_page` converts date, time and datetime values to ISO strings, `Decimal`/`timedelta`/`UUID` to `str`, and non-finite floats (`NaN`/`Infinity`) to strings. Otherwise `jsonify` would emit invalid JSON tokens that break `response.json()` and `JSON.parse`.
- **XSS**: column names and cells come from users. The page passes them to Alpine only through `{{ ...|tojson }}` in a `<script type="application/json">` block and renders them with `x-text` / `x-for`. They are **never** interpolated into Alpine expressions or attributes. The component is mounted as `x-data="datasetTable"` and reads its config from `data-rows-url` / `data-max-page-size`. **Never put `|tojson` inside a double-quoted attribute**: Flask's `tojson` doesn't escape `"`.
- **Timestamps**: `Dataset.ingested_at` is tz-aware UTC everywhere. `MetadataRepository` stores naive UTC in `TIMESTAMP` and re-attaches UTC when it reads.
- **File installs are transactional**: uploads and URL downloads are staged as hidden `.{uuid}.part` files. `CsvIngestService.install_and_ingest` (public; also used by `UrlIngestService`) backs up any existing same-named file, moves the staged file into place, ingests it, and restores the backup on failure. A failed re-ingest therefore never destroys the user's previous CSV. `CsvDownloader` returns `DownloadedFile(path, filename)` and never writes the final name itself.
- **Canonical unloadable CSV** for tests: a **0-byte file** (`b""`), rejected deterministically by `create_table_from_csv`'s empty check (task 005). Invalid UTF-8 is **no longer** a failing sample, because the Latin-1 fallback loads it.
- **URL ingest is its own service**: `UrlIngestService(downloader, ingest_service)` calls `CsvIngestService.install_and_ingest` (public). `CsvIngestService` has no downloader dependency.
- **CSRF**: `app/security.py::register_same_origin_check` rejects POST/PUT/PATCH/DELETE whose `Origin` (or `Referer`) isn't this app, and allows requests that carry neither (curl, the test client).
- **Flash size**: flashed messages live in Flask's cookie session (about 4 KB). DuckDB errors are cut to one line of 200 characters or fewer (005), and the ingest blueprint truncates flashes and caps per-file scan errors at 5 (016).

## Parallel Batch Rules
Tasks in the same batch share one working tree:
- **Scope your checks.** While a batch is running, run only your own test files (`uv run pytest tests/unit/repositories/test_metadata_repository.py`) and `uv run ruff check <your files>`. Other workers' tests may be red in the middle of their TDD cycles. The full-suite gate runs once the batch finishes, and in task 019.
- **Commit only your own files.** Use `git add <explicit paths>`. Never use `git add -A`, `git add .` or `git commit -a`, which would sweep in another worker's half-finished files.
- **Package `__init__.py` files have no re-exports** in `app/repositories/` and `app/services/`, so parallel tasks never edit a shared `__init__`.
- **Only task 001 edits `pyproject.toml` / `uv.lock`.**
- **Tests never call `create_app(TestConfig)` without tmp_path overrides.** Use the `app` / `make_app` fixtures.
- **Scripts**: `dataset_table.js` (deferred) must come **before** the deferred Alpine CDN script, so its `alpine:init` listener is registered before Alpine starts.
- **Env overrides**: `app.config.from_prefixed_env("CSV_EXPLORER")`, e.g. `CSV_EXPLORER_ALLOW_PRIVATE_URLS=true`.

## Risks & Mitigations
- **uv not installed**: `brew install uv` before running the plan. Task 001 stops as blocked if `uv` is missing.
- **`read_csv_auto(?)` parameter binding may not be supported for table functions**: fall back to a `quote_literal` helper that escapes `'`. The path is always server-generated inside `CSV_DIR`, so this is safe.
- **DuckDB file lock under the Flask debug reloader** (two processes opening `data/app.duckdb`): this **will** happen with an eager connection, because Flask 3.x loads the app in the reloader parent too. Mitigation: the service container is built lazily on first use (task 014), so the parent never opens the file. A `WERKZEUG_RUN_MAIN` guard was rejected because it breaks `--no-reload`. Verified by the smoke test in task 019.
- **Deleted datasets coming back on the next scan**: **resolved**. Deletion leaves a marker, and the scan skips unchanged files that carry one (tasks 007, 012, 013; end-to-end test in 019).
- **DNS rebinding / TOCTOU between UrlGuard and requests**: accepted for a local tool and documented. Redirects are disabled in `requests` and every hop is validated manually.
- **Table-name collisions** (`Sales.csv` and `sales.csv` → `sales`): accepted under replace semantics (last ingest wins) and documented in the README.
- **Parallel xdist tests**: every test uses `tmp_path` for `CSV_DIR`/`DUCKDB_PATH` and never touches `data/`.
- **Tailwind binary download needs network access**: task 004 finds the newest v4 tag once, downloads that exact release, and records it in `.tailwind-version`. No test depends on the binary.
- **Latin-1 fallback may mis-decode other 8-bit encodings** (e.g. Windows-1252 curly quotes, `€`): accepted, and documented in the README (task 019).
