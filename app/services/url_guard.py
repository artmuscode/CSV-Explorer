"""SSRF protection for URL ingest.

`UrlGuard.validate` checks that a URL is safe to fetch *before* any network
request happens: only http/https, a resolvable host, and (unless explicitly
allowed) only addresses that are publicly routable.
"""

import ipaddress
import re
import socket
from collections.abc import Callable
from urllib.parse import urlsplit

from app.exceptions import IngestError

_UNSAFE_CHARS_RE = re.compile(r"[\\\s\x00-\x1f\x7f]")


def _default_resolver(host: str) -> list[str]:
    """Resolve `host` to its unique IP addresses via `socket.getaddrinfo`."""
    infos = socket.getaddrinfo(host, None)
    addresses: list[str] = []
    for info in infos:
        address = info[4][0]
        if address not in addresses:
            addresses.append(address)
    return addresses


class UrlGuard:
    """Validates that a URL is safe to fetch, rejecting SSRF-prone targets."""

    def __init__(
        self,
        allow_private: bool = False,
        resolver: Callable[[str], list[str]] | None = None,
    ) -> None:
        self._allow_private = allow_private
        self._resolver = resolver or _default_resolver

    def validate(self, url: str) -> None:
        """Raise `IngestError` if `url` is unsafe to fetch."""
        if _UNSAFE_CHARS_RE.search(url):
            raise IngestError(f"URL contains unsafe characters: {url!r}")

        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            raise IngestError(f"Unsupported URL scheme: {parts.scheme!r}")

        host = parts.hostname
        if not host:
            raise IngestError(f"URL is missing a host: {url!r}")

        try:
            addresses = self._resolver(host)
        except socket.gaierror as exc:
            raise IngestError(f"Could not resolve host: {host}") from exc

        if not addresses:
            raise IngestError(f"Could not resolve host: {host}")

        if self._allow_private:
            return

        for address in addresses:
            if not self._is_public(address):
                raise IngestError(f"URL resolves to a non-public address: {address}")

    @staticmethod
    def _is_public(address: str) -> bool:
        ip = ipaddress.ip_address(address)
        unwrapped = getattr(ip, "ipv4_mapped", None) or ip
        return unwrapped.is_global and not unwrapped.is_multicast
