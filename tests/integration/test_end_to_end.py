"""End-to-end tests: full stack, from an HTTP request through the service
container and repository to DuckDB and back, for every ingest path.

These go through the Flask test client only (no real network, no real
`data/` directory — `make_app`/`client`/`write_csv`/`fake_network` all point
at `tmp_path`). Network is always faked with `fake_network` (task 014).
"""

import io

from tests.fakes import FakeResponse


def _flashed_messages(client):
    with client.session_transaction() as session:
        return [message for _category, message in session.get("_flashes", [])]


def test_end_to_end_scan_folder_then_query_rows_api_with_filters(client, write_csv):
    write_csv(
        "sales.csv",
        "name,city,amount\nada,london,10\ngrace,paris,20\nada,paris,30\n",
    )

    scan_response = client.post("/ingest/scan", follow_redirects=False)
    assert scan_response.status_code == 302
    assert any("Ingested 1" in message for message in _flashed_messages(client))

    rows_response = client.get(
        "/api/datasets/sales/rows?q=ada&filter[city]=paris&sort=amount&dir=desc"
    )

    assert rows_response.status_code == 200
    payload = rows_response.get_json()
    assert payload["total"] == 1
    assert payload["rows"][0]["name"] == "ada"
    assert payload["rows"][0]["city"] == "paris"
    assert payload["rows"][0]["amount"] == 30


def test_end_to_end_upload_then_reupload_replaces_rows(client):
    first = {"file": (io.BytesIO(b"id,name\n1,Ada\n2,Grace\n"), "people.csv")}
    first_response = client.post(
        "/ingest/upload", data=first, content_type="multipart/form-data", follow_redirects=False
    )
    assert first_response.status_code == 302
    assert first_response.headers["Location"] == "/datasets/people"
    assert any(
        "Created" in message and "2 rows" in message for message in _flashed_messages(client)
    )

    first_rows = client.get("/api/datasets/people/rows").get_json()
    assert first_rows["total"] == 2

    second = {"file": (io.BytesIO(b"id,name\n1,Ada\n2,Grace\n3,Alan\n"), "people.csv")}
    second_response = client.post(
        "/ingest/upload", data=second, content_type="multipart/form-data", follow_redirects=False
    )
    assert second_response.status_code == 302
    assert any(
        "Replaced" in message and "3 rows" in message for message in _flashed_messages(client)
    )

    second_rows = client.get("/api/datasets/people/rows").get_json()
    assert second_rows["total"] == 3
    names = {row["name"] for row in second_rows["rows"]}
    assert names == {"Ada", "Grace", "Alan"}


def test_end_to_end_url_ingest_then_view_then_delete(client, fake_network):
    fake_network.routes["https://example.com/sales.csv"] = FakeResponse(
        body=b"name,amount\nada,10\ngrace,20\n", headers={"Content-Type": "text/csv"}
    )

    ingest_response = client.post(
        "/ingest/url", data={"url": "https://example.com/sales.csv"}, follow_redirects=False
    )
    assert ingest_response.status_code == 302
    assert ingest_response.headers["Location"] == "/datasets/sales"

    show_response = client.get("/datasets/sales")
    assert show_response.status_code == 200
    body = show_response.get_data(as_text=True)
    assert "sales" in body
    assert "URL: https://example.com/sales.csv" in body

    delete_response = client.post(
        "/datasets/sales/delete",
        headers={"Origin": "http://localhost"},
        base_url="http://localhost",
        follow_redirects=False,
    )
    assert delete_response.status_code == 302
    assert delete_response.headers["Location"] == "/"

    after_delete = client.get("/datasets/sales")
    assert after_delete.status_code == 404

    index_response = client.get("/")
    assert "sales" not in index_response.get_data(as_text=True)


def test_end_to_end_malicious_csv_headers_are_escaped_on_every_page(client, write_csv):
    malicious_header = "<script>alert(1)</script>"
    lines = [f"{malicious_header},amount"]
    for i in range(1, 41):
        lines.append(f"row{i},{i}")
    write_csv("evil.csv", "\n".join(lines) + "\n")

    scan_response = client.post("/ingest/scan", follow_redirects=False)
    assert scan_response.status_code == 302

    show_response = client.get("/datasets/evil")
    assert show_response.status_code == 200
    html_body = show_response.get_data(as_text=True)
    assert malicious_header not in html_body
    assert "\\u003cscript\\u003e" in html_body

    page_one = client.get("/api/datasets/evil/rows?page=1&per_page=10")
    page_two = client.get("/api/datasets/evil/rows?page=2&per_page=10")

    for response in (page_one, page_two):
        assert response.status_code == 200
        assert response.content_type == "application/json"
        payload = response.get_json()
        column_names = [column["name"] for column in payload["columns"]]
        assert malicious_header in column_names


def test_end_to_end_deleted_folder_dataset_stays_deleted_after_rescan_until_file_changes(
    client, write_csv
):
    path = write_csv("sales.csv", "name,amount\nada,10\n")
    client.post("/ingest/scan", follow_redirects=False)
    assert client.get("/datasets/sales").status_code == 200

    delete_response = client.post(
        "/datasets/sales/delete",
        headers={"Origin": "http://localhost"},
        base_url="http://localhost",
        follow_redirects=False,
    )
    assert delete_response.status_code == 302
    assert client.get("/datasets/sales").status_code == 404

    rescan_response = client.post("/ingest/scan", follow_redirects=False)
    assert rescan_response.status_code == 302
    assert any("Ingested 0, skipped 1" in message for message in _flashed_messages(client))
    assert client.get("/datasets/sales").status_code == 404

    path.write_text("name,amount\nada,10\ngrace,20\n")
    client.post("/ingest/scan", follow_redirects=False)

    restored_response = client.get("/datasets/sales")
    assert restored_response.status_code == 200
    rows = client.get("/api/datasets/sales/rows").get_json()
    assert rows["total"] == 2


def test_end_to_end_cross_origin_delete_is_blocked_and_dataset_survives(client, ingested):
    ingested("sales.csv", "name,amount\nada,10\n")

    delete_response = client.post(
        "/datasets/sales/delete",
        headers={"Origin": "http://evil.example"},
        base_url="http://localhost",
        follow_redirects=False,
    )

    assert delete_response.status_code == 403

    show_response = client.get("/datasets/sales")
    assert show_response.status_code == 200
