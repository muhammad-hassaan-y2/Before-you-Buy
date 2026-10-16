"""SSRF-hardened HTTP GET for product listing pages.

Connects to a DNS-resolved public IP while preserving the original hostname for
TLS SNI / certificate verification (Host header + sni_hostname), so validation
and the TCP connection use the same address for that attempt.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

logger = logging.getLogger("byb.inference.fetch")

MAX_RESPONSE_BYTES = 1_000_000
MAX_REDIRECTS = 5
ALLOWED_CONTENT_TYPES = (
    "text/html",
    "application/xhtml+xml",
    "text/plain",
    "application/json",
)


class FetchError(Exception):
    """Raised when a URL cannot be fetched safely."""


def _host_ips(hostname: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FetchError(f"DNS resolution failed for {hostname!r}") from exc
    addresses: list[str] = []
    for info in infos:
        addr = info[4][0]
        if addr not in addresses:
            addresses.append(addr)
    if not addresses:
        raise FetchError(f"no addresses for {hostname!r}")
    return addresses


def _is_blocked_ip(raw: str) -> bool:
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return True
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _public_ips(hostname: str) -> list[str]:
    addresses = _host_ips(hostname)
    public = [addr for addr in addresses if not _is_blocked_ip(addr)]
    if not public:
        raise FetchError(f"hostname resolves only to blocked addresses: {addresses}")
    return public


def validate_url(url: str) -> tuple[str, str, str]:
    """Validate URL; return (normalized_url, hostname, pinned_ip)."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise FetchError("only http and https URLs are allowed")
    if not parsed.hostname:
        raise FetchError("URL missing hostname")
    host = parsed.hostname.lower()
    if host in {"localhost", "metadata", "metadata.google.internal"}:
        raise FetchError("hostname is blocked")
    try:
        ipaddress.ip_address(host)
        if _is_blocked_ip(host):
            raise FetchError("URL targets a private or reserved address")
        pinned = host
    except ValueError:
        pinned = _public_ips(host)[0]
    return url.strip(), host, pinned


def _pin_url(url: str, hostname: str, ip: str) -> str:
    parsed = urlparse(url)
    port = parsed.port
    if port is None:
        netloc = f"[{ip}]" if ":" in ip else ip
    else:
        netloc = f"[{ip}]:{port}" if ":" in ip else f"{ip}:{port}"
    return urlunparse((parsed.scheme, netloc, parsed.path or "/", parsed.params, parsed.query, parsed.fragment))


def _host_header(hostname: str, url: str) -> str:
    parsed = urlparse(url)
    if parsed.port:
        return f"{hostname}:{parsed.port}"
    return hostname


def _content_type_ok(header: str | None) -> bool:
    if not header:
        return True
    media = header.split(";", 1)[0].strip().lower()
    return any(media == allowed or media.startswith(allowed) for allowed in ALLOWED_CONTENT_TYPES)


async def fetch_product_html(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout_s: float,
    user_agent: str,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> str:
    """GET a product page with redirect checks and IP-pinned connections."""
    current, _, _ = validate_url(url)
    base_headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    }

    for _ in range(MAX_REDIRECTS + 1):
        current, hostname, pinned_ip = validate_url(current)
        pinned = _pin_url(current, hostname, pinned_ip)
        headers = {
            **base_headers,
            "Host": _host_header(hostname, current),
        }
        # Connect to pinned_ip; keep original hostname for TLS SNI / cert verify.
        extensions = {"sni_hostname": hostname} if urlparse(current).scheme == "https" else {}

        try:
            response = await client.get(
                pinned,
                headers=headers,
                timeout=timeout_s,
                follow_redirects=False,
                extensions=extensions,
            )
        except httpx.HTTPError as exc:
            raise FetchError(f"request failed: {exc}") from exc

        if response.is_redirect:
            location = response.headers.get("location")
            if not location:
                raise FetchError("redirect without Location header")
            # Resolve relative to the *logical* URL (hostname), not the IP form.
            current, _, _ = validate_url(urljoin(current, location))
            continue

        if response.status_code >= 400:
            raise FetchError(f"HTTP {response.status_code}")

        if not _content_type_ok(response.headers.get("content-type")):
            raise FetchError(f"unsupported content type: {response.headers.get('content-type')}")

        body = response.content
        if len(body) > max_bytes:
            raise FetchError(f"response exceeds {max_bytes} bytes")
        return body.decode(response.encoding or "utf-8", errors="replace")

    raise FetchError("too many redirects")
