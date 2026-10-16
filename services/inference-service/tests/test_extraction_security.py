"""Extraction quality, unit conversion, and SSRF-safe fetch tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from byb_inference.products import (
    _to_cm,
    build_enrichment_context,
    extract_context,
    fallback_profile,
    parse_dimensions,
)
from byb_inference.safe_fetch import FetchError, fetch_product_html, validate_url

FIXTURES = Path(__file__).parent / "fixtures"


def _run(coro):
    return asyncio.run(coro)


def test_jsonld_product_dimensions():
    html = (FIXTURES / "product_jsonld.html").read_text(encoding="utf-8")
    context = extract_context(html)
    assert "Oak Writing Desk" in context or "oak writing desk" in context.lower()
    dims = parse_dimensions(context, kind="assembled")
    assert dims["width_cm"] == 140
    assert dims["depth_cm"] == 70
    assert dims["height_cm"] == 75


def test_html_specification_table_prefers_product_over_package():
    html = (FIXTURES / "product_spec_table.html").read_text(encoding="utf-8")
    context = extract_context(html)
    assembled = parse_dimensions(context, kind="assembled")
    package = parse_dimensions(context, kind="package")
    assert assembled["width_cm"] == 228
    assert assembled["depth_cm"] == 95
    assert package.get("width_cm") == 230
    assert "package_dimensions_cm" in context
    assert "do not use as product footprint" in context
    profile = fallback_profile(context, "https://example.com/sofa")
    assert profile.geometry.width_cm == 228


def test_unit_conversions():
    assert _to_cm("1200", "mm") == 120.0
    assert _to_cm("1.5", "m") == 150.0
    assert _to_cm("48", "inches") == 121.92
    assert parse_dimensions("Width: 1200 mm Depth: 600 mm Height: 400 mm")["width_cm"] == 120
    assert parse_dimensions("width: 1.5 m")["width_cm"] == 150
    assert parse_dimensions("Width: 48 inches")["width_cm"] == 121.92


def test_missing_dimensions_uses_category_estimates():
    context = "og:title: Cosy grey sofa\nshopper notes: soft linen"
    profile = fallback_profile(context, None)
    assert profile.geometry.width_cm == 220
    assert profile.confidence == 0.25
    assert "estimate" in profile.summary.lower() or "heuristic" in profile.summary.lower()


def test_conflicting_measurements_prefer_first_assembled_label():
    text = "Width: 200 cm Width: 250 cm Depth: 90 cm Height: 80 cm"
    dims = parse_dimensions(text, kind="assembled")
    assert dims["width_cm"] == 200


def test_package_vs_assembled_dimensions():
    text = (
        "Product dimensions Width: 180 cm Depth: 90 cm Height: 75 cm "
        "Package width: 190 cm Package depth: 95 cm Package height: 20 cm"
    )
    assert parse_dimensions(text, kind="assembled")["width_cm"] == 180
    assert parse_dimensions(text, kind="package")["width_cm"] == 190


def test_malformed_html_does_not_crash():
    html = (FIXTURES / "malformed.html").read_text(encoding="utf-8")
    context = extract_context(html)
    assert isinstance(context, str)


def test_shopper_notes_without_url():
    context = build_enrichment_context("", "three-seater linen sofa, oak legs, about 220 cm wide")
    assert "shopper notes:" in context
    profile = fallback_profile(context, None)
    assert profile.category == "sofa"
    assert profile.source == "heuristic"


def test_private_network_urls_rejected():
    with pytest.raises(FetchError):
        validate_url("http://127.0.0.1/product")
    with pytest.raises(FetchError):
        validate_url("http://localhost/product")
    with pytest.raises(FetchError):
        validate_url("http://192.168.1.10/sofa")
    with pytest.raises(FetchError):
        validate_url("ftp://example.com/x")


def test_unreachable_urls_and_oversized_responses(monkeypatch):
    monkeypatch.setattr("byb_inference.safe_fetch._public_ips", lambda host: ["203.0.113.10"])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/big"):
            return httpx.Response(200, content=b"x" * 50, headers={"content-type": "text/html"})
        raise httpx.ConnectError("failed", request=request)

    transport = httpx.MockTransport(handler)

    async def run_unreachable():
        async with httpx.AsyncClient(transport=transport) as client:
            await fetch_product_html(
                client,
                "https://example.com/missing",
                timeout_s=2,
                user_agent="test",
            )

    with pytest.raises(FetchError):
        _run(run_unreachable())

    async def run_oversize():
        async with httpx.AsyncClient(transport=transport) as client:
            await fetch_product_html(
                client,
                "https://example.com/big",
                timeout_s=2,
                user_agent="test",
                max_bytes=10,
            )

    with pytest.raises(FetchError, match="exceeds"):
        _run(run_oversize())


def test_redirect_based_ssrf_blocked(monkeypatch):
    monkeypatch.setattr("byb_inference.safe_fetch._public_ips", lambda host: ["203.0.113.10"])

    def handler(request: httpx.Request) -> httpx.Response:
        # Connection is pinned to the resolved IP; Host keeps the public name.
        if request.headers.get("Host", "").startswith("example.com"):
            return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
        return httpx.Response(200, text="ok", headers={"content-type": "text/html"})

    transport = httpx.MockTransport(handler)

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            await fetch_product_html(
                client,
                "https://example.com/sofa",
                timeout_s=2,
                user_agent="test",
            )

    with pytest.raises(FetchError):
        _run(run())
