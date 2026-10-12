"""Main blueprint: the dataset list page and dataset deletion."""

from flask import Blueprint, abort, flash, redirect, render_template, url_for

from app.container import current_services
from app.exceptions import DatasetNotFoundError

bp = Blueprint("main", __name__)


@bp.route("/")
def index() -> str:
    datasets = current_services().dataset_service.list_datasets()
    return render_template("index.html", datasets=datasets)


@bp.route("/datasets/<name>/delete", methods=["POST"])
def delete(name: str):
    try:
        current_services().dataset_service.delete_dataset(name)
    except DatasetNotFoundError:
        abort(404)

    flash(
        f'Deleted "{name}". Its CSV file was kept and won\'t be re-imported unless it changes.',
        "success",
    )
    return redirect(url_for("main.index"))
