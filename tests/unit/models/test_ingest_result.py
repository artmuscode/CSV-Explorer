from datetime import UTC, datetime

from app.models.dataset import Dataset, DatasetSource
from app.models.ingest_result import IngestResult, ScanResult


def _make_dataset(**overrides):
    defaults = {
        "name": "sales",
        "original_filename": "sales.csv",
        "source": DatasetSource.FOLDER,
        "row_count": 10,
        "ingested_at": datetime.now(UTC),
    }
    return Dataset(**{**defaults, **overrides})


def test_ingest_result_holds_dataset_and_replaced_flag():
    dataset = _make_dataset()

    result = IngestResult(dataset=dataset, replaced=True)

    assert result.dataset is dataset
    assert result.replaced is True


def test_scan_result_holds_ingested_skipped_and_errors():
    dataset = _make_dataset()
    ingest_result = IngestResult(dataset=dataset, replaced=False)

    scan_result = ScanResult(
        ingested=[ingest_result],
        skipped=["already_loaded.csv"],
        errors={"broken.csv": "could not parse"},
    )

    assert scan_result.ingested == [ingest_result]
    assert scan_result.skipped == ["already_loaded.csv"]
    assert scan_result.errors == {"broken.csv": "could not parse"}
