# Code Standards

## Style Guide
PEP 8, enforced by ruff. Configure it in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "N"]
```

## Linting
```bash
# Check for issues
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .
```

## Formatting
```bash
# Format
uv run ruff format .

# Verify formatting (CI / pre-commit)
uv run ruff format --check .
```

## Pre-commit Checks
- `uv run ruff check .` passes
- `uv run ruff format --check .` passes
- `uv run pytest -n auto` passes
- Coverage stays at or above 80%

## Naming Conventions
- Classes: `PascalCase` (`DuckDBRepository`, `CsvIngestService`)
- Functions / methods: `snake_case`
- Variables: `snake_case`
- Constants: `SCREAMING_SNAKE_CASE` (`PAGE_SIZE`, `MAX_DOWNLOAD_BYTES`)
- Modules / files: `snake_case.py`
- Templates: `snake_case.html`
- Private helpers: leading underscore (`_quote_identifier`)

## Code Structure Rules
- One primary class per module. Name the module after the class (`duckdb_repository.py` → `DuckDBRepository`).
- Type hints on every public function and method signature, using modern syntax (`list[str]`, `str | None`).
- Docstrings on public classes and on non-obvious public methods. Skip docstrings that just restate the name.
- Use `@dataclass(frozen=True, slots=True)` for DTOs unless mutation is needed.
- Pass collaborators into `__init__`. Don't reach into globals or `current_app` from services or repositories.
- Keep route handlers thin: parse the request → call a service → render or jsonify.
- Raise domain exceptions (e.g. `IngestError`, `DatasetNotFoundError`) from services. Map them to HTTP responses in the blueprints.

## Security Rules (non-negotiable)
- **SQL values**: always use DuckDB parameter binding (`?`). Never f-string or `%`-format user input into SQL.
- **SQL identifiers** (table and column names can't be bound): validate against the known schema (`information_schema` / the repository's table list), then double-quote them with embedded quotes escaped.
- **Uploaded files**: `werkzeug.utils.secure_filename`, `.csv` extension only, saved only inside `CSV_DIR`.
- **URL ingest**: `http`/`https` schemes only, request timeout, `MAX_DOWNLOAD_BYTES` enforced while streaming, and derived file names sanitized.
- **Templates**: rely on Jinja autoescaping. Never mark CSV data `|safe`. Alpine templates render text with `x-text`, never `x-html`.

## Frontend Conventions
- Tailwind v4 utility classes in templates. The only custom CSS source is `app/static/css/input.css` (`@import "tailwindcss";` plus `@theme` tokens).
- Alpine components are small. Put anything longer than a few lines into `Alpine.data('name', () => ({...}))` in `app/static/js/`.
- Reference static assets with `url_for('static', filename=...)`.

## Code Review Checklist
- [ ] Tests written first and passing
- [ ] No SQL outside `app/repositories/`
- [ ] No Flask imports in services/repositories
- [ ] User input never interpolated into SQL
- [ ] Type hints present; ruff clean
