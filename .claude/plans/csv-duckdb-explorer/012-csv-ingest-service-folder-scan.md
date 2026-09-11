# Task 012: CsvIngestService — Folder Scan

**Status**: pending
**Depends on**: 001, 002, 003, 005, 007, 011
**Retry count**: 0

## Description
Add `scan_folder` to `CsvIngestService`. It ingests new or changed CSVs from the drop folder. It skips files that haven't changed and files the user deleted, and it reports per-file errors and table-name collisions without aborting the scan. URL ingest is a separate service (task 021).

## Context
- Related files (modify): `app/services/csv_ingest_service.py`, `tests/unit/services/test_csv_ingest_service.py`. Task 021 runs in the same batch but only creates **new** files (`url_ingest_service.py` and its own tests), so there's no conflict.
- **No constructor change.** Don't add a `downloader` parameter.
- `scan_folder() -> ScanResult`:
  - Look at the top-level files in `csv_dir` (not recursive) whose suffix, lowercased, is `.csv`. Ignore hidden files (which covers the `.part` / `.bak` staging files from tasks 010 and 011) and `*.part`.
  - **Glob characters:** DuckDB's `read_csv_auto` treats `*`, `?` and `[` in a path as glob patterns. Record a file whose name contains any of them in `errors[filename] = "Skipped: file name contains *, ? or ["` and don't ingest it. Uploads and downloads are already safe, because `secure_filename` strips these characters.
  - Sort files by name for deterministic order.
  - **Table-name collisions within one scan:** keep a `seen: dict[table_name, filename]`. If a later file maps to a table an earlier file in the same scan already claimed (e.g. `my-data.csv` and `my_data.csv` both → `my_data`), don't ingest it. Record `errors[filename] = f"Skipped: maps to the same dataset '{table}' as {seen[table]}"`. Without this, the two files overwrite each other on **every** scan and startup, because each one's metadata never matches the other file, which defeats skip-unchanged.
  - **Skip unchanged** (add the file to `skipped`) when an existing metadata record, looked up by `table_name_from_filename(name)`, has the same `original_filename`, `file_size` and `file_mtime`. **This applies whether or not the record is marked deleted.** A deleted dataset whose file hasn't changed stays deleted (the user chose "remember deletions"). If the file later changes (different size or mtime), it's re-ingested, and `ingest_file` clears the marker (task 011).
  - Otherwise `ingest_file(path, DatasetSource.FOLDER)`.
  - An `IngestError` for one file is caught and stored in `errors[filename] = str(exc)`, and the scan carries on. A `ValueError` from `table_name_from_filename` becomes an error entry too.
- **Tests:** real in-memory repositories, a `tmp_path` csv_dir and a fixed clock. The unloadable file is the canonical 0-byte CSV from task 005. To simulate a changed file, rewrite it and use `os.utime` to set a different mtime. To simulate a deletion, call `metadata.mark_deleted(name, clock())` and `repository.drop_table(name)` directly; `DatasetService` is in a parallel task.

## Requirements (Test Descriptions)
- [ ] `test_scan_folder_ingests_new_csv_files`
- [ ] `test_scan_folder_skips_files_unchanged_since_last_ingest`
- [ ] `test_scan_folder_reingests_files_whose_size_or_mtime_changed`
- [ ] `test_scan_folder_does_not_resurrect_deleted_dataset_until_its_file_changes`
- [ ] `test_scan_folder_collects_errors_for_bad_files_and_continues`
- [ ] `test_scan_folder_ignores_non_csv_hidden_partial_and_glob_character_files`
- [ ] `test_scan_folder_reports_table_name_collision_and_is_stable_across_rescans` (`my-data.csv` and `my_data.csv`: the first scan ingests one and reports the other; the second scan ingests nothing)

## Acceptance Criteria
- All requirements have passing tests
- Code follows code standards
- No decrease in test coverage

## Implementation Notes
(Left blank - filled in by programmer during implementation)
