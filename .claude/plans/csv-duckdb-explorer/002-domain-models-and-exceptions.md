# Task 002: Domain Models (Dataclass DTOs) & Exceptions

**Status**: pending
**Depends on**: 001
**Retry count**: 0

## Description
Create the immutable dataclass DTOs that pass between layers, plus the domain exception hierarchy. They are pure Python with no Flask or DuckDB imports.

## Context
- Related files (new): `app/models/__init__.py` (re-exports), `app/models/column.py`, `app/models/dataset.py`, `app/models/row_query.py`, `app/models/page.py`, `app/models/ingest_result.py`, `app/exceptions.py`, `tests/unit/models/__init__.py`, `tests/unit/models/test_*.py`, `tests/unit/test_exceptions.py`
- Name the model test files after their modules (`test_column.py`, `test_dataset.py`, `test_row_query.py`, `test_page.py`, `test_ingest_result.py`) so they don't clash with test files in other directories.
- All DTOs use `@dataclass(frozen=True, slots=True)`:
  - `Column(name: str, type: str)`
  - `DatasetSource(StrEnum)`: `FOLDER = "folder"`, `UPLOAD = "upload"`, `URL = "url"`
  - `Dataset(name: str, original_filename: str, source: DatasetSource, row_count: int, ingested_at: datetime, source_url: str | None = None, file_size: int | None = None, file_mtime: float | None = None, deleted_at: datetime | None = None)` with a property `is_deleted` → `deleted_at is not None`. **Contract:** `ingested_at` and `deleted_at` are always timezone-aware UTC datetimes. Task 011's clock produces `datetime.now(UTC)`, and task 007 must round-trip them unchanged. Put this in the class docstring.
    - `deleted_at` is the **deletion marker** (the user chose "remember deletions"). Deleting a dataset drops its table and sets `deleted_at` but keeps the metadata row. That way the folder scan can tell the file was deliberately removed, and won't re-ingest it unless the file changes (tasks 007, 012, 013).
  - `SortDirection(StrEnum)`: `ASC = "asc"`, `DESC = "desc"`
  - `RowQuery(page: int = 1, per_page: int = 25, search: str = "", filters: Mapping[str, str] = field(default_factory=dict), sort_by: str | None = None, sort_dir: SortDirection = SortDirection.ASC)` with property `offset` → `(page - 1) * per_page`
  - `Page(rows: list[dict[str, Any]], columns: list[Column], page: int, per_page: int, total: int)`:
    - property `total_pages` → `max(1, ceil(total / per_page))`
    - properties `has_next` and `has_prev`
    - `to_dict()` → `{"rows", "columns": [{"name","type"}], "page", "per_page", "total", "total_pages", "has_next", "has_prev"}`
  - `IngestResult(dataset: Dataset, replaced: bool)`
  - `ScanResult(ingested: list[IngestResult], skipped: list[str], errors: dict[str, str])`
- `app/exceptions.py`: `CsvExplorerError(Exception)` is the base class, with `IngestError`, `DatasetNotFoundError` and `InvalidQueryError` as subclasses.
- Patterns to follow: `.claude/code-standards.md` (DTO rules)

## Requirements (Test Descriptions)
- [ ] `test_row_query_offset_is_derived_from_page_and_per_page`
- [ ] `test_page_total_pages_rounds_up_partial_last_page_and_is_one_when_empty` (parametrized)
- [ ] `test_page_has_next_is_false_on_last_page`
- [ ] `test_page_has_prev_is_false_on_first_page`
- [ ] `test_page_to_dict_includes_rows_columns_and_paging_fields`
- [ ] `test_dataset_is_deleted_reflects_deleted_at`
- [ ] `test_domain_exceptions_inherit_from_csv_explorer_error`

## Acceptance Criteria
- All requirements have passing tests
- Code follows code standards
- No decrease in test coverage

## Implementation Notes
(Left blank - filled in by programmer during implementation)
