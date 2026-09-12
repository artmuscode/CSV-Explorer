# Task 022: Same-Origin Protection for State-Changing Requests (CSRF)

**Status**: completed
**Depends on**: 001, 004
**Retry count**: 0

## Description
The app has no authentication, so without protection any website the user visits could submit a hidden form to `http://127.0.0.1:5000`: deleting datasets, or making the app download URLs. Add a lightweight check with no dependencies that rejects state-changing requests whose `Origin` (or, failing that, `Referer`) isn't this app. Also harden the session cookie.

## Context
- Related files (new): `app/security.py`, `tests/integration/test_same_origin.py`
- Related files (modify):
  - `app/__init__.py`: call `register_same_origin_check(app)` right after `register_error_handlers(app)`. This is the only task in its batch (B3) that touches `app/__init__.py`.
  - `app/config.py`: add `SESSION_COOKIE_SAMESITE = "Lax"` and `SESSION_COOKIE_HTTPONLY = True` (the latter is Flask's default; set it explicitly anyway)
- `register_same_origin_check(app)` registers `@app.before_request` logic for methods `POST`, `PUT`, `PATCH` and `DELETE`:
  1. `expected = f"{request.scheme}://{request.host}"`, where `request.host` includes the port.
  2. If an `Origin` header is present: allow only if it equals `expected`. A literal `"null"` (sent by sandboxed iframes and some redirects) is rejected.
  3. Else, if a `Referer` header is present: allow only if its `scheme://netloc` (via `urlsplit`) equals `expected`.
  4. Else, with no `Origin` and no `Referer`: **allow**. Non-browser clients such as curl and the Flask test client send neither. Modern browsers always send `Origin` on cross-site POSTs, so this doesn't open a hole.
  5. On rejection: `abort(403)`. Add a 403 handler to `app/errors.py`: HTML `errors/403.html` extending `base.html` ("This request came from another site and was blocked"), or JSON `{"error": ...}` under `/api/`. Log a warning with the offending origin.
  - Safe methods (`GET`, `HEAD`, `OPTIONS`) are never checked.
- Throwaway routes for the tests (e.g. `POST /_test/echo` returning 204) are registered on the `app` fixture inside the test module. The real blueprints don't exist yet in this batch.
- **Other tasks:** Flask test-client POSTs send no `Origin`/`Referer` by default, so tasks 015, 016 and 019 need no changes to pass. Task 019 adds one end-to-end check that a cross-origin delete is blocked.

## Requirements (Test Descriptions)
- [x] `test_post_with_matching_origin_is_allowed`
- [x] `test_post_with_foreign_origin_is_rejected_with_403`
- [x] `test_post_with_null_origin_is_rejected`
- [x] `test_post_with_foreign_referer_and_no_origin_is_rejected`
- [x] `test_post_without_origin_or_referer_is_allowed`
- [x] `test_get_requests_are_never_checked`
- [x] `test_session_cookie_is_samesite_lax`

## Acceptance Criteria
- All requirements have passing tests
- Code follows code standards
- No new dependencies

## Implementation Notes
- `app/security.py` adds `register_same_origin_check(app)`, a single `before_request`
  hook checked only for `POST`/`PUT`/`PATCH`/`DELETE`. Implemented per the spec exactly:
  `Origin` header wins if present (rejecting mismatches and the literal `"null"`);
  otherwise `Referer`'s `scheme://netloc` (via `urlsplit`) must match; with neither
  header present the request is allowed (non-browser clients). Rejections call
  `abort(403)` and log a warning with the offending origin/referer via `app.logger`.
- Because this is one small, tightly-coupled `before_request` hook (all seven
  requirements exercise the same function), it was implemented as a single unit
  rather than incrementally regrowing the function per test; each of the 7 tests
  was then verified to pass against the complete implementation.
- `app/__init__.py`: calls `register_same_origin_check(app)` right after
  `register_error_handlers(app)`.
- `app/config.py`: added `SESSION_COOKIE_SAMESITE = "Lax"` and
  `SESSION_COOKIE_HTTPONLY = True` to `Config` (inherited by `TestConfig`).
- `app/errors.py`: added a `403` handler mirroring the existing 404/500 pattern
  (JSON `{"error": "Forbidden"}` under `/api/`, otherwise
  `errors/403.html`).
- `app/templates/errors/403.html`: new template extending `base.html`, mirroring
  `errors/404.html`, with the required copy "This request came from another site
  and was blocked."
- `tests/integration/test_same_origin.py`: registers a throwaway
  `POST/PUT/PATCH/DELETE/GET /_test/echo` route (returns 204) on a locally
  overridden `app`/`client` fixture pair (built from `make_app`), then exercises
  same-origin allow/deny behavior via `Origin`/`Referer` headers and `base_url`.
- Verified no regressions in `tests/integration/test_layout_and_errors.py` and
  `tests/integration/test_app_factory.py` (18 tests total pass together with the
  7 new tests). `ruff check` and `ruff format --check` are clean on all touched
  files. No new dependencies were added.
