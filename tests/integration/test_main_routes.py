"""Integration tests for the main blueprint: dataset list and delete."""

import pytest


def test_index_lists_ingested_datasets_with_row_counts(client, ingested):
    ingested("people.csv", "id,name\n1,Ada\n2,Grace\n")

    response = client.get("/")

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "people" in body
    assert "2" in body


def test_index_links_each_dataset_to_its_table_view(client, ingested):
    ingested("people.csv", "id,name\n1,Ada\n")

    response = client.get("/")

    body = response.get_data(as_text=True)
    assert '/datasets/people"' in body


def test_index_shows_empty_state_when_no_datasets(client):
    response = client.get("/")

    body = response.get_data(as_text=True)
    assert "No datasets yet" in body


def test_index_renders_upload_url_and_scan_forms(client):
    response = client.get("/")

    body = response.get_data(as_text=True)
    assert "/ingest/upload" in body
    assert 'enctype="multipart/form-data"' in body
    assert 'name="file"' in body
    assert 'accept=".csv"' in body
    assert "/ingest/url" in body
    assert 'name="url"' in body
    assert 'type="url"' in body
    assert "/ingest/scan" in body


def test_delete_removes_dataset_and_redirects_with_flash(client, ingested):
    ingested("people.csv", "id,name\n1,Ada\n")

    response = client.post("/datasets/people/delete", follow_redirects=True)

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "No datasets yet" in body
    assert "Deleted" in body
    assert "people" in body
    assert "re-imported unless it changes" in body


@pytest.mark.parametrize(
    "name",
    ["unknown", "gone"],
)
def test_delete_unknown_or_already_deleted_dataset_returns_404(client, ingested, name):
    if name == "gone":
        ingested("gone.csv", "id\n1\n")
        client.post("/datasets/gone/delete")

    response = client.post(f"/datasets/{name}/delete")

    assert response.status_code == 404
