# CSV Explorer (Flask + DuckDB)

A small Flask app for exploring CSV files without spinning up a database by
hand. Drop a CSV into a folder (or upload one, or give it a URL), and it
loads the file into [DuckDB](https://duckdb.org/) as a table, then shows it
as a paginated, searchable, sortable, filterable HTML table.

## What it does

- Watches (on demand) a drop folder of CSV files and ingests any that are
  new or changed.
- Accepts CSV uploads through the browser.
- Downloads a CSV from a URL you paste in and ingests it, with safeguards
  against SSRF (private/loopback addresses, DNS rebinding, oversized
  downloads, non-CSV content).
- Renders every dataset as a table with global search, per-column filters,
  sortable columns, and server-side pagination, backed by parameterized SQL
  against DuckDB.
- Lets you delete a dataset (its table is dropped; the CSV file itself and a
  "this was deleted" marker are kept, so a folder rescan won't silently
  bring it back).

## Stack

- **Language**: Python 3.13
- **Framework**: Flask 3.1 (app factory + blueprints)
- **Database**: DuckDB (also does the CSV parsing, via `read_csv_auto`)
- **Frontend**: Jinja2 templates, Alpine.js 3 (from a pinned CDN build),
  Tailwind CSS 4 (standalone CLI, no Node toolchain)
- **Testing**: pytest, pytest-xdist (parallel runs), pytest-cov
- **Linting**: ruff (lint + format)
- **Dependency management**: uv + `pyproject.toml`

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/): `brew install uv`

## Setup

```bash
# Install Python dependencies (including dev/test tools)
uv sync

# Download the Tailwind CSS v4 standalone CLI binary (see .tailwind-version
# for the exact tag; macOS arm64 shown below — swap in the binary for your
# platform from the same release if needed)
curl -sLo bin/tailwindcss \
  "https://github.com/tailwindlabs/tailwindcss/releases/download/$(cat .tailwind-version)/tailwindcss-macos-arm64"
chmod +x bin/tailwindcss

# Build the CSS once
./bin/tailwindcss -i app/static/css/input.css -o app/static/css/app.css --minify
```

`bin/tailwindcss` and `app/static/css/app.css` are both gitignored; every
clone needs to redo the two setup steps above.

## Running

```bash
# Terminal 1: the Flask dev server
uv run flask --app app run --debug

# Terminal 2: rebuild CSS on change while you edit templates/input.css
./bin/tailwindcss -i app/static/css/input.css -o app/static/css/app.css --watch
```

Then open http://127.0.0.1:5000/. The CSV drop folder (`data/csv/`) and the
DuckDB database file (`data/app.duckdb`) are created automatically; both are
gitignored.

Startup behavior: the DuckDB connection and every service are built lazily,
on the first request the server actually handles (not when the app is
constructed). That's deliberate — `flask run --debug`'s reloader loads the
app in a parent process that never serves a request, and eagerly opening
DuckDB there would hold its exclusive file lock and make the child process
that does serve requests fail with a lock error. In practice this means the
"scan the drop folder on startup" behavior (`SCAN_ON_STARTUP`, on by
default) runs on the first page load, not the moment the process starts.

## Running with Docker

The image builds its own Tailwind CSS (Linux binary, version from
`.tailwind-version`), so no local `bin/tailwindcss` is needed.

```bash
export CSV_EXPLORER_SECRET_KEY=$(openssl rand -hex 32)
docker compose up --build
```

Then open http://localhost:8000/. Notes:

- `./data` is bind-mounted to `/app/data`, so the DuckDB file and the CSV drop
  folder persist across rebuilds, and files dropped into `data/csv/` on the
  host are picked up by the startup scan.
- Don't run the dev server and the container on the same `data/` at once:
  DuckDB's exclusive file lock lets only one process open `app.duckdb`.
- The container runs gunicorn with **one worker** (4 threads) for the same
  reason. Don't raise `--workers`.
- Any `CSV_EXPLORER_*` environment variable overrides config, e.g.
  `CSV_EXPLORER_PAGE_SIZE=50`.
- The app runs as the non-root user `app` (uid 1000). On a Linux host, make
  sure `./data` is writable by that uid.

## Usage

- **Drop folder**: put `.csv` files in `data/csv/`, then click "Scan
  folder" on the home page (or restart the server, since `SCAN_ON_STARTUP`
  scans it on first request).
- **Upload**: use the upload form on the home page. Only `.csv` files are
  accepted; the file name is sanitized before it's saved.
- **URL**: paste an `http(s)` URL into the "Ingest from a URL" form. The
  download is streamed with a byte cap and a timeout, and the target address
  is checked against private/loopback ranges before and after any redirect.
- **Viewing a dataset**: click its name to open the table view. Use the
  search box to match any column, the per-column boxes under the header row
  to filter individual columns, click a column header to sort by it (click
  again to reverse direction), and use the page-size selector and
  first/prev/next/last controls to page through results. All of this is
  server-side: `GET /api/datasets/<name>/rows` does the searching, filtering,
  sorting, and paging, so it works correctly over the whole dataset, not
  just the currently loaded page.
- **Deleting**: the "Delete" button on the home page drops the dataset's
  table but keeps its CSV file on disk (see Known Limitations below).

## Configuration

Every setting can be overridden with an environment variable prefixed
`CSV_EXPLORER_`, read via Flask's `from_prefixed_env`. Flask JSON-decodes
the value first and falls back to the raw string if that fails, so a plain
path or a bare word works unquoted, and things that look like other JSON
types need care:

