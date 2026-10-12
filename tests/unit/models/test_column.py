from app.models.column import Column


def test_column_holds_name_and_type():
    column = Column(name="id", type="INTEGER")

    assert column.name == "id"
    assert column.type == "INTEGER"
