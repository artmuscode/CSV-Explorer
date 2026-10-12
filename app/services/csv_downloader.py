"""Downloads a CSV from a URL into a staged file inside the CSV directory."""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from uuid import uuid4

import requests
from werkzeug.utils import secure_filename

from app.exceptions import IngestError
from app.services.url_guard import UrlGuard

_CONTENT_DISPOSITION_FILENAME_RE = re.compile(r'filename\*?=(?:"([^"]+)"|([^;]+))')
_CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True, slots=True)
class DownloadedFile:
    """A staged download awaiting installation by `CsvIngestService`."""

    path: Path
    filename: str


class CsvDownloader:
    """Streams a CSV from a URL into a hidden staging file.

    Validates the URL (and every redirect hop) with `UrlGuard`, enforces a
    byte cap and a total time deadline while streaming, and derives a
    sanitized `.csv` filename. Does not move the staged file into its final
    name; that is the caller's job (`CsvIngestService.install_and_ingest`),
    so a failed ingest can roll back to the previous file.
    """

    def __init__(
        self,
        dest_dir: Path,
        url_guard: UrlGuard,
        max_bytes: int,
        timeout: float,
        session: requests.Session | None = None,
        max_redirects: int = 5,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._dest_dir = dest_dir
        self._url_guard = url_guard
        self._max_bytes = max_bytes
        self._timeout = timeout
        self._session = session or requests.Session()
        self._max_redirects = max_redirects
        self._monotonic = monotonic

    def download(self, url: str) -> DownloadedFile:
        """Fetch `url` into a staged `.part` file and return it."""
        start = self._monotonic()
        response = self._fetch_final_response(url)
        try:
            filename = self._resolve_filename(url, response)
            self._reject_non_csv_content_type(response)
            self._reject_oversized_content_length(response)
            part_path = self._stream_to_part_file(response, start)
        finally:
            response.close()

        return DownloadedFile(path=part_path, filename=filename)

    def _fetch_final_response(self, url: str) -> requests.Response:
        """Follow redirects (each re-validated by `UrlGuard`) to a final response."""
        current_url = url
        for _ in range(self._max_redirects + 1):
            self._url_guard.validate(current_url)
            try:
                response = self._session.get(
                    current_url, stream=True, timeout=self._timeout, allow_redirects=False
                )
            except requests.RequestException as exc:
                raise IngestError(f"Failed to fetch URL: {exc}") from exc

            if 300 <= response.status_code < 400 and "Location" in response.headers:
                location = response.headers["Location"]
                response.close()
                current_url = urljoin(current_url, location)
                continue

            if response.status_code != 200:
                status = response.status_code
                response.close()
                raise IngestError(f"URL returned status {status}")

            return response

        raise IngestError(f"Too many redirects (> {self._max_redirects})")

    @staticmethod
    def _reject_non_csv_content_type(response: requests.Response) -> None:
        content_type = response.headers.get("Content-Type", "")
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type == "text/html":
            raise IngestError("URL returned an HTML page, not a CSV")

    def _reject_oversized_content_length(self, response: requests.Response) -> None:
        content_length = response.headers.get("Content-Length")
        if content_length is None:
            return
        try:
            length = int(content_length)
        except ValueError:
            return
        if length > self._max_bytes:
            raise IngestError(f"Content-Length {length} exceeds the {self._max_bytes} byte limit")

    def _stream_to_part_file(self, response: requests.Response, start: float) -> Path:
        part_path = self._dest_dir / f".{uuid4().hex}.part"
        try:
            written = 0
            with part_path.open("wb") as fh:
                for chunk in response.iter_content(_CHUNK_SIZE):
                    written += len(chunk)
                    if written > self._max_bytes:
                        raise IngestError(f"Download exceeded the {self._max_bytes} byte limit")
                    if self._monotonic() - start > self._timeout:
                        raise IngestError(f"Download exceeded the {self._timeout}s deadline")
                    fh.write(chunk)
        except (requests.RequestException, OSError) as exc:
            part_path.unlink(missing_ok=True)
            raise IngestError(f"Failed while downloading: {exc}") from exc
        except IngestError:
            part_path.unlink(missing_ok=True)
            raise
        return part_path

    @staticmethod
    def _resolve_filename(url: str, response: requests.Response) -> str:
        disposition = response.headers.get("Content-Disposition", "")
        match = _CONTENT_DISPOSITION_FILENAME_RE.search(disposition)
        if match:
            raw_name = match.group(1) or match.group(2)
        else:
            path = urlsplit(url).path
            raw_name = unquote(path.rsplit("/", 1)[-1])

        name = secure_filename(raw_name)
        if not name.lower().endswith(".csv"):
            name = f"{name}.csv"
        if name == ".csv" or not name:
            name = "download.csv"
        return name
