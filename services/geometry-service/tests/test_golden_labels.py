"""Every verdict in the golden set is re-derived here, by the engine that owns it.

This is what keeps the agent's false-fit gate honest. The labels it is judged against are not an
opinion someone typed into a JSON file and left to rot: they are `POST /v1/fit` for that SKU box
in that room, re-run on every commit.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

GOLDEN_SET = Path(__file__).resolve().parents[3] / "evals" / "golden_briefs.json"
DOC = json.loads(GOLDEN_SET.read_text(encoding="utf-8"))


def labels() -> list[tuple[str, dict[str, float], dict[str, Any]]]:
    return [(case["id"], case["room"], candidate) for case in DOC["cases"] for candidate in case["candidates"]]


LABEL_IDS = [f"{case_id}-{candidate['sku']}" for case_id, _room, candidate in labels()]


def fit_body(room: dict[str, float], candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "simulation_id": f"golden-{candidate['sku'].lower()}",
        "profile": {
            "name": candidate["name"],
            "category": candidate["category"],
            "material": candidate["material"],
            "source": "catalog",
            "confidence": 0.8,
            "geometry": candidate["geometry"],
        },
        "candidate": None,
        "scan": {
            "width_m": room["width_m"],
            "depth_m": room["depth_m"],
            "height_m": room["height_m"],
            "obstacles": [],
            "measured": False,
            "method": "declared",
        },
    }


@pytest.mark.parametrize("case_id, room, candidate", labels(), ids=LABEL_IDS)
def test_the_label_is_what_the_engine_says(client, case_id: str, room: dict[str, float], candidate: dict[str, Any]) -> None:
    report = client.post("/v1/fit", json=fit_body(room, candidate)).json()
    engine = candidate["engine"]
    assert report["verdict"] == engine["verdict"], f"{case_id}/{candidate['sku']}: the golden set says {engine['verdict']}, geometry says {report['verdict']}"
    assert report["door_pass"] == engine["door_pass"], f"{case_id}/{candidate['sku']}: delivery path changed"
    assert report["fragile"] == engine["fragile"], f"{case_id}/{candidate['sku']}: the tolerance verdict changed"


def test_the_set_covers_every_way_a_piece_can_fail() -> None:
    """One case per rejection route, or the agent is only ever tested against good news."""
    engines = [candidate["engine"] for case in DOC["cases"] for candidate in case["candidates"]]
    assert {"fits", "tight", "blocked"} <= {engine["verdict"] for engine in engines}
    assert any(engine["door_pass"] == "blocked" for engine in engines)
    assert any(engine["fragile"] for engine in engines)
