from datetime import UTC, datetime

import duckdb
import pytest

from app.models.dataset import Dataset, DatasetSource
from app.repositories.metadata_repository import MetadataRepository


@pytest.fixture
def repo() -> MetadataRepository:
    connection = duckdb.connect(":memory:")
    repository = MetadataRepository(connection)
    repository.ensure_schema()
    return repository


def make_dataset(**overrides) -> Dataset:
    defaults = dict(
        name="my_file",
        original_filename="my_file.csv",
        source=DatasetSource.FOLDER,
        row_count=42,
        ingested_at=datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC),
        source_url=None,
        file_size=1024,
        file_mtime=1_700_000_000.0,
        deleted_at=None,
    )
    defaults.update(overrides)
    return Dataset(**defaults)


def test_ensure_schema_is_idempotent(repo: MetadataRepository) -> None:
    repo.ensure_schema()
    repo.ensure_schema()


def test_upsert_then_get_round_trips_dataset(repo: MetadataRepository) -> None:
    original = make_dataset(
        ingested_at=datetime(2026, 9, 10, 12, 30, 0, tzinfo=UTC),
    )

    repo.upsert(original)

    assert repo.get(original.name) == original


def test_upsert_replaces_existing_record_with_same_name(repo: MetadataRepository) -> None:
    original = make_dataset(row_count=10)
    repo.upsert(original)

    updated = make_dataset(row_count=99, original_filename="renamed.csv")
    repo.upsert(updated)

    result = repo.get(original.name)
    assert result is not None
    assert result.row_count == 99
    assert result.original_filename == "renamed.csv"


def test_get_returns_none_for_unknown_name(repo: MetadataRepository) -> None:
    assert repo.get("does_not_exist") is None


def test_list_all_returns_datasets_newest_first(repo: MetadataRepository) -> None:
    older = make_dataset(name="older", ingested_at=datetime(2026, 1, 1, tzinfo=UTC))
    newer = make_dataset(name="newer", ingested_at=datetime(2026, 6, 1, tzinfo=UTC))
    repo.upsert(older)
    repo.upsert(newer)

    result = repo.list_all()

    assert [dataset.name for dataset in result] == ["newer", "older"]


def test_mark_deleted_hides_dataset_from_list_all_but_get_still_returns_it(
    repo: MetadataRepository,
) -> None:
    dataset = make_dataset(name="to_delete")
    repo.upsert(dataset)

    deleted_at = datetime(2026, 9, 10, 13, 0, 0, tzinfo=UTC)
    repo.mark_deleted("to_delete", deleted_at)

    assert repo.list_all() == []
    result = repo.get("to_delete")
    assert result is not None
    assert result.is_deleted
    assert result.deleted_at == deleted_at
    assert result.file_size == dataset.file_size
    assert result.file_mtime == dataset.file_mtime


def test_upsert_clears_deletion_marker(repo: MetadataRepository) -> None:
    dataset = make_dataset(name="undeleted")
    repo.upsert(dataset)
    repo.mark_deleted("undeleted", datetime(2026, 9, 10, tzinfo=UTC))
    assert repo.get("undeleted").is_deleted

    reingested = make_dataset(
        name="undeleted",
        ingested_at=datetime(2026, 9, 11, tzinfo=UTC),
        deleted_at=None,
    )
    repo.upsert(reingested)

    result = repo.get("undeleted")
    assert result is not None
    assert not result.is_deleted
    assert result.deleted_at is None
    assert result in repo.list_all()
