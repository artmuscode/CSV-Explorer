from app.models.row_query import RowQuery


def test_row_query_offset_is_derived_from_page_and_per_page():
    query = RowQuery(page=3, per_page=25)

    assert query.offset == 50
