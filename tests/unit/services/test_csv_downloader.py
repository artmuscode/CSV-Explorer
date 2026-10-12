from pathlib import Path

import pytest
import requests

from app.exceptions import IngestError
from app.services.csv_downloader import CsvDownloader
from app.services.url_guard import UrlGuard
from tests.fakes import FakeResponse, FakeSession, static_resolver


def make_downloader(tmp_path: Path, routes: dict, **kwargs) -> CsvDownloader:
    session = FakeSession(routes)
    guard = UrlGuard(resolver=static_resolver({}))
    return CsvDownloader(
        dest_dir=tmp_path,
        url_guard=guard,
        max_bytes=1024,
        timeout=5.0,
        session=session,
        **kwargs,
    )


def test_download_stages_body_in_hidden_part_file_and_returns_sanitized_filename(tmp_path):
    url = "http://example.com/data.csv"
    downloader = make_downloader(
        tmp_path,
        {
            url: FakeResponse(
                status_code=200, body=b"a,b\n1,2\n", headers={"Content-Type": "text/csv"}
            )
        },
    )

    result = downloader.download(url)

    assert result.path.parent == tmp_path
    assert result.path.name.startswith(".")
    assert result.path.name.endswith(".part")
    assert result.path.read_bytes() == b"a,b\n1,2\n"
    assert result.filename == "data.csv"


def test_download_derives_filename_from_url_path_and_ensures_csv_suffix(tmp_path):
    url = "http://example.com/exports/monthly%20report"
    downloader = make_downloader(
        tmp_path,
        {url: FakeResponse(status_code=200, body=b"x", headers={"Content-Type": "text/plain"})},
    )

    result = downloader.download(url)

    assert result.filename == "monthly_report.csv"


def test_download_prefers_content_disposition_filename(tmp_path):
    url = "http://example.com/download?id=123"
    downloader = make_downloader(
        tmp_path,
        {
            url: FakeResponse(
                status_code=200,
                body=b"x",
                headers={
                    "Content-Type": "text/plain",
                    "Content-Disposition": 'attachment; filename="report-final.csv"',
                },
            )
        },
    )

    result = downloader.download(url)

    assert result.filename == "report-final.csv"


def test_download_does_not_touch_existing_file_with_same_name(tmp_path):
    url = "http://example.com/data.csv"
    existing = tmp_path / "data.csv"
    existing.write_bytes(b"old-contents")
    downloader = make_downloader(
        tmp_path,
        {
            url: FakeResponse(
                status_code=200, body=b"new-contents", headers={"Content-Type": "text/csv"}
            )
        },
    )

    result = downloader.download(url)

    assert existing.read_bytes() == b"old-contents"
    assert result.path != existing
    assert result.filename == "data.csv"


def test_download_raises_ingest_error_on_non_200_status(tmp_path):
    url = "http://example.com/missing.csv"
    downloader = make_downloader(
        tmp_path,
        {url: FakeResponse(status_code=404, body=b"not found")},
    )

    with pytest.raises(IngestError):
        downloader.download(url)

    assert list(tmp_path.iterdir()) == []


def test_download_raises_ingest_error_on_timeout(tmp_path):
    url = "http://example.com/slow.csv"
    downloader = make_downloader(tmp_path, {url: requests.Timeout("timed out")})

    with pytest.raises(IngestError) as exc_info:
        downloader.download(url)

    assert exc_info.value.__cause__ is not None
    assert isinstance(exc_info.value.__cause__, requests.Timeout)
    assert list(tmp_path.glob(".*.part")) == []


def test_download_rejects_declared_content_length_over_max_before_reading_body(tmp_path):
    url = "http://example.com/huge.csv"
    downloader = make_downloader(
        tmp_path,
        {
            url: FakeResponse(
                status_code=200,
                body=b"a" * 2000,
                headers={"Content-Type": "text/csv", "Content-Length": "2000"},
            )
        },
    )

    with pytest.raises(IngestError):
        downloader.download(url)

    assert list(tmp_path.glob(".*.part")) == []


def test_download_aborts_and_removes_partial_file_when_exceeding_max_bytes(tmp_path):
    url = "http://example.com/big.csv"
    downloader = make_downloader(
        tmp_path,
        {
            url: FakeResponse(
                status_code=200,
                body=b"a" * 2000,
                headers={"Content-Type": "text/csv"},
                chunk_size=100,
            )
        },
    )

    with pytest.raises(IngestError):
        downloader.download(url)

    assert list(tmp_path.glob(".*.part")) == []


