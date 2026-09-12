# Task 019: End-to-End Tests, README & Final Verification

**Status**: completed
**Depends on**: 001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 012, 013, 014, 015, 016, 017, 018, 020, 021, 022
**Retry count**: 0

## Description
Add end-to-end integration tests that run each ingest path through to querying the rows API. Rewrite the README for the new stack and sync the architecture docs with what was built. Finish with the full quality gate: parallel tests, coverage, ruff, and a minified Tailwind build.

## Context
- Related files (new): `tests/integration/test_end_to_end.py`
- Related files (modify):
  - `README.md` (currently lists Sqlite3/AlpineAjax, which is out of date)
  - `.claude/architecture.md` and `CLAUDE.md`, only if the implementation drifted (e.g. new modules like `container.py`, `security.py`, `url_guard.py`, `csv_downloader.py`, `url_ingest_service.py`, `row_query_builder.py`, `metadata_repository.py`)
- README sections:
  - what the app does
  - stack
  - prerequisites (`brew install uv`)
  - setup (`uv sync`, the Tailwind binary download command using the tag in `.tailwind-version`, a CSS build)
  - running (`uv run flask --app app run --debug`, plus the Tailwind `--watch` command)
  - usage (drop folder, upload, URL, scan button, filters and sort)
  - configuration via `CSV_EXPLORER_*` env vars (`CSV_DIR`, `DUCKDB_PATH`, `ALLOW_PRIVATE_URLS`, `MAX_DOWNLOAD_BYTES`, `PAGE_SIZE`, `SCAN_ON_STARTUP`)
  - testing and linting commands
  - known limitations:
    - files whose names map to the same table replace each other (`Sales.csv` / `sales.csv` → `sales`). Within one folder scan, the second file is reported as a collision instead.
    - DNS-rebinding caveat
    - no auth. Cross-site form posts are blocked by a same-origin check (task 022), but anyone who can reach the port can use the app, so keep the server bound to `127.0.0.1` and never use `--host 0.0.0.0`
    - deleting a dataset keeps its CSV file and remembers the deletion: the scan won't re-import that file unless it changes. Re-uploading it, or re-downloading it by URL, brings the dataset back.
    - single process only: DuckDB allows one writer process, so don't run it under multi-worker gunicorn
    - the "startup" scan runs on the first request after the server starts (the container is built lazily; see task 014)
    - encoding: files are read as UTF-8, with an automatic Latin-1 fallback. Windows-1252 files load, but the characters `€`, `‘ ’ “ ”`, `–` and `—` show up as control characters. UTF-16 isn't supported.
    - empty (0-byte) CSVs and file names containing `*`, `?` or `[` are rejected
    - dropped CSVs in `data/csv/` are gitignored
- The end-to-end tests go through the Flask test client and the real service container. Network is always faked with the `fake_network` fixture (task 014). Use the canonical unloadable CSV from task 005 (a 0-byte file) wherever a failing file is needed.
- Final gate:
  ```bash
  uv run pytest -n auto --cov=app --cov-report=term-missing --cov-fail-under=80
  uv run ruff check . && uv run ruff format --check .
  ./bin/tailwindcss -i app/static/css/input.css -o app/static/css/app.css --minify
  ```
- Smoke test (automate what you can):
  1. Start `uv run flask --app app run --debug --port 5055` in the background, using a scratch `CSV_EXPLORER_CSV_DIR` / `CSV_EXPLORER_DUCKDB_PATH` so the real `data/` stays clean.
  2. Put a CSV in the scratch folder, `curl` `/`, and check it's listed.
  3. `curl` `/api/datasets/<name>/rows?q=...&sort=...`.
  4. Touch a `.py` file to trigger a reload, `curl` again, and confirm the log has **no DuckDB lock errors**.
  5. Stop the server.

  The in-browser Alpine check (filter, sort, paging) is best effort. If no browser tool is available, write "browser check pending for user" plus a checklist in Implementation Notes. Don't mark the task blocked.

## Requirements (Test Descriptions)
- [x] `test_end_to_end_scan_folder_then_query_rows_api_with_filters`
- [x] `test_end_to_end_upload_then_reupload_replaces_rows`
- [x] `test_end_to_end_url_ingest_then_view_then_delete`
- [x] `test_end_to_end_malicious_csv_headers_are_escaped_on_every_page`
- [x] `test_end_to_end_deleted_folder_dataset_stays_deleted_after_rescan_until_file_changes`
- [x] `test_end_to_end_cross_origin_delete_is_blocked_and_dataset_survives`

## Acceptance Criteria
- All requirements have passing tests
- Full suite passes in parallel with coverage ≥ 80%
- ruff check and ruff format --check are clean
- README accurately describes setup, usage, config and limitations
- Smoke test done (or its browser portion recorded as pending), with results in Implementation Notes
- `.claude/architecture.md` / `CLAUDE.md` reflect the lazy service container (`init_services` / `get_services`) and the fact that SQL lives in `app/repositories/` (three modules), not only in `DuckDBRepository`

## Implementation Notes

All six end-to-end tests were added to `tests/integration/test_end_to_end.py`. Each
drives the real Flask test client + real service container (`fake_network` fakes
the HTTP layer for the URL-ingest test; everything else touches only `tmp_path`).
Every test passed on the first run — no new requirement uncovered an app bug, so
no `app/` code changed for this task. Notes per test:

