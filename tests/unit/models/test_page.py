import pytest

from app.models.column import Column
from app.models.page import Page


@pytest.mark.parametrize(
    ("total", "per_page", "expected_total_pages"),
    [
        (0, 25, 1),
        (1, 25, 1),
        (25, 25, 1),
        (26, 25, 2),
        (51, 25, 3),
    ],
)
def test_page_total_pages_rounds_up_partial_last_page_and_is_one_when_empty(
    total, per_page, expected_total_pages
):
    page = Page(rows=[], columns=[], page=1, per_page=per_page, total=total)

    assert page.total_pages == expected_total_pages


def test_page_has_next_is_false_on_last_page():
    page = Page(rows=[], columns=[], page=3, per_page=25, total=51)

    assert page.has_next is False


def test_page_has_prev_is_false_on_first_page():
    page = Page(rows=[], columns=[], page=1, per_page=25, total=51)

    assert page.has_prev is False


def test_page_to_dict_includes_rows_columns_and_paging_fields():
    page = Page(
        rows=[{"id": 1, "name": "Alice"}],
        columns=[Column(name="id", type="INTEGER"), Column(name="name", type="VARCHAR")],
        page=1,
        per_page=25,
        total=1,
    )

    assert page.to_dict() == {
        "rows": [{"id": 1, "name": "Alice"}],
        "columns": [
            {"name": "id", "type": "INTEGER"},
            {"name": "name", "type": "VARCHAR"},
        ],
        "page": 1,
        "per_page": 25,
        "total": 1,
        "total_pages": 1,
        "has_next": False,
        "has_prev": False,
    }
