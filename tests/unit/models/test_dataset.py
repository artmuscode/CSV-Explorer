from datetime import UTC, datetime

from app.models.dataset import Dataset, DatasetSource


def _make_dataset(**overrides):
    defaults = {
        "name": "sales",
        "original_filename": "sales.csv",
        "source": DatasetSource.FOLDER,
        "row_count": 10,
        "ingested_at": datetime.now(UTC),
    }
    return Dataset(**{**defaults, **overrides})


def test_dataset_is_deleted_reflects_deleted_at():
    active = _make_dataset(deleted_at=None)
    deleted = _make_dataset(deleted_at=datetime.now(UTC))

    assert active.is_deleted is False
    assert deleted.is_deleted is True
