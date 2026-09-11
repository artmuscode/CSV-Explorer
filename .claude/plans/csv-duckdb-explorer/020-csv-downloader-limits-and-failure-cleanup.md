# Task 020: CsvDownloader — Limits, Deadlines & Failure Cleanup

**Status**: pending
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
- [ ] `test_download_raises_ingest_error_on_timeout`
- [ ] `test_download_rejects_declared_content_length_over_max_before_reading_body`
- [ ] `test_download_aborts_and_removes_partial_file_when_exceeding_max_bytes`
- [ ] `test_download_aborts_and_removes_partial_file_when_total_deadline_exceeded`
- [ ] `test_download_wraps_mid_stream_request_exception_and_removes_partial_file`
- [ ] `test_download_closes_response_on_every_failure_path`

## Acceptance Criteria
- All requirements have passing tests, and task 010's tests still pass
- No `.part` files remain after any failure
- Code follows code standards

## Implementation Notes
(Left blank - filled in by programmer during implementation)
