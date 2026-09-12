class CsvExplorerError(Exception):
    """Base class for all domain exceptions raised by CSV Explorer."""


class IngestError(CsvExplorerError):
    """Raised when a CSV file or URL cannot be ingested into DuckDB."""


class DatasetNotFoundError(CsvExplorerError):
    """Raised when a requested dataset does not exist."""


class InvalidQueryError(CsvExplorerError):
    """Raised when a row query (search, filter, sort) is invalid."""
