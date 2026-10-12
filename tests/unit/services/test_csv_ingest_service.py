import io
import os
from datetime import UTC, datetime

import duckdb
import pytest

from app.exceptions import IngestError
from app.models.dataset import DatasetSource
from app.repositories.duckdb_repository import DuckDBRepository
from app.repositories.metadata_repository import MetadataRepository
from app.services.csv_ingest_service import CsvIngestService

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
def csv_dir(tmp_path):
    directory = tmp_path / "csv"
    directory.mkdir()
    return directory


@pytest.fixture
def service(repository, metadata, csv_dir):
    return CsvIngestService(repository, metadata, csv_dir, clock=lambda: FIXED_NOW)


def test_ingest_file_creates_table_named_after_file(service, repository, csv_dir):
    csv_path = csv_dir / "Sales Report.csv"
    csv_path.write_text("id,amount\n1,10\n2,20\n")

    result = service.ingest_file(csv_path)

    assert result.dataset.name == "sales_report"
    assert repository.table_exists("sales_report")
    assert repository.count_rows("sales_report") == 2


def test_ingest_file_records_metadata_with_source_size_and_mtime(service, metadata, csv_dir):
    csv_path = csv_dir / "people.csv"
    csv_path.write_text("id,name\n1,Alice\n")
    stat = csv_path.stat()

    result = service.ingest_file(csv_path, source=DatasetSource.FOLDER)

    dataset = metadata.get("people")
    assert dataset is not None
    assert dataset.original_filename == "people.csv"
    assert dataset.source == DatasetSource.FOLDER
    assert dataset.row_count == 1
    assert dataset.file_size == stat.st_size
    assert dataset.file_mtime == stat.st_mtime
    assert dataset.ingested_at == FIXED_NOW
    assert result.dataset == dataset


def test_ingest_file_reports_replaced_only_when_a_live_dataset_already_existed(
    service, csv_dir, metadata
):
    csv_path = csv_dir / "people.csv"
    csv_path.write_text("id,name\n1,Alice\n")

    first_result = service.ingest_file(csv_path)
    assert first_result.replaced is False

    csv_path.write_text("id,name\n1,Alice\n2,Bob\n")
    second_result = service.ingest_file(csv_path)
    assert second_result.replaced is True

    metadata.mark_deleted("people", FIXED_NOW)
    third_result = service.ingest_file(csv_path)
    assert third_result.replaced is False
    assert third_result.dataset.deleted_at is None
    assert metadata.get("people").deleted_at is None


def test_ingest_file_rejects_non_csv_extension(service, csv_dir):
    txt_path = csv_dir / "notes.txt"
    txt_path.write_text("hello")

    with pytest.raises(IngestError):
        service.ingest_file(txt_path)


def test_save_upload_writes_sanitized_filename_into_csv_dir(service, csv_dir, repository):
    stream = io.BytesIO(b"id,name\n1,Alice\n")

    result = service.save_upload("../../weird name!.csv", stream)

    expected_path = csv_dir / "weird_name.csv"
    assert expected_path.exists()
    assert result.dataset.original_filename == "weird_name.csv"
    assert repository.table_exists("weird_name")
    # No stray staging or backup files left behind.
    leftovers = [p.name for p in csv_dir.iterdir() if p.name != "weird_name.csv"]
    assert leftovers == []


def test_save_upload_rejects_empty_filename(service):
    stream = io.BytesIO(b"id,name\n1,Alice\n")

    with pytest.raises(IngestError):
        service.save_upload("///", stream)


def test_save_upload_removes_file_when_csv_is_unloadable(service, csv_dir):
    stream = io.BytesIO(b"")

    with pytest.raises(IngestError):
        service.save_upload("broken.csv", stream)

    leftovers = list(csv_dir.iterdir())
    assert leftovers == []


def test_save_upload_restores_previous_file_and_table_when_replacement_is_unloadable(
    service, csv_dir, repository, metadata
):
    original_bytes = b"id,name\n1,Alice\n2,Bob\n"
    good_stream = io.BytesIO(original_bytes)
    service.save_upload("sales.csv", good_stream)

    original_dataset = metadata.get("sales")

    bad_stream = io.BytesIO(b"")
    with pytest.raises(IngestError):
        service.save_upload("sales.csv", bad_stream)

    sales_path = csv_dir / "sales.csv"
    assert sales_path.read_bytes() == original_bytes
    assert repository.count_rows("sales") == 2
    assert metadata.get("sales") == original_dataset

    leftovers = [p.name for p in csv_dir.iterdir() if p.name != "sales.csv"]
    assert leftovers == []


