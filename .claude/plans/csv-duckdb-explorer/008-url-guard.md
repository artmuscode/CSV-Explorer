# Task 008: UrlGuard (SSRF Protection)

**Status**: pending
**Depends on**: 001, 002
**Retry count**: 0

## Description
Create `UrlGuard`, which checks that a URL is safe to fetch before any network request happens. It allows only http/https and rejects hosts that resolve to non-public addresses, unless private addresses are explicitly allowed.

## Context
- Related files (new): `app/services/__init__.py`, `app/services/url_guard.py`, `tests/unit/services/__init__.py`, `tests/unit/services/test_url_guard.py`
- **`app/services/__init__.py` stays empty, with no re-exports.** Tasks 010 and 011 add modules to this package in the same parallel batch (B4).
- Constructor: `UrlGuard(allow_private: bool = False, resolver: Callable[[str], list[str]] | None = None)`. The default resolver returns the unique IPs from `socket.getaddrinfo(host, None)`.
- `validate(url: str) -> None` raises `IngestError` when:
  - the scheme isn't `http`/`https` after parsing with `urllib.parse.urlsplit`
  - there's no hostname
  - resolution fails (`socket.gaierror`) or returns no addresses
  - `allow_private` is false and **any** resolved address isn't publicly routable. Use an allow-list rule: unwrap IPv4-mapped IPv6 (`addr.ipv4_mapped or addr`), then reject unless `addr.is_global and not addr.is_multicast`. A deny-list of `is_private` / `is_loopback` / `is_link_local` / `is_reserved` / `is_unspecified` misses carrier-grade NAT (`100.64.0.0/10`, which is neither private nor global) and similar ranges. The `is_multicast` check is still needed because Python reports IPv4 multicast as `is_global`.
  - the URL contains a backslash, whitespace or control characters. `urllib.parse` and urllib3 parse these differently, so the host the guard validates might not be the host `requests` connects to.
- Tests always inject a fake `resolver`. **No real DNS lookups.**

## Requirements (Test Descriptions)
- [ ] `test_validate_rejects_non_http_schemes` (parametrize: `file:///etc/passwd`, `ftp://example.com/a.csv`, `javascript:alert(1)`)
- [ ] `test_validate_rejects_url_without_host`
- [ ] `test_validate_rejects_unresolvable_host`
- [ ] `test_validate_rejects_loopback_private_and_link_local_addresses` (parametrize: `127.0.0.1`, `::1`, `10.0.0.5`, `192.168.1.10`, `169.254.169.254`, `::ffff:127.0.0.1`, `100.64.0.1`, `0.0.0.0`, `224.0.0.1`, `fd00::1`)
- [ ] `test_validate_rejects_urls_with_backslashes_or_whitespace` (e.g. `http://example.com\@127.0.0.1/a.csv`)
- [ ] `test_validate_rejects_when_any_resolved_address_is_private`
- [ ] `test_validate_allows_public_address`
- [ ] `test_validate_allows_private_address_when_flag_enabled`

## Acceptance Criteria
- All requirements have passing tests
- No network access in tests
- Code follows code standards

## Implementation Notes
(Left blank - filled in by programmer during implementation)
