import json

import duckdb
import pytest

from app.exceptions import DatasetNotFoundError, IngestError, InvalidQueryError
from app.models.row_query import RowQuery, SortDirection
from app.repositories.duckdb_repository import DuckDBRepository
from app.repositories.row_query_builder import BuiltExport


@pytest.fixture
def connection():
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def repository(connection):
    return DuckDBRepository(connection)


def test_create_table_from_csv_returns_number_of_rows_loaded(repository, tmp_path):
    csv_path = tmp_path / "people.csv"
    csv_path.write_text("id,name\n1,Alice\n2,Bob\n")

    row_count = repository.create_table_from_csv("people", csv_path)

    assert row_count == 2


def test_create_table_from_csv_replaces_existing_table_with_same_name(repository, tmp_path):
    first_csv = tmp_path / "people.csv"
    first_csv.write_text("id,name\n1,Alice\n")
    repository.create_table_from_csv("people", first_csv)

    second_csv = tmp_path / "people2.csv"
    second_csv.write_text("id,name\n1,Alice\n2,Bob\n3,Carol\n")
    row_count = repository.create_table_from_csv("people", second_csv)

    assert row_count == 3
    assert repository.count_rows("people") == 3


@pytest.mark.parametrize(
    "csv_bytes",
    [
        pytest.param(b"", id="empty_file"),
        pytest.param(bytes(range(256)), id="duckdb_sniffing_failure"),
    ],
)
def test_create_table_from_csv_raises_single_line_ingest_error_for_empty_or_malformed_csv(
    repository, tmp_path, csv_bytes
):
    csv_path = tmp_path / "broken.csv"
    csv_path.write_bytes(csv_bytes)

    with pytest.raises(IngestError) as exc_info:
        repository.create_table_from_csv("broken", csv_path)

    message = str(exc_info.value)
    assert "\n" not in message
    assert len(message) <= 250


def test_create_table_from_csv_falls_back_to_latin1_when_utf8_decoding_fails(repository, tmp_path):
    csv_path = tmp_path / "cities.csv"
    csv_path.write_bytes("id,city\n1,Zürich\n".encode("latin-1"))

    row_count = repository.create_table_from_csv("cities", csv_path)

    assert row_count == 1
    rows = repository._conn.execute('SELECT city FROM "cities"').fetchall()
    assert rows == [("Zürich",)]


def test_create_table_from_csv_supports_column_names_with_spaces_and_quotes(repository, tmp_path):
    csv_path = tmp_path / "weird.csv"
    csv_path.write_text('first name,"say ""hi"""\nAlice,hello\n')

    row_count = repository.create_table_from_csv("weird", csv_path)

    assert row_count == 1
    columns = repository.get_columns("weird")
    assert [column.name for column in columns] == ["first name", 'say "hi"']


def test_get_columns_returns_names_and_types_in_file_order(repository, tmp_path):
    csv_path = tmp_path / "typed.csv"
    csv_path.write_text("id,name,score\n1,Alice,9.5\n2,Bob,8.1\n")
    repository.create_table_from_csv("typed", csv_path)

    columns = repository.get_columns("typed")

    assert [column.name for column in columns] == ["id", "name", "score"]
    assert columns[0].type == "BIGINT"
    assert columns[1].type == "VARCHAR"
    assert columns[2].type == "DOUBLE"


def test_drop_table_removes_table_so_table_exists_is_false(repository, tmp_path):
    csv_path = tmp_path / "temp.csv"
    csv_path.write_text("id\n1\n")
    repository.create_table_from_csv("temp", csv_path)
    assert repository.table_exists("temp") is True

    repository.drop_table("temp")

    assert repository.table_exists("temp") is False


def test_fetch_page_returns_requested_slice_of_rows(repository, tmp_path):
    csv_path = tmp_path / "numbers.csv"
    csv_path.write_text("id\n" + "\n".join(str(n) for n in range(1, 11)))
    repository.create_table_from_csv("numbers", csv_path)

    page = repository.fetch_page("numbers", RowQuery(page=2, per_page=3))

    assert [row["id"] for row in page.rows] == [4, 5, 6]


def test_fetch_page_total_reflects_filtered_row_count(repository, tmp_path):
    csv_path = tmp_path / "people.csv"
    csv_path.write_text("id,name\n1,Alice\n2,Bob\n3,Alicia\n")
    repository.create_table_from_csv("people", csv_path)

    page = repository.fetch_page("people", RowQuery(search="Ali"))

    assert page.total == 2


def test_fetch_page_returns_rows_as_dicts_keyed_by_column_name(repository, tmp_path):
    csv_path = tmp_path / "people.csv"
    csv_path.write_text("id,name\n1,Alice\n")
    repository.create_table_from_csv("people", csv_path)

    page = repository.fetch_page("people", RowQuery())

    assert page.rows == [{"id": 1, "name": "Alice"}]


def test_fetch_page_serializes_dates_and_timestamps_as_iso_strings(repository):
    repository._conn.execute("CREATE TABLE events (event_date DATE, event_ts TIMESTAMP)")
    repository._conn.execute(
        "INSERT INTO events VALUES (?, ?)",
        ["2024-01-15", "2024-01-15 10:30:00"],
    )

    page = repository.fetch_page("events", RowQuery())

    assert page.rows == [{"event_date": "2024-01-15", "event_ts": "2024-01-15T10:30:00"}]


