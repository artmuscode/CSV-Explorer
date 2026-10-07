from datetime import UTC, datetime

import duckdb
import pytest

from app.exceptions import DatasetNotFoundError, InvalidQueryError
from app.models.row_query import RowQuery
from app.repositories.duckdb_repository import DuckDBRepository
from app.repositories.metadata_repository import MetadataRepository
from app.services.dataset_service import DatasetService

FIXED_NOW = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def connection():
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def repository(connection):
    return DuckDBRepository(connection)


@pytest.fixture
def metadata(connection):
    repo = MetadataRepository(connection)
    repo.ensure_schema()
    return repo


@pytest.fixture
def service(repository, metadata):
    return DatasetService(repository, metadata, clock=lambda: FIXED_NOW)


def make_dataset(repository, metadata, csv_dir, name, content, ingested_at=FIXED_NOW):
    csv_path = csv_dir / f"{name}.csv"
    csv_path.write_text(content)
    repository.create_table_from_csv(name, csv_path)
    from app.models.dataset import Dataset, DatasetSource

    dataset = Dataset(
        name=name,
        original_filename=f"{name}.csv",
        source=DatasetSource.FOLDER,
        row_count=repository.count_rows(name),
        ingested_at=ingested_at,
    )
    metadata.upsert(dataset)
    return dataset


def test_list_datasets_returns_metadata_newest_first(service, repository, metadata, tmp_path):
    older = make_dataset(
        repository,
        metadata,
        tmp_path,
        "older",
        "id\n1\n",
        ingested_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    newer = make_dataset(
        repository,
        metadata,
        tmp_path,
        "newer",
        "id\n1\n",
        ingested_at=datetime(2026, 2, 1, tzinfo=UTC),
    )

    result = service.list_datasets()

    assert [dataset.name for dataset in result] == [newer.name, older.name]


@pytest.mark.parametrize("scenario", ["unknown", "deleted"])
def test_get_page_raises_dataset_not_found_for_unknown_or_deleted_dataset(
    service, repository, metadata, tmp_path, scenario
):
    if scenario == "deleted":
        make_dataset(repository, metadata, tmp_path, "gone", "id\n1\n")
        metadata.mark_deleted("gone", FIXED_NOW)
        name = "gone"
    else:
        name = "does_not_exist"

    with pytest.raises(DatasetNotFoundError):
        service.get_page(name, RowQuery())


def test_get_page_returns_filtered_page_from_repository(service, repository, metadata, tmp_path):
    make_dataset(
        repository,
        metadata,
        tmp_path,
        "people",
        "id,name\n1,Alice\n2,Bob\n3,Carol\n",
    )

    page = service.get_page("people", RowQuery(filters={"name": "Bob"}))

    assert page.total == 1
    assert page.rows == [{"id": 2, "name": "Bob"}]


@pytest.mark.parametrize("scenario", ["unknown", "deleted"])
def test_export_rows_raises_dataset_not_found_for_unknown_or_deleted_dataset(
    service, repository, metadata, tmp_path, scenario
):
    if scenario == "deleted":
        make_dataset(repository, metadata, tmp_path, "gone", "id\n1\n")
        metadata.mark_deleted("gone", FIXED_NOW)
        name = "gone"
    else:
        name = "does_not_exist"

    with pytest.raises(DatasetNotFoundError):
        service.export_rows(name, RowQuery())


def test_export_rows_returns_all_filtered_rows_ignoring_paging(
    service, repository, metadata, tmp_path
):
    make_dataset(
        repository,
        metadata,
        tmp_path,
        "people",
        "id,name\n1,Alice\n2,Bob\n3,Alan\n",
    )

    stream = service.export_rows("people", RowQuery(page=2, per_page=1, filters={"name": "Al"}))

    assert stream.column_names == ["id", "name"]
    assert list(stream.rows) == [{"id": 1, "name": "Alice"}, {"id": 3, "name": "Alan"}]


def test_build_query_clamps_per_page_to_max_page_size(service):
    query = service.build_query(
        page=None, per_page="9999", search=None, filters={}, sort_by=None, sort_dir=None
    )

    assert query.per_page == service._max_page_size


@pytest.mark.parametrize("page_value", ["abc", "0", "-1", "1000001"])
def test_build_query_raises_invalid_query_error_for_non_integer_or_out_of_range_page(
    service, page_value
):
    with pytest.raises(InvalidQueryError):
        service.build_query(
            page=page_value, per_page=None, search=None, filters={}, sort_by=None, sort_dir=None
        )


def test_build_query_drops_blank_filter_values(service):
    query = service.build_query(
        page=None,
        per_page=None,
        search=None,
        filters={"name": "  Bob  ", "email": "   "},
        sort_by=None,
        sort_dir=None,
    )

    assert query.filters == {"name": "Bob"}


def test_delete_dataset_drops_table_and_hides_it_from_list_while_keeping_marker(
    service, repository, metadata, tmp_path
):
    make_dataset(repository, metadata, tmp_path, "people", "id,name\n1,Alice\n")

    service.delete_dataset("people")

    assert [dataset.name for dataset in service.list_datasets()] == []
    deleted = metadata.get("people")
    assert deleted is not None
    assert deleted.is_deleted is True
