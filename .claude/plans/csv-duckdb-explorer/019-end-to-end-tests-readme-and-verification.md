# Task 019: End-to-End Tests, README & Final Verification

**Status**: pending
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
- [ ] `test_end_to_end_scan_folder_then_query_rows_api_with_filters`
- [ ] `test_end_to_end_upload_then_reupload_replaces_rows`
- [ ] `test_end_to_end_url_ingest_then_view_then_delete`
- [ ] `test_end_to_end_malicious_csv_headers_are_escaped_on_every_page`
- [ ] `test_end_to_end_deleted_folder_dataset_stays_deleted_after_rescan_until_file_changes`
- [ ] `test_end_to_end_cross_origin_delete_is_blocked_and_dataset_survives`

## Acceptance Criteria
- All requirements have passing tests
- Full suite passes in parallel with coverage ≥ 80%
- ruff check and ruff format --check are clean
- README accurately describes setup, usage, config and limitations
- Smoke test done (or its browser portion recorded as pending), with results in Implementation Notes
- `.claude/architecture.md` / `CLAUDE.md` reflect the lazy service container (`init_services` / `get_services`) and the fact that SQL lives in `app/repositories/` (three modules), not only in `DuckDBRepository`

## Implementation Notes
(Left blank - filled in by programmer during implementation)
