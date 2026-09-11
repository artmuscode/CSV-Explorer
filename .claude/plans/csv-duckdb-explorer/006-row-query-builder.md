# Task 006: RowQueryBuilder — Search / Filter / Sort SQL

**Status**: pending
**Depends on**: 001, 002, 003
**Retry count**: 0

## Description
Create `RowQueryBuilder`, a pure class that turns a table name, its columns and a `RowQuery` into parameterized SELECT and COUNT statements. It is the single place where user search, filter and sort input becomes SQL, and it rejects unknown columns.

## Context
- Related files (new): `app/repositories/row_query_builder.py`, `tests/unit/repositories/test_row_query_builder.py`
- API: `RowQueryBuilder().build(table: str, columns: list[Column], query: RowQuery) -> BuiltQuery`. `BuiltQuery` is a frozen dataclass with `select_sql`, `select_params`, `count_sql` and `count_params`.
- Rules:
  - **Search** (non-empty `query.search`): `(CAST("c1" AS VARCHAR) ILIKE ? ESCAPE '\' OR CAST("c2" AS VARCHAR) ILIKE ? ESCAPE '\' ...)`, with one `%term%` parameter per column
  - **Column filters**: each `{col: value}` → `CAST("col" AS VARCHAR) ILIKE ? ESCAPE '\'`, ANDed together and with the search clause
  - **Escaping**: escape `\`, `%` and `_` in user input before wrapping it in `%...%`
  - **Ordering**: default `ORDER BY rowid`. With `sort_by` it becomes `ORDER BY "col" ASC|DESC NULLS LAST, rowid`. The direction comes only from the `SortDirection` enum.
  - **A user column named `rowid`** (case-insensitive) hides DuckDB's built-in `rowid`, which would make ordering unstable. In that case use the tiebreaker `ORDER BY` every column in `ordinal_position` order instead. Cover it with a short case inside the sort test; no extra requirement.
  - **Paging**: `LIMIT ? OFFSET ?` from `query.per_page` / `query.offset`
  - **Count**: `SELECT COUNT(*)` with the same WHERE clause and params
  - **Validation**: a filter or `sort_by` column not in `columns` raises `InvalidQueryError`
  - **Quoting**: identifiers only go through `quote_identifier`
- **Test by behavior.** Create a small in-memory DuckDB table in each test, run the built SQL with its params, and assert on the rows that come back. Only assert on raw SQL text where that's unavoidable (e.g. the `LIMIT ? OFFSET ?` params).

## Requirements (Test Descriptions)
- [ ] `test_build_without_filters_returns_rows_in_insertion_order_with_limit_and_offset`
- [ ] `test_build_search_matches_any_column_case_insensitively`
- [ ] `test_build_column_filters_are_combined_with_and`
- [ ] `test_build_treats_percent_and_underscore_in_user_input_literally`
- [ ] `test_build_sorts_by_requested_column_and_direction_with_nulls_last`
- [ ] `test_build_raises_invalid_query_error_for_unknown_filter_column`
- [ ] `test_build_raises_invalid_query_error_for_unknown_sort_column`

## Acceptance Criteria
- All requirements have passing tests
- No user-supplied value is interpolated into SQL text
- Code follows code standards

## Implementation Notes
(Left blank - filled in by programmer during implementation)
