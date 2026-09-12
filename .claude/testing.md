# Testing Configuration

## Test Framework
pytest, with pytest-xdist (parallel runs) and pytest-cov (coverage). Dependencies are managed by uv in `pyproject.toml`.

## TDD Methodology

Each task follows strict Red → Green → Refactor:

1. Write failing test for one requirement
2. Write minimum code to pass
3. Refactor while tests stay green
4. Repeat for next requirement
5. Commit when task complete

## Commands
```bash
# Run all tests (parallel)
uv run pytest -n auto

# Run all tests (sequential, for debugging failures)
uv run pytest

# Run specific test file
uv run pytest tests/unit/services/test_csv_ingest_service.py

# Run a single test
uv run pytest tests/unit/services/test_csv_ingest_service.py::test_ingest_url_rejects_non_http_scheme

# Run with coverage
uv run pytest -n auto --cov=app --cov-report=term-missing --cov-fail-under=80
```

## Parallel Execution
- **Default**: Always run tests in parallel unless debugging a specific failure
- Parallel command: `uv run pytest -n auto`
- Sequential fallback: `uv run pytest` (use only when parallel causes flaky failures)
- Tests must not share state. Every test gets its own DuckDB database and CSV directory, so xdist workers can't collide.

## Test File Locations
- Unit tests: `tests/unit/`, mirroring `app/` (e.g. `app/services/dataset_service.py` → `tests/unit/services/test_dataset_service.py`)
- Integration tests: `tests/integration/`, for Flask test-client and route tests covering the full blueprint → service → repository → DuckDB path
- Shared fixtures: `tests/conftest.py`

## Coverage Requirements
- Minimum: 80%
- New code must have tests

## Test Naming Convention
- Test files: `test_<module>.py`
- Test functions: `test_<behavior>`, e.g. `test_get_page_returns_second_page_of_rows`, `test_ingest_url_rejects_non_http_scheme`
- Group related tests with plain functions. Only use `class Test<Subject>:` when shared setup makes it clearer.

## Common Patterns

### DuckDB
- Unit tests for the repository use an in-memory database: `duckdb.connect(":memory:")`, or a `tmp_path / "test.duckdb"` file.
- Never touch `data/app.duckdb` from tests.

### CSV fixtures
- Write small CSVs into `tmp_path` inside the test or a fixture. Don't depend on files in `data/csv/`.
- Include edge cases: empty file, header only, quoted commas, mixed types, unicode, duplicate column names.

### Flask app
- `app` fixture: `create_app(TestConfig)` with `CSV_DIR` and `DUCKDB_PATH` pointed at `tmp_path`
- `client` fixture: `app.test_client()`
- Assert on status codes, JSON payloads, and key rendered HTML fragments.

### Network (URL ingest)
- **Never make real network calls in tests.** Mock the HTTP layer with `monkeypatch` or `unittest.mock.patch`.
- Cover: non-http(s) scheme rejected, timeout, non-200 response, oversized download, non-CSV content.

### Mocking strategy
- Services take their collaborators through the constructor, so unit tests can pass fakes or `Mock(spec=DuckDBRepository)`.
- Don't mock the thing under test. Repository tests use a real in-memory DuckDB.
