"""Turns a CSV file on disk into a dataset: a DuckDB table plus metadata.

`CsvIngestService` also saves browser uploads into the CSV folder. Folder
scan and URL ingest build on top of it in later tasks; this service never
imports Flask or knows about HTTP downloads.
"""

import os
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from werkzeug.utils import secure_filename

from app.exceptions import IngestError
from app.models.dataset import Dataset, DatasetSource
from app.models.ingest_result import IngestResult, ScanResult
from app.repositories.duckdb_repository import DuckDBRepository
from app.repositories.identifiers import table_name_from_filename
from app.repositories.metadata_repository import MetadataRepository

_GLOB_CHARACTERS = ("*", "?", "[")


class CsvIngestService:
    """Loads CSV files into DuckDB tables and records their metadata."""

    def __init__(
        self,
        repository: DuckDBRepository,
        metadata: MetadataRepository,
        csv_dir: Path,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._metadata = metadata
        self._csv_dir = csv_dir
        self._clock = clock

    def ingest_file(
        self,
        path: Path,
        source: DatasetSource = DatasetSource.FOLDER,
        source_url: str | None = None,
    ) -> IngestResult:
        """Load `path` into a DuckDB table and record its metadata.

        Raises:
            IngestError: if `path` isn't a `.csv` file, if a table name
                can't be derived from its filename, or if the file can't be
                loaded (task 005).
        """
        if path.suffix.lower() != ".csv":
            raise IngestError(f"Not a CSV file: {path.name}")

        try:
            table = table_name_from_filename(path.name)
        except ValueError as exc:
            raise IngestError(str(exc)) from exc

        existing = self._metadata.get(table)
        replaced = existing is not None and not existing.is_deleted

        row_count = self._repository.create_table_from_csv(table, path)
        stat = path.stat()

        dataset = Dataset(
            name=table,
            original_filename=path.name,
            source=source,
            row_count=row_count,
            ingested_at=self._clock(),
            source_url=source_url,
            file_size=stat.st_size,
            file_mtime=stat.st_mtime,
        )
        self._metadata.upsert(dataset)

        return IngestResult(dataset, replaced)

    def install_and_ingest(
        self,
        staged: Path,
        filename: str,
        source: DatasetSource,
        source_url: str | None = None,
    ) -> IngestResult:
        """Move `staged` into `csv_dir / filename` and ingest it.

        If ingest fails, the previous file (if any) is restored so disk and
        table stay consistent.
        """
        final = self._csv_dir / filename
        backup = None
        if final.exists():
            backup = self._csv_dir / f".{filename}.{uuid4().hex}.bak"
            os.replace(final, backup)

        os.replace(staged, final)

        try:
            return self.ingest_file(final, source, source_url)
        except Exception:
            final.unlink(missing_ok=True)
            if backup is not None:
                os.replace(backup, final)
            Path(staged).unlink(missing_ok=True)
            raise
        else:
            if backup is not None:
                backup.unlink(missing_ok=True)

    def save_upload(self, filename: str, stream: BinaryIO) -> IngestResult:
        """Save an uploaded CSV `stream` into `csv_dir` and ingest it.

        Raises:
            IngestError: if `filename` sanitizes to an empty or non-`.csv`
                name.
        """
        safe = secure_filename(filename)
        if not safe or not safe.lower().endswith(".csv"):
            raise IngestError(f"Invalid upload filename: {filename!r}")

        staged = self._csv_dir / f".{uuid4().hex}.part"
        with staged.open("wb") as destination:
            shutil.copyfileobj(stream, destination)

        return self.install_and_ingest(staged, safe, DatasetSource.UPLOAD)

    def scan_folder(self) -> ScanResult:
        """Ingest new or changed CSVs from `csv_dir`, skipping the rest.

        Per-file failures (bad table names, unloadable CSVs, glob characters
        in the name, table-name collisions within this scan) are collected
        in `ScanResult.errors` instead of aborting the whole scan.
        """
        ingested: list[IngestResult] = []
        skipped: list[str] = []
        errors: dict[str, str] = {}
        seen: dict[str, str] = {}

        for path in self._list_candidate_files():
            name = path.name

            if any(char in name for char in _GLOB_CHARACTERS):
                errors[name] = "Skipped: file name contains *, ? or ["
                continue

            try:
                table = table_name_from_filename(name)
            except ValueError as exc:
                errors[name] = str(exc)
                continue

            if table in seen:
                errors[name] = f"Skipped: maps to the same dataset '{table}' as {seen[table]}"
                continue
            seen[table] = name

            if self._is_unchanged(table, path):
                skipped.append(name)
                continue

            try:
                ingested.append(self.ingest_file(path, DatasetSource.FOLDER))
            except IngestError as exc:
                errors[name] = str(exc)

        return ScanResult(ingested=ingested, skipped=skipped, errors=errors)

    def _list_candidate_files(self) -> list[Path]:
        return sorted(
            (
                path
                for path in self._csv_dir.iterdir()
                if path.is_file()
                and not path.name.startswith(".")
                and not path.name.endswith(".part")
                and path.suffix.lower() == ".csv"
            ),
            key=lambda path: path.name,
        )

    def _is_unchanged(self, table: str, path: Path) -> bool:
        existing = self._metadata.get(table)
        if existing is None:
            return False
        stat = path.stat()
        return (
            existing.original_filename == path.name
            and existing.file_size == stat.st_size
            and existing.file_mtime == stat.st_mtime
        )
