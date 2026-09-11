# Task 016: Ingest Blueprint — Upload, URL, Scan

**Status**: pending
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
- [ ] `test_upload_ingests_csv_and_redirects_to_dataset_view`
- [ ] `test_upload_without_file_flashes_error_and_redirects_home`
- [ ] `test_upload_of_unloadable_csv_flashes_error`
- [ ] `test_upload_exceeding_max_content_length_flashes_error`
- [ ] `test_url_ingest_redirects_to_dataset_view_on_success`
- [ ] `test_url_ingest_flashes_error_for_blocked_private_address`
- [ ] `test_scan_flashes_summary_of_ingested_skipped_and_failed_files`
- [ ] `test_scan_with_many_failures_caps_flashed_errors_and_session_cookie_stays_small` (7 empty `.csv` files: at most 5 error flashes plus "…and 2 more", and the `Set-Cookie` session value is under 4000 bytes)

## Acceptance Criteria
- All requirements have passing tests
- Route handlers contain no business logic beyond request parsing and flash/redirect
- Code follows code standards

## Implementation Notes
(Left blank - filled in by programmer during implementation)
