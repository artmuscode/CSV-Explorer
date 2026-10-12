"""Ingest blueprint: file upload, URL ingest, and folder scan.

Route handlers only parse the request, delegate to `CsvIngestService` or
`UrlIngestService`, and flash a message before redirecting. All ingest logic
(saving uploads, downloading URLs, scanning the CSV folder) lives in the
services in `app/services/`.
"""

from flask import Blueprint, flash, redirect, request, url_for
from werkzeug.exceptions import RequestEntityTooLarge

from app.container import current_services
from app.exceptions import IngestError
from app.models.ingest_result import IngestResult

bp = Blueprint("ingest", __name__, url_prefix="/ingest")

_MAX_FLASH_LENGTH = 300
_MAX_SCAN_ERROR_FLASHES = 5


def _truncate(message: str) -> str:
    """Shorten `message` to `_MAX_FLASH_LENGTH` characters.

    Flash messages live in the signed cookie session; letting them grow
    unbounded risks pushing the cookie past the ~4 KB browsers accept,
    which silently drops every flashed message on the next request.
    """
    if len(message) <= _MAX_FLASH_LENGTH:
        return message
    return message[: _MAX_FLASH_LENGTH - 1] + "…"


def _flash_ingest_result(result: IngestResult) -> str:
    verb = "Replaced" if result.replaced else "Created"
    flash(
        _truncate(f'{verb} "{result.dataset.name}" with {result.dataset.row_count} rows'),
        "success",
    )
    return result.dataset.name


@bp.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if file is None or not file.filename:
        flash(_truncate("Please choose a CSV file to upload"), "error")
        return redirect(url_for("main.index"))

    try:
        result = current_services().ingest_service.save_upload(file.filename, file.stream)
    except IngestError as exc:
        flash(_truncate(str(exc)), "error")
        return redirect(url_for("main.index"))

    name = _flash_ingest_result(result)
    return redirect(url_for("datasets.show", name=name))


@bp.route("/url", methods=["POST"])
def from_url():
    url = request.form.get("url", "").strip()

    try:
        result = current_services().url_ingest_service.ingest(url)
    except IngestError as exc:
        flash(_truncate(str(exc)), "error")
        return redirect(url_for("main.index"))

    name = _flash_ingest_result(result)
    return redirect(url_for("datasets.show", name=name))


@bp.route("/scan", methods=["POST"])
def scan():
    try:
        result = current_services().ingest_service.scan_folder()
    except IngestError as exc:
        flash(_truncate(str(exc)), "error")
        return redirect(url_for("main.index"))

    flash(
        _truncate(
            f"Ingested {len(result.ingested)}, skipped {len(result.skipped)}, "
            f"failed {len(result.errors)}"
        ),
        "success",
    )

    errors = list(result.errors.items())
    for filename, message in errors[:_MAX_SCAN_ERROR_FLASHES]:
        flash(_truncate(f"{filename}: {message}"), "error")

    remaining = len(errors) - _MAX_SCAN_ERROR_FLASHES
    if remaining > 0:
        flash(_truncate(f"…and {remaining} more"), "error")

    return redirect(url_for("main.index"))


@bp.app_errorhandler(RequestEntityTooLarge)
def handle_file_too_large(_error: RequestEntityTooLarge):
    flash(_truncate("File too large"), "error")
    return redirect(url_for("main.index"))
