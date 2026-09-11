# Task 018: Alpine.js `datasetTable` Component

**Status**: pending
**Depends on**: 001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 012, 013, 014, 017, 020, 021, 022
**Retry count**: 0

## Description
Turn the dataset page into an interactive Alpine.js table: a debounced global search, a per-column filter row, click-to-sort headers, a page-size selector and pagination controls. Every change fetches from the rows JSON API, so all of it runs on the server, and everything is styled with Tailwind.

## Context
- Related files (new): `app/static/js/dataset_table.js`, `tests/integration/test_dataset_table_component.py`
- Related files (modify): `app/templates/datasets/show.html`, and `tests/integration/test_datasets_routes.py` (task 017's tests) only if a test there asserted on the plain-table markup you're replacing. Keep its intent, and assert through the `initial-page` JSON instead.
- `dataset_table.js` registers the component with `document.addEventListener('alpine:init', () => Alpine.data('datasetTable', () => ({...})))`. It takes **no arguments** (see Security below).
  - **State**: `rowsUrl`, `maxPageSize`, `columns`, `rows`, `page`, `perPage`, `total`, `totalPages`, `search`, `filters` (an object keyed by column name; create it with `Object.create(null)` so a column called `__proto__` or `constructor` can't collide with `Object.prototype`), `sortBy`, `sortDir`, `loading`, `error`
  - **`init()`**:
    1. `this.rowsUrl = this.$el.dataset.rowsUrl` and `this.maxPageSize = Number(this.$el.dataset.maxPageSize)`. Both come from the `data-*` attributes task 017 put on the container.
    2. Read `JSON.parse(document.getElementById('initial-page').textContent)`, and fill `columns`, `rows`, `page`, `perPage`, `total` and `totalPages` from it.
    3. Fill `filters` with `''` for each column.
    4. **Only then** register the watchers, so the initial assignments don't trigger a redundant fetch.
  - **Watchers** (Alpine v3's `$watch` already watches objects deeply, because it `JSON.stringify`s the value. There's no `{deep: true}` option; that's Vue.):
    - `search` and `filters` → debounce 300 ms → `page = 1` → `fetchRows()`
    - `perPage` → `page = 1` → `fetchRows()`, with no debounce
  - **`fetchRows()`**:
    - builds a `URLSearchParams` with `page`, `per_page`, `q`, `sort`, `dir` and `filter[<col>]` for non-blank filters
    - `fetch(this.rowsUrl + '?' + params)`
    - on a non-OK response, sets `error` from the JSON `error` field (fall back to a generic message if the body isn't JSON)
    - sets `loading` around the request
    - ignores stale responses: keep a request counter and apply only the latest response
  - **`toggleSort(col)`** cycles asc → desc → none, then sets `page = 1` and calls `fetchRows()`.
  - **`goTo(page)`** clamps to `[1, totalPages]`, then calls `fetchRows()` if the page changed.
  - **`clearFilters()`** resets search and all filters, letting the watchers fetch once.
  - **Getters**: `rangeStart`, `rangeEnd` ("Showing 26–50 of 1,234"; format with `toLocaleString()`).
- `show.html`:
  - Mount with `<div x-data="datasetTable" data-rows-url="{{ url_for('datasets.rows', name=dataset.name) }}" data-max-page-size="{{ config.MAX_PAGE_SIZE }}">`. Normal Jinja autoescaping in `data-*` attributes is safe.
  - **Don't** write `x-data="datasetTable({{ ...|tojson }})"`. Flask's `tojson` escapes `<`, `>`, `&` and `'`, but **not `"`**. In a double-quoted attribute it renders `x-data="datasetTable("/api/datasets/x/rows", 100)"`, which ends the attribute at the first `"`, so the component never mounts. (The original plan wrongly said the quotes were escaped as `&#34;`.) Flask's docs say `tojson` is safe only in `<script>` blocks and **single-quoted** attributes. The `data-*` approach avoids the problem.
  - Header cells use `<template x-for="col in columns" :key="col.name">`. Each header button gets `@click="toggleSort(col.name)"` and shows a sort indicator.
  - The filter row uses `x-for` with `x-model="filters[col.name]"`.
  - The body uses `x-for` rows, then `x-for` columns with `x-text="row[col.name] ?? ''"`.
  - Also add:
    - a page-size `<select x-model.number="perPage">` with options 10/25/50/100, **server-rendered** with a Jinja loop that keeps only options `<= config.MAX_PAGE_SIZE`
    - first/prev/next/last buttons with `:disabled`
    - a loading indicator, an error banner, an empty "No matching rows" state and a "Clear filters" button
  - In `{% block scripts %}`, add `<script defer src="{{ url_for('static', filename='js/dataset_table.js') }}"></script>`. The block renders before the deferred Alpine tag in `base.html`.
  - Keep the `<script type="application/json" id="initial-page">{{ page.to_dict()|tojson }}</script>` block from task 017.
- **Security (critical):** column names come from untrusted CSV headers.
  - **Never** interpolate a column name or cell value into an Alpine expression or HTML attribute. They only enter through the `initial-page` JSON and `x-for` / `x-text`.
  - **Never** use `x-html`.
- Rebuild Tailwind after the template changes: `./bin/tailwindcss -i app/static/css/input.css -o app/static/css/app.css`.
- Tests are integration tests on the rendered HTML (there's no JS test runner). Parse the HTML with `html.parser` / `HTMLParser` for attribute checks instead of substring matching.
- **Manual browser check (best effort).** If you have a browser or browser-automation tool, check that search, filters, sort, page size and pagination work against the API, and write what you saw in Implementation Notes. If you don't, write "manual browser check pending for user" plus a short checklist in Implementation Notes. **Don't mark the task blocked over this.**

## Requirements (Test Descriptions)
- [ ] `test_show_mounts_dataset_table_component_with_data_attributes` (the parsed `x-data` attribute equals `datasetTable` exactly, and `data-rows-url` equals `url_for('datasets.rows', ...)`)
- [ ] `test_show_loads_dataset_table_script_before_alpine`
- [ ] `test_show_renders_filter_inputs_bound_to_columns_via_x_for`
- [ ] `test_show_renders_cells_with_x_text_and_never_x_html`
- [ ] `test_show_never_interpolates_column_names_into_alpine_expressions` (use a CSV header like `a'); alert(1); ('`, one containing a double quote `"`, and a `<script>` header. Assert these appear only inside the escaped `initial-page` JSON, and that every parsed attribute value is free of them)
- [ ] `test_show_renders_page_size_options_up_to_max_page_size` (with `make_app(MAX_PAGE_SIZE=50)` there's no 100 option)

## Acceptance Criteria
- All requirements have passing tests, and task 017's tests still pass
- Manual browser check done, or explicitly recorded as pending for the user
- Code follows code standards

## Implementation Notes
(Left blank - filled in by programmer during implementation)
