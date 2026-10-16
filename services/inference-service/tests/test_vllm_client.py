"""Mocked OpenAI-compatible client tests (AMD Token Factory wiring)."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from byb_inference import vllm_client
from byb_inference.settings import settings


VALID_COMPLETION = {
    "choices": [
        {
            "message": {
                "content": (
                    '{"name": "Linen sofa", "brand": null, "category": "sofa", "material": "linen", '
                    '"price_band": "mid", "width_cm": 220, "depth_cm": 95, "height_cm": 85, '
                    '"clearance_cm": 90, "summary": "Three-seater from notes."}'
                )
            }
        }
    ]
}


@pytest.fixture
def configured_llm(monkeypatch):
    monkeypatch.setattr(settings, "vllm_base_url", "https://token-factory.example/v1")
    monkeypatch.setattr(settings, "vllm_model", "example-model-id")
    monkeypatch.setattr(settings, "vllm_api_key", "tf-test-key")
    monkeypatch.setattr(settings, "vllm_timeout_s", 5.0)


def _run(coro):
    return asyncio.run(coro)


def test_describe_product_success(configured_llm):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("Authorization")
        seen["model"] = json.loads(request.content.decode())["model"]
        assert str(request.url).endswith("/chat/completions")
        return httpx.Response(200, json=VALID_COMPLETION)

    transport = httpx.MockTransport(handler)

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await vllm_client.describe_product(client, "three-seater linen sofa")

    profile = _run(run())
    assert profile is not None
    assert profile.source == "amd_token_factory"
    assert profile.provider == "amd_token_factory"
    assert profile.model == "example-model-id"
    assert profile.measurement_basis == "amd_token_factory"
    assert profile.dimension_reliability["width_cm"] == "extracted"
    assert profile.name == "Linen sofa"
    assert profile.geometry.width_cm == 220
    assert seen["authorization"] == "Bearer tf-test-key"
    assert seen["model"] == "example-model-id"


def test_describe_product_authentication_failure(configured_llm):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid_api_key"})

    transport = httpx.MockTransport(handler)

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await vllm_client.describe_product(client, "sofa")

    assert _run(run()) is None


def test_describe_product_invalid_model_identifier(configured_llm):
    """Token Factory rejects unknown model ids with 400 (per AMD docs)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "Requested model not supported"})

    transport = httpx.MockTransport(handler)

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await vllm_client.describe_product(client, "sofa")

    assert _run(run()) is None


def test_describe_product_timeout(configured_llm):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    transport = httpx.MockTransport(handler)

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await vllm_client.describe_product(client, "sofa")

    assert _run(run()) is None


def test_describe_product_invalid_model_response(configured_llm):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Sorry, I cannot produce JSON today."}}]},
        )

    transport = httpx.MockTransport(handler)

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await vllm_client.describe_product(client, "sofa")

    assert _run(run()) is None


def test_to_profile_rejects_missing_dimensions():
    assert vllm_client.to_profile({"name": "Sofa", "width_cm": 200}, model_id="m") is None
    assert (
        vllm_client.to_profile(
            {"name": "Sofa", "width_cm": 200, "depth_cm": 90, "height_cm": "nope"},
            model_id="m",
        )
        is None
    )


def test_describe_product_skips_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "vllm_base_url", "")
    monkeypatch.setattr(settings, "vllm_model", "")
    monkeypatch.setattr(settings, "vllm_api_key", "")

    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json=VALID_COMPLETION)

    transport = httpx.MockTransport(handler)

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await vllm_client.describe_product(client, "sofa")

    assert _run(run()) is None
    assert called is False
