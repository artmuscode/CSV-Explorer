import pytest

from app.repositories.identifiers import (
    quote_identifier,
    quote_literal,
    table_name_from_filename,
)


def test_quote_identifier_wraps_name_in_double_quotes():
    assert quote_identifier("my_column") == '"my_column"'


def test_quote_identifier_escapes_embedded_double_quotes():
    assert quote_identifier('weird"column') == '"weird""column"'


def test_quote_literal_wraps_value_in_single_quotes():
    assert quote_literal("/tmp/data.csv") == "'/tmp/data.csv'"


def test_quote_literal_escapes_embedded_single_quotes():
    assert quote_literal("O'Brien.csv") == "'O''Brien.csv'"


def test_table_name_from_filename_lowercases_and_drops_csv_extension():
    assert table_name_from_filename("MyFile.CSV") == "myfile"


def test_table_name_from_filename_replaces_non_alphanumeric_runs_with_single_underscore():
    assert table_name_from_filename("my  file--data.csv") == "my_file_data"


def test_table_name_from_filename_prefixes_t_when_starting_with_digit():
    assert table_name_from_filename("2024_report.csv") == "t_2024_report"


def test_table_name_from_filename_never_starts_with_underscore():
    assert table_name_from_filename("__secret.csv") == "secret"


def test_table_name_from_filename_raises_value_error_when_nothing_usable_remains():
    with pytest.raises(ValueError):
        table_name_from_filename("---.csv")
