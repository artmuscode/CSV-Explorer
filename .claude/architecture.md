# Architecture

## Overview
A Flask app that loads CSV files into DuckDB and shows them as paginated, filterable HTML tables. CSVs come in two ways:
1. **Drop folder**: files placed in (or uploaded to) `data/csv/` get scanned and ingested.
2. **URL**: the user gives a URL, and the app downloads the CSV into `data/csv/` and ingests it.

Each ingested CSV becomes one DuckDB table, called a "dataset".

## Directory Structure
Target layout. The legacy starter files (`main.py`, `templates/`, `assets/`) get migrated into `app/` early in the feature plan.

```
app/
  __init__.py              # create_app(config_class) factory; builds repository + services, registers blueprints
  config.py                # Config / TestConfig: CSV_DIR, DUCKDB_PATH, PAGE_SIZE, MAX_PAGE_SIZE,
                           #   MAX_DOWNLOAD_BYTES, DOWNLOAD_TIMEOUT, ALLOW_PRIVATE_URLS, SCAN_ON_STARTUP
  container.py             # ServiceContainer dataclass, build_container(config), lazy get_services(app) /
                           #   current_services() — DuckDB opened on first use (reloader-safe)
  errors.py                # register_error_handlers(app): 403/404/500 (HTML or JSON for /api/)
  security.py              # register_same_origin_check(app): rejects cross-origin POST/PUT/PATCH/DELETE
  exceptions.py            # CsvExplorerError → IngestError, DatasetNotFoundError, InvalidQueryError
  models/                  # @dataclass(frozen=True, slots=True) DTOs
    column.py              # Column(name, type)
    dataset.py             # Dataset(name, original_filename, source, row_count, ingested_at, source_url,
                           #   file_size, file_mtime, deleted_at) + DatasetSource enum (folder/upload/url)
    row_query.py           # RowQuery(page, per_page, search, filters, sort_by, sort_dir) + SortDirection
    page.py                # Page(rows, columns, page, per_page, total) + total_pages/has_next/has_prev/to_dict
    ingest_result.py       # IngestResult(dataset, replaced), ScanResult(ingested, skipped, errors)
  repositories/
    identifiers.py         # quote_identifier, quote_literal, table_name_from_filename
    duckdb_repository.py   # DuckDBRepository: create_table_from_csv, table_exists, get_columns,
                           #   count_rows, drop_table, fetch_page(table, RowQuery) -> Page
    row_query_builder.py   # RowQueryBuilder: RowQuery -> parameterized SELECT + COUNT (search/filter/sort)
    metadata_repository.py # MetadataRepository: _datasets table (ensure_schema, upsert, get, list_all,
                           #   mark_deleted — deletion markers keep deleted files from being re-scanned)
  services/
    url_guard.py           # UrlGuard: http(s) only, blocks non-global addresses unless allowed
    csv_downloader.py      # CsvDownloader: streamed, size/deadline-capped, redirect-validated download
                           #   into a staged .part file → DownloadedFile(path, filename)
    csv_ingest_service.py  # CsvIngestService: ingest_file, save_upload, install_and_ingest (rollback), scan_folder
    url_ingest_service.py  # UrlIngestService: download → CsvIngestService.install_and_ingest
    dataset_service.py     # DatasetService: list_datasets, get_dataset, build_query, get_page, delete_dataset
  blueprints/
    __init__.py            # register_blueprints(app)
    main.py                # GET / (dataset list + ingest forms), POST /datasets/<name>/delete
    ingest.py              # POST /ingest/upload, /ingest/url, /ingest/scan
    datasets.py            # GET /datasets/<name> (HTML), GET /api/datasets/<name>/rows (JSON)
  templates/
    base.html              # layout, Tailwind CSS, Alpine.js
    partials/              # header, footer, flash messages, pagination
    index.html
    errors/                # 404.html, 500.html
    datasets/show.html     # table view + Alpine filter component
  static/
    css/input.css          # Tailwind v4 source (@import "tailwindcss";)
    css/app.css            # built output (gitignored)
    js/dataset_table.js    # Alpine.data('datasetTable', ...) component
data/
  csv/                     # CSV drop folder
  app.duckdb               # DuckDB database (gitignored)
tests/
  conftest.py
  unit/                    # mirrors app/
  integration/             # Flask test-client tests
bin/tailwindcss            # Tailwind v4 standalone CLI binary (gitignored)
pyproject.toml             # deps (uv), ruff + pytest config
```

