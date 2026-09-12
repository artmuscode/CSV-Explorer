# Task 016: Ingest Blueprint — Upload, URL, Scan

**Status**: completed
**Depends on**: 001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 012, 013, 014, 020, 021, 022
**Retry count**: 0

## Description
Implement the three ingest endpoints. Upload and scan delegate to `CsvIngestService`, and URL ingest to `UrlIngestService` (task 021). Each one shows the outcome as a flash message, and redirects: to the new dataset's table on success, or back home on error or after a scan.

## Context
- Related files (modify): `app/blueprints/ingest.py`. Replace the 501 stubs from task 014 and keep the same endpoint names. Only edit this module (and `app/errors.py` if 413 is handled there). Tasks 015 and 017 own the other blueprints.
- Related files (new): `tests/integration/test_ingest_routes.py`
- Endpoints (blueprint `ingest`, `url_prefix="/ingest"`):
  - `POST /ingest/upload` (endpoint `upload`): `file = request.files.get("file")`.
    - Missing or empty file name → flash `error`, redirect to `main.index`.
    - Otherwise `ingest_service.save_upload(file.filename, file.stream)`, flash success ("Replaced" or "Created" `<name>` with N rows), then redirect to `datasets.show`.
  - `POST /ingest/url` (endpoint `from_url`): the `url` form field, stripped.
    - Blank → flash error.
    - Otherwise `current_services().url_ingest_service.ingest(url)`, then redirect to `datasets.show`.
  - `POST /ingest/scan` (endpoint `scan`): `scan_folder()`, then flash a summary ("Ingested X, skipped Y, failed Z"). Also flash **at most 5** per-file errors as `error`, adding "…and N more" if there are more, then redirect to `main.index`.
- `IngestError` from any service call → flash `error` with `str(exc)`, redirect to `main.index`.
- **Flash size budget.** Flask stores flashes in the signed cookie session, and browsers drop cookies over roughly 4 KB. When that happens every message on the redirect disappears without warning, and Werkzeug only logs a warning. So truncate every flashed message to 300 characters (a small private helper in this module) and cap per-file scan errors as described above. Task 005 already shortens DuckDB messages to one line.
- **413**: register `@bp.app_errorhandler(RequestEntityTooLarge)` (or handle it in `app/errors.py`). It flashes "File too large" and redirects to `main.index`. In the test, use `make_app(MAX_CONTENT_LENGTH=1024)` (task 001 fixture). Never call `create_app(TestConfig)` without tmp_path overrides.
- **URL tests:** never hit the network. Use the `fake_network` fixture from task 014:
  - `fake_network.routes["https://example.com/sales.csv"] = FakeResponse(body=b"a,b\n1,2\n", headers={"Content-Type": "text/csv"})`
  - For the blocked-address test: `fake_network.dns["internal.test"] = ["127.0.0.1"]`, with `ALLOW_PRIVATE_URLS=False` (the TestConfig default).
  - Don't monkeypatch private attributes such as `url_ingest_service._downloader`.
- **Unloadable files in tests:** use the canonical 0-byte CSV from task 005. Invalid UTF-8 now loads through the Latin-1 fallback, so it no longer fails.

## Requirements (Test Descriptions)
- [x] `test_upload_ingests_csv_and_redirects_to_dataset_view`
- [x] `test_upload_without_file_flashes_error_and_redirects_home`
- [x] `test_upload_of_unloadable_csv_flashes_error`
- [x] `test_upload_exceeding_max_content_length_flashes_error`
- [x] `test_url_ingest_redirects_to_dataset_view_on_success`
- [x] `test_url_ingest_flashes_error_for_blocked_private_address`
- [x] `test_scan_flashes_summary_of_ingested_skipped_and_failed_files`
- [x] `test_scan_with_many_failures_caps_flashed_errors_and_session_cookie_stays_small` (7 empty `.csv` files: at most 5 error flashes plus "…and 2 more", and the `Set-Cookie` session value is under 4000 bytes)

## Acceptance Criteria
- All requirements have passing tests
- Route handlers contain no business logic beyond request parsing and flash/redirect
- Code follows code standards

## Implementation Notes
- All 8 requirements implemented and passing together in one pass (each was written and confirmed RED against the 501 stubs before implementing).
- `app/blueprints/ingest.py`: three thin routes (`upload`, `from_url`, `scan`) plus a `bp.app_errorhandler(RequestEntityTooLarge)` handler for 413. `_truncate` (private helper, 300-char cap) wraps every flashed string, including the capped scan-error and "File too large" messages. `_flash_ingest_result` is a small shared helper for the upload/URL "Replaced"/"Created" success message so both routes share the same wording logic.
- `from_url` relies on `UrlIngestService.ingest` to raise `IngestError("Please enter a URL")` for a blank URL rather than duplicating that check in the route, since the plan's "IngestError -> flash error, redirect main.index" rule already covers it.
- Scan errors: flashes at most 5 `"<filename>: <message>"` error flashes (in the same sorted-by-filename order `scan_folder` produces), then one more `"…and N more"` flash if there were additional failures.
- `app/errors.py` untouched; the 413 handler lives in `app/blueprints/ingest.py` via `app_errorhandler`, which registers app-wide once the blueprint is registered.
- New test file `tests/integration/test_ingest_routes.py`. Flash assertions read `session["_flashes"]` via `client.session_transaction()` instead of following redirects, since `main.index`/`datasets.show` may still be 501 stubs from the parallel 015/017 tasks. Redirect assertions check `response.headers["Location"]` directly (e.g. `/datasets/people`, `/`).
- Verified: `uv run pytest tests/integration/test_ingest_routes.py` (8 passed), plus `tests/unit/services/test_csv_ingest_service.py` and `tests/unit/services/test_url_ingest_service.py` still green (28 total). `uv run ruff check` / `ruff format --check` clean on the two files I own.
