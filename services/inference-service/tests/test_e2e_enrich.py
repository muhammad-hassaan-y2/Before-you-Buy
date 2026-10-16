"""End-to-end POST /v1/enrich with mocked product fetch, Token Factory, and geometry."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from byb_common.dapr import DaprTransport
from byb_inference.main import app
from byb_inference.settings import settings

FIXTURES = Path(__file__).parent / "fixtures"
PRODUCT_HTML = (FIXTURES / "product_spec_table.html").read_text(encoding="utf-8")

ENRICH_BODY = {
    "simulation_id": "e2einteg-0000-0000-0000-000000000001",
    "room_width_m": 4.0,
    "room_depth_m": 3.5,
    "room_height_m": 2.4,
    "product_link": "https://shop.example/nord-sofa",
    "shopper_notes": "three-seater linen sofa",
}

TF_SUCCESS = {
    "choices": [
        {
            "message": {
                "content": json.dumps(
                    {
                        "name": "Nord Sofa",
                        "brand": None,
                        "category": "sofa",
                        "material": "linen",
                        "price_band": "mid",
                        "width_cm": 228,
                        "depth_cm": 95,
                        "height_cm": 80,
                        "clearance_cm": 90,
                        "summary": "Assembled dims from product table.",
                    }
                )
            }
        }
    ]
}


@pytest.fixture
def tf_settings(monkeypatch):
    monkeypatch.setattr(settings, "vllm_base_url", "https://token-factory.example/v1")
    monkeypatch.setattr(settings, "vllm_model", "example-model-id")
    monkeypatch.setattr(settings, "vllm_api_key", "tf-test-key")
    monkeypatch.setattr(settings, "vllm_timeout_s", 5.0)
    monkeypatch.setattr(settings, "dapr_http_endpoint", None)
    monkeypatch.setattr(settings, "geometry_url", "http://geometry.example")
    monkeypatch.setattr(settings, "internal_token", "test-internal-token")
    monkeypatch.setattr("byb_inference.safe_fetch._public_ips", lambda host: ["203.0.113.10"])
    monkeypatch.setattr("byb_inference.vllm_client._retry_delay_s", lambda attempt, response: 0.0)


def _make_handler(recorder: dict, *, tf_responder):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/chat/completions" in url:
            recorder["tf_request"] = {
                "url": url,
                "authorization": request.headers.get("Authorization"),
                "body": json.loads(request.content.decode()),
            }
            return tf_responder(request)
        if url.rstrip("/").endswith("/v1/measure"):
            recorder["geometry_payload"] = json.loads(request.content.decode())
            recorder["geometry_token"] = request.headers.get("x-byb-token")
            return httpx.Response(200, json={"status": "ok"})
        # Product page (IP-pinned)
        recorder["product_fetch"] = {
            "url": url,
            "host": request.headers.get("Host"),
        }
        return httpx.Response(200, text=PRODUCT_HTML, headers={"content-type": "text/html; charset=utf-8"})

    return handler


def _enrich_client(handler) -> tuple[TestClient, httpx.AsyncClient]:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport, follow_redirects=True)
    client = TestClient(app)
    client.__enter__()
    app.state.http = http_client
    app.state.transport = DaprTransport(
        dapr_http_endpoint=None,
        routes={"geometry-service": "http://geometry.example"},
        token=settings.internal_token,
    )
    return client, http_client


def _close(client: TestClient, http_client: httpx.AsyncClient) -> None:
    import asyncio

    try:
        client.__exit__(None, None, None)
    finally:
        asyncio.run(http_client.aclose())


def test_enrich_success_reaches_geometry_with_token_factory_profile(tf_settings):
    recorder: dict = {}

    def tf_responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=TF_SUCCESS)

    client, http_client = _enrich_client(_make_handler(recorder, tf_responder=tf_responder))
    try:
        response = client.post("/v1/enrich", json=ENRICH_BODY)
    finally:
        _close(client, http_client)

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "amd_token_factory"
    assert body["provider"] == "amd_token_factory"
    assert body["model"] == "example-model-id"
    assert body["geometry"]["width_cm"] == 228
    assert body["geometry"]["depth_cm"] == 95
    assert body["geometry"]["height_cm"] == 80
    assert body["dimension_reliability"]["width_cm"] == "extracted"
    assert body["measurement_basis"] == "amd_token_factory"

    tf_req = recorder["tf_request"]
    assert tf_req["authorization"] == "Bearer tf-test-key"
    assert tf_req["body"]["model"] == "example-model-id"
    assert tf_req["body"]["messages"]
    assert tf_req["url"].endswith("/chat/completions")
    # Fixture evidence should reach the model prompt
    user_content = tf_req["body"]["messages"][-1]["content"]
    assert "228" in user_content or "sofa" in user_content.lower()

    geo = recorder["geometry_payload"]
    assert geo["simulation_id"] == ENRICH_BODY["simulation_id"]
    assert geo["profile"]["source"] == "amd_token_factory"
    assert geo["profile"]["geometry"]["width_cm"] == 228
    assert geo["room_width_m"] == 4.0
    assert recorder["geometry_token"] == "test-internal-token"
    assert recorder["product_fetch"]["host"] == "shop.example"


def test_enrich_timeout_falls_back_without_claiming_verified(tf_settings):
    recorder: dict = {}

    def tf_responder(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client, http_client = _enrich_client(_make_handler(recorder, tf_responder=tf_responder))
    try:
        response = client.post("/v1/enrich", json=ENRICH_BODY)
    finally:
        _close(client, http_client)

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "heuristic"
    # Listing table provides all three axes → verified, not estimated
    assert body["measurement_basis"] == "listing_verified"
    assert all(v == "verified" for v in body["dimension_reliability"].values())
    assert "estimate" not in body["summary"].lower()
    assert recorder.get("geometry_payload") is not None
    assert recorder["geometry_payload"]["profile"]["source"] == "heuristic"


def test_enrich_http_401_falls_back(tf_settings):
    recorder: dict = {}

    def tf_responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    client, http_client = _enrich_client(_make_handler(recorder, tf_responder=tf_responder))
    try:
        response = client.post("/v1/enrich", json=ENRICH_BODY)
    finally:
        _close(client, http_client)

    assert response.status_code == 200
    assert response.json()["source"] == "heuristic"
    assert recorder["geometry_payload"]["profile"]["source"] == "heuristic"


def test_enrich_http_429_then_success(tf_settings):
    recorder: dict = {"tf_calls": 0}

    def tf_responder(request: httpx.Request) -> httpx.Response:
        recorder["tf_calls"] += 1
        if recorder["tf_calls"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"error": "rate"})
        return httpx.Response(200, json=TF_SUCCESS)

    client, http_client = _enrich_client(_make_handler(recorder, tf_responder=tf_responder))
    try:
        response = client.post("/v1/enrich", json=ENRICH_BODY)
    finally:
        _close(client, http_client)

    assert response.status_code == 200
    assert response.json()["source"] == "amd_token_factory"
    assert recorder["tf_calls"] == 2
    assert recorder["geometry_payload"]["profile"]["source"] == "amd_token_factory"


def test_enrich_invalid_json_falls_back(tf_settings):
    recorder: dict = {}

    def tf_responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "I refuse to emit JSON."}}]},
        )

    client, http_client = _enrich_client(_make_handler(recorder, tf_responder=tf_responder))
    try:
        response = client.post("/v1/enrich", json=ENRICH_BODY)
    finally:
        _close(client, http_client)

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "heuristic"
    assert body["dimension_reliability"]["width_cm"] == "verified"


def test_enrich_missing_model_dimensions_falls_back(tf_settings):
    recorder: dict = {}

    def tf_responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "name": "Nord Sofa",
                                    "category": "sofa",
                                    "width_cm": None,
                                    "depth_cm": 95,
                                    "height_cm": 80,
                                    "summary": "width unknown",
                                }
                            )
                        }
                    }
                ]
            },
        )

    client, http_client = _enrich_client(_make_handler(recorder, tf_responder=tf_responder))
    try:
        response = client.post("/v1/enrich", json=ENRICH_BODY)
    finally:
        _close(client, http_client)

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "heuristic"
    # Must not pretend TF verified missing width
    assert body["provider"] is None
    assert body["measurement_basis"] == "listing_verified"


def test_enrich_notes_only_category_estimate_not_verified(tf_settings):
    """No URL / empty scrape → estimates must be labeled estimated."""
    recorder: dict = {}

    def tf_responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "down"})

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/chat/completions" in url:
            return tf_responder(request)
        if "/v1/measure" in url:
            recorder["geometry_payload"] = json.loads(request.content.decode())
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(200, text="<html></html>", headers={"content-type": "text/html"})

    client, http_client = _enrich_client(handler)
    try:
        response = client.post(
            "/v1/enrich",
            json={
                **ENRICH_BODY,
                "product_link": None,
                "shopper_notes": "grey sofa for living room",
                "simulation_id": "e2einteg-0000-0000-0000-000000000099",
            },
        )
    finally:
        _close(client, http_client)

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "heuristic"
    assert body["measurement_basis"] == "category_estimate"
    assert all(v == "estimated" for v in body["dimension_reliability"].values())
    assert "not verified" in body["summary"].lower()
    assert recorder["geometry_payload"]["profile"]["measurement_basis"] == "category_estimate"