- `test_end_to_end_scan_folder_then_query_rows_api_with_filters`: writes a CSV
  straight into `CSV_DIR`, POSTs `/ingest/scan`, then GETs
  `/api/datasets/<name>/rows` with `q`, `filter[col]`, `sort`, `dir` together and
  checks the filtered/sorted JSON.
- `test_end_to_end_upload_then_reupload_replaces_rows`: uploads the same filename
  twice with different contents through `/ingest/upload`, checks the
  "Created"/"Replaced" flash wording and that the rows API reflects the new data
  after the second upload (`CREATE OR REPLACE TABLE` semantics).
- `test_end_to_end_url_ingest_then_view_then_delete`: fakes a CSV download via
  `fake_network`, ingests it by URL, views the dataset page (confirms
  `source_url` is shown), deletes it (same-origin header set so the delete is
  allowed), then confirms both the detail page (404) and the home page no longer
  show it.
- `test_end_to_end_malicious_csv_headers_are_escaped_on_every_page`: ingests a
  CSV whose header is `<script>alert(1)</script>`, spanning two pages of rows.
  Confirms the dataset `show.html` page never contains the raw
  `<script>alert(1)</script>` string (it's JSON-escaped as `<script>`
  inside the `#initial-page` script tag, per Jinja's `tojson` filter), and that
  the JSON rows API (page 1 and page 2) returns `application/json` with the
  literal column name intact — safe because a JSON response is never parsed as
  HTML, and the Alpine template renders it with `x-text`, never `x-html`.
- `test_end_to_end_deleted_folder_dataset_stays_deleted_after_rescan_until_file_changes`:
  scans, deletes, rescans (unchanged file: still "skipped", dataset stays gone),
  then rewrites the file's contents and rescans again (dataset comes back with
  the new row count). Confirms the `deleted_at` marker behavior end to end.
- `test_end_to_end_cross_origin_delete_is_blocked_and_dataset_survives`: POSTs
  `/datasets/<name>/delete` with a foreign `Origin` header and confirms 403 plus
  that the dataset's detail page still returns 200 afterward.

Documentation:
- Rewrote `README.md` from scratch (previous version said Sqlite3/AlpineAjax).
  Covers what the app does, the actual stack, prerequisites (`brew install uv`),
  setup (`uv sync` + downloading `bin/tailwindcss` at the tag in
  `.tailwind-version` + a CSS build), running (dev server + `--watch`), usage
  (drop folder/upload/URL/scan, search/filter/sort/page), the full
  `CSV_EXPLORER_*` config table (including the `from_prefixed_env` JSON-decoding
  note — plain strings like paths work unquoted, booleans/numbers are JSON), test
  and lint commands, and every known limitation called out in the task
  (name collisions, DNS rebinding, no-auth/same-origin/127.0.0.1, soft deletes,
  single-process DuckDB, lazy "startup" scan, encoding fallback and its Windows-1252
  caveat, rejected files, gitignored `data/csv/`). Added a "Manual UI check"
  section with a checklist, since no browser tool was available.
- `.claude/architecture.md` was already current on the module list (container.py,
  security.py, url_guard.py, csv_downloader.py, url_ingest_service.py,
  row_query_builder.py, metadata_repository.py all present). Fixed two small
  drifts: the `templates/` tree listed a non-existent `partials/pagination`
  (pagination is inline Alpine markup in `datasets/show.html`, not a separate
  partial) and omitted `errors/403.html`; and the "Error Handling" section didn't
  mention the 403 handler. Both fixed.
- `CLAUDE.md` was already accurate (mentions the layered architecture, lazy
  container, and that SQL only lives in `app/repositories/`); no changes needed.

Smoke test (task's step-by-step, automated):
1. Started `uv run flask --app app run --debug --port 5055` in the background
   with `CSV_EXPLORER_CSV_DIR`/`CSV_EXPLORER_DUCKDB_PATH` pointed at a scratch
   dir under the session scratchpad (never `data/`).
2. Put `sales.csv` (3 rows) in the scratch folder; `curl /` returned 200 and
   listed "sales" (first request triggers the lazy startup scan).
3. `curl "/api/datasets/sales/rows?q=ada&sort=amount&dir=desc"` returned the
   correctly filtered/sorted JSON.
4. Touched `app/errors.py` to trigger the debug reloader, waited for it to
   restart, then `curl /` (200) and `curl "/api/datasets/sales/rows?per_page=2"`
   (200, correct paging) again. Checked `server.log`: no "lock" string anywhere,
   confirming the reloader parent never opened DuckDB (task 014's lazy
   container design working as intended).
5. Stopped the server with
   `pkill -f "flask --app app run --debug --port 5055"` and confirmed no process
   remained.

Browser check: pending for user — no browser tool was available in this
environment. See the "Manual UI check" checklist added to `README.md` (search,
per-column filters, sort toggling, page-size selector, pagination controls,
ingest forms, delete, error pages).

Final gate results:
- `uv run pytest -n auto --cov=app --cov-report=term-missing --cov-fail-under=80`:
  183 passed, 95.98% coverage (required 80%).
- `uv run ruff check .`: all checks passed.
- `uv run ruff format --check .`: all files formatted (ran `ruff format` once on
  the new test file to fix two long lines it flagged, then reconfirmed clean).
- `./bin/tailwindcss -i app/static/css/input.css -o app/static/css/app.css --minify`:
  built successfully (`Done in 45ms`).
