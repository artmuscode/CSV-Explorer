# Task 017: Datasets Blueprint — Table Page & Rows JSON API

**Status**: pending
**Depends on**: 001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 012, 013, 014, 020, 021, 022
**Retry count**: 0

## Description
Implement the dataset table page and the JSON rows API that the Alpine component (task 018) calls. The page embeds the first page of data as JSON. The API applies pagination, search, column filters and sort on the server.

## Context
- Related files (modify): `app/blueprints/datasets.py`. Replace the 501 stubs from task 014 and keep the endpoint names `show` and `rows`. Only edit this module and `app/templates/datasets/`. Tasks 015 and 016 own the other blueprints.
- Related files (new): `app/templates/datasets/show.html`, `tests/integration/test_datasets_routes.py`
- `GET /datasets/<name>` (endpoint `show`):
  - `dataset = dataset_service.get_dataset(name)`
  - `page = dataset_service.get_page(name, dataset_service.build_query(None, None, None, {}, None, None))`
  - `DatasetNotFoundError` → `abort(404)`
- `show.html` (a basic version; task 018 builds it into the Alpine component):
  - dataset heading with name, source, row count and `source_url`, plus a back link
  - `<script type="application/json" id="initial-page">{{ page.to_dict()|tojson }}</script>`
  - `data-rows-url="{{ url_for('datasets.rows', name=dataset.name) }}"` on the table container
  - a plain server-rendered `<table>` of the first page (header cells from `page.columns`, cells autoescaped)
- `GET /api/datasets/<name>/rows` (endpoint `rows`):
  - Parse `page`, `per_page`, `q`, `sort`, `dir` and every arg shaped like `filter[<col>]` (a regex `^filter\[(.+)\]$` on `request.args` keys) into a dict.
  - Call `dataset_service.build_query(...)`, then `get_page`, then `jsonify(page.to_dict())`.
  - `DatasetNotFoundError` → `404 {"error": "Dataset not found"}`
  - `InvalidQueryError` → `400 {"error": str(exc)}`
- Tests use the `ingested` fixture with a CSV of about 30 rows, with columns such as `name,city,amount`.
- **Keep the tests stable across task 018.** Task 018 replaces the plain server-rendered `<table>` with Alpine `x-for` templates, so column headers won't be in the server HTML any more. They'll only be in the `initial-page` JSON. So in `test_show_renders_dataset_name_and_column_headers` and `test_show_embeds_initial_page_as_json`:
  - find the `<script id="initial-page">` block, `json.loads` its text, and assert on `columns` / `rows`
  - assert the dataset name in the heading
  - **don't** assert on `<th>` markup
- Also put `data-max-page-size="{{ config.MAX_PAGE_SIZE }}"` next to `data-rows-url` on the table container. Task 018's component reads both through `this.$el.dataset`.

## Requirements (Test Descriptions)
- [ ] `test_show_renders_dataset_name_and_column_headers`
- [ ] `test_show_embeds_initial_page_as_json`
- [ ] `test_show_unknown_dataset_returns_404`
- [ ] `test_rows_api_returns_paged_rows_as_json`
- [ ] `test_rows_api_applies_search_column_filters_and_sort`
- [ ] `test_rows_api_returns_400_json_for_invalid_query`
- [ ] `test_rows_api_returns_404_json_for_unknown_dataset`

## Acceptance Criteria
- All requirements have passing tests
- CSV values never pass through `|safe`
- Code follows code standards

## Implementation Notes
(Left blank - filled in by programmer during implementation)