```bash
export CSV_EXPLORER_CSV_DIR=/var/data/csv           # plain string, works unquoted
export CSV_EXPLORER_DUCKDB_PATH=/var/data/app.duckdb
export CSV_EXPLORER_ALLOW_PRIVATE_URLS=true         # JSON boolean
export CSV_EXPLORER_PAGE_SIZE=50                    # JSON number
export CSV_EXPLORER_MAX_DOWNLOAD_BYTES=104857600
export CSV_EXPLORER_SCAN_ON_STARTUP=false
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `CSV_EXPLORER_CSV_DIR` | `data/csv` | Folder scanned for CSVs, and where uploads/URL downloads are saved |
| `CSV_EXPLORER_DUCKDB_PATH` | `data/app.duckdb` | Path to the DuckDB database file |
| `CSV_EXPLORER_ALLOW_PRIVATE_URLS` | `false` | If `true`, URL ingest also allows private/loopback/link-local addresses (useful in a sandboxed dev environment; never enable this on a box with real internal network access) |
| `CSV_EXPLORER_MAX_DOWNLOAD_BYTES` | `52428800` (50 MiB) | Cap on a URL ingest download; the request is aborted once exceeded |
| `CSV_EXPLORER_PAGE_SIZE` | `25` | Default rows per page when the client doesn't ask for a specific size |
| `CSV_EXPLORER_MAX_PAGE_SIZE` | `100` | Largest `per_page` a client can request |
| `CSV_EXPLORER_SCAN_ON_STARTUP` | `true` | Whether the drop folder is scanned automatically on the first request the process serves |

## Testing and linting

```bash
uv run pytest -n auto                                                       # tests, parallel
uv run pytest                                                                # tests, sequential (debugging)
uv run pytest -n auto --cov=app --cov-report=term-missing --cov-fail-under=80  # with coverage gate
uv run ruff check .                                                          # lint
uv run ruff format --check .                                                 # format check
./bin/tailwindcss -i app/static/css/input.css -o app/static/css/app.css --minify  # CSS build
```

## Known limitations

- **Name collisions**: table names are derived from the file name (lowercased,
  non-alphanumeric runs collapsed to `_`). `Sales.csv` and `sales.csv` both
  map to the dataset `sales`, so ingesting one replaces the other. Within a
  single folder scan, the second colliding file is reported as skipped
  rather than replacing the first.
- **DNS rebinding**: the URL-ingest guard resolves the hostname and checks
  the resolved address before connecting, but a DNS record that changes
  between that check and the actual request (or between redirect hops) is
  an inherent risk of blocklist-based SSRF protection. It reduces risk; it
  doesn't eliminate it.
- **No authentication**: there's no login. A same-origin check rejects
  cross-site `POST`/`PUT`/`PATCH`/`DELETE` requests (so a hidden form on
  another site can't trigger an upload or delete on your behalf), but
  anyone who can reach the port can use the app freely. Keep it bound to
  `127.0.0.1` and never pass `--host 0.0.0.0` (or otherwise expose it)
  unless you've put your own auth or network controls in front of it.
- **Deletes are soft, for the folder scan's sake**: deleting a dataset drops
  its DuckDB table but keeps its CSV file on disk and records that it was
  deleted. A folder rescan won't re-import that file unless it changes
  (different size or modification time). Re-uploading the same file, or
  re-downloading it by URL, does bring the dataset back.
- **Single process only**: DuckDB allows exactly one writer process against
  a given database file. Run this with the Flask dev server or a single
  worker; don't put it behind multi-worker gunicorn/uwsgi.
- **The "startup" scan isn't at startup**: because the service container is
  built lazily (see Running, above), `SCAN_ON_STARTUP` actually runs on the
  first request the serving process handles, not when the process starts.
- **Encoding**: files are read as UTF-8 first, with an automatic Latin-1
  fallback if that fails. Windows-1252 files will load under the Latin-1
  fallback, but characters outside Latin-1's range that Windows-1252
  represents (`€`, `‘ ’ “ ”`, `–`, `—`) come through as control characters
  rather than the right glyph. UTF-16 files aren't supported at all.
- **Rejected files**: empty (0-byte) CSVs are rejected, as are file names
  containing `*`, `?`, or `[` (they'd be ambiguous or unsafe as DuckDB glob
  patterns).
- CSVs placed in `data/csv/` are gitignored; they're runtime data, not
  source.

## Manual UI check

The automated suite covers every route end to end through the Flask test
client, and the smoke test below exercises a real running server, but
neither drives an actual browser. If you have one handy, it's worth
confirming by hand:

- [ ] Global search box filters rows across all columns as you type
- [ ] Per-column filter inputs (under each header) narrow results further
- [ ] Clicking a column header sorts by it; clicking again reverses direction
- [ ] The sort indicator (^/v) shows on the active sort column
- [ ] Changing "Rows per page" reloads the table with the new page size
- [ ] First/Prev/Next/Last buttons page correctly and disable at the ends
- [ ] Uploading a CSV, ingesting a URL, and clicking "Scan folder" all work
      from the home page and redirect/flash as expected
- [ ] Deleting a dataset removes it from the home page list
- [ ] The 404 and 500 error pages render with the site's layout

This is best-effort automation; the checklist above is pending a manual
pass in a real browser.
