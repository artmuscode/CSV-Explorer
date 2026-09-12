"""Datasets blueprint: the dataset detail page and paginated row API."""

import re

from flask import Blueprint, Response, abort, jsonify, render_template, request

from app.container import current_services
from app.exceptions import DatasetNotFoundError, InvalidQueryError

bp = Blueprint("datasets", __name__)

_FILTER_KEY_RE = re.compile(r"^filter\[(.+)\]$")


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
    filters = {
        match.group(1): value
        for key, value in request.args.items()
        if (match := _FILTER_KEY_RE.match(key))
    }

    try:
        query = dataset_service.build_query(
            request.args.get("page"),
            request.args.get("per_page"),
            request.args.get("q"),
            filters,
            request.args.get("sort"),
            request.args.get("dir"),
        )
        page = dataset_service.get_page(name, query)
    except DatasetNotFoundError:
        return jsonify(error="Dataset not found"), 404
    except InvalidQueryError as exc:
        return jsonify(error=str(exc)), 400

    return jsonify(page.to_dict())
