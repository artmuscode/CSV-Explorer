# Task 003: SQL Identifier & Table-Naming Helpers

**Status**: completed
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
- [x] `test_quote_identifier_wraps_name_in_double_quotes`
- [x] `test_quote_identifier_escapes_embedded_double_quotes`
- [x] `test_table_name_from_filename_lowercases_and_drops_csv_extension`
- [x] `test_table_name_from_filename_replaces_non_alphanumeric_runs_with_single_underscore`
- [x] `test_table_name_from_filename_prefixes_t_when_starting_with_digit`
- [x] `test_table_name_from_filename_never_starts_with_underscore`
- [x] `test_table_name_from_filename_raises_value_error_when_nothing_usable_remains`

## Acceptance Criteria
- All requirements have passing tests
- Code follows code standards
- No decrease in test coverage

## Implementation Notes
- Created `app/repositories/identifiers.py` with `quote_identifier`, `quote_literal`, and
  `table_name_from_filename`, plus empty `app/repositories/__init__.py` (no re-exports, per
  task instructions) and `tests/unit/repositories/__init__.py`.
- Added `test_quote_literal_wraps_value_in_single_quotes` and
  `test_quote_literal_escapes_embedded_single_quotes` in addition to the listed requirements,
  since `quote_literal` is part of this module's documented contract (used by task 005) and
  needed test coverage; not part of the original checklist so left un-checkboxed above.
- `table_name_from_filename` uses `re.sub(r"\.csv$", "", filename, flags=re.IGNORECASE)` to
  drop the extension, lowercases, replaces non-`[a-z0-9]` runs with `_` via
  `re.sub(r"[^a-z0-9]+", "_", ...)`, strips leading/trailing `_`, prefixes `t_` if the result
  starts with a digit, and raises `ValueError` if nothing remains.
- `uv run pytest tests/unit/repositories/test_identifiers.py -v`: 9 passed.
- `uv run ruff check` and `uv run ruff format --check` on all new files: clean.
