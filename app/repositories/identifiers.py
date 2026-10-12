"""Pure helpers for safely quoting DuckDB identifiers and literals.

Table and column names can't be bound as SQL parameters, so these helpers are
the one place identifier safety is handled.
"""

import re

_NON_ALPHANUMERIC_RUN = re.compile(r"[^a-z0-9]+")
_CSV_SUFFIX = re.compile(r"\.csv$", re.IGNORECASE)


def quote_identifier(name: str) -> str:
    """Double-quote a DuckDB identifier, escaping embedded double quotes."""
    return '"' + name.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    """Single-quote a DuckDB string literal, escaping embedded single quotes.

    This is the fallback for file paths passed to `read_csv_auto`, and only
    ever takes server-generated paths.
    """
    return "'" + value.replace("'", "''") + "'"


def table_name_from_filename(filename: str) -> str:
    """Derive a safe DuckDB table name from a CSV file name.

    Raises:
        ValueError: if nothing usable remains after sanitization.
    """
    stem = _CSV_SUFFIX.sub("", filename).lower()
    sanitized = _NON_ALPHANUMERIC_RUN.sub("_", stem).strip("_")
    if not sanitized:
        raise ValueError(f"No usable table name could be derived from {filename!r}")
    if sanitized[0].isdigit():
        sanitized = f"t_{sanitized}"
    return sanitized
