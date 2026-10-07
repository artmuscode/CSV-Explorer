from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from app.models.column import Column


@dataclass(frozen=True, slots=True)
class RowStream:
    """Every row matching a query, streamed instead of paged.

    `rows` is lazy and single-use: it is produced in batches as it is
    consumed, so exporting a large dataset never materializes it all at
    once. `columns` is resolved eagerly, so a caller can write a CSV header
    before pulling the first row.
    """

    columns: list[Column]
    rows: Iterator[dict[str, Any]]

    @property
    def column_names(self) -> list[str]:
        return [column.name for column in self.columns]
