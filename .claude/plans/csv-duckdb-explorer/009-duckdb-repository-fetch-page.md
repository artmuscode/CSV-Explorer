# Task 009: DuckDBRepository.fetch_page

**Status**: pending
**Depends on**: 001, 002, 003, 005, 006
**Retry count**: 0

## Description
Add `fetch_page` to `DuckDBRepository`. It uses `RowQueryBuilder` to run a filtered, sorted, paginated query and returns a `Page` DTO whose rows are JSON-safe dicts.

## Context
- Related files (modify): `app/repositories/duckdb_repository.py`, `tests/unit/repositories/test_duckdb_repository.py`
- The constructor gains an optional `query_builder: RowQueryBuilder | None = None`, defaulting to `RowQueryBuilder()`.
- `fetch_page(table: str, query: RowQuery) -> Page`:
  1. If `not self.table_exists(table)`, raise `DatasetNotFoundError`.
  2. `columns = self.get_columns(table)`.
  3. `built = builder.build(table, columns, query)`.
  4. Execute the count and select statements with their params.
  5. Turn each tuple into a `{column.name: value}` dict.
  6. Return `Page(rows, columns, query.page, query.per_page, total)`.
- Value normalization goes in a private `_to_json_safe(value)`:
  - `date` / `datetime` / `time` → `.isoformat()`
  - `timedelta` → `str`
  - `Decimal` → `str`
  - `UUID` → `str`
  - `bytes` → `.hex()`
  - **non-finite floats** (`nan`, `inf`, `-inf`) → `"NaN"`, `"Infinity"`, `"-Infinity"`. DuckDB's sniffer types a column holding `1.5,NaN,inf` as DOUBLE. Python's `json.dumps` then emits bare `NaN` / `Infinity` tokens, which aren't valid JSON, so `response.json()` in the Alpine component and `JSON.parse` of the `initial-page` block both throw and the table page breaks.
  - everything else (None, int, finite float, str, bool) passes through unchanged
- `InvalidQueryError` from the builder propagates unchanged.
- Tests use in-memory DuckDB. Create typed tables directly with SQL (e.g. a `DATE`, `TIMESTAMP` and `DECIMAL(10,2)` column) to exercise normalization.

## Requirements (Test Descriptions)
- [ ] `test_fetch_page_returns_requested_slice_of_rows`
- [ ] `test_fetch_page_total_reflects_filtered_row_count`
- [ ] `test_fetch_page_returns_rows_as_dicts_keyed_by_column_name`
- [ ] `test_fetch_page_serializes_dates_and_timestamps_as_iso_strings`
- [ ] `test_fetch_page_serializes_decimals_as_strings`
- [ ] `test_fetch_page_serializes_non_finite_floats_as_strings` (assert `json.dumps(page.to_dict(), allow_nan=False)` succeeds)
- [ ] `test_fetch_page_raises_dataset_not_found_for_unknown_table`
- [ ] `test_fetch_page_beyond_last_page_returns_empty_rows_with_total`

## Acceptance Criteria
- All requirements have passing tests
- Code follows code standards
- No decrease in test coverage

## Implementation Notes
(Left blank - filled in by programmer during implementation)
