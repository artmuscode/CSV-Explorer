# Task 013: DatasetService

**Status**: completed
**Depends on**: 001, 002, 003, 005, 006, 007, 009
**Retry count**: 0

## Description
Create `DatasetService`, the read and delete side of the domain. It lists datasets, turns raw request parameters into a validated `RowQuery`, returns pages of rows, and deletes datasets. Blueprints stay thin and just pass raw strings to it.

## Context
- Related files (new): `app/services/dataset_service.py`, `tests/unit/services/test_dataset_service.py`
- Constructor: `DatasetService(repository: DuckDBRepository, metadata: MetadataRepository, default_page_size: int = 25, max_page_size: int = 100, clock: Callable[[], datetime] = lambda: datetime.now(UTC))`
- Methods:
  - `list_datasets() -> list[Dataset]` → `metadata.list_all()`, which already excludes deleted datasets (task 007)
  - `get_dataset(name: str) -> Dataset`: `DatasetNotFoundError` if metadata has no record for it **or the record is marked deleted** (`is_deleted`)
  - `build_query(page: str | None, per_page: str | None, search: str | None, filters: Mapping[str, str], sort_by: str | None, sort_dir: str | None) -> RowQuery`:
    - An absent or blank value means use the default.
    - A non-integer `page`/`per_page` → `InvalidQueryError`.
    - `page < 1` or `page > MAX_PAGE_NUMBER` (a module constant, `1_000_000`) → `InvalidQueryError`. Without the upper bound, a huge `page` overflows DuckDB's BIGINT `OFFSET` parameter and returns a 500.
    - `per_page` is clamped to `[1, max_page_size]`.
    - `sort_dir` must be `asc`/`desc`, case-insensitive; anything else → `InvalidQueryError`.
    - `search` and filter values are stripped, and blank filter values are dropped.
    - Column validity is **not** checked here. `RowQueryBuilder` does that.
  - `get_page(name: str, query: RowQuery) -> Page`: `get_dataset(name)`, then `repository.fetch_page(name, query)`
  - `delete_dataset(name: str) -> None`: `get_dataset(name)`, then `repository.drop_table(name)` and `metadata.mark_deleted(name, clock())`. The CSV file stays on disk. Because the metadata row is kept with a deletion marker, the folder scan won't bring the dataset back unless the file changes (task 012). The user chose "remember deletions".
- Tests use real in-memory repositories with small tables created through `repository.create_table_from_csv` and `metadata.upsert`.

## Requirements (Test Descriptions)
- [x] `test_list_datasets_returns_metadata_newest_first`
- [x] `test_get_page_raises_dataset_not_found_for_unknown_or_deleted_dataset` (parametrized)
- [x] `test_get_page_returns_filtered_page_from_repository`
- [x] `test_build_query_clamps_per_page_to_max_page_size`
- [x] `test_build_query_raises_invalid_query_error_for_non_integer_or_out_of_range_page` (parametrized: `"abc"`, `"0"`, `"-1"`, `"1000001"`)
- [x] `test_build_query_drops_blank_filter_values`
- [x] `test_delete_dataset_drops_table_and_hides_it_from_list_while_keeping_marker` (after the delete, `list_datasets()` excludes it, and `metadata.get(name).is_deleted` is true)

## Acceptance Criteria
- All requirements have passing tests
- No Flask imports in `app/services/`
- Code follows code standards

## Implementation Notes
- `build_query` added: parses `page`/`per_page` strings via `int()`, catching `ValueError` into
  `InvalidQueryError`; `page` bounds checked against `1..MAX_PAGE_NUMBER` (module constant
  `1_000_000`); `per_page` clamped to `[1, max_page_size]` (never raises on out-of-range, only on
  non-integer input); `sort_dir` parsed case-insensitively via `SortDirection(...)`, raising
  `InvalidQueryError` on anything else; blank/whitespace-only `page`, `per_page`, `search`,
  `sort_by`, `sort_dir` fall back to defaults; filter values are stripped and blank ones dropped.
- `delete_dataset` added: calls `get_dataset` (so it 404s on unknown/already-deleted names), then
  `repository.drop_table(name)` and `metadata.mark_deleted(name, self._clock())`. Leaves the CSV
  file on disk untouched.
- All 11 requirement tests plus the earlier 4 pass together (`uv run pytest
  tests/unit/services/test_dataset_service.py -q` → 11 passed). `ruff check` / `ruff format
  --check` clean on both changed files.
