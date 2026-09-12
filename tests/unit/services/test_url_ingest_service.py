from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb
import pytest

from app.exceptions import IngestError
from app.models.dataset import DatasetSource
from app.repositories.duckdb_repository import DuckDBRepository
from app.repositories.metadata_repository import MetadataRepository
from app.services.csv_downloader import DownloadedFile
from app.services.csv_ingest_service import CsvIngestService
from app.services.url_ingest_service import UrlIngestService

FIXED_NOW = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)


class FakeDownloader:
    """Stands in for `CsvDownloader`: stages a given body or raises an `IngestError`."""

    def __init__(
        self,
        csv_dir: Path,
        body: bytes = b"id,name\n1,Alice\n",
        filename: str = "download.csv",
        error: IngestError | None = None,
    ) -> None:
        self._csv_dir = csv_dir
        self._body = body
        self._filename = filename
        self._error = error
        self.calls: list[str] = []

    def download(self, url: str) -> DownloadedFile:
        self.calls.append(url)
        if self._error is not None:
            raise self._error

        part_path = self._csv_dir / f".{uuid4().hex}.part"
        part_path.write_bytes(self._body)
        return DownloadedFile(path=part_path, filename=self._filename)


@pytest.fixture
def connection():
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def repository(connection):
    return DuckDBRepository(connection)


@pytest.fixture
def metadata(connection):
    repo = MetadataRepository(connection)
    repo.ensure_schema()
    return repo


@pytest.fixture
def csv_dir(tmp_path):
    directory = tmp_path / "csv"
    directory.mkdir()
    return directory


@pytest.fixture
def ingest_service(repository, metadata, csv_dir):
    return CsvIngestService(repository, metadata, csv_dir, clock=lambda: FIXED_NOW)


def test_ingest_records_url_source_and_source_url(ingest_service, csv_dir, metadata):
    downloader = FakeDownloader(csv_dir, body=b"id,name\n1,Alice\n", filename="people.csv")
    service = UrlIngestService(downloader, ingest_service)

    result = service.ingest("https://example.com/people.csv")

    assert result.dataset.name == "people"
    assert result.dataset.source == DatasetSource.URL
    assert result.dataset.source_url == "https://example.com/people.csv"
    assert metadata.get("people").source_url == "https://example.com/people.csv"


def test_ingest_rejects_blank_url_without_downloading(ingest_service, csv_dir):
    downloader = FakeDownloader(csv_dir)
    service = UrlIngestService(downloader, ingest_service)

    with pytest.raises(IngestError):
        service.ingest("   ")

    assert downloader.calls == []


def test_ingest_propagates_downloader_ingest_error(ingest_service, csv_dir):
    downloader = FakeDownloader(csv_dir, error=IngestError("URL returned status 404"))
    service = UrlIngestService(downloader, ingest_service)

    with pytest.raises(IngestError, match="URL returned status 404"):
        service.ingest("https://example.com/missing.csv")


def test_ingest_removes_staged_file_when_downloaded_csv_is_unloadable(ingest_service, csv_dir):
    downloader = FakeDownloader(csv_dir, body=b"", filename="broken.csv")
    service = UrlIngestService(downloader, ingest_service)

    with pytest.raises(IngestError):
        service.ingest("https://example.com/broken.csv")

    leftovers = list(csv_dir.iterdir())
    assert leftovers == []


def test_ingest_keeps_existing_file_with_same_name_when_download_is_unloadable(
    ingest_service, csv_dir, repository, metadata
):
    original_bytes = b"id,name\n1,Alice\n2,Bob\n"
    good_downloader = FakeDownloader(csv_dir, body=original_bytes, filename="sales.csv")
    UrlIngestService(good_downloader, ingest_service).ingest("https://example.com/sales.csv")

    original_dataset = metadata.get("sales")

    bad_downloader = FakeDownloader(csv_dir, body=b"", filename="sales.csv")
    with pytest.raises(IngestError):
        UrlIngestService(bad_downloader, ingest_service).ingest("https://example.com/sales.csv")

    sales_path = csv_dir / "sales.csv"
    assert sales_path.read_bytes() == original_bytes
    assert repository.count_rows("sales") == 2
    assert metadata.get("sales") == original_dataset

    leftovers = [p.name for p in csv_dir.iterdir() if p.name != "sales.csv"]
    assert leftovers == []
