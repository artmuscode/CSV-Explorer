"""Integration tests for the datasets blueprint: table page, rows JSON API and CSV export."""

import csv
import io
import json

import pytest


def _csv_with_rows(n: int) -> str:
    lines = ["name,city,amount"]
    for i in range(1, n + 1):
        lines.append(f"person{i},city{i % 3},{i}")
    return "\n".join(lines) + "\n"


def _parse_csv(response) -> list[list[str]]:
    return list(csv.reader(io.StringIO(response.get_data(as_text=True))))


def test_show_renders_dataset_name_and_column_headers(client, ingested):
    ingested("people.csv", _csv_with_rows(30))

    response = client.get("/datasets/people")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "people" in body

    script_start = body.index('<script type="application/json" id="initial-page">')
    script_start = body.index(">", script_start) + 1
    script_end = body.index("</script>", script_start)
    payload = json.loads(body[script_start:script_end])
    column_names = [column["name"] for column in payload["columns"]]
    assert column_names == ["name", "city", "amount"]


def test_show_embeds_initial_page_as_json(client, ingested):
    ingested("people.csv", _csv_with_rows(30))

    response = client.get("/datasets/people")

    body = response.get_data(as_text=True)
    script_start = body.index('<script type="application/json" id="initial-page">')
    script_start = body.index(">", script_start) + 1
    script_end = body.index("</script>", script_start)
    payload = json.loads(body[script_start:script_end])

    assert payload["page"] == 1
    assert payload["total"] == 30
    assert len(payload["rows"]) == payload["per_page"]
    assert payload["rows"][0]["name"] == "person1"

    assert 'data-rows-url="/api/datasets/people/rows"' in body
    assert "data-max-page-size=" in body


def test_show_unknown_dataset_returns_404(client):
    response = client.get("/datasets/unknown")

    assert response.status_code == 404


def test_rows_api_returns_paged_rows_as_json(client, ingested):
    ingested("people.csv", _csv_with_rows(30))

    response = client.get("/api/datasets/people/rows?page=2&per_page=10")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["page"] == 2
    assert payload["per_page"] == 10
    assert payload["total"] == 30
    assert len(payload["rows"]) == 10
    assert payload["rows"][0]["name"] == "person11"


def test_rows_api_applies_search_column_filters_and_sort(client, ingested):
    ingested("people.csv", _csv_with_rows(30))

    response = client.get(
        "/api/datasets/people/rows?q=person1&filter[city]=city1&sort=amount&dir=desc&per_page=100"
    )

    assert response.status_code == 200
    payload = response.get_json()
    amounts = [row["amount"] for row in payload["rows"]]
    assert amounts == sorted(amounts, reverse=True)
    for row in payload["rows"]:
        assert "person1" in row["name"]
        assert row["city"] == "city1"


def test_rows_api_returns_400_json_for_invalid_query(client, ingested):
    ingested("people.csv", _csv_with_rows(30))

    response = client.get("/api/datasets/people/rows?page=not-a-number")

    assert response.status_code == 400
    payload = response.get_json()
    assert "error" in payload


def test_rows_api_returns_404_json_for_unknown_dataset(client):
    response = client.get("/api/datasets/unknown/rows")

    assert response.status_code == 404
    payload = response.get_json()
    assert payload == {"error": "Dataset not found"}


def test_rows_api_column_filter_matches_only_from_the_start_of_a_value(client, ingested):
    ingested("readings.csv", "label,amount\nzero,0\nhundred,100\nten,10\nminus,-100\n")

    response = client.get("/api/datasets/readings/rows?filter[amount]=0")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total"] == 1
    assert payload["rows"] == [{"label": "zero", "amount": 0}]


def test_export_streams_every_filtered_row_as_csv_ignoring_paging(client, ingested):
    ingested("people.csv", _csv_with_rows(30))

    response = client.get("/datasets/people/export.csv?filter[city]=city1&page=3&per_page=5")

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/csv; charset=utf-8"

    rows = _parse_csv(response)
    assert rows[0] == ["name", "city", "amount"]
    assert len(rows) == 11
    assert all(row[1] == "city1" for row in rows[1:])


def test_export_applies_search_and_sort(client, ingested):
    ingested("people.csv", _csv_with_rows(30))

    response = client.get("/datasets/people/export.csv?q=person1&sort=amount&dir=desc")

    assert response.status_code == 200
    rows = _parse_csv(response)
    assert rows[0] == ["name", "city", "amount"]

    amounts = [int(row[2]) for row in rows[1:]]
    assert amounts == [19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 1]


def test_export_sends_a_csv_attachment_named_after_the_dataset(client, ingested):
    ingested("people.csv", _csv_with_rows(3))

    response = client.get("/datasets/people/export.csv")

    disposition = response.headers["Content-Disposition"]
    assert disposition.startswith("attachment;")
    assert 'filename="people-' in disposition
    assert disposition.endswith('.csv"')


def test_export_streams_a_dataset_larger_than_one_flush_batch(client, ingested):
    row_count = 1200
    ingested("people.csv", _csv_with_rows(row_count))

    response = client.get("/datasets/people/export.csv")

    assert response.status_code == 200
    rows = _parse_csv(response)
    assert len(rows) == row_count + 1
    assert rows[1][0] == "person1"
    assert rows[-1][0] == f"person{row_count}"


def test_export_of_a_filter_matching_nothing_returns_just_the_header_row(client, ingested):
    ingested("people.csv", _csv_with_rows(3))

    response = client.get("/datasets/people/export.csv?filter[name]=nobody")

    assert response.status_code == 200
    assert _parse_csv(response) == [["name", "city", "amount"]]


def test_export_returns_404_for_unknown_dataset(client):
    response = client.get("/datasets/unknown/export.csv")

    assert response.status_code == 404


@pytest.mark.parametrize("query_string", ["sort=bogus", "dir=sideways", "filter[bogus]=x"])
def test_export_returns_400_for_invalid_query(client, ingested, query_string):
    ingested("people.csv", _csv_with_rows(3))

    response = client.get(f"/datasets/people/export.csv?{query_string}")

    assert response.status_code == 400
