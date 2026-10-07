"""Turns a `RowQuery` into parameterized SELECT and COUNT statements.

This is the single place where user search, filter and sort input becomes
SQL text. Values are always passed as bound parameters; only column and
table identifiers (validated against the known schema) are interpolated.
"""

import re
from dataclasses import dataclass
from typing import Any

from app.exceptions import InvalidQueryError
from app.models.column import Column
from app.models.row_query import RowQuery, SortDirection
from app.repositories.identifiers import quote_identifier

_LIKE_SPECIAL_CHARS = re.compile(r"([\\%_])")


def _escape_like_term(value: str) -> str:
    """Escape `\\`, `%` and `_` so they are matched literally by ILIKE."""
    return _LIKE_SPECIAL_CHARS.sub(r"\\\1", value)


@dataclass(frozen=True, slots=True)
class BuiltQuery:
    """A parameterized SELECT/COUNT pair produced by `RowQueryBuilder`."""

    select_sql: str
    select_params: list[Any]
    count_sql: str
    count_params: list[Any]


@dataclass(frozen=True, slots=True)
class BuiltExport:
    """An unpaginated parameterized SELECT produced by `RowQueryBuilder`."""

    sql: str
    params: list[Any]


class RowQueryBuilder:
    """Builds parameterized SELECT and COUNT SQL from a table, its columns and a RowQuery."""

    def build(self, table: str, columns: list[Column], query: RowQuery) -> BuiltQuery:
        column_names = {column.name for column in columns}
        self._validate(query, column_names)

        where_sql, where_params = self._build_where(columns, query)
        select_sql = self._build_select(table, columns, query, where_sql)

        count_sql = f"SELECT COUNT(*) FROM {quote_identifier(table)}{where_sql}"

        return BuiltQuery(
            select_sql=f"{select_sql} LIMIT ? OFFSET ?",
            select_params=[*where_params, query.per_page, query.offset],
            count_sql=count_sql,
            count_params=list(where_params),
        )

    def build_export(self, table: str, columns: list[Column], query: RowQuery) -> BuiltExport:
        """Build the same filtered, sorted SELECT as `build`, without paging.

        Used by exports, which cover every matching row rather than one page.

        Raises:
            InvalidQueryError: if `query` references an unknown column.
        """
        column_names = {column.name for column in columns}
        self._validate(query, column_names)

        where_sql, where_params = self._build_where(columns, query)

        return BuiltExport(
            sql=self._build_select(table, columns, query, where_sql),
            params=list(where_params),
        )

    def _build_select(
        self, table: str, columns: list[Column], query: RowQuery, where_sql: str
    ) -> str:
        order_sql = self._build_order_by(columns, query)
        return f"SELECT * FROM {quote_identifier(table)}{where_sql} {order_sql}"

    def _validate(self, query: RowQuery, column_names: set[str]) -> None:
        for name in query.filters:
            if name not in column_names:
                raise InvalidQueryError(f"Unknown filter column: {name!r}")
        if query.sort_by is not None and query.sort_by not in column_names:
            raise InvalidQueryError(f"Unknown sort column: {query.sort_by!r}")

    def _build_where(self, columns: list[Column], query: RowQuery) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if query.search:
            pattern = f"%{_escape_like_term(query.search)}%"
            search_clauses = []
            for column in columns:
                search_clauses.append(self._like_clause(column.name))
                params.append(pattern)
            clauses.append("(" + " OR ".join(search_clauses) + ")")

        # Column filters anchor at the start of the value: filtering a numeric
        # column by "0" should match 0, not 100.
        for name, value in query.filters.items():
            clauses.append(self._like_clause(name))
            params.append(f"{_escape_like_term(value)}%")

        if not clauses:
            return "", []
        return " WHERE " + " AND ".join(clauses), params

    def _like_clause(self, column_name: str) -> str:
        quoted = quote_identifier(column_name)
        return f"CAST({quoted} AS VARCHAR) ILIKE ? ESCAPE '\\'"

    def _build_order_by(self, columns: list[Column], query: RowQuery) -> str:
        tiebreaker = self._tiebreaker(columns)

        if query.sort_by is None:
            return f"ORDER BY {tiebreaker}"

        direction = "ASC" if query.sort_dir == SortDirection.ASC else "DESC"
        quoted_sort_column = quote_identifier(query.sort_by)
        return f"ORDER BY {quoted_sort_column} {direction} NULLS LAST, {tiebreaker}"

    def _tiebreaker(self, columns: list[Column]) -> str:
        has_user_rowid = any(column.name.lower() == "rowid" for column in columns)
        if has_user_rowid:
            return ", ".join(quote_identifier(column.name) for column in columns)
        return "rowid"
