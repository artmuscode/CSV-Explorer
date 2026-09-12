from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class SortDirection(StrEnum):
    """Direction to sort rows in a `RowQuery`."""

    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True, slots=True)
class RowQuery:
    """Query parameters for paginating, searching, filtering and sorting rows."""

    page: int = 1
    per_page: int = 25
    search: str = ""
    filters: Mapping[str, str] = field(default_factory=dict)
    sort_by: str | None = None
    sort_dir: SortDirection = SortDirection.ASC

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page
