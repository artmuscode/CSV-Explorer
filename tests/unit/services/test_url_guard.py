import socket

import pytest

from app.exceptions import IngestError
from app.services.url_guard import UrlGuard


@pytest.mark.parametrize(
    "url",
    ["file:///etc/passwd", "ftp://example.com/a.csv", "javascript:alert(1)"],
)
def test_validate_rejects_non_http_schemes(url):
    guard = UrlGuard(resolver=lambda host: ["93.184.216.34"])

    with pytest.raises(IngestError):
        guard.validate(url)


def test_validate_rejects_url_without_host():
    guard = UrlGuard(resolver=lambda host: ["93.184.216.34"])

    with pytest.raises(IngestError):
        guard.validate("http:///a.csv")


def test_validate_rejects_unresolvable_host():
    def resolver(host: str) -> list[str]:
        raise socket.gaierror("Name or service not known")

    guard = UrlGuard(resolver=resolver)

    with pytest.raises(IngestError):
        guard.validate("http://does-not-exist.example/a.csv")


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "::1",
        "10.0.0.5",
        "192.168.1.10",
        "169.254.169.254",
        "::ffff:127.0.0.1",
        "100.64.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "fd00::1",
    ],
)
def test_validate_rejects_loopback_private_and_link_local_addresses(address):
    guard = UrlGuard(resolver=lambda host: [address])

    with pytest.raises(IngestError):
        guard.validate("http://example.com/a.csv")


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com\\@127.0.0.1/a.csv",
        "http://example.com/a b.csv",
        "http://example.com/a\t.csv",
    ],
)
def test_validate_rejects_urls_with_backslashes_or_whitespace(url):
    guard = UrlGuard(resolver=lambda host: ["93.184.216.34"])

    with pytest.raises(IngestError):
        guard.validate(url)


def test_validate_rejects_when_any_resolved_address_is_private():
    guard = UrlGuard(resolver=lambda host: ["93.184.216.34", "10.0.0.5"])

    with pytest.raises(IngestError):
        guard.validate("http://example.com/a.csv")


def test_validate_allows_public_address():
    guard = UrlGuard(resolver=lambda host: ["93.184.216.34"])

    guard.validate("http://example.com/a.csv")


def test_validate_allows_private_address_when_flag_enabled():
    guard = UrlGuard(allow_private=True, resolver=lambda host: ["10.0.0.5"])

    guard.validate("http://internal.example/a.csv")
