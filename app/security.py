"""Same-origin protection for state-changing requests."""

from urllib.parse import urlsplit

from flask import Flask, abort, request

_CHECKED_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def register_same_origin_check(app: Flask) -> None:
    """Reject state-changing requests whose Origin/Referer isn't this app.

    Runs before every `POST`, `PUT`, `PATCH`, and `DELETE` request. Safe
    methods (`GET`, `HEAD`, `OPTIONS`) are never checked. Without
    authentication, this is the app's only defense against a hidden form on
    another site submitting requests to it.
    """

    @app.before_request
    def check_same_origin() -> None:
        if request.method not in _CHECKED_METHODS:
            return

        expected = f"{request.scheme}://{request.host}"

        origin = request.headers.get("Origin")
        if origin is not None:
            if origin != expected:
                app.logger.warning("Rejected cross-origin request from Origin=%s", origin)
                abort(403)
            return

        referer = request.headers.get("Referer")
        if referer is not None:
            referer_origin = urlsplit(referer)
            referer_origin = f"{referer_origin.scheme}://{referer_origin.netloc}"
            if referer_origin != expected:
                app.logger.warning("Rejected cross-origin request from Referer=%s", referer)
                abort(403)
            return
