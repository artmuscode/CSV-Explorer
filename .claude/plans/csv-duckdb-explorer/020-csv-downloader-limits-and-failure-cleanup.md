# Task 020: CsvDownloader — Limits, Deadlines & Failure Cleanup

**Status**: completed
**Depends on**: 001, 002, 008, 010
**Retry count**: 0

## Description
Harden `CsvDownloader` (created in task 010) against hostile or broken servers: oversized bodies, lying or huge `Content-Length`, slow-drip responses, timeouts and mid-stream connection failures. Every failure must raise `IngestError` and leave **no** `.part` file behind. This was split out of task 010 to keep each task to one TDD cycle.

## Context
- Related files (modify): `app/services/csv_downloader.py`, `tests/unit/services/test_csv_downloader.py`. Task 010 created both. This task runs after 010 finishes, so there's no parallel conflict. Nothing else in its batch touches these files.
- Behaviour to verify, and fix if needed (task 010's Context has the full `download()` flow):
  - **Declared size:** `Content-Length` > `max_bytes` → `IngestError` **before** calling `iter_content`. A non-integer `Content-Length` is ignored.
  - **Actual size:** stream `iter_content(64 * 1024)`, counting bytes. Once the count passes `max_bytes`, stop, delete the `.part` file, and raise `IngestError`. This covers servers that send no or false `Content-Length`, and gzip bombs, because decoded bytes are counted.
  - **Total deadline:** if `monotonic() - start > timeout` while streaming, stop, delete the `.part` file, and raise `IngestError`. `requests`' own timeout only applies per socket read.
  - **Timeouts and connection errors:** `requests.Timeout` from `session.get` → `IngestError`, chained with `from exc`.
  - **Mid-stream failure:** any `requests.RequestException` raised from `iter_content` (e.g. `ChunkedEncodingError`), or an `OSError` from the file write, → `IngestError`, and the `.part` file is deleted.
  - **Responses are always closed**, including on every failure path. `FakeResponse.close()` records this.
- Tests use `FakeSession` / `FakeResponse` / `static_resolver` from `tests/fakes.py` (task 010), plus a fake `monotonic` whose value jumps past the deadline after the first chunk. To make `iter_content` raise mid-stream, extend `FakeResponse` with an optional `raise_after_chunks: int | None` / `exc` pair, or a `chunks` iterable that can include an exception. Keep the change backward compatible with task 010's tests.
- After every failure test, assert that `list(dest_dir.glob(".*.part")) == []`.

## Requirements (Test Descriptions)
- [x] `test_download_raises_ingest_error_on_timeout`
- [x] `test_download_rejects_declared_content_length_over_max_before_reading_body`
- [x] `test_download_aborts_and_removes_partial_file_when_exceeding_max_bytes`
- [x] `test_download_aborts_and_removes_partial_file_when_total_deadline_exceeded`
- [x] `test_download_wraps_mid_stream_request_exception_and_removes_partial_file`
- [x] `test_download_closes_response_on_every_failure_path`

## Acceptance Criteria
- All requirements have passing tests, and task 010's tests still pass
- No `.part` files remain after any failure
- Code follows code standards

## Implementation Notes
Task 010's `CsvDownloader` implementation already satisfied every hardening
behaviour this task specifies: declared `Content-Length` is checked before
`_stream_to_part_file` (and thus before `iter_content` is ever called),
actual streamed bytes are counted and compared to `max_bytes` inside the
`iter_content` loop, the `monotonic()` deadline is checked every chunk,
`requests.Timeout`/`RequestException` from `session.get` is wrapped in
`IngestError` with `from exc` in `_fetch_final_response`, and
`_stream_to_part_file`'s `try/except (requests.RequestException, OSError)`
already deletes the `.part` file and raises `IngestError` with the original
exception chained. `response.close()` is called in a `finally` block in
`download()`, covering every failure path.

All 6 new tests pass without any implementation changes, confirming this
existing behaviour rather than adding it. `app/services/csv_downloader.py`
was not modified.

Extended `tests/fakes.py`'s `FakeResponse` with optional
`raise_after_chunks: int | None` and `exc: Exception | None` constructor
parameters (default `None`, so all task 010 usages are unaffected). When set,
`iter_content` raises `exc` after yielding `raise_after_chunks` chunks,
simulating a mid-stream `ChunkedEncodingError`. Used `enumerate(...,
start=1)` over the chunk-start offsets to count yielded chunks (ruff SIM113
flagged a manual counter).

Added 6 tests to `tests/unit/services/test_csv_downloader.py`:
`test_download_raises_ingest_error_on_timeout`,
`test_download_rejects_declared_content_length_over_max_before_reading_body`,
`test_download_aborts_and_removes_partial_file_when_exceeding_max_bytes`,
`test_download_aborts_and_removes_partial_file_when_total_deadline_exceeded`
(uses an injected `monotonic` callable that jumps from `0.0` to `100.0`
after the first chunk), `test_download_wraps_mid_stream_request_exception_and_removes_partial_file`,
and `test_download_closes_response_on_every_failure_path` (exercises five
distinct failure routes against one `FakeSession` and asserts `.closed` on
each underlying `FakeResponse`).

Full suite: `uv run pytest -n auto` -> 140 passed. `uv run ruff check` and
`uv run ruff format --check` clean on the three edited files.
