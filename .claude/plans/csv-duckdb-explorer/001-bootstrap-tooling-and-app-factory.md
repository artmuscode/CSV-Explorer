# Task 001: Bootstrap Tooling, Config & App Factory Skeleton

**Status**: completed
**Depends on**: none
**Retry count**: 0

## Description
Set up uv, `pyproject.toml`, ruff and pytest, then create the `app` package with a `create_app` factory and `Config`/`TestConfig` classes. Every later task builds and tests against this foundation.

## Context
- Related files (new): `pyproject.toml`, `.python-version`, `app/__init__.py`, `app/config.py`, `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/conftest.py`, `tests/unit/test_config.py`, `tests/integration/test_app_factory.py`
- Related files (delete with `git rm -r`): `main.py`, `templates/` (whole folder), `assets/` (whole folder), `__pycache__/main.cpython-313.pyc`. **Delete them in this task** (moved here from task 004): `main.py` is tracked and isn't ruff-formatted (single quotes, extra blank lines), so `uv run ruff format --check .` would fail this task's acceptance if it were left in place. Nothing later depends on these files.
- `uv` must be on PATH. If it isn't, mark the task **blocked** and say "run `brew install uv`". Do not pip-install into the old `venv/`.
- Create an empty `data/csv/.gitkeep` and commit it. `.gitignore` already ignores `data/csv/*` except `.gitkeep`, so dropped and downloaded CSVs never get committed.
- `pyproject.toml`:
  - `[project]` name `csv-explorer`, `requires-python = ">=3.13"`, dependencies `flask>=3.1`, `duckdb>=1.1`, `requests>=2.32`
  - `[dependency-groups] dev = ["pytest", "pytest-xdist", "pytest-cov", "ruff"]`
  - `[tool.pytest.ini_options] testpaths = ["tests"]`, `addopts = "-ra"`, `pythonpath = ["."]`. The uv project is virtual (the `app` package isn't installed), so `pythonpath` keeps `import app` and `from tests.fakes import ...` (task 010) working from any test directory.
  - **Only this task edits `pyproject.toml` / `uv.lock`.** Later tasks run in parallel batches and must not `uv add` anything. If a later task truly needs a new dependency, it stops and says so in its Implementation Notes.
- Test packages: every test directory gets an empty `__init__.py`. This task creates `tests/`, `tests/unit/` and `tests/integration/`. Whichever task first creates a subdirectory adds its `__init__.py`: `tests/unit/models/` (002), `tests/unit/repositories/` (003), `tests/unit/services/` (008).
  - `[tool.ruff]` exactly as in `.claude/code-standards.md`
  - Then run `uv sync`.
- `Config` class attributes:
  - `SECRET_KEY` (dev default)
  - `CSV_DIR = BASE_DIR / "data" / "csv"`
  - `DUCKDB_PATH = BASE_DIR / "data" / "app.duckdb"`
  - `PAGE_SIZE = 25`, `MAX_PAGE_SIZE = 100`
  - `MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024`, `MAX_CONTENT_LENGTH = 50 * 1024 * 1024`
  - `DOWNLOAD_TIMEOUT = 30`
  - `ALLOW_PRIVATE_URLS = False`
  - `SCAN_ON_STARTUP = True`
- `TestConfig(Config)`: `TESTING = True`, `SCAN_ON_STARTUP = False`, `SECRET_KEY = "test"`.
- `create_app(config_class: type = Config, overrides: Mapping[str, Any] | None = None) -> Flask`, applied in this order:
  1. `from_object(config_class)`
  2. `from_prefixed_env("CSV_EXPLORER")`
  3. `overrides`
  4. Coerce `CSV_DIR`/`DUCKDB_PATH` to `Path`
  5. `mkdir(parents=True, exist_ok=True)` for `CSV_DIR` and `DUCKDB_PATH.parent`

  Don't build any services yet (task 014 does that).
- `tests/conftest.py`:
  - a `make_app` fixture returns a factory `(**overrides) -> Flask`. It calls `create_app(TestConfig, overrides={"CSV_DIR": tmp_path / "csv", "DUCKDB_PATH": tmp_path / "test.duckdb", **overrides})`.
  - an `app` fixture returns `make_app()`, and a `client` fixture wraps it.
  - **Rule for every later task:** tests never call `create_app(TestConfig)` without `tmp_path` overrides. `TestConfig` still inherits the real `data/` paths, so a bare call would create `data/csv/` and open `data/app.duckdb`. That breaks the "never touch `data/`" rule and makes xdist workers, or a running dev server, collide on DuckDB's file lock. Use `app` or `make_app(...)` whenever you need non-default config (e.g. `make_app(SCAN_ON_STARTUP=True)`).
- Patterns to follow: `.claude/architecture.md`, `.claude/code-standards.md`

## Requirements (Test Descriptions)
- [x] `test_create_app_returns_flask_app_instance`
- [x] `test_create_app_applies_test_config_testing_flag`
- [x] `test_create_app_applies_overrides_after_config_class`
- [x] `test_create_app_reads_csv_explorer_prefixed_environment_variables`
- [x] `test_create_app_creates_csv_dir_when_missing`
- [x] `test_default_config_page_size_is_25_and_max_page_size_is_100`
- [x] `test_default_config_blocks_private_urls_and_scans_on_startup`

## Acceptance Criteria
- All requirements have passing tests (`uv run pytest -n auto`)
- `uv run ruff check .` and `uv run ruff format --check .` pass (`venv/` and `.venv/` are gitignored, and ruff respects `.gitignore`)
- `uv.lock` is created and committed
- The legacy `main.py`, `templates/`, `assets/` and `__pycache__/main.cpython-313.pyc` are removed from git

## Implementation Notes
- `uv sync` created `.venv/` and `uv.lock` against Python 3.13.5. All dev/runtime deps installed cleanly (flask 3.1.3, duckdb 1.5.5, requests 2.34.2, ruff 0.16.7, pytest 9.1.1, pytest-xdist, pytest-cov).
- Removed legacy `main.py`, `templates/`, `assets/` via `git rm -r` and deleted the stray tracked `__pycache__/main.cpython-313.pyc`; these deletions are staged/in the working tree for the orchestrator's single commit.
- `Config` and `create_app` were each implemented as one cohesive unit rather than incrementally per test, since the task spec defines them as single, indivisible behaviors (a config class listing all its attributes together; a factory applying one fixed, ordered config-merge algorithm). Consequently `test_default_config_blocks_private_urls_and_scans_on_startup` and all `test_create_app_*` tests after the first (`test_create_app_returns_flask_app_instance`) passed immediately once written — documented here per the "note over-implementation and move on" rule rather than artificially splitting `create_app` into meaningless partial versions.
- `app.config.from_prefixed_env("CSV_EXPLORER")` uses `json.loads` internally, so `CSV_EXPLORER_PAGE_SIZE=7` becomes the int `7`, not the string `"7"` — reflected in the test assertion.
- Created `data/csv/.gitkeep` (verified it is NOT excluded by `.gitignore`'s `!data/csv/.gitkeep` negation via `git check-ignore`).
- Full suite: `uv run pytest -n auto` -> 7 passed. `uv run ruff check .` -> All checks passed. `uv run ruff format --check .` -> already formatted.
- Left the old `venv/` directory in place (already gitignored, untouched per task scope) alongside the new uv-managed `.venv/`.
