import pytest

from app.exceptions import (
    CsvExplorerError,
    DatasetNotFoundError,
    IngestError,
    InvalidQueryError,
)


@pytest.mark.parametrize("exception_class", [IngestError, DatasetNotFoundError, InvalidQueryError])
def test_domain_exceptions_inherit_from_csv_explorer_error(exception_class):
    assert issubclass(exception_class, CsvExplorerError)
