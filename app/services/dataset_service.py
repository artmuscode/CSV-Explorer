"""Read and delete side of the dataset domain.

`DatasetService` lists datasets, turns raw request parameters into a
validated `RowQuery`, returns pages of rows, and deletes datasets. It never
imports Flask; blueprints stay thin and pass raw strings to it.
"""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from app.exceptions import DatasetNotFoundError, InvalidQueryError
from app.models.dataset import Dataset
from app.models.page import Page
from app.models.row_query import RowQuery, SortDirection
from app.models.row_stream import RowStream
from app.repositories.duckdb_repository import DuckDBRepository
from app.repositories.metadata_repository import MetadataRepository

MAX_PAGE_NUMBER = 1_000_000


class DatasetService:
    """Lists, queries, and deletes datasets."""

    def __init__(
        self,
        repository: DuckDBRepository,
        metadata: MetadataRepository,
        default_page_size: int = 25,
        max_page_size: int = 100,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._metadata = metadata
        self._default_page_size = default_page_size
        self._max_page_size = max_page_size
        self._clock = clock

    def list_datasets(self) -> list[Dataset]:
        """Return all non-deleted datasets, newest first."""
        return self._metadata.list_all()

    def get_dataset(self, name: str) -> Dataset:
        """Return the dataset record for `name`.

        Raises:
            DatasetNotFoundError: if there is no record for `name`, or the
                record is marked deleted.
        """
        dataset = self._metadata.get(name)
        if dataset is None or dataset.is_deleted:
            raise DatasetNotFoundError(f"Dataset not found: {name!r}")
        return dataset

    def get_page(self, name: str, query: RowQuery) -> Page:
        """Return a page of rows for the dataset `name`.

        Raises:
            DatasetNotFoundError: if there is no record for `name`, or the
                record is marked deleted.
        """
        self.get_dataset(name)
        return self._repository.fetch_page(name, query)

    def export_rows(self, name: str, query: RowQuery) -> RowStream:
        """Return every row of `name` matching `query`, unpaged, for export.

        `query`'s search, filters and sort still apply; its paging does not.

        Raises:
            DatasetNotFoundError: if there is no record for `name`, or the
                record is marked deleted.
            InvalidQueryError: if `query` references an unknown column.
        """
        self.get_dataset(name)
        return self._repository.stream_rows(name, query)

    def build_query(
        self,
        page: str | None,
        per_page: str | None,
        search: str | None,
        filters: Mapping[str, str],
        sort_by: str | None,
        sort_dir: str | None,
    ) -> RowQuery:
        """Validate raw request parameters and turn them into a `RowQuery`.

        Raises:
            InvalidQueryError: if `page`/`per_page` isn't a valid integer or
                `page` is out of range, or `sort_dir` isn't `asc`/`desc`.
        """
        parsed_page = self._parse_page(page)
        parsed_per_page = self._parse_per_page(per_page)
        parsed_sort_dir = self._parse_sort_dir(sort_dir)
        parsed_search = search.strip() if search else ""
        parsed_filters = {
            key: value.strip() for key, value in filters.items() if value and value.strip()
        }
        parsed_sort_by = sort_by.strip() if sort_by and sort_by.strip() else None

        return RowQuery(
            page=parsed_page,
            per_page=parsed_per_page,
            search=parsed_search,
            filters=parsed_filters,
            sort_by=parsed_sort_by,
            sort_dir=parsed_sort_dir,
        )

    def _parse_page(self, page: str | None) -> int:
        if page is None or not page.strip():
            return 1
        try:
            parsed = int(page)
        except ValueError as exc:
            raise InvalidQueryError(f"Invalid page: {page!r}") from exc
        if parsed < 1 or parsed > MAX_PAGE_NUMBER:
            raise InvalidQueryError(f"Page out of range: {page!r}")
        return parsed

    def _parse_per_page(self, per_page: str | None) -> int:
        if per_page is None or not per_page.strip():
            return self._default_page_size
        try:
            parsed = int(per_page)
        except ValueError as exc:
            raise InvalidQueryError(f"Invalid per_page: {per_page!r}") from exc
        return max(1, min(parsed, self._max_page_size))

    def _parse_sort_dir(self, sort_dir: str | None) -> SortDirection:
        if sort_dir is None or not sort_dir.strip():
            return SortDirection.ASC
        try:
            return SortDirection(sort_dir.strip().lower())
        except ValueError as exc:
            raise InvalidQueryError(f"Invalid sort_dir: {sort_dir!r}") from exc

    def delete_dataset(self, name: str) -> None:
        """Delete the dataset `name`, keeping a deletion marker in metadata.

        The CSV file on disk is left untouched.

        Raises:
            DatasetNotFoundError: if there is no record for `name`, or the
                record is marked deleted.
        """
        self.get_dataset(name)
        self._repository.drop_table(name)
        self._metadata.mark_deleted(name, self._clock())
