from dataclasses import dataclass

from app.models.dataset import Dataset


@dataclass(frozen=True, slots=True)
class IngestResult:
    """The outcome of ingesting a single CSV file into DuckDB."""

    dataset: Dataset
    replaced: bool


@dataclass(frozen=True, slots=True)
class ScanResult:
    """The outcome of scanning the CSV folder for new or changed files."""

    ingested: list[IngestResult]
    skipped: list[str]
    errors: dict[str, str]
