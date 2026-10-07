"""Repository owning user dataset tables in DuckDB.

Every method opens its own cursor via `self._conn.cursor()` so concurrent
requests handled by different threads never share a cursor's state.
"""

import math
from collections.abc import Iterator
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import duckdb

from app.exceptions import DatasetNotFoundError, IngestError
from app.models.column import Column
from app.models.page import Page
from app.models.row_query import RowQuery
from app.models.row_stream import RowStream
from app.repositories.identifiers import quote_identifier
from app.repositories.row_query_builder import RowQueryBuilder

_MAX_ERROR_MESSAGE_LENGTH = 200
_UNICODE_ERROR_MARKERS = ("invalid unicode", "utf-8")
_STREAM_BATCH_SIZE = 1000


class DuckDBRepository:
    """Creates, inspects, and drops the DuckDB tables backing each dataset."""

    def __init__(
        self,
        connection: duckdb.DuckDBPyConnection,
        query_builder: RowQueryBuilder | None = None,
    ) -> None:
        self._conn = connection
        self._query_builder = query_builder if query_builder is not None else RowQueryBuilder()

    def create_table_from_csv(self, table: str, csv_path: Path) -> int:
        """Load `csv_path` into `table`, replacing any existing table of that name.

        Raises:
            IngestError: if the file is empty, or DuckDB cannot parse it
                (even after a Latin-1 encoding retry).
        """
        if csv_path.stat().st_size == 0:
            raise IngestError(f"Could not load {csv_path.name}: file is empty")

        quoted_table = quote_identifier(table)
        path_str = str(csv_path)

        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    f"CREATE OR REPLACE TABLE {quoted_table} AS SELECT * FROM read_csv_auto(?)",
                    [path_str],
                )
        except duckdb.Error as exc:
            if not _looks_like_unicode_error(str(exc)):
                raise IngestError(_short_error_message(csv_path, str(exc))) from exc
            try:
                with self._conn.cursor() as cur:
                    cur.execute(
                        f"CREATE OR REPLACE TABLE {quoted_table} AS "
                        "SELECT * FROM read_csv_auto(?, encoding = 'latin-1')",
                        [path_str],
                    )
            except duckdb.Error as retry_exc:
                raise IngestError(_short_error_message(csv_path, str(retry_exc))) from retry_exc

        return self.count_rows(table)

    def table_exists(self, table: str) -> bool:
        with self._conn.cursor() as cur:
            row = cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = ? AND table_schema = 'main'",
                [table],
            ).fetchone()
        return row is not None

    def get_columns(self, table: str) -> list[Column]:
        with self._conn.cursor() as cur:
            rows = cur.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = ? AND table_schema = 'main' "
                "ORDER BY ordinal_position",
                [table],
            ).fetchall()
        return [Column(name=name, type=data_type) for name, data_type in rows]

    def count_rows(self, table: str) -> int:
        with self._conn.cursor() as cur:
            (count,) = cur.execute(f"SELECT count(*) FROM {quote_identifier(table)}").fetchone()
        return count

    def drop_table(self, table: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {quote_identifier(table)}")

    def fetch_page(self, table: str, query: RowQuery) -> Page:
        """Run a filtered, sorted, paginated query and return a `Page` of rows.

        Raises:
            DatasetNotFoundError: if `table` does not exist.
            InvalidQueryError: if `query` references an unknown column.
        """
        if not self.table_exists(table):
            raise DatasetNotFoundError(f"Dataset not found: {table!r}")

        columns = self.get_columns(table)
        built = self._query_builder.build(table, columns, query)

        with self._conn.cursor() as cur:
            (total,) = cur.execute(built.count_sql, built.count_params).fetchone()
            result_rows = cur.execute(built.select_sql, built.select_params).fetchall()

        column_names = [column.name for column in columns]
        rows = [
            {name: self._to_json_safe(value) for name, value in zip(column_names, row, strict=True)}
            for row in result_rows
        ]

        return Page(rows, columns, query.page, query.per_page, total)

    def stream_rows(self, table: str, query: RowQuery) -> RowStream:
        """Return every row matching `query`, streamed in batches, unpaged.

        `query`'s `page`/`per_page` are ignored; its search, filters and sort
        are not. Validation and the initial execute happen eagerly, so a bad
        table or column raises here rather than part way through iteration
        (which, for an HTTP export, would be after the response has started).

        Raises:
            DatasetNotFoundError: if `table` does not exist.
            InvalidQueryError: if `query` references an unknown column.
        """
        if not self.table_exists(table):
            raise DatasetNotFoundError(f"Dataset not found: {table!r}")

        columns = self.get_columns(table)
        built = self._query_builder.build_export(table, columns, query)

        cursor = self._conn.cursor()
        try:
            cursor.execute(built.sql, built.params)
        except Exception:
            cursor.close()
            raise

        column_names = [column.name for column in columns]
        return RowStream(columns=columns, rows=self._iter_rows(cursor, column_names))

    def _iter_rows(
        self, cursor: duckdb.DuckDBPyConnection, column_names: list[str]
    ) -> Iterator[dict[str, Any]]:
        """Yield `cursor`'s remaining rows as dicts, closing it when done.

        The `finally` also covers an abandoned generator (the consumer stops
        early, or an export's client disconnects), so the cursor is never
        left open.
        """
        try:
            while batch := cursor.fetchmany(_STREAM_BATCH_SIZE):
                for row in batch:
                    yield {
                        name: self._to_json_safe(value)
                        for name, value in zip(column_names, row, strict=True)
                    }
        finally:
            cursor.close()

    def _to_json_safe(self, value: Any) -> Any:
        if isinstance(value, datetime | date | time):
            return value.isoformat()
        if isinstance(value, timedelta):
            return str(value)
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, bytes):
            return value.hex()
        if isinstance(value, float) and not math.isfinite(value):
            if math.isnan(value):
                return "NaN"
            return "Infinity" if value > 0 else "-Infinity"
        return value


def _looks_like_unicode_error(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _UNICODE_ERROR_MARKERS)


def _short_error_message(csv_path: Path, duckdb_message: str) -> str:
    first_line = duckdb_message.splitlines()[0] if duckdb_message else ""
    first_line = first_line[:_MAX_ERROR_MESSAGE_LENGTH]
    return f"Could not load {csv_path.name}: {first_line}"
