"""Integration tests for the base layout, partials, and error handlers."""

import re

from flask import render_template_string


def test_unknown_route_returns_404_page_with_base_layout(client):
    response = client.get("/this-route-does-not-exist")

    assert response.status_code == 404
    body = response.get_data(as_text=True)
    assert "<html" in body
    assert "404" in body


def test_unknown_api_route_returns_404_json_error(client):
    response = client.get("/api/this-route-does-not-exist")

    assert response.status_code == 404
    assert response.content_type == "application/json"
    assert "error" in response.get_json()


def test_base_layout_links_tailwind_app_stylesheet(client):
    response = client.get("/this-route-does-not-exist")

    body = response.get_data(as_text=True)
    assert "/static/css/app.css" in body


def test_base_layout_loads_pinned_alpine_version_with_sri_integrity(client):
    response = client.get("/this-route-does-not-exist")

    body = response.get_data(as_text=True)
    match = re.search(
        r'<script[^>]*src="https://cdn\.jsdelivr\.net/npm/alpinejs@(?P<version>[^"]+)'
        r'/dist/cdn\.min\.js"[^>]*integrity="(?P<integrity>[^"]+)"[^>]*'
        r'crossorigin="anonymous"[^>]*>',
        body,
    )
    assert match is not None, body

    version = match.group("version")
    assert re.fullmatch(r"3\.\d+\.\d+", version), version
    assert match.group("integrity").startswith("sha384-")


def test_500_handler_renders_error_page_without_exception_details(app, client):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.route("/boom")
    def boom():
        raise RuntimeError("kaboom - sensitive detail")

    response = client.get("/boom")

    assert response.status_code == 500
    body = response.get_data(as_text=True)
    assert "kaboom" not in body
    assert "sensitive detail" not in body


def test_flash_messages_render_with_category_styling(app, client):
    @app.route("/flash-test")
    def flash_test():
        from flask import flash

        flash("It worked", "success")
        flash("Something broke", "error")
        flash("For your information", "info")
        return render_template_string("{% include 'partials/flash_messages.html' %}")

    response = client.get("/flash-test")

    body = response.get_data(as_text=True)
    assert "It worked" in body
    assert "Something broke" in body
    assert "For your information" in body
