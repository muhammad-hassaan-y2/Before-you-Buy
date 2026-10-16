"""Enrich endpoints: Token Factory success path and heuristic fallback."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from byb_common.contracts import ProductGeometry, ProductProfile
from byb_inference.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


PROFILE_BODY = {
    "simulation_id": "proveamd01-0000-0000-0000-000000000001",
    "room_width_m": 4.0,
    "room_depth_m": 3.5,
    "room_height_m": 2.4,
    "shopper_notes": "three-seater linen sofa, oak legs",
}


def test_profile_endpoint_returns_token_factory_provenance(client):
    fake = ProductProfile(
        name="Linen sofa",
        category="sofa",
        geometry=ProductGeometry(width_cm=220, depth_cm=95, height_cm=85, clearance_cm=90),
        confidence=0.72,
        summary="Inferred via AMD Token Factory.",
        source="amd_token_factory",
        provider="amd_token_factory",
        model="example-model-id",
    )
    with patch("byb_inference.main.describe_product", new_callable=AsyncMock, return_value=fake):
        response = client.post("/v1/profile", json=PROFILE_BODY)
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "amd_token_factory"
    assert body["provider"] == "amd_token_factory"
    assert body["model"] == "example-model-id"
    assert body["name"] == "Linen sofa"


def test_profile_endpoint_heuristic_fallback(client):
    with patch("byb_inference.main.describe_product", new_callable=AsyncMock, return_value=None):
        response = client.post(
            "/v1/profile",
            json={**PROFILE_BODY, "simulation_id": "proveamd01-0000-0000-0000-000000000002"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "heuristic"
    assert body.get("provider") in (None, "")
    assert body["category"] == "sofa"
