# Task 005: DuckDBRepository — Table Operations

**Status**: completed
**Depends on**: 001, 002, 003
**Retry count**: 0

## Description
Create `DuckDBRepository`, the class that owns user dataset tables. It creates or replaces a table from a CSV file, inspects columns, counts rows, and drops tables. Paged reads come in task 009.

## Context
- Related files (new): `app/repositories/duckdb_repository.py`, `tests/unit/repositories/test_duckdb_repository.py`
- Constructor: `DuckDBRepository(connection: duckdb.DuckDBPyConnection)`. Every method runs on `cur = self._conn.cursor()` so threaded requests are safe.
- Methods:
  - `create_table_from_csv(table: str, csv_path: Path) -> int`
    - **Empty-file check first:** if `csv_path.stat().st_size == 0`, raise `IngestError(f"Could not load {csv_path.name}: file is empty")` without calling DuckDB.
    - runs `CREATE OR REPLACE TABLE {quote_identifier(table)} AS SELECT * FROM read_csv_auto(?)`
    - **Latin-1 fallback** (the user asked for it): if that fails with a DuckDB error whose message mentions invalid unicode or UTF-8, retry once with `read_csv_auto(?, encoding = 'latin-1')`. DuckDB ≥ 1.1 decodes `latin-1` natively. Only if the retry also fails, raise `IngestError` using the retry's message. Other DuckDB errors are not retried.
    - then returns `count_rows(table)`
    - If DuckDB rejects the `?` parameter inside `read_csv_auto`, use `quote_literal(str(csv_path))` from task 003 instead.
    - Catch `duckdb.Error` and re-raise it as `IngestError` with a short readable message: `f"Could not load {csv_path.name}: {first_line}"`, where `first_line` is the first line of the DuckDB message, truncated to 200 characters. DuckDB CSV errors span several lines (with "Possible Solution" hints and the absolute server path). Those messages are flashed into Flask's roughly 4 KB cookie session (task 016), and long ones make the browser silently drop every flash. Chain the original error with `raise ... from exc` so the full text still reaches the logs.
  - `table_exists(table: str) -> bool`: `information_schema.tables` with a bound `table_name = ?` **and `table_schema = 'main'`**
  - `get_columns(table: str) -> list[Column]`: `information_schema.columns` filtered by `table_name = ?` **and `table_schema = 'main'`**, `ORDER BY ordinal_position`
  - Use `with self._conn.cursor() as cur:` so every cursor is closed.
  - `count_rows(table: str) -> int`
  - `drop_table(table: str) -> None`: `DROP TABLE IF EXISTS`
- Tests use `duckdb.connect(":memory:")` and write CSVs into `tmp_path`. Include a CSV whose header contains a space and a double quote, e.g. `first name,"say ""hi"""`.
- **Canonical "unloadable CSV" sample: a 0-byte file (`b""`).** This replaces the earlier invalid-UTF-8 sample, which the Latin-1 fallback now loads successfully, because every byte is valid Latin-1. Empty files are rejected by our own check, so the failure is deterministic whatever DuckDB's sniffer does. Tasks 011, 012, 016 and 019 use it wherever they need an ingest to fail.
- **DuckDB-level malformed sample (this task only).** Also find a non-empty file that DuckDB rejects even after the Latin-1 retry, e.g. an unterminated quote `b'id,name\n1,"abc\n'` or ragged rows `b'a,b\n1,2,3,4\n'`. Verify it by experiment and write the exact bytes in Implementation Notes. If no candidate fails reliably on the installed DuckDB version, say so there and parametrize the error-message test with the empty file only.
- **Latin-1 sample**: `"id,city\n1,Zürich\n".encode("latin-1")` must load, with the `city` value equal to `"Zürich"`.
- Patterns to follow: `app/repositories/identifiers.py` (quote every identifier); no Flask imports

## Requirements (Test Descriptions)
- [x] `test_create_table_from_csv_returns_number_of_rows_loaded`
- [x] `test_create_table_from_csv_replaces_existing_table_with_same_name`
- [x] `test_create_table_from_csv_raises_single_line_ingest_error_for_empty_or_malformed_csv` (parametrized over the empty file and the DuckDB-level malformed sample; the message is one line of 250 characters or fewer)
- [x] `test_create_table_from_csv_falls_back_to_latin1_when_utf8_decoding_fails`
- [x] `test_create_table_from_csv_supports_column_names_with_spaces_and_quotes`
- [x] `test_get_columns_returns_names_and_types_in_file_order`
- [x] `test_drop_table_removes_table_so_table_exists_is_false`

## Acceptance Criteria
- All requirements have passing tests
- No SQL string-formats user-supplied values; identifiers only go through `quote_identifier`
- Code follows code standards

## Implementation Notes
- Verified on the installed DuckDB 1.5.5: an unterminated quote (`b'id,name\n1,"abc\n'`) and ragged rows (`b'a,b\n1,2,3,4\n'`) both load *successfully* — DuckDB's sniffer/parallel CSV reader tolerates them (auto-detects quoting/columns or null-pads). They are **not** usable as the "DuckDB-level malformed" sample.
- Found a reliable DuckDB-level malformed sample instead: `bytes(range(256))` (256 raw bytes, all byte values 0-255). DuckDB's dialect sniffer raises `Invalid Input Error: Error when sniffing file "...": It was not possible to automatically detect the CSV parsing dialect...` — a multi-line error not related to unicode/UTF-8, so it is not retried with the Latin-1 fallback and reaches `IngestError` directly. Used as the `duckdb_sniffing_failure` parametrize case alongside the empty-file (`b""`) case.
- `create_table_from_csv` binds the CSV path via the `?` parameter of `read_csv_auto` (bound parameter, not `quote_literal`) — DuckDB 1.5.5 accepts it fine, so the `quote_literal` fallback described in Context was not needed.
- Latin-1 retry trigger: checks whether the lowercased DuckDB error message contains `"invalid unicode"` or `"utf-8"` (DuckDB's actual message is "Invalid unicode (byte sequence mismatch) detected. This file is not utf-8 encoded."). Only that class of error is retried with `encoding = 'latin-1'`.
- Every method wraps its work in `with self._conn.cursor() as cur:` (confirmed `duckdb.DuckDBPyConnection.cursor()` supports the context-manager protocol on 1.5.5).
- `table_exists` / `get_columns` filter on both `table_name = ?` and `table_schema = 'main'`, both bound parameters.
