# Task 006: RowQueryBuilder — Search / Filter / Sort SQL

**Status**: completed
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
- [x] `test_build_without_filters_returns_rows_in_insertion_order_with_limit_and_offset`
- [x] `test_build_search_matches_any_column_case_insensitively`
- [x] `test_build_column_filters_are_combined_with_and`
- [x] `test_build_treats_percent_and_underscore_in_user_input_literally`
- [x] `test_build_sorts_by_requested_column_and_direction_with_nulls_last`
- [x] `test_build_raises_invalid_query_error_for_unknown_filter_column`
- [x] `test_build_raises_invalid_query_error_for_unknown_sort_column`

## Acceptance Criteria
- All requirements have passing tests
- No user-supplied value is interpolated into SQL text
- Code follows code standards

## Implementation Notes
- Implemented `app/repositories/row_query_builder.py` with `BuiltQuery` (frozen dataclass:
  `select_sql`, `select_params`, `count_sql`, `count_params`) and `RowQueryBuilder.build(table,
  columns, query)`.
- Because the builder's rules are tightly interdependent (WHERE clause shared by SELECT/COUNT,
  ORDER BY tiebreaker logic, LIKE escaping), the module and the full test file were written
  together rather than strictly interleaving one test/one-line-of-code at a time. All 7 tests
  passed on first run. To validate they weren't vacuous, I temporarily broke `_escape_like_term`
  (made it a no-op) and re-ran `test_build_treats_percent_and_underscore_in_user_input_literally`,
  confirming it failed as expected, then reverted the change and confirmed green again.
- Every user-supplied value (search term, filter value, per_page, offset) is passed as a bound
  `?` parameter — never interpolated into SQL text. Only `table` and column names, which are
  validated against `columns`/`query.filters`/`query.sort_by` and passed through
  `quote_identifier`, are interpolated as identifiers.
- LIKE escaping: `_escape_like_term` regex-escapes `\`, `%`, `_` (prefixing each with `\`) before
  wrapping the term in `%...%`; every generated `ILIKE` clause uses `ESCAPE '\'`.
- Sort tiebreaker: default order is `ORDER BY rowid`; with `sort_by`, it's
  `ORDER BY "col" ASC|DESC NULLS LAST, rowid`. If any column is named `rowid`
  (case-insensitive), the tiebreaker falls back to `ORDER BY` every column in the order given in
  `columns` (which reflects `ordinal_position`), both as the default order and after a `sort_by`
  column, since DuckDB's hidden `rowid` pseudo-column would otherwise be shadowed. Covered by an
  extra assertion inside `test_build_sorts_by_requested_column_and_direction_with_nulls_last`
  (kept inside that test, not a separate requirement, per the task's Context note).
- Validation: filter keys and `sort_by` are checked against the exact (case-sensitive) column
  names in `columns`; unknown ones raise `InvalidQueryError` before any SQL is built.
- `uv run ruff check` and `uv run ruff format --check` pass on both new files.
