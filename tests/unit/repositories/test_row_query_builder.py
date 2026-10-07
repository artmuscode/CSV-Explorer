import duckdb
import pytest

from app.exceptions import InvalidQueryError
from app.models.column import Column
from app.models.row_query import RowQuery, SortDirection
from app.repositories.row_query_builder import RowQueryBuilder


@pytest.fixture
def connection():
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def builder():
    return RowQueryBuilder()


def _fetch(connection, built_query):
    rows = connection.execute(built_query.select_sql, built_query.select_params).fetchall()
    total = connection.execute(built_query.count_sql, built_query.count_params).fetchone()[0]
    return rows, total


def test_build_without_filters_returns_rows_in_insertion_order_with_limit_and_offset(
    connection, builder
):
    connection.execute("CREATE TABLE people (id INTEGER, name VARCHAR)")
    connection.executemany(
        "INSERT INTO people VALUES (?, ?)",
        [(1, "Alice"), (2, "Bob"), (3, "Carol"), (4, "Dan"), (5, "Eve")],
    )
    columns = [Column(name="id", type="INTEGER"), Column(name="name", type="VARCHAR")]

    built = builder.build("people", columns, RowQuery(page=2, per_page=2))
    rows, total = _fetch(connection, built)

    assert rows == [(3, "Carol"), (4, "Dan")]
    assert total == 5


def test_build_search_matches_any_column_case_insensitively(connection, builder):
    connection.execute("CREATE TABLE people (name VARCHAR, city VARCHAR)")
    connection.executemany(
        "INSERT INTO people VALUES (?, ?)",
        [("Alice", "Boston"), ("Bob", "Chicago"), ("Carol", "Dallas")],
    )
    columns = [Column(name="name", type="VARCHAR"), Column(name="city", type="VARCHAR")]

    built = builder.build("people", columns, RowQuery(search="ALICE"))
    rows, total = _fetch(connection, built)
    assert rows == [("Alice", "Boston")]
    assert total == 1

    built = builder.build("people", columns, RowQuery(search="chicago"))
    rows, total = _fetch(connection, built)
    assert rows == [("Bob", "Chicago")]
    assert total == 1


def test_build_column_filters_are_combined_with_and(connection, builder):
    connection.execute("CREATE TABLE people (name VARCHAR, city VARCHAR)")
    connection.executemany(
        "INSERT INTO people VALUES (?, ?)",
        [("Alice", "Wonderland"), ("Alison", "Boston"), ("Bob", "Wonderland")],
    )
    columns = [Column(name="name", type="VARCHAR"), Column(name="city", type="VARCHAR")]

    built = builder.build("people", columns, RowQuery(filters={"name": "ali", "city": "wonder"}))
    rows, total = _fetch(connection, built)

    assert rows == [("Alice", "Wonderland")]
    assert total == 1


def test_build_column_filters_match_only_from_the_start_of_a_value(connection, builder):
    connection.execute("CREATE TABLE readings (amount INTEGER, label VARCHAR)")
    connection.executemany(
        "INSERT INTO readings VALUES (?, ?)",
        [(0, "zero"), (100, "hundred"), (10, "ten"), (-100, "minus"), (1, "one")],
    )
    columns = [Column(name="amount", type="INTEGER"), Column(name="label", type="VARCHAR")]

    built = builder.build("readings", columns, RowQuery(filters={"amount": "0"}))
    rows, total = _fetch(connection, built)

    assert rows == [(0, "zero")]
    assert total == 1


def test_build_global_search_still_matches_anywhere_in_a_value(connection, builder):
    connection.execute("CREATE TABLE readings (amount INTEGER, label VARCHAR)")
    connection.executemany(
        "INSERT INTO readings VALUES (?, ?)",
        [(0, "zero"), (100, "hundred"), (10, "ten")],
    )
    columns = [Column(name="amount", type="INTEGER"), Column(name="label", type="VARCHAR")]

    built = builder.build("readings", columns, RowQuery(search="0"))
    rows, total = _fetch(connection, built)

    assert rows == [(0, "zero"), (100, "hundred"), (10, "ten")]
    assert total == 3


def test_build_treats_percent_and_underscore_in_user_input_literally(connection, builder):
    connection.execute("CREATE TABLE deals (description VARCHAR)")
    connection.executemany(
        "INSERT INTO deals VALUES (?)",
        [("50% off",), ("50X off",), ("a_b",), ("axb",)],
    )
    columns = [Column(name="description", type="VARCHAR")]

    built = builder.build("deals", columns, RowQuery(search="50%"))
    rows, total = _fetch(connection, built)
    assert rows == [("50% off",)]
    assert total == 1

    built = builder.build("deals", columns, RowQuery(search="a_b"))
    rows, total = _fetch(connection, built)
    assert rows == [("a_b",)]
    assert total == 1


