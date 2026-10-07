"""Integration tests for the Alpine.js `datasetTable` component on the dataset page."""

import json
from html.parser import HTMLParser


class _AttrCollectingParser(HTMLParser):
    """Collects every tag's attributes, plus each `<script>` tag's own text content."""

    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self._current_script_id: str | None = None
        self.script_contents: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = dict(attrs)
        self.tags.append((tag, attr_dict))
        if tag == "script":
            self._current_script_id = attr_dict.get("id")
            if self._current_script_id:
                self.script_contents[self._current_script_id] = ""

    def handle_data(self, data: str) -> None:
        if self._current_script_id:
            self.script_contents[self._current_script_id] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._current_script_id = None

    def find(self, tag: str, **attr_filters: str) -> dict[str, str | None] | None:
        for found_tag, attrs in self.tags:
            if found_tag != tag:
                continue
            if all(attrs.get(key) == value for key, value in attr_filters.items()):
                return attrs
        return None

    def find_all(self, tag: str) -> list[dict[str, str | None]]:
        return [attrs for found_tag, attrs in self.tags if found_tag == tag]


def _parse(body: str) -> _AttrCollectingParser:
    parser = _AttrCollectingParser()
    parser.feed(body)
    return parser


def _csv_with_rows(n: int) -> str:
    lines = ["name,city,amount"]
    for i in range(1, n + 1):
        lines.append(f"person{i},city{i % 3},{i}")
    return "\n".join(lines) + "\n"


def test_show_mounts_dataset_table_component_with_data_attributes(client, ingested):
    ingested("people.csv", _csv_with_rows(5))

    response = client.get("/datasets/people")
    body = response.get_data(as_text=True)
    parser = _parse(body)

    mount = parser.find("div", **{"x-data": "datasetTable"})
    assert mount is not None
    assert mount["x-data"] == "datasetTable"
    assert mount["data-rows-url"] == "/api/datasets/people/rows"


def test_show_loads_dataset_table_script_before_alpine(client, ingested):
    ingested("people.csv", _csv_with_rows(5))

    response = client.get("/datasets/people")
    body = response.get_data(as_text=True)
    parser = _parse(body)

    scripts = parser.find_all("script")
    src_list = [attrs.get("src") for attrs in scripts if attrs.get("src")]

    dataset_table_index = next(
        i for i, src in enumerate(src_list) if src and "dataset_table.js" in src
    )
    alpine_index = next(i for i, src in enumerate(src_list) if src and "alpinejs" in src)

    assert dataset_table_index < alpine_index

    dataset_table_attrs = next(
        attrs for attrs in scripts if "dataset_table.js" in (attrs.get("src") or "")
    )
    assert "defer" in dataset_table_attrs


def test_show_renders_export_link_bound_to_the_live_filter_state(client, ingested):
    ingested("people.csv", _csv_with_rows(5))

    response = client.get("/datasets/people")
    body = response.get_data(as_text=True)
    parser = _parse(body)

    mount = parser.find("div", **{"x-data": "datasetTable"})
    assert mount is not None
    assert mount["data-export-url"] == "/datasets/people/export.csv"

    export_link = parser.find("a", **{":href": "exportHref"})
    assert export_link is not None


def test_show_renders_filter_inputs_bound_to_columns_via_x_for(client, ingested):
    ingested("people.csv", _csv_with_rows(5))

    response = client.get("/datasets/people")
    body = response.get_data(as_text=True)
    parser = _parse(body)

    filter_input = parser.find("input", **{"x-model": "filters[col.name]"})
    assert filter_input is not None

    header_template = parser.find("template", **{"x-for": "col in columns"})
    assert header_template is not None


def test_show_renders_cells_with_x_text_and_never_x_html(client, ingested):
    ingested("people.csv", _csv_with_rows(5))

    response = client.get("/datasets/people")
    body = response.get_data(as_text=True)
    parser = _parse(body)

    cell = parser.find("td", **{"x-text": "row[col.name] ?? ''"})
    assert cell is not None

    for _tag, attrs in parser.tags:
        assert "x-html" not in attrs


def test_show_never_interpolates_column_names_into_alpine_expressions(client, ingested):
    csv_text = '"a\'); alert(1); (\'","has ""quote"" char",<script>\n1,2,3\n'
    ingested("evil.csv", csv_text)

    response = client.get("/datasets/evil")
    body = response.get_data(as_text=True)
    parser = _parse(body)

    dangerous_snippets = [
        "a'); alert(1); ('",
        'has "quote" char',
        "<script>",
    ]

    initial_page_json = parser.script_contents.get("initial-page")
    assert initial_page_json is not None
    payload = json.loads(initial_page_json)
    column_names = [column["name"] for column in payload["columns"]]
    assert column_names == ["a'); alert(1); ('", 'has "quote" char', "<script>"]

    for _tag, attrs in parser.tags:
        for value in attrs.values():
            if value is None:
                continue
            for snippet in dangerous_snippets:
                assert snippet not in value


class _OptionParser(HTMLParser):
    """Collects `<option value>`s that appear inside the per-page `<select>`."""

    def __init__(self) -> None:
        super().__init__()
        self._in_target_select = False
        self.values: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = dict(attrs)
        if tag == "select" and attr_dict.get("x-model.number") == "perPage":
            self._in_target_select = True
        elif tag == "option" and self._in_target_select:
            self.values.append(attr_dict.get("value"))

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self._in_target_select = False


def test_show_renders_page_size_options_up_to_max_page_size(make_app):
    app = make_app(MAX_PAGE_SIZE=50)
    client = app.test_client()

    from app.container import get_services

    services = get_services(app)
    csv_dir = app.config["CSV_DIR"]
    csv_dir.mkdir(parents=True, exist_ok=True)
    csv_path = csv_dir / "people.csv"
    csv_path.write_text(_csv_with_rows(5))
    services.ingest_service.ingest_file(csv_path)

    response = client.get("/datasets/people")
    body = response.get_data(as_text=True)

    select_parser = _parse(body)
    select = select_parser.find("select", **{"x-model.number": "perPage"})
    assert select is not None

    option_parser = _OptionParser()
    option_parser.feed(body)

    assert option_parser.values == ["10", "25", "50"]
    assert "100" not in option_parser.values
