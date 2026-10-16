"""Retries, dimension provenance, and IP-pin SSRF behaviour."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from byb_inference import vllm_client
from byb_inference.products import fallback_profile
from byb_inference.safe_fetch import FetchError, fetch_product_html
from byb_inference.settings import settings


VALID_COMPLETION = {
    "choices": [
        {
            "message": {
                "content": (
                    '{"name": "Linen sofa", "brand": null, "category": "sofa", "material": "linen", '
                    '"price_band": "mid", "width_cm": 220, "depth_cm": 95, "height_cm": 85, '
                    '"clearance_cm": 90, "summary": "From listing."}'
                )
            }
        }
    ]
}


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def configured_llm(monkeypatch):
    monkeypatch.setattr(settings, "vllm_base_url", "https://token-factory.example/v1")
    monkeypatch.setattr(settings, "vllm_model", "example-model-id")
    monkeypatch.setattr(settings, "vllm_api_key", "tf-test-key")
    monkeypatch.setattr(settings, "vllm_timeout_s", 5.0)
    monkeypatch.setattr(vllm_client, "_retry_delay_s", lambda attempt, response: 0.0)


def test_retry_succeeds_after_503(configured_llm):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, json={"error": "busy"})
        return httpx.Response(200, json=VALID_COMPLETION)

    transport = httpx.MockTransport(handler)

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await vllm_client.describe_product(client, "sofa")

    profile = _run(run())
    assert profile is not None
    assert calls["n"] == 2
    assert profile.dimension_reliability["width_cm"] == "extracted"
    assert profile.measurement_basis == "amd_token_factory"


def test_retry_exhaustion_on_502(configured_llm):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"error": "bad_gateway"})

    transport = httpx.MockTransport(handler)

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await vllm_client.describe_product(client, "sofa")

    assert _run(run()) is None


def test_auth_failure_not_retried(configured_llm):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={"error": "unauthorized"})

    transport = httpx.MockTransport(handler)

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await vllm_client.describe_product(client, "sofa")

    assert _run(run()) is None
    assert calls["n"] == 1


def test_missing_dimensions_reject_model_json(configured_llm):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "name": "Mystery chair",
                                    "category": "chair",
                                    "width_cm": None,
                                    "depth_cm": 55,
                                    "height_cm": 85,
                                    "summary": "width unknown",
                                }
                            )
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await vllm_client.describe_product(client, "chair")

    assert _run(run()) is None


def test_estimated_dimension_provenance():
    profile = fallback_profile("og:title: Cosy grey sofa", None)
    assert profile.measurement_basis == "category_estimate"
    assert profile.dimension_reliability == {
        "width_cm": "estimated",
        "depth_cm": "estimated",
        "height_cm": "estimated",
    }
    assert "not verified" in profile.summary.lower()


def test_partial_listing_provenance():
    profile = fallback_profile("title: Desk\nWidth: 140 cm\nDepth: 70 cm", None)
    assert profile.dimension_reliability["width_cm"] == "verified"
    assert profile.dimension_reliability["depth_cm"] == "verified"
    assert profile.dimension_reliability["height_cm"] == "estimated"
    assert profile.measurement_basis == "listing_partial"


def test_dns_pin_uses_resolved_ip_and_sni_host(monkeypatch):
    monkeypatch.setattr("byb_inference.safe_fetch._public_ips", lambda host: ["203.0.113.50"])
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["host_header"] = request.headers.get("Host")
        seen["url_host"] = request.url.host
        seen["extensions"] = dict(request.extensions)
        return httpx.Response(200, text="<html>ok</html>", headers={"content-type": "text/html"})

    transport = httpx.MockTransport(handler)

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_product_html(
                client,
                "https://shop.example/product",
                timeout_s=2,
                user_agent="test",
            )

    body = _run(run())
    assert "ok" in body
    assert seen["url_host"] == "203.0.113.50"
    assert seen["host_header"] == "shop.example"
    assert seen["extensions"].get("sni_hostname") == "shop.example"


def test_https_hostname_verification_extension_set(monkeypatch):
    """Document that TLS verify uses original hostname via sni_hostname (not the pinned IP)."""
    monkeypatch.setattr("byb_inference.safe_fetch._public_ips", lambda host: ["198.51.100.9"])
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["sni"] = request.extensions.get("sni_hostname")
        captured["connect_host"] = request.url.host
        return httpx.Response(200, text="x", headers={"content-type": "text/html"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await fetch_product_html(client, "https://cdn.example/item", timeout_s=2, user_agent="t")

    _run(run())
    assert captured["connect_host"] == "198.51.100.9"
    assert captured["sni"] == "cdn.example"


def test_rebinding_redirect_to_private_still_blocked(monkeypatch):
    monkeypatch.setattr("byb_inference.safe_fetch._public_ips", lambda host: ["203.0.113.77"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await fetch_product_html(client, "https://example.com/x", timeout_s=2, user_agent="t")

    with pytest.raises(FetchError):
        _run(run())
