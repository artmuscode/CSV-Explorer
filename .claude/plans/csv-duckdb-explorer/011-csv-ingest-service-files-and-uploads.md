# Task 011: CsvIngestService — Files & Uploads

**Status**: pending
**Depends on**: 001, 002, 003, 005, 007
**Retry count**: 0

## Description
Create `CsvIngestService`, which turns a CSV file on disk into a dataset: a DuckDB table plus a metadata record. It also saves browser uploads into the CSV folder. Folder scan and URL ingest are added in task 012.

## Context
- Related files (new): `app/services/csv_ingest_service.py`, `tests/unit/services/test_csv_ingest_service.py`
- Constructor: `CsvIngestService(repository: DuckDBRepository, metadata: MetadataRepository, csv_dir: Path, clock: Callable[[], datetime] = lambda: datetime.now(UTC))`.
  - **Don't add a `downloader` parameter or import `app.services.csv_downloader` here.** URL ingest lives in a separate `UrlIngestService` (task 021), which calls this service's public `install_and_ingest`. `CsvIngestService` never knows about downloads.
- `repository.create_table_from_csv` may itself raise `IngestError` for malformed files (task 005). Use the canonical malformed-CSV sample recorded in task 005.
- `ingest_file(path: Path, source: DatasetSource = DatasetSource.FOLDER, source_url: str | None = None) -> IngestResult`:
  - Reject files whose suffix isn't `.csv` (case-insensitive) with `IngestError`.
  - `table = table_name_from_filename(path.name)`. Wrap `ValueError` as `IngestError`.
  - `existing = metadata.get(table)`, then `replaced = existing is not None and not existing.is_deleted`. Re-ingesting a deleted dataset counts as "created", not "replaced".
  - The new `Dataset` has `deleted_at=None`, so the upsert clears any deletion marker. Explicitly uploading, downloading or changing a deleted file brings the dataset back.
  - `row_count = repository.create_table_from_csv(table, path)`.
  - `stat = path.stat()`.
  - Build a `Dataset(name=table, original_filename=path.name, source, row_count, ingested_at=clock(), source_url, file_size=stat.st_size, file_mtime=stat.st_mtime)` and pass it to `metadata.upsert(...)`.
  - Return `IngestResult(dataset, replaced)`.
- `install_and_ingest(staged: Path, filename: str, source: DatasetSource, source_url: str | None = None) -> IngestResult` (**public**; `UrlIngestService` in task 021 calls it). It moves a staged file into `csv_dir / filename` and ingests it, and **puts the previous file back if ingest fails**:
  1. `final = csv_dir / filename`.
  2. If `final` exists, `os.replace(final, csv_dir / f".{filename}.{uuid4().hex}.bak")`.
  3. `os.replace(staged, final)`. A rename keeps the mtime, so the `stat()` inside `ingest_file` is still valid for scan-skip.
  4. `ingest_file(final, source, source_url)`.
  5. On **any** exception: unlink `final`, restore the backup with `os.replace(backup, final)` if there was one, unlink `staged` if it still exists, then re-raise. On success, unlink the backup.

  **Why:** the original plan wrote the upload over `csv_dir / safe` and deleted it if ingest failed. Re-uploading a broken `sales.csv` would then **destroy the user's existing, good `sales.csv`**, while the old `sales` table kept pointing at a file that no longer existed. `CREATE OR REPLACE` fails atomically, so the old table is untouched on failure, and restoring the file keeps disk and table consistent.
- `save_upload(filename: str, stream: BinaryIO) -> IngestResult`:
  - `safe = secure_filename(filename)`. An empty result or a non-`.csv` name → `IngestError`.
  - Copy the stream (`shutil.copyfileobj`) into a staged file `csv_dir / f".{uuid4().hex}.part"`. Hidden `.part` files are ignored by `scan_folder`.
  - `return self.install_and_ingest(staged, safe, DatasetSource.UPLOAD)`
- **Unloadable file in tests:** use the canonical 0-byte file from task 005 (`b""`). Invalid UTF-8 now loads through the Latin-1 fallback.
- Don't import Flask. Take a plain `(filename, stream)`, not a `FileStorage`.
- **Tests use real repositories** on `duckdb.connect(":memory:")` with `metadata.ensure_schema()`, a `tmp_path` csv_dir and a fixed clock. Don't use mocks.

## Requirements (Test Descriptions)
- [ ] `test_ingest_file_creates_table_named_after_file`
- [ ] `test_ingest_file_records_metadata_with_source_size_and_mtime`
- [ ] `test_ingest_file_reports_replaced_only_when_a_live_dataset_already_existed` (existing live dataset → `replaced=True`; dataset marked deleted → `replaced=False`, and the marker is cleared)
- [ ] `test_ingest_file_rejects_non_csv_extension`
- [ ] `test_save_upload_writes_sanitized_filename_into_csv_dir`
- [ ] `test_save_upload_rejects_empty_filename`
- [ ] `test_save_upload_removes_file_when_csv_is_unloadable`
- [ ] `test_save_upload_restores_previous_file_and_table_when_replacement_is_unloadable` (ingest a good `sales.csv`, then upload an empty `sales.csv`, then assert the original bytes, the original rows and the metadata are unchanged, and that no `.part`/`.bak` files remain)

## Acceptance Criteria
- All requirements have passing tests
- No Flask imports in `app/services/`, and no import of `app.services.csv_downloader`
- Code follows code standards

## Implementation Notes
(Left blank - filled in by programmer during implementation)
