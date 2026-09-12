"""Integration tests for the datasets blueprint: table page and rows JSON API."""

import json


def _csv_with_rows(n: int) -> str:
    lines = ["name,city,amount"]
    for i in range(1, n + 1):
        lines.append(f"person{i},city{i % 3},{i}")
    return "\n".join(lines) + "\n"


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
