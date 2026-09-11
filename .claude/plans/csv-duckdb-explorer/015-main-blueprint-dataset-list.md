# Task 015: Main Blueprint — Dataset List & Delete

**Status**: pending
**Depends on**: 001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 012, 013, 014, 020, 021, 022
**Retry count**: 0

## Description
Build the home page. It lists every dataset with its source, row count and ingest time, and holds the three ingest forms: upload, URL and scan folder. It also adds a POST route to delete a dataset.

## Context
- Related files (modify): `app/blueprints/main.py`
- Related files (new): `app/templates/index.html`, `tests/integration/test_main_routes.py`
- Routes:
  - `GET /` → `index.html` with `datasets = current_services().dataset_service.list_datasets()`
  - `POST /datasets/<name>/delete` → `dataset_service.delete_dataset(name)`, then flash `success` and redirect to `main.index`. `DatasetNotFoundError` → `abort(404)`. This covers already-deleted datasets too.
    - The flash text explains the "remember deletions" behaviour: `Deleted "<name>". Its CSV file was kept and won't be re-imported unless it changes.`
- `index.html` extends `base.html`:
  - **Upload form**: `method=post`, `enctype=multipart/form-data`, `action={{ url_for('ingest.upload') }}`, field name `file`, `accept=".csv"`
  - **URL form**: `action={{ url_for('ingest.from_url') }}`, field `url`, `type=url`
  - **Scan button**: a form posting to `url_for('ingest.scan')`
  - **Datasets table**: name linking to `url_for('datasets.show', name=...)`, a source badge, `row_count`, `ingested_at`, and a delete form button
  - **Empty state**: "No datasets yet"
  - Style everything with Tailwind utilities.
- Task 014 already created every endpoint as a stub: `ingest.upload`, `ingest.from_url`, `ingest.scan`, `datasets.show`, `datasets.rows`. `url_for` resolves them even while tasks 016/017 run in parallel. **Only edit `app/blueprints/main.py` and `app/templates/index.html`**. Don't touch the other blueprint modules. Replace the `main.index` and `main.delete` stubs.
- Use the `ingested` fixture from `tests/conftest.py` to create datasets.

## Requirements (Test Descriptions)
- [ ] `test_index_lists_ingested_datasets_with_row_counts`
- [ ] `test_index_links_each_dataset_to_its_table_view`
- [ ] `test_index_shows_empty_state_when_no_datasets`
- [ ] `test_index_renders_upload_url_and_scan_forms`
- [ ] `test_delete_removes_dataset_and_redirects_with_flash`
- [ ] `test_delete_unknown_or_already_deleted_dataset_returns_404` (parametrized)

## Acceptance Criteria
- All requirements have passing tests
- Dataset names are rendered only through Jinja autoescaping (no `|safe`)
- Code follows code standards

## Implementation Notes
(Left blank - filled in by programmer during implementation)
