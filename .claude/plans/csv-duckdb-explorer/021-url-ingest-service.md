# Task 021: UrlIngestService

**Status**: pending
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
- [ ] `test_ingest_records_url_source_and_source_url`
- [ ] `test_ingest_rejects_blank_url_without_downloading`
- [ ] `test_ingest_propagates_downloader_ingest_error`
- [ ] `test_ingest_removes_staged_file_when_downloaded_csv_is_unloadable`
- [ ] `test_ingest_keeps_existing_file_with_same_name_when_download_is_unloadable`

## Acceptance Criteria
- All requirements have passing tests
- No Flask imports; `CsvIngestService` isn't modified by this task
- Code follows code standards

## Implementation Notes
(Left blank - filled in by programmer during implementation)
