from typing import Any

import pytest

from byb_common.contracts import CatalogCandidate, ProductGeometry, ProductProfile
from byb_common.parts import build_parts
from byb_inference.products import best_profile, fallback_profile, profile_from_candidate

CANDIDATE = CatalogCandidate(
    sku="SOFA-302",
    name="Ektorp 3-seat sofa",
    brand="Ektorp",
    category="sofa",
    material="linen",
    price_band="$$",
    geometry=ProductGeometry(width_cm=218, depth_cm=95, height_cm=85, clearance_cm=90),
    parts=build_parts("sofa", 218, 95, 85),
    score=0.72,
)


def test_catalog_candidate_beats_a_guess():
    profile = profile_from_candidate(CANDIDATE)
    assert profile.source == "catalog"
    assert profile.geometry.width_cm == 218
    assert profile.confidence >= 0.6
    assert profile.parts, "a catalog SKU always knows its own box breakdown"


def test_heuristics_now_carry_parts_for_the_engine():
    profile = fallback_profile("three seater linen sofa", None)
    assert profile.parts
    assert {part.tone for part in profile.parts} & {"upholstery", "leg"}


def test_best_profile_takes_the_confident_one():
    weak = ProductProfile(name="weak", geometry=CANDIDATE.geometry, confidence=0.3)
    strong = ProductProfile(name="strong", geometry=CANDIDATE.geometry, confidence=0.8)
    assert best_profile(weak, strong).name == "strong"
    assert best_profile(None, weak).name == "weak"
    assert best_profile(None, None) is None


def test_best_profile_breaks_ties_towards_the_earlier_argument():
    a = ProductProfile(name="catalog", geometry=CANDIDATE.geometry, confidence=0.72)
    b = ProductProfile(name="vllm", geometry=CANDIDATE.geometry, confidence=0.72)
    assert best_profile(a, b).name == "catalog"


def test_sidecar_handshake_listens_for_the_catalog_topic(client):
    assert client.get("/dapr/subscribe").json() == [
        {"pubsubname": "byb-pubsub", "topic": "simulation.catalogued", "route": "/events"}
    ]


@pytest.fixture
def no_vllm(monkeypatch):
    """Keep the suite off the network: pretend the model endpoint did not answer."""

    async def silent(client, context, image=None):
        return None

    monkeypatch.setattr("byb_inference.main.describe_product", silent)


def test_enrich_reports_progress_then_moves_on(client, transport, no_vllm):
    payload = {
        "simulation_id": "cafe1234deadbeef",
        "room_width_m": 4.0,
        "room_depth_m": 3.5,
        "room_height_m": 2.4,
        "product_link": None,
        "image_key": None,
        "shopper_notes": "three seater linen sofa",
        "candidate": CANDIDATE.model_dump(),
    }
    profile: dict[str, Any] = client.post("/v1/enrich", json=payload).json()

    assert profile["source"] == "catalog"
    assert profile["name"] == "Ektorp 3-seat sofa"
    assert [(app_id, method) for app_id, method, _ in transport.calls] == [
        ("api-gateway", "/api/v1/internal/progress"),
        ("vision-service", "/v1/scan"),
    ]
    assert transport.calls[0][2]["status"] == "enriching"


def test_forwarded_message_carries_the_candidate_and_image(client, transport, no_vllm):
    payload = {
        "simulation_id": "deadbeefcafe1234",
        "room_width_m": 5.0,
        "room_depth_m": 4.0,
        "room_height_m": 2.5,
        "product_link": "https://example.com/p/unknown-thing",
        "image_key": "abc-room.jpg",
        "candidate": None,
    }
    client.post("/v1/enrich", json=payload)

    _, _, measured = transport.calls[-1]
    assert measured["image_key"] == "abc-room.jpg"
    assert measured["candidate"] is None
    assert measured["room_width_m"] == 5.0
    # No catalog hit and no vLLM answer, so the heuristics had to carry it.
    assert measured["profile"]["source"] == "heuristic"
