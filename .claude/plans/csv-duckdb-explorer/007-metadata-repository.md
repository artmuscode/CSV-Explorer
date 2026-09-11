# Task 007: MetadataRepository (`_datasets`)

**Status**: pending
**Depends on**: 001, 002, 003
**Retry count**: 0

## Description
Create `MetadataRepository`, which stores one row per dataset in an internal `_datasets` DuckDB table: file name, source, URL, row count, file size/mtime and ingest time. It powers the dataset list and lets folder scans skip unchanged files.

## Context
- Related files (new): `app/repositories/metadata_repository.py`, `tests/unit/repositories/test_metadata_repository.py`
- Constructor: `MetadataRepository(connection: duckdb.DuckDBPyConnection)`. Use `self._conn.cursor()` per call.
- `ensure_schema()` runs `CREATE TABLE IF NOT EXISTS _datasets (name VARCHAR PRIMARY KEY, original_filename VARCHAR NOT NULL, source VARCHAR NOT NULL, source_url VARCHAR, row_count BIGINT NOT NULL, file_size BIGINT, file_mtime DOUBLE, ingested_at TIMESTAMP NOT NULL, deleted_at TIMESTAMP)`.
- Methods:
  - `upsert(dataset: Dataset) -> None`: `INSERT OR REPLACE INTO _datasets VALUES (?, ...)`. It writes `dataset.deleted_at` too, so re-ingesting (a Dataset with `deleted_at=None`) clears a deletion marker.
  - `get(name: str) -> Dataset | None`: returns the record **including deleted ones**. The folder scan (task 012) needs a deleted record's `file_size` / `file_mtime` to decide whether to skip.
  - `list_all() -> list[Dataset]`: `WHERE deleted_at IS NULL ORDER BY ingested_at DESC, name`. Deleted datasets are hidden.
  - `mark_deleted(name: str, deleted_at: datetime) -> None`: `UPDATE _datasets SET deleted_at = ? WHERE name = ?`. It replaces the earlier hard `delete(name)`, because the user chose "remember deletions".
- `deleted_at` follows the same naive-UTC storage and UTC-on-read contract as `ingested_at` (below).
- Map rows to `Dataset` DTOs (`source` → `DatasetSource(value)`). All values are bound with `?`. Use an explicit column list in the INSERT (`INSERT OR REPLACE INTO _datasets (name, original_filename, ...) VALUES (?, ...)`) so the code doesn't depend on column order.
- **Timestamp contract (cross-task).** `Dataset.ingested_at` is always a tz-aware UTC datetime (task 002, and task 011's clock is `datetime.now(UTC)`). If you bind an aware datetime to a DuckDB `TIMESTAMP` column, DuckDB converts it through the session `TimeZone` (local wall time) and reads it back **naive**. Then `metadata.get(x).ingested_at == clock()` fails in tasks 011 and 013 through no fault of their own. `TIMESTAMPTZ` avoids that but depends on the local timezone and pytz. So:
  - on write, bind `ingested_at.astimezone(UTC).replace(tzinfo=None)` (naive UTC)
  - on read, return `value.replace(tzinfo=UTC)`
- Tests use `duckdb.connect(":memory:")`.

## Requirements (Test Descriptions)
- [ ] `test_ensure_schema_is_idempotent`
- [ ] `test_upsert_then_get_round_trips_dataset` (with a tz-aware UTC `ingested_at`, and asserts `get(...) == original`)
- [ ] `test_upsert_replaces_existing_record_with_same_name`
- [ ] `test_get_returns_none_for_unknown_name`
- [ ] `test_list_all_returns_datasets_newest_first`
- [ ] `test_mark_deleted_hides_dataset_from_list_all_but_get_still_returns_it`
- [ ] `test_upsert_clears_deletion_marker`

## Acceptance Criteria
- All requirements have passing tests
- Code follows code standards
- No decrease in test coverage

## Implementation Notes
(Left blank - filled in by programmer during implementation)
