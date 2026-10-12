"""Shared HTTP test fakes for URL-ingest tests.

Not a test module itself: `FakeResponse`, `FakeSession` and `static_resolver`
are imported by `tests/unit/services/test_csv_downloader.py` and friends to
avoid any real network calls.
"""

import socket
from collections.abc import Callable, Iterator, Sequence

from requests.structures import CaseInsensitiveDict


class FakeResponse:
    """A minimal stand-in for `requests.Response`."""

    def __init__(
        self,
        status_code: int = 200,
        body: bytes = b"",
        headers: dict[str, str] | None = None,
        chunk_size: int | None = None,
        raise_after_chunks: int | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self.body = body
        self.headers = CaseInsensitiveDict(headers or {})
        self._chunk_size = chunk_size
        self._raise_after_chunks = raise_after_chunks
        self._exc = exc
        self.closed = False

    def iter_content(self, chunk_size: int) -> Iterator[bytes]:
        size = self._chunk_size or chunk_size
        for chunk_number, start in enumerate(range(0, len(self.body), size), start=1):
            yield self.body[start : start + size]
            if self._raise_after_chunks is not None and chunk_number >= self._raise_after_chunks:
                raise self._exc

    def close(self) -> None:
        self.closed = True


class FakeSession:
    """A minimal stand-in for `requests.Session`."""

    def __init__(self, routes: dict[str, "FakeResponse | Exception"]) -> None:
        self._routes = routes
        self.calls: list[dict] = []

    def get(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if url not in self._routes:
            raise AssertionError(f"FakeSession has no route for {url!r}")
        route = self._routes[url]
        if isinstance(route, Exception):
            raise route
        return route


def static_resolver(
    mapping: dict[str, list[str]],
    default: Sequence[str] | None = ("93.184.216.34",),
) -> Callable[[str], list[str]]:
    """Build a resolver function for `UrlGuard` from a static host->IPs mapping."""

    def resolver(host: str) -> list[str]:
        if host in mapping:
            return list(mapping[host])
        if default is None:
            raise socket.gaierror(f"Name or service not known: {host}")
        return list(default)

    return resolver
