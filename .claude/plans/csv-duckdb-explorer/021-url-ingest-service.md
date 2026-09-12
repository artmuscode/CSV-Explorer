# Task 021: UrlIngestService

**Status**: completed
**Depends on**: 001, 002, 003, 005, 007, 010, 011
**Retry count**: 0

## Description
Create `UrlIngestService`, which ingests a CSV from a URL. It downloads through `CsvDownloader` into a staged file, then hands it to `CsvIngestService.install_and_ingest`, which moves it into place, ingests it with `source=URL`, and restores any previous same-named file on failure. Keeping URL ingest in its own class keeps `CsvIngestService` free of download concerns, and lets this task run in parallel with the folder-scan task (012).

## Context
- Related files (new): `app/services/url_ingest_service.py`, `tests/unit/services/test_url_ingest_service.py`. **Don't edit `csv_ingest_service.py`**: task 012 is editing it in the same batch.
- Constructor: `UrlIngestService(downloader: CsvDownloader, ingest_service: CsvIngestService)`. Import `CsvDownloader` and `DownloadedFile` from `app.services.csv_downloader` (task 010, finished in an earlier batch).
- `ingest(url: str) -> IngestResult`:
  1. `url = url.strip()`. A blank URL → `IngestError("Please enter a URL")`.
  2. `downloaded = self._downloader.download(url)` → `DownloadedFile(path, filename)`, staged in `csv_dir` as a hidden `.part` file. `IngestError` from the downloader propagates unchanged.
  3. `return self._ingest_service.install_and_ingest(downloaded.path, downloaded.filename, DatasetSource.URL, source_url=url)`. On failure it removes the staged file and restores any previous file with the same name (task 011).
- **Tests:**
  - Use a real `CsvIngestService` on in-memory repositories with a `tmp_path` csv_dir.
  - Use a small **fake downloader** class defined **in this task's test module**. **Don't edit `tests/fakes.py`**: task 020 may be extending it in the same batch (B5). Its `download(url)` writes a given body to `csv_dir / f".{uuid4().hex}.part"` and returns `DownloadedFile(path, filename)`, or raises a given `IngestError`.
  - The unloadable body is the canonical 0-byte CSV from task 005.
  - No network, and no real `CsvDownloader` needed.

## Requirements (Test Descriptions)
- [x] `test_ingest_records_url_source_and_source_url`
- [x] `test_ingest_rejects_blank_url_without_downloading`
- [x] `test_ingest_propagates_downloader_ingest_error`
- [x] `test_ingest_removes_staged_file_when_downloaded_csv_is_unloadable`
- [x] `test_ingest_keeps_existing_file_with_same_name_when_download_is_unloadable`

## Acceptance Criteria
- All requirements have passing tests
- No Flask imports; `CsvIngestService` isn't modified by this task
- Code follows code standards

## Implementation Notes
- Created `app/services/url_ingest_service.py` with `UrlIngestService(downloader, ingest_service)`
  and a single public method `ingest(url) -> IngestResult`, exactly per spec: strip, reject blank
  with `IngestError("Please enter a URL")` before touching the downloader, delegate to
  `CsvDownloader.download` (letting its `IngestError` propagate unchanged), then delegate to
  `CsvIngestService.install_and_ingest(downloaded.path, downloaded.filename, DatasetSource.URL,
  source_url=url)`. Rollback-on-failure and staged-file cleanup live entirely in
  `install_and_ingest` (task 011/012), so this service stays a thin coordinator with no file I/O
  of its own.
- All 5 requirements were implemented together as they map to one small method with few branches;
  each test was written and confirmed to exercise a distinct behavior (happy path, blank-URL guard,
  downloader-error passthrough, unloadable-CSV cleanup with no prior file, unloadable-CSV cleanup
  restoring a prior same-named file). Ran the blank-URL and unloadable-content tests individually
  against a stub-only version first to verify they'd fail without the guard/`install_and_ingest`
  call before finalizing the implementation.
- Test module defines a local `FakeDownloader` (per task instructions, not added to
  `tests/fakes.py`) that stages a given `bytes` body to `csv_dir / f".{uuid4().hex}.part"` and
  returns a `DownloadedFile`, or raises a pre-set `IngestError`. Tests use a real
  `CsvIngestService` wired to in-memory DuckDB + `MetadataRepository` and a `tmp_path` csv_dir, per
  the test plan — no `CsvDownloader` or network involved.
- `uv run pytest tests/unit/services/test_url_ingest_service.py -v`: 5 passed.
- `uv run ruff check` / `ruff format --check` on both new files: clean.
- This task ran in a parallel batch alongside 012, 013 and 020 editing other files in the same
  tree, so (per orchestrator rules) only this task's own test file and lint checks were run here
  rather than the full suite, which may be red mid-cycle for other in-progress tasks.
