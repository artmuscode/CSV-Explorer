"""Integration tests for the ingest blueprint: upload, URL ingest, folder scan."""

import io

from tests.fakes import FakeResponse


def _flashed_messages(client):
    with client.session_transaction() as session:
        return [message for _category, message in session.get("_flashes", [])]


def test_upload_ingests_csv_and_redirects_to_dataset_view(client):
    data = {"file": (io.BytesIO(b"id,name\n1,Ada\n2,Grace\n"), "people.csv")}

    response = client.post(
        "/ingest/upload", data=data, content_type="multipart/form-data", follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/datasets/people"
    messages = _flashed_messages(client)
    assert any("people" in message and "2" in message for message in messages)


def test_upload_without_file_flashes_error_and_redirects_home(client):
    response = client.post("/ingest/upload", data={}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert _flashed_messages(client)


def test_upload_of_unloadable_csv_flashes_error(client):
    data = {"file": (io.BytesIO(b""), "broken.csv")}

    response = client.post(
        "/ingest/upload", data=data, content_type="multipart/form-data", follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert _flashed_messages(client)


def test_upload_exceeding_max_content_length_flashes_error(make_app):
    app = make_app(MAX_CONTENT_LENGTH=1024)
    client = app.test_client()
    data = {"file": (io.BytesIO(b"a" * 2048), "big.csv")}

    response = client.post(
        "/ingest/upload", data=data, content_type="multipart/form-data", follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    messages = _flashed_messages(client)
    assert any("too large" in message.lower() for message in messages)


def test_url_ingest_redirects_to_dataset_view_on_success(client, fake_network):
    fake_network.routes["https://example.com/sales.csv"] = FakeResponse(
        body=b"a,b\n1,2\n", headers={"Content-Type": "text/csv"}
    )

    response = client.post(
        "/ingest/url", data={"url": "https://example.com/sales.csv"}, follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/datasets/sales"
    messages = _flashed_messages(client)
    assert any("sales" in message for message in messages)


def test_url_ingest_flashes_error_for_blocked_private_address(client, fake_network):
    fake_network.dns["internal.test"] = ["127.0.0.1"]

    response = client.post(
        "/ingest/url", data={"url": "https://internal.test/data.csv"}, follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert _flashed_messages(client)


def test_scan_flashes_summary_of_ingested_skipped_and_failed_files(client, write_csv):
    write_csv("people.csv", "id,name\n1,Ada\n")
    write_csv("broken.csv", "")

    response = client.post("/ingest/scan", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    messages = _flashed_messages(client)
    assert any("Ingested 1, skipped 0, failed 1" in message for message in messages)


def test_scan_with_many_failures_caps_flashed_errors_and_session_cookie_stays_small(
    client, write_csv
):
    for index in range(7):
        write_csv(f"broken{index}.csv", "")

    response = client.post("/ingest/scan", follow_redirects=False)

    assert response.status_code == 302
    messages = _flashed_messages(client)
    error_detail_messages = [message for message in messages if message.startswith("broken")]
    assert len(error_detail_messages) == 5
    assert any("…and 2 more" in message for message in messages)

    set_cookie_header = response.headers.get("Set-Cookie", "")
    assert len(set_cookie_header) < 4000
