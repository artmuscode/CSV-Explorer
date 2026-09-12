from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Column:
    """A single column's name and DuckDB type."""

    name: str
    type: str
