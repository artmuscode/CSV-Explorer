"""Datasets blueprint: the dataset detail page, paginated row API and CSV export."""

import csv
import io
import re
from collections.abc import Iterator
from datetime import UTC, datetime

from flask import (
    Blueprint,
    Response,
    abort,
    jsonify,
    render_template,
    request,
    stream_with_context,
)

from app.container import current_services
from app.exceptions import DatasetNotFoundError, InvalidQueryError
from app.models.row_stream import RowStream

bp = Blueprint("datasets", __name__)

_FILTER_KEY_RE = re.compile(r"^filter\[(.+)\]$")
_CSV_FLUSH_ROWS = 500


@bp.route("/datasets/<name>")
def show(name: str) -> str:
    dataset_service = current_services().dataset_service
    try:
        dataset = dataset_service.get_dataset(name)
        query = dataset_service.build_query(None, None, None, {}, None, None)
        page = dataset_service.get_page(name, query)
    except DatasetNotFoundError:
        abort(404)

    return render_template("datasets/show.html", dataset=dataset, page=page)


@bp.route("/api/datasets/<name>/rows")
def rows(name: str) -> Response | tuple[Response, int]:
    dataset_service = current_services().dataset_service

    try:
        query = dataset_service.build_query(
            request.args.get("page"),
            request.args.get("per_page"),
            request.args.get("q"),
            _filters_from_request(),
            request.args.get("sort"),
            request.args.get("dir"),
        )
        page = dataset_service.get_page(name, query)
    except DatasetNotFoundError:
        return jsonify(error="Dataset not found"), 404
    except InvalidQueryError as exc:
        return jsonify(error=str(exc)), 400

    return jsonify(page.to_dict())


@bp.route("/datasets/<name>/export.csv")
def export(name: str) -> Response:
    """Download every row matching the current search, filters and sort.

    Paging parameters are deliberately ignored: the export covers the whole
    filtered result set, not the page the user happens to be looking at. The
    body is streamed, so a large dataset never has to be built in memory.
    """
    dataset_service = current_services().dataset_service

    try:
        query = dataset_service.build_query(
            None,
            None,
            request.args.get("q"),
            _filters_from_request(),
            request.args.get("sort"),
            request.args.get("dir"),
        )
        stream = dataset_service.export_rows(name, query)
    except DatasetNotFoundError:
        abort(404)
    except InvalidQueryError:
        abort(400)

    return Response(
        stream_with_context(_csv_chunks(stream)),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{_export_filename(name)}"'},
    )


def _filters_from_request() -> dict[str, str]:
    """Collect `filter[column]=value` query parameters into a plain mapping."""
    return {
        match.group(1): value
        for key, value in request.args.items()
        if (match := _FILTER_KEY_RE.match(key))
    }


def _csv_chunks(stream: RowStream) -> Iterator[str]:
    """Yield `stream` as CSV text: a header row, then rows in flushed batches."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=stream.column_names)
    writer.writeheader()

    for row_number, row in enumerate(stream.rows, start=1):
        writer.writerow(row)
        if row_number % _CSV_FLUSH_ROWS == 0:
            yield _drain(buffer)

    remaining = _drain(buffer)
    if remaining:
        yield remaining


def _drain(buffer: io.StringIO) -> str:
    """Return everything written to `buffer` so far, and reset it."""
    text = buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)
    return text


def _export_filename(name: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{name}-{timestamp}.csv"
