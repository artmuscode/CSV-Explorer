"""Error handler registration for the Flask application."""

from flask import Flask, Response, jsonify, render_template, request


def register_error_handlers(app: Flask) -> None:
    """Register 404 and 500 handlers on `app`.

    Requests under `/api/` get a JSON `{"error": ...}` body instead of an
    HTML error page.
    """

    @app.errorhandler(403)
    def handle_forbidden(error: Exception) -> tuple[Response | str, int]:
        if request.path.startswith("/api/"):
            return jsonify(error="Forbidden"), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def handle_not_found(error: Exception) -> tuple[Response | str, int]:
        if request.path.startswith("/api/"):
            return jsonify(error="Not found"), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def handle_server_error(error: Exception) -> tuple[Response | str, int]:
        app.logger.exception("Unhandled exception while handling a request")
        if request.path.startswith("/api/"):
            return jsonify(error="Internal server error"), 500
        return render_template("errors/500.html"), 500
