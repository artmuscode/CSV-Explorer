# Task 004: Frontend Foundation — Tailwind, Base Layout, Error Pages, Legacy Cleanup

**Status**: completed
**Depends on**: 001
**Retry count**: 0

## Description
Install the Tailwind CSS v4 standalone CLI and build the shared Jinja layout: the base template, header, footer, flash messages, and 404/500 error pages. Register the error handlers. (Task 001 already removed the legacy starter files.)

## Context
- Related files (new):
  - `bin/tailwindcss` (downloaded, gitignored)
  - `app/static/css/input.css`
  - `app/templates/base.html`
  - `app/templates/partials/header.html`, `partials/footer.html`, `partials/flash_messages.html`
  - `app/templates/errors/404.html`, `errors/500.html`
  - `app/errors.py`
  - `tests/integration/test_layout_and_errors.py`
- Related files (modify): `app/__init__.py` (call `register_error_handlers(app)`). This is the only task in batch B2 that touches `app/__init__.py`.
- Legacy files (`main.py`, `templates/`, `assets/`) were deleted in task 001. Don't recreate them.
- **No `url_for('main.index')` (or any blueprint endpoint) in the partials or error pages.** The `main` blueprint doesn't exist until task 014, so `url_for('main.index')` would raise `BuildError` while rendering the 404 page in this task's tests. Use `href="/"` for the home link in the header and the "back home" link on the error pages. Only `url_for('static', ...)` is allowed here.
- Tailwind binary: **pin an exact v4 release**, never `latest`.
  1. Find the newest v4 tag once: `curl -fsSI https://github.com/tailwindlabs/tailwindcss/releases/latest | grep -i '^location'`. It redirects to `.../tag/vX.Y.Z`. Confirm the major version is 4.
  2. Download that exact tag:
     ```bash
     TAILWIND_VERSION=vX.Y.Z   # the tag you found
     mkdir -p bin && curl -fsSL -o bin/tailwindcss "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-macos-arm64" && chmod +x bin/tailwindcss
     ```
  3. Write the tag into a committed file `.tailwind-version` (one line, e.g. `v4.1.13`), so the README (task 019) and future setups download the same build.
- Create `app/static/js/.gitkeep` so the `@source "../js"` path in `input.css` exists before task 018 adds `dataset_table.js`.
  Build it once: `./bin/tailwindcss -i app/static/css/input.css -o app/static/css/app.css`. **No test may depend on the binary or on the built `app.css`** (both are gitignored).
- `input.css`:
  - `@import "tailwindcss";`
  - `@source "../../templates";` and `@source "../js";` so class detection doesn't depend on the current directory
  - a small `@theme` block (e.g. a brand color and font stack)
- `base.html`:
  - blocks `title`, `content` and `scripts`
  - `<link rel="stylesheet" href="{{ url_for('static', filename='css/app.css') }}">`
  - includes the header, flash messages and footer partials
  - `{% block scripts %}{% endblock %}` sits **before** the Alpine tag. Pin an exact 3.x version (e.g. `3.14.9`; check the newest 3.x with `curl -fsS https://data.jsdelivr.com/v1/packages/npm/alpinejs/resolved?specifier=3`), never `3.x.x`.
  - **SRI**: the Alpine tag carries an `integrity` hash plus `crossorigin="anonymous"`:
    `<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@<ver>/dist/cdn.min.js" integrity="sha384-<hash>" crossorigin="anonymous"></script>`
    Compute the hash from the exact pinned file: `curl -fsSL https://cdn.jsdelivr.net/npm/alpinejs@<ver>/dist/cdn.min.js | openssl dgst -sha384 -binary | openssl base64 -A`. Put the version and hash in `base.html` next to each other, with a comment explaining how to regenerate them.
