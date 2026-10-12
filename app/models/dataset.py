from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class DatasetSource(StrEnum):
    """Where a dataset's CSV data came from."""

    FOLDER = "folder"
    UPLOAD = "upload"
    URL = "url"


@dataclass(frozen=True, slots=True)
class Dataset:
    """Metadata for a CSV file loaded into DuckDB.

    `ingested_at` and `deleted_at` are always timezone-aware UTC datetimes.
    Task 011's clock produces `datetime.now(UTC)`, and task 007 must
    round-trip them unchanged.

    `deleted_at` is the deletion marker (the user chose "remember
    deletions"). Deleting a dataset drops its table and sets `deleted_at`
    but keeps the metadata row. That way the folder scan can tell the file
    was deliberately removed, and won't re-ingest it unless the file
    changes (tasks 007, 012, 013).
    """

    name: str
    original_filename: str
    source: DatasetSource
    row_count: int
    ingested_at: datetime
    source_url: str | None = None
    file_size: int | None = None
    file_mtime: float | None = None
    deleted_at: datetime | None = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