## Patterns Used
- **App factory and blueprints**: yes. `create_app(config_class=Config)` builds everything. Blueprints group routes by concern (main, ingest, datasets). No module-level `app` global.
- **Repository pattern**: yes. `DuckDBRepository` is the only code that talks to DuckDB and the only place SQL lives. It returns plain Python and DTOs, never DuckDB relations.
- **Service classes**: yes. `CsvIngestService` and `DatasetService` hold the business logic: validation, file handling, downloading, paging maths. They receive the repository and config values through `__init__`.
- **Dataclasses as DTOs**: yes. `Dataset`, `Page`, and `IngestResult` pass data between layers instead of loose dicts.
- Event sourcing / CQRS: no.

## Layering

```
blueprints  →  services  →  repository  →  DuckDB
  (Flask)       (pure Python)  (SQL only)
```

- Dependencies point one way only. Lower layers never import higher ones.
- Services and repositories must not import Flask. That keeps them unit-testable without an app context.
- `create_app` builds one `DuckDBRepository` plus the services and stores them on `app.extensions["csv_explorer"]`. Blueprints get them through a small accessor.

## Data Flow

**Ingest (folder / upload / URL)**
1. Blueprint validates request shape → calls `CsvIngestService`.
2. Service sanitizes the file name and, for a URL, checks scheme, timeout and size, then streams into `CSV_DIR`.
3. Service derives a safe table name from the file name, then calls `repository.create_table_from_csv(table, path)`.
4. Repository runs `CREATE OR REPLACE TABLE "<table>" AS SELECT * FROM read_csv_auto(?)`.
5. Service returns an `IngestResult`. The blueprint flashes a message and redirects.

**View / paginate / filter**
1. `GET /datasets/<name>` renders the page shell: columns plus the first page, server-rendered.
2. The Alpine.js component holds the filter state (global search plus per-column values) and the current page.
3. When a filter or the page changes, Alpine fetches `GET /api/datasets/<name>/rows?page=N&per_page=M&q=...&filter[col]=...`.
4. `DatasetService.build_query` validates paging and sort direction. `RowQueryBuilder` checks the columns against the schema and produces a parameterized `WHERE ... ILIKE ?` with `ORDER BY ... , rowid` and `LIMIT/OFFSET`, plus a matching `COUNT(*)`.
5. The JSON response carries `{rows, columns, page, per_page, total, total_pages}`, and Alpine re-renders the table body and pagination.

Pagination and filtering both run **server-side**, so filters apply across the whole dataset, not just the visible page.

## Conventions
- One primary class per file. Tests mirror source structure.
- Table names are derived from file names: lowercase, non-alphanumerics → `_`, leading and trailing `_` stripped, prefixed with `t_` if they start with a digit. User tables therefore never collide with the internal `_datasets` metadata table.
- Re-ingesting a file whose name maps to an existing table **replaces** that table.
- Deleting a dataset drops its table and sets `deleted_at` in `_datasets`, keeping the CSV file. The folder scan skips a deleted file until it changes (size or mtime), and any re-ingest clears the marker.
- CSVs are read as UTF-8, with a Latin-1 fallback. 0-byte files are rejected before DuckDB is called.
- Config values come from `Config`, which environment variables can override. No hard-coded paths in services.
- DuckDB connection: one per process, opened **lazily on first service use** (not in `create_app`), so the Flask debug reloader's parent process never takes DuckDB's file lock. Use cursors (`with conn.cursor() as cur`) per operation for thread safety under the Flask dev server.
- State-changing requests (POST/PUT/PATCH/DELETE) must pass the same-origin check in `app/security.py`.

## Key Integrations
- **DuckDB** (`duckdb` Python package): storage and CSV parsing via `read_csv_auto`.
- **HTTP downloads**: stdlib `urllib.request` or `requests`, streamed with a size cap and timeout.
- **Alpine.js v3**: loaded from the jsDelivr CDN in `base.html`, pinned to an exact version.
- **Tailwind CSS v4**: standalone CLI:
  ```bash
  ./bin/tailwindcss -i app/static/css/input.css -o app/static/css/app.css --watch   # dev
  ./bin/tailwindcss -i app/static/css/input.css -o app/static/css/app.css --minify  # build
  ```

## Error Handling
- Services raise domain exceptions from `app/exceptions.py`.
- Blueprints turn them into flash messages (HTML routes) or `{"error": ...}` with a 4xx status (JSON routes).
- A 404 handler covers unknown datasets. Unexpected errors are logged and return a 500 page, without leaking stack traces in production.