def test_fetch_page_serializes_decimals_as_strings(repository):
    repository._conn.execute("CREATE TABLE prices (amount DECIMAL(10,2))")
    repository._conn.execute("INSERT INTO prices VALUES (?)", [19.99])

    page = repository.fetch_page("prices", RowQuery())

    assert page.rows == [{"amount": "19.99"}]


def test_fetch_page_serializes_non_finite_floats_as_strings(repository, tmp_path):
    csv_path = tmp_path / "measurements.csv"
    csv_path.write_text("value\n1.5\nNaN\ninf\n-inf\n")
    repository.create_table_from_csv("measurements", csv_path)

    page = repository.fetch_page("measurements", RowQuery())

    assert [row["value"] for row in page.rows] == [1.5, "NaN", "Infinity", "-Infinity"]
    assert json.dumps(page.to_dict(), allow_nan=False)


def test_fetch_page_raises_dataset_not_found_for_unknown_table(repository):
    with pytest.raises(DatasetNotFoundError):
        repository.fetch_page("does_not_exist", RowQuery())


def test_fetch_page_beyond_last_page_returns_empty_rows_with_total(repository, tmp_path):
    csv_path = tmp_path / "people.csv"
    csv_path.write_text("id,name\n1,Alice\n2,Bob\n")
    repository.create_table_from_csv("people", csv_path)

    page = repository.fetch_page("people", RowQuery(page=5, per_page=10))

    assert page.rows == []
    assert page.total == 2


def test_stream_rows_returns_columns_and_every_filtered_row_ignoring_paging(repository, tmp_path):
    csv_path = tmp_path / "people.csv"
    csv_path.write_text("id,name\n1,Alice\n2,Bob\n3,Alan\n4,Carol\n5,Amy\n")
    repository.create_table_from_csv("people", csv_path)
    query = RowQuery(
        page=2,
        per_page=2,
        filters={"name": "a"},
        sort_by="name",
        sort_dir=SortDirection.ASC,
    )

    stream = repository.stream_rows("people", query)

    assert [column.name for column in stream.columns] == ["id", "name"]
    assert list(stream.rows) == [
        {"id": 3, "name": "Alan"},
        {"id": 1, "name": "Alice"},
        {"id": 5, "name": "Amy"},
    ]


def test_stream_rows_yields_rows_spanning_more_than_one_fetch_batch(repository, tmp_path):
    row_count = 2500
    csv_path = tmp_path / "numbers.csv"
    csv_path.write_text("id\n" + "\n".join(str(n) for n in range(1, row_count + 1)) + "\n")
    repository.create_table_from_csv("numbers", csv_path)

    rows = list(repository.stream_rows("numbers", RowQuery()).rows)

    assert len(rows) == row_count
    assert rows[0] == {"id": 1}
    assert rows[-1] == {"id": row_count}


def test_stream_rows_normalizes_values_the_same_way_fetch_page_does(repository):
    repository._conn.execute("CREATE TABLE events (event_ts TIMESTAMP, amount DECIMAL(10,2))")
    repository._conn.execute("INSERT INTO events VALUES (?, ?)", ["2024-01-15 10:30:00", 19.99])

    rows = list(repository.stream_rows("events", RowQuery()).rows)

    assert rows == [{"event_ts": "2024-01-15T10:30:00", "amount": "19.99"}]


def test_stream_rows_raises_dataset_not_found_before_iteration_starts(repository):
    with pytest.raises(DatasetNotFoundError):
        repository.stream_rows("does_not_exist", RowQuery())


def test_stream_rows_raises_invalid_query_error_before_iteration_starts(repository, tmp_path):
    csv_path = tmp_path / "people.csv"
    csv_path.write_text("id,name\n1,Alice\n")
    repository.create_table_from_csv("people", csv_path)

    with pytest.raises(InvalidQueryError):
        repository.stream_rows("people", RowQuery(filters={"bogus": "x"}))


def test_stream_rows_closes_its_cursor_and_propagates_when_the_query_fails(connection, tmp_path):
    class _BrokenQueryBuilder:
        def build_export(self, table, columns, query):
            return BuiltExport(sql="SELECT * FROM no_such_table", params=[])

    repository = DuckDBRepository(connection, query_builder=_BrokenQueryBuilder())
    csv_path = tmp_path / "people.csv"
    csv_path.write_text("id,name\n1,Alice\n")
    repository.create_table_from_csv("people", csv_path)

    with pytest.raises(duckdb.Error):
        repository.stream_rows("people", RowQuery())

    assert repository.count_rows("people") == 1


def test_stream_rows_releases_its_cursor_when_abandoned_part_way_through(repository, tmp_path):
    csv_path = tmp_path / "numbers.csv"
    csv_path.write_text("id\n" + "\n".join(str(n) for n in range(1, 11)) + "\n")
    repository.create_table_from_csv("numbers", csv_path)

    stream = repository.stream_rows("numbers", RowQuery())
    assert next(stream.rows) == {"id": 1}
    stream.rows.close()

    assert repository.count_rows("numbers") == 10
