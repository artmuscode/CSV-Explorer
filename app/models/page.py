from dataclasses import dataclass
from math import ceil
from typing import Any

from app.models.column import Column


@dataclass(frozen=True, slots=True)
class Page:
    """A single page of rows returned from a dataset query."""

    rows: list[dict[str, Any]]
    columns: list[Column]
    page: int
    per_page: int
    total: int

    @property
    def total_pages(self) -> int:
        return max(1, ceil(self.total / self.per_page))

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "columns": [{"name": column.name, "type": column.type} for column in self.columns],
            "page": self.page,
            "per_page": self.per_page,
            "total": self.total,
            "total_pages": self.total_pages,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }
