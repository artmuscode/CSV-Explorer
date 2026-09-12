"""Ingests a CSV from a URL by downloading it and handing it to `CsvIngestService`."""

from app.exceptions import IngestError
from app.models.dataset import DatasetSource
from app.models.ingest_result import IngestResult
from app.services.csv_downloader import CsvDownloader
from app.services.csv_ingest_service import CsvIngestService


class UrlIngestService:
    """Downloads a CSV from a URL and installs it as a dataset.

    Keeps download concerns (`CsvDownloader`) separate from install-and-ingest
    concerns (`CsvIngestService`), so `CsvIngestService` never has to know
    about HTTP.
    """

    def __init__(self, downloader: CsvDownloader, ingest_service: CsvIngestService) -> None:
        self._downloader = downloader
        self._ingest_service = ingest_service

    def ingest(self, url: str) -> IngestResult:
        """Download `url` and ingest it as a `DatasetSource.URL` dataset.

        Raises:
            IngestError: if `url` is blank, if the download fails (invalid
                scheme, timeout, non-200 response, oversized or non-CSV
                content), or if the downloaded CSV can't be loaded.
        """
        url = url.strip()
        if not url:
            raise IngestError("Please enter a URL")

        downloaded = self._downloader.download(url)

        return self._ingest_service.install_and_ingest(
            downloaded.path, downloaded.filename, DatasetSource.URL, source_url=url
        )