def test_download_aborts_and_removes_partial_file_when_total_deadline_exceeded(tmp_path):
    url = "http://example.com/slow.csv"
    session = FakeSession(
        {
            url: FakeResponse(
                status_code=200,
                body=b"a,b\n1,2\n3,4\n",
                headers={"Content-Type": "text/csv"},
                chunk_size=4,
            )
        }
    )
    guard = UrlGuard(resolver=static_resolver({}))
    clock = iter([0.0, 0.0, 100.0])
    downloader = CsvDownloader(
        dest_dir=tmp_path,
        url_guard=guard,
        max_bytes=1024,
        timeout=5.0,
        session=session,
        monotonic=lambda: next(clock),
    )

    with pytest.raises(IngestError):
        downloader.download(url)

    assert list(tmp_path.glob(".*.part")) == []


def test_download_wraps_mid_stream_request_exception_and_removes_partial_file(tmp_path):
    url = "http://example.com/flaky.csv"
    downloader = make_downloader(
        tmp_path,
        {
            url: FakeResponse(
                status_code=200,
                body=b"a,b\n1,2\n3,4\n",
                headers={"Content-Type": "text/csv"},
                chunk_size=4,
                raise_after_chunks=1,
                exc=requests.exceptions.ChunkedEncodingError("connection broken"),
            )
        },
    )

    with pytest.raises(IngestError) as exc_info:
        downloader.download(url)

    assert isinstance(exc_info.value.__cause__, requests.exceptions.ChunkedEncodingError)
    assert list(tmp_path.glob(".*.part")) == []


def test_download_closes_response_on_every_failure_path(tmp_path):
    non_200_response = FakeResponse(status_code=404, body=b"not found")
    html_response = FakeResponse(
        status_code=200, body=b"<html></html>", headers={"Content-Type": "text/html"}
    )
    oversized_declared_response = FakeResponse(
        status_code=200,
        body=b"a" * 2000,
        headers={"Content-Type": "text/csv", "Content-Length": "2000"},
    )
    oversized_actual_response = FakeResponse(
        status_code=200,
        body=b"a" * 2000,
        headers={"Content-Type": "text/csv"},
        chunk_size=100,
    )
    mid_stream_failure_response = FakeResponse(
        status_code=200,
        body=b"a,b\n1,2\n",
        headers={"Content-Type": "text/csv"},
        chunk_size=4,
        raise_after_chunks=1,
        exc=requests.exceptions.ChunkedEncodingError("connection broken"),
    )

    cases = {
        "http://example.com/missing.csv": non_200_response,
        "http://example.com/oops": html_response,
        "http://example.com/huge.csv": oversized_declared_response,
        "http://example.com/big.csv": oversized_actual_response,
        "http://example.com/flaky.csv": mid_stream_failure_response,
    }
    downloader = make_downloader(tmp_path, cases)

    for url, response in cases.items():
        with pytest.raises(IngestError):
            downloader.download(url)
        assert response.closed is True

    assert list(tmp_path.glob(".*.part")) == []


def test_download_rejects_redirect_to_private_address(tmp_path):
    start_url = "http://example.com/redirect"
    private_url = "http://internal.example/secret.csv"
    session = FakeSession(
        {
            start_url: FakeResponse(status_code=302, headers={"Location": private_url}),
        }
    )
    guard = UrlGuard(
        resolver=static_resolver({"internal.example": ["10.0.0.5"]}),
    )
    downloader = CsvDownloader(
        dest_dir=tmp_path,
        url_guard=guard,
        max_bytes=1024,
        timeout=5.0,
        session=session,
    )

    with pytest.raises(IngestError):
        downloader.download(start_url)

    assert list(tmp_path.iterdir()) == []


def test_download_rejects_html_content_type(tmp_path):
    url = "http://example.com/oops"
    downloader = make_downloader(
        tmp_path,
        {
            url: FakeResponse(
                status_code=200,
                body=b"<html><body>not a csv</body></html>",
                headers={"Content-Type": "text/html; charset=utf-8"},
            )
        },
    )

    with pytest.raises(IngestError):
        downloader.download(url)

    assert list(tmp_path.iterdir()) == []
