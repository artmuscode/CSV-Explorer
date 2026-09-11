# Task 003: SQL Identifier & Table-Naming Helpers

**Status**: pending
**Depends on**: 001
**Retry count**: 0

## Description
Add pure helper functions for safely quoting DuckDB identifiers and for deriving a safe table name from a CSV file name. Table and column names can't be bound as SQL parameters, so these helpers are the one place identifier safety is handled.

## Context
- Related files (new): `app/repositories/__init__.py`, `app/repositories/identifiers.py`, `tests/unit/repositories/__init__.py`, `tests/unit/repositories/test_identifiers.py`
- **`app/repositories/__init__.py` stays empty, with no re-exports.** Tasks 005, 006 and 007 each add a module to this package in the same parallel batch (B3). If the package re-exported classes, all three would edit this file at once. Callers import from the module (`from app.repositories.duckdb_repository import DuckDBRepository`).
- `quote_identifier(name: str) -> str` → `'"' + name.replace('"', '""') + '"'`
- `quote_literal(value: str) -> str` → `"'" + value.replace("'", "''") + "'"`. This is the fallback for file paths passed to `read_csv_auto` in task 005, and only ever takes server-generated paths.
- `table_name_from_filename(filename: str) -> str`:
  1. Take the stem, dropping the `.csv` suffix case-insensitively, and lowercase it.
  2. Replace runs of non-`[a-z0-9]` characters with a single `_`.
  3. Strip leading and trailing `_`.
  4. Prefix `t_` if the result starts with a digit.
  5. Raise `ValueError` if nothing is left.

  Because leading underscores are stripped, a user table can never collide with the internal `_datasets` table.
- No dependency on `app.exceptions`. Callers wrap `ValueError` into `IngestError`.

## Requirements (Test Descriptions)
- [ ] `test_quote_identifier_wraps_name_in_double_quotes`
- [ ] `test_quote_identifier_escapes_embedded_double_quotes`
- [ ] `test_table_name_from_filename_lowercases_and_drops_csv_extension`
- [ ] `test_table_name_from_filename_replaces_non_alphanumeric_runs_with_single_underscore`
- [ ] `test_table_name_from_filename_prefixes_t_when_starting_with_digit`
- [ ] `test_table_name_from_filename_never_starts_with_underscore`
- [ ] `test_table_name_from_filename_raises_value_error_when_nothing_usable_remains`

## Acceptance Criteria
- All requirements have passing tests
- Code follows code standards
- No decrease in test coverage

## Implementation Notes
(Left blank - filled in by programmer during implementation)
