# Task 010: CsvDownloader — Core Download, Redirects & Filenames

**Status**: completed
**Depends on**: 001, 002, 008
**Retry count**: 0

## Description
Create `CsvDownloader`, which fetches a CSV from a URL into a **staged** file in the CSV folder. It validates every URL and redirect hop with `UrlGuard`, streams the body with a size cap and a timeout, and returns the staged file together with a sanitized `.csv` name. It does **not** move the file into its final name: `CsvIngestService.install_and_ingest` does that (tasks 011 and 021), so it can roll back to the previous file if ingest fails. This task also creates the shared HTTP test fakes used by tasks 014, 016 and 019.

**Split note:** this task implements the whole `download()` flow below, including the size cap, the total deadline and exception wrapping. Its tests cover the happy path, redirects, status/content-type checks and filename rules. **Task 020** adds the tests for size, deadline and failure cleanup, and hardens whatever they uncover.

## Context
- Related files (new): `app/services/csv_downloader.py`, `tests/fakes.py`, `tests/unit/services/test_csv_downloader.py`
- `DownloadedFile` is a `@dataclass(frozen=True, slots=True)` defined in `csv_downloader.py` with `path: Path` (the staged file) and `filename: str` (the sanitized final name, ending in `.csv`).
- Constructor: `CsvDownloader(dest_dir: Path, url_guard: UrlGuard, max_bytes: int, timeout: float, session: requests.Session | None = None, max_redirects: int = 5, monotonic: Callable[[], float] = time.monotonic)`
- `download(url: str) -> DownloadedFile`:
  1. Run `url_guard.validate(url)`.
  2. Call `session.get(url, stream=True, timeout=timeout, allow_redirects=False)`.
  3. On a 3xx with a `Location` header: `urljoin` the new URL, validate it again, and repeat. More than `max_redirects` hops → `IngestError`.
  4. Any final status other than 200 → `IngestError` naming the status.
  5. If the `Content-Type` media type is `text/html` → `IngestError("URL returned an HTML page, not a CSV")`. `.claude/testing.md` requires a "non-CSV content" case. Don't allow-list types: CSV hosts commonly send `text/plain`, `application/octet-stream` or `application/vnd.ms-excel`.
  6. `Content-Length` > `max_bytes` → `IngestError` before reading the body. Ignore a non-integer `Content-Length`.
  7. Stream `iter_content(64 * 1024)` into `dest_dir / f".{uuid4().hex}.part"`, counting bytes. The stream counts decoded bytes, which also covers gzip bombs. If the count passes `max_bytes`, or `monotonic() - start > timeout` (a **total** deadline: the `requests` timeout only applies per socket read, so a slow-drip server could otherwise hold the request open indefinitely), stop and raise `IngestError`.
  8. File name: use the `Content-Disposition` `filename=` if present, otherwise the last URL path segment passed through `urllib.parse.unquote`. Run it through `werkzeug.utils.secure_filename`, append `.csv` if it doesn't already end in `.csv` (case-insensitive), and fall back to `download.csv` if it's empty.
  9. Return `DownloadedFile(path=part_path, filename=name)`. **Don't** `os.replace` into `dest_dir / name`.

  - Catch `requests.RequestException`, the base class (`Timeout`, `ConnectionError`, `ChunkedEncodingError`, `ContentDecodingError`, `InvalidURL` and so on), plus `OSError` from the file write, and re-raise them as `IngestError` with `from exc`.
  - On **any** failure, delete the `.part` file in a `try/finally` or `except` block before re-raising.
  - Always close every response, including the 3xx hops.
- `tests/fakes.py` (shared test helpers, not a test module):
  - `FakeResponse(status_code: int = 200, body: bytes = b"", headers: dict[str, str] | None = None, chunk_size: int | None = None)`. Store `headers` as a `requests.structures.CaseInsensitiveDict`. Provide `iter_content(chunk_size)`, which yields the body in chunks, and `close()`, which records that it was closed.
  - `FakeSession(routes: dict[str, FakeResponse | Exception])`. `get(url, **kwargs)` returns the routed response, or raises the routed exception. It records `calls` (url + kwargs). An unknown URL raises `AssertionError`.
  - `static_resolver(mapping: dict[str, list[str]], default: Sequence[str] | None = ("93.184.216.34",)) -> Callable[[str], list[str]]`. It raises `socket.gaierror` for unknown hosts when `default` is `None`.
- Tests inject `FakeSession` plus a `UrlGuard(resolver=static_resolver(...))`. **No real network.** Use a fake `monotonic` for the deadline test.

## Requirements (Test Descriptions)
- [x] `test_download_stages_body_in_hidden_part_file_and_returns_sanitized_filename`
- [x] `test_download_derives_filename_from_url_path_and_ensures_csv_suffix`
- [x] `test_download_prefers_content_disposition_filename`
- [x] `test_download_does_not_touch_existing_file_with_same_name`
- [x] `test_download_raises_ingest_error_on_non_200_status`
- [x] `test_download_rejects_html_content_type`
- [x] `test_download_rejects_redirect_to_private_address`

(Timeout, size-cap, deadline and mid-stream-failure tests are in task 020.)

## Acceptance Criteria
- All requirements have passing tests
- No `.part` files remain after any failure
- `tests/fakes.py` exists and is importable as `from tests.fakes import FakeResponse, FakeSession, static_resolver`
- Code follows code standards

## Implementation Notes
- Implemented `app/services/csv_downloader.py` with `DownloadedFile` (frozen/slots dataclass) and `CsvDownloader`. `download()` is split into private helpers: `_fetch_final_response` (redirect loop, re-validating each hop with `UrlGuard`, closing every intermediate 3xx/non-200 response), `_reject_non_csv_content_type`, `_reject_oversized_content_length` (ignores non-integer `Content-Length`), `_stream_to_part_file` (byte-count cap + total `monotonic()` deadline, always unlinking the `.part` file on any `IngestError`/`RequestException`/`OSError` before re-raising as `IngestError`), and `_resolve_filename` (Content-Disposition regex first, else last URL path segment via `unquote` → `secure_filename`, forcing a `.csv` suffix and falling back to `download.csv`).
- Built `tests/fakes.py` (`FakeResponse`, `FakeSession`, `static_resolver`) exactly to spec; verified all three in an ad-hoc script (chunking, `close()` flag, `calls` recording, unknown-URL `AssertionError`, and `static_resolver`'s `socket.gaierror` fallback).
- Because the whole `download()` flow (redirects, status, content-type, content-length, filename, streaming with cleanup) had to be implemented as one coherent method per the task's "Split note", requirements 4 (`does_not_touch_existing_file`), 6 (`rejects_html_content_type`) and 7 (`rejects_redirect_to_private_address`) passed immediately once the core flow existed for requirement 1/5 — noted per the TDD rules rather than force-splitting the implementation unnaturally. Every test was still written and confirmed against the module before any code satisfying it was added (module didn't exist until after test 1 was RED; status-code check didn't exist until test 5 was RED).
- `uv run pytest tests/unit/services/test_csv_downloader.py` (7 passed) and `uv run ruff check` / `uv run ruff format` on the three owned files are clean.
- Size-cap, deadline and mid-stream-failure tests are intentionally left to task 020 per the split note; the implementation already includes the byte-count and `monotonic()` deadline checks in `_stream_to_part_file` and `Content-Length` pre-check in `_reject_oversized_content_length`, ready for those tests.