def test_scan_folder_ingests_new_csv_files(service, repository, csv_dir):
    (csv_dir / "people.csv").write_text("id,name\n1,Alice\n")
    (csv_dir / "sales.csv").write_text("id,amount\n1,10\n2,20\n")

    result = service.scan_folder()

    ingested_names = {r.dataset.name for r in result.ingested}
    assert ingested_names == {"people", "sales"}
    assert result.skipped == []
    assert result.errors == {}
    assert repository.table_exists("people")
    assert repository.table_exists("sales")


def test_scan_folder_skips_files_unchanged_since_last_ingest(service, csv_dir):
    (csv_dir / "people.csv").write_text("id,name\n1,Alice\n")
    first_result = service.scan_folder()
    assert {r.dataset.name for r in first_result.ingested} == {"people"}

    second_result = service.scan_folder()

    assert second_result.ingested == []
    assert second_result.skipped == ["people.csv"]
    assert second_result.errors == {}


def test_scan_folder_reingests_files_whose_size_or_mtime_changed(service, csv_dir, repository):
    path = csv_dir / "people.csv"
    path.write_text("id,name\n1,Alice\n")
    service.scan_folder()

    path.write_text("id,name\n1,Alice\n2,Bob\n")
    new_mtime = path.stat().st_mtime + 10
    os.utime(path, (new_mtime, new_mtime))

    result = service.scan_folder()

    assert {r.dataset.name for r in result.ingested} == {"people"}
    assert result.skipped == []
    assert repository.count_rows("people") == 2


def test_scan_folder_does_not_resurrect_deleted_dataset_until_its_file_changes(
    service, csv_dir, repository, metadata
):
    path = csv_dir / "people.csv"
    path.write_text("id,name\n1,Alice\n")
    service.scan_folder()

    metadata.mark_deleted("people", FIXED_NOW)
    repository.drop_table("people")

    result = service.scan_folder()

    assert result.ingested == []
    assert result.skipped == ["people.csv"]
    assert not repository.table_exists("people")
    assert metadata.get("people").is_deleted

    path.write_text("id,name\n1,Alice\n2,Bob\n")
    new_mtime = path.stat().st_mtime + 10
    os.utime(path, (new_mtime, new_mtime))

    second_result = service.scan_folder()

    assert {r.dataset.name for r in second_result.ingested} == {"people"}
    assert repository.table_exists("people")
    assert not metadata.get("people").is_deleted


def test_scan_folder_collects_errors_for_bad_files_and_continues(service, csv_dir, repository):
    (csv_dir / "broken.csv").write_bytes(b"")
    (csv_dir / "people.csv").write_text("id,name\n1,Alice\n")

    result = service.scan_folder()

    assert {r.dataset.name for r in result.ingested} == {"people"}
    assert "broken.csv" in result.errors
    assert repository.table_exists("people")
    assert not repository.table_exists("broken")


def test_scan_folder_ignores_non_csv_hidden_partial_and_glob_character_files(
    service, csv_dir, repository
):
    (csv_dir / "notes.txt").write_text("not a csv")
    (csv_dir / ".hidden.csv").write_text("id,name\n1,Alice\n")
    (csv_dir / "staging.csv.part").write_text("id,name\n1,Alice\n")
    (csv_dir / "wei*rd.csv").write_text("id,name\n1,Alice\n")
    (csv_dir / "people.csv").write_text("id,name\n1,Alice\n")

    result = service.scan_folder()

    ingested_names = {r.dataset.name for r in result.ingested}
    assert ingested_names == {"people"}
    assert result.errors == {"wei*rd.csv": "Skipped: file name contains *, ? or ["}
    assert not repository.table_exists("notes")
    assert not repository.table_exists("hidden")
    assert not repository.table_exists("staging")


def test_scan_folder_reports_table_name_collision_and_is_stable_across_rescans(
    service, csv_dir, repository
):
    (csv_dir / "my-data.csv").write_text("id,name\n1,Alice\n")
    (csv_dir / "my_data.csv").write_text("id,name\n1,Bob\n")

    first_result = service.scan_folder()

    ingested_names = {r.dataset.name for r in first_result.ingested}
    assert ingested_names == {"my_data"}
    assert first_result.errors == {
        "my_data.csv": "Skipped: maps to the same dataset 'my_data' as my-data.csv"
    }
    assert repository.table_exists("my_data")

    second_result = service.scan_folder()

    assert second_result.ingested == []
    assert second_result.errors == {
        "my_data.csv": "Skipped: maps to the same dataset 'my_data' as my-data.csv"
    }
    assert second_result.skipped == ["my-data.csv"]
