# CSV Explorer (Flask + DuckDB)

A Flask app that ingests CSV files, either dropped or uploaded into a folder or downloaded from a URL, into DuckDB and shows them as paginated, filterable tables built with Alpine.js and Tailwind CSS 4.

## Tech Stack

- **Language**: Python 3.13
- **Framework**: Flask 3.1 (app factory + blueprints)
- **Database**: DuckDB
- **Frontend**: Jinja2, Alpine.js 3, Tailwind CSS 4 (standalone CLI)
- **Testing**: pytest, pytest-xdist, pytest-cov
- **Linting**: ruff (lint + format)
- **Deps**: uv + `pyproject.toml`

## Core Principles

1. **TDD first**: Red → Green → Refactor for every task. No production code without a failing test.
2. **Layered OOP**: blueprints → services → repository → DuckDB, with dependencies injected through constructors.
3. **SQL lives only in `DuckDBRepository`**: routes and services never write SQL.
4. **Secure ingest**: parameterized SQL, validated identifiers, sanitized file names, capped URL downloads.
5. **Server-side pagination and filtering**: Alpine.js holds UI state and the server does the querying.

## Project Structure

- `app/`: `create_app()` factory, `config.py`, `models/` (dataclass DTOs), `repositories/`, `services/`, `blueprints/`, `templates/`, `static/`
- `data/csv/`: CSV drop folder. `data/app.duckdb` is the database (gitignored).
- `tests/unit/` mirrors `app/`. `tests/integration/` holds Flask test-client tests.

## Commands

```bash
uv run pytest -n auto                                   # tests (parallel)
uv run ruff check --fix . && uv run ruff format .       # lint + format
uv run flask --app app run --debug                      # dev server
./bin/tailwindcss -i app/static/css/input.css -o app/static/css/app.css --watch  # CSS
```

## Key Rules

- Bind SQL values with `?`. Validate table and column names against the schema, then quote them.
- No Flask imports in `services/` or `repositories/`.
- Keep route handlers thin: parse → call service → render/jsonify.
- DTOs are `@dataclass(frozen=True, slots=True)`. No loose dicts between layers.
- Type hints on all public signatures. PEP 8 naming (snake_case, PascalCase classes).
- Uploaded or downloaded file names go through `secure_filename`, and only `.csv` is accepted.
- Never render CSV data with `|safe` or `x-html`.
- Tests never hit the network or `data/app.duckdb`. Use `tmp_path` and in-memory DuckDB.
- Keep coverage at 80% or higher.

## Detailed Configuration

Project configuration files are in `.claude/`:
- `architecture.md`: technical patterns, structure, data flow
- `testing.md`: test configuration and commands
- `code-standards.md`: coding conventions and security rules
- `pipeline.md`: workflow agents
