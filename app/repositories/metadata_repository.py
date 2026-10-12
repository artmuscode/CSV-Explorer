"""Repository for dataset metadata, stored in the internal `_datasets` table."""

from datetime import UTC, datetime

import duckdb

from app.models.dataset import Dataset, DatasetSource

_COLUMNS = (
    "name",
    "original_filename",
    "source",
    "source_url",
    "row_count",
    "file_size",
    "file_mtime",
    "ingested_at",
    "deleted_at",
)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS _datasets (
    name VARCHAR PRIMARY KEY,
    original_filename VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    source_url VARCHAR,
    row_count BIGINT NOT NULL,
    file_size BIGINT,
    file_mtime DOUBLE,
    ingested_at TIMESTAMP NOT NULL,
    deleted_at TIMESTAMP
)
"""

_UPSERT_SQL = f"""
INSERT OR REPLACE INTO _datasets ({", ".join(_COLUMNS)})
VALUES ({", ".join("?" for _ in _COLUMNS)})
"""

_SELECT_COLUMNS = ", ".join(_COLUMNS)


class MetadataRepository:
    """Stores one row per dataset in the internal `_datasets` DuckDB table."""

    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self._conn = connection

    def ensure_schema(self) -> None:
        """Create the `_datasets` table if it doesn't already exist."""
        self._conn.cursor().execute(_CREATE_TABLE_SQL)

    def upsert(self, dataset: Dataset) -> None:
        """Insert or replace the metadata row for `dataset`.

        Writes `dataset.deleted_at` too, so re-ingesting a dataset (with
        `deleted_at=None`) clears any earlier deletion marker.
        """
        self._conn.cursor().execute(
            _UPSERT_SQL,
            [
                dataset.name,
                dataset.original_filename,
                dataset.source.value,
                dataset.source_url,
                dataset.row_count,
                dataset.file_size,
                dataset.file_mtime,
                _to_naive_utc(dataset.ingested_at),
                _to_naive_utc(dataset.deleted_at),
            ],
        )

    def get(self, name: str) -> Dataset | None:
        """Return the dataset record for `name`, including deleted ones."""
        row = (
            self._conn.cursor()
            .execute(
                f"SELECT {_SELECT_COLUMNS} FROM _datasets WHERE name = ?",
                [name],
            )
            .fetchone()
        )
        if row is None:
            return None
        return _row_to_dataset(row)

    def list_all(self) -> list[Dataset]:
        """Return non-deleted datasets, newest first."""
        rows = (
            self._conn.cursor()
            .execute(
                f"SELECT {_SELECT_COLUMNS} FROM _datasets "
                "WHERE deleted_at IS NULL ORDER BY ingested_at DESC, name"
            )
            .fetchall()
        )
        return [_row_to_dataset(row) for row in rows]

    def mark_deleted(self, name: str, deleted_at: datetime) -> None:
        """Mark the dataset `name` as deleted without removing its metadata row."""
        self._conn.cursor().execute(
            "UPDATE _datasets SET deleted_at = ? WHERE name = ?",
            [_to_naive_utc(deleted_at), name],
        )


def _to_naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(UTC).replace(tzinfo=None)


def _row_to_dataset(row: tuple) -> Dataset:
    (
        name,
        original_filename,
        source,
        source_url,
        row_count,
        file_size,
        file_mtime,
        ingested_at,
        deleted_at,
    ) = row
    return Dataset(
        name=name,
        original_filename=original_filename,
        source=DatasetSource(source),
        source_url=source_url,
        row_count=row_count,
        file_size=file_size,
        file_mtime=file_mtime,
        ingested_at=ingested_at.replace(tzinfo=UTC),
        deleted_at=deleted_at.replace(tzinfo=UTC) if deleted_at is not None else None,
    )