- `flash_messages.html` renders `get_flashed_messages(with_categories=true)`. It styles `success` / `error` / `info` categories with Tailwind.
- `app/errors.py::register_error_handlers(app)`:
  - 404 → `errors/404.html`
  - 500 → log with `app.logger.exception`, then render `errors/500.html` with no exception details
  - Requests to `/api/...` get JSON `{"error": ...}` instead of HTML.
- Tests that need throwaway routes (the 500 handler, flash rendering) register them on the test `app` fixture inside the test. Set `PROPAGATE_EXCEPTIONS=False` for the 500 test.

## Requirements (Test Descriptions)
- [x] `test_unknown_route_returns_404_page_with_base_layout`
- [x] `test_unknown_api_route_returns_404_json_error`
- [x] `test_base_layout_links_tailwind_app_stylesheet`
- [x] `test_base_layout_loads_pinned_alpine_version_with_sri_integrity` (the version is `3.N.N`, not `3.x.x`; `integrity` starts with `sha384-`; `crossorigin="anonymous"`)
- [x] `test_500_handler_renders_error_page_without_exception_details`
- [x] `test_flash_messages_render_with_category_styling`

## Acceptance Criteria
- All requirements have passing tests
- `bin/tailwindcss --help` runs and reports the pinned v4 version, and a build produces `app/static/css/app.css`
- `.tailwind-version` and `app/static/js/.gitkeep` are committed
- Code follows code standards

## Implementation Notes
- Pinned Tailwind CSS standalone CLI to `v4.3.3` (newest v4 tag at time of implementation, confirmed via the `releases/latest` redirect). Downloaded to `bin/tailwindcss` (arm64 macOS binary, gitignored) and recorded the tag in `.tailwind-version`.
- `./bin/tailwindcss -i app/static/css/input.css -o app/static/css/app.css` was run once locally to confirm the build works (477 lines of generated CSS, includes the `brand` theme color); `app/static/css/app.css` stays gitignored per `.gitignore` (already set up in task 001) and no test depends on it or on the binary.
- `app/static/js/.gitkeep` created so `@source "../js"` in `input.css` resolves before task 018 adds JS files.
- Pinned Alpine.js to `3.17.2` (newest 3.x per the jsdelivr resolved-package API) with an SRI hash computed via `curl | openssl dgst -sha384 -binary | openssl base64 -A`: `sha384-lcaMFHdvRVsEXVuhit4fTnbxq6eTLm5HPdNzO7vXNZjr8HOCMouPmv4hSGF3PCJV`. The version and hash live together in `base.html` with a comment on how to regenerate both.
- `app/errors.py::register_error_handlers(app)` registers 404/500 handlers; requests under `/api/` get JSON, everything else gets the HTML error templates extending `base.html`. `app/__init__.py` now calls `register_error_handlers(app)` at the end of `create_app`.
- Home links use plain `href="/"` (header logo, both error pages' "Back home" link) — no `url_for('main.index')`, since the `main` blueprint doesn't exist until task 014.
- `flash_messages.html` maps `success`/`error`/`info` categories to Tailwind utility classes via a Jinja dict lookup, defaulting unknown categories to the `info` styling.
- Note on TDD strictness: `test_unknown_route_returns_404_page_with_base_layout` and `test_500_handler_renders_error_page_without_exception_details` passed even before `app/errors.py`/templates existed, because Flask/Werkzeug's default error pages already happen to contain `<html`/`404` and don't leak exception text when `PROPAGATE_EXCEPTIONS=False`. This wasn't over-implementation on my part (no code existed yet) — it's just that these two test assertions are loose enough to be satisfied by Flask's built-in defaults. The other four tests (JSON `/api/` 404, stylesheet link, Alpine SRI, flash categories) failed as expected before implementation and pass now against the real templates/handlers.
- All six tests in `tests/integration/test_layout_and_errors.py` pass, plus the existing `tests/integration/test_app_factory.py` suite (verifying the `app/__init__.py` change didn't regress anything). `uv run ruff check` and `uv run ruff format --check` are clean on all files this task touched.