def test_build_treats_percent_and_underscore_in_column_filters_literally(connection, builder):
    connection.execute("CREATE TABLE deals (description VARCHAR)")
    connection.executemany(
        "INSERT INTO deals VALUES (?)",
        [("50% off",), ("50X off",), ("a_b",), ("axb",)],
    )
    columns = [Column(name="description", type="VARCHAR")]

    built = builder.build("deals", columns, RowQuery(filters={"description": "50%"}))
    rows, total = _fetch(connection, built)
    assert rows == [("50% off",)]
    assert total == 1

    built = builder.build("deals", columns, RowQuery(filters={"description": "a_"}))
    rows, total = _fetch(connection, built)
    assert rows == [("a_b",)]
    assert total == 1


def test_build_sorts_by_requested_column_and_direction_with_nulls_last(connection, builder):
    connection.execute("CREATE TABLE people (id INTEGER, score INTEGER)")
    connection.executemany(
        "INSERT INTO people VALUES (?, ?)",
        [(1, 30), (2, None), (3, 10), (4, 20)],
    )
    columns = [Column(name="id", type="INTEGER"), Column(name="score", type="INTEGER")]

    built = builder.build("people", columns, RowQuery(sort_by="score", sort_dir=SortDirection.ASC))
    rows, _ = _fetch(connection, built)
    assert rows == [(3, 10), (4, 20), (1, 30), (2, None)]

    built = builder.build("people", columns, RowQuery(sort_by="score", sort_dir=SortDirection.DESC))
    rows, _ = _fetch(connection, built)
    assert rows == [(1, 30), (4, 20), (3, 10), (2, None)]

    # A user column named "rowid" shadows DuckDB's hidden rowid, so ties fall
    # back to ordering by every column (in ordinal position order) instead.
    connection.execute('CREATE TABLE weird ("rowid" INTEGER, score INTEGER)')
    connection.executemany("INSERT INTO weird VALUES (?, ?)", [(2, 10), (1, 10)])
    weird_columns = [Column(name="rowid", type="INTEGER"), Column(name="score", type="INTEGER")]

    built = builder.build("weird", weird_columns, RowQuery(sort_by="score"))
    rows, _ = _fetch(connection, built)
    assert rows == [(1, 10), (2, 10)]


def test_build_raises_invalid_query_error_for_unknown_filter_column(connection, builder):
    columns = [Column(name="name", type="VARCHAR")]

    with pytest.raises(InvalidQueryError):
        builder.build("people", columns, RowQuery(filters={"bogus": "x"}))


def test_build_raises_invalid_query_error_for_unknown_sort_column(connection, builder):
    columns = [Column(name="name", type="VARCHAR")]

    with pytest.raises(InvalidQueryError):
        builder.build("people", columns, RowQuery(sort_by="bogus"))


def test_build_export_returns_every_matching_row_ignoring_paging(connection, builder):
    connection.execute("CREATE TABLE people (id INTEGER, name VARCHAR)")
    connection.executemany(
        "INSERT INTO people VALUES (?, ?)",
        [(1, "Alice"), (2, "Bob"), (3, "Alan"), (4, "Carol"), (5, "Amy")],
    )
    columns = [Column(name="id", type="INTEGER"), Column(name="name", type="VARCHAR")]
    query = RowQuery(
        page=2,
        per_page=2,
        filters={"name": "a"},
        sort_by="name",
        sort_dir=SortDirection.ASC,
    )

    built = builder.build_export("people", columns, query)
    rows = connection.execute(built.sql, built.params).fetchall()

    assert "LIMIT" not in built.sql.upper()
    assert "OFFSET" not in built.sql.upper()
    assert rows == [(3, "Alan"), (1, "Alice"), (5, "Amy")]


def test_build_export_uses_the_same_where_and_order_by_as_build(connection, builder):
    columns = [Column(name="id", type="INTEGER"), Column(name="name", type="VARCHAR")]
    query = RowQuery(search="a", filters={"name": "b"}, sort_by="name", sort_dir=SortDirection.DESC)

    paged = builder.build("people", columns, query)
    export = builder.build_export("people", columns, query)

    assert export.sql == paged.select_sql.removesuffix(" LIMIT ? OFFSET ?")
    assert export.params == paged.select_params[:-2]


@pytest.mark.parametrize(
    "query",
    [RowQuery(filters={"bogus": "x"}), RowQuery(sort_by="bogus")],
)
def test_build_export_raises_invalid_query_error_for_unknown_columns(connection, builder, query):
    columns = [Column(name="name", type="VARCHAR")]

    with pytest.raises(InvalidQueryError):
        builder.build_export("people", columns, query)
