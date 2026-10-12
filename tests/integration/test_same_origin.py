"""Integration tests for same-origin protection on state-changing requests."""

import pytest


@pytest.fixture
def app(make_app):
    app = make_app()

    @app.route("/_test/echo", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def echo():
        return "", 204

    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_post_with_matching_origin_is_allowed(client):
    response = client.post(
        "/_test/echo",
        headers={"Origin": "http://localhost"},
        base_url="http://localhost",
    )

    assert response.status_code == 204


def test_post_with_foreign_origin_is_rejected_with_403(client):
    response = client.post(
        "/_test/echo",
        headers={"Origin": "http://evil.example"},
        base_url="http://localhost",
    )

    assert response.status_code == 403


def test_post_with_null_origin_is_rejected(client):
    response = client.post(
        "/_test/echo",
        headers={"Origin": "null"},
        base_url="http://localhost",
    )

    assert response.status_code == 403


def test_post_with_foreign_referer_and_no_origin_is_rejected(client):
    response = client.post(
        "/_test/echo",
        headers={"Referer": "http://evil.example/some-page"},
        base_url="http://localhost",
    )

    assert response.status_code == 403


def test_post_without_origin_or_referer_is_allowed(client):
    response = client.post("/_test/echo", base_url="http://localhost")

    assert response.status_code == 204


def test_get_requests_are_never_checked(client):
    response = client.get(
        "/_test/echo",
        headers={"Origin": "http://evil.example"},
        base_url="http://localhost",
    )

    assert response.status_code == 204


def test_session_cookie_is_samesite_lax(app):
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
