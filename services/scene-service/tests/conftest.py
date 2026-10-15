import sys
from pathlib import Path
from typing import Any

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE.parents[1] / "libs" / "byb-common" / "src"))


class StubResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None


class StubTransport:
    """Records what the worker reports to the gateway instead of calling it over HTTP."""

    def __init__(self) -> None:
        self.calls = []

    async def request(self, client, app_id, method, payload):
        self.calls.append((app_id, method, payload))
        return StubResponse()


@pytest.fixture
def transport():
    return StubTransport()


@pytest.fixture
def client(transport):
    from fastapi.testclient import TestClient

    from byb_scene.main import app

    with TestClient(app) as test_client:
        test_client.app.state.transport = transport
        yield test_client


PROFILE: dict[str, Any] = {
    "name": "Ektorp 3-seat sofa",
    "category": "sofa",
    "source": "catalog",
    "confidence": 0.72,
    "geometry": {"width_cm": 218, "depth_cm": 95, "height_cm": 85, "clearance_cm": 90},
}

OBSTACLE = {"label": "radiator", "ring": [[0.0, 0.0], [0.9, 0.0], [0.9, 0.2], [0.0, 0.2], [0.0, 0.0]], "height_m": 0.6, "source": "declared"}


def placement(label: str, centre_x: float, centre_y: float, rotation: float, fits: bool, walkway: dict[str, float]) -> dict[str, Any]:
    half_w, half_d = (1.09, 0.475) if rotation == 0 else (0.475, 1.09)
    corners = [
        [round(centre_x - half_w, 3), round(centre_y - half_d, 3)],
        [round(centre_x + half_w, 3), round(centre_y - half_d, 3)],
        [round(centre_x + half_w, 3), round(centre_y + half_d, 3)],
        [round(centre_x - half_w, 3), round(centre_y + half_d, 3)],
    ]
    return {
        "label": label,
        "ring": [*corners, corners[0]],
        "area_m2": round(2 * half_w * 2 * half_d, 2),
        "footprint_m2": round(2.18 * 0.95, 2),
        "fits": fits,
        "centre_x_m": centre_x,
        "centre_y_m": centre_y,
        "rotation_deg": rotation,
        "walkway_m": walkway,
    }


FIT: dict[str, Any] = {
    "room_area_m2": 12.0,
    "usable_area_m2": 11.2,
    "verdict": "fits",
    "coverage_pct": 18.5,
    "conflicts": ["in the front-left corner: collides with the door swing."],
    "obstacles": [OBSTACLE],
    "door_swing_m": 0.85,
    "placements": [
        placement("centred on the back wall", 2.0, 2.55, 0.0, True, {"left": 0.9, "right": 0.9, "front": 2.1, "back": 0.05}),
        placement("flush with the left wall", 1.1, 1.5, 0.0, True, {"left": 0.01, "right": 1.99, "front": 1.05, "back": 1.05}),
        placement("in the front-left corner", 1.1, 0.55, 0.0, False, {"left": 1.1, "right": 1.1, "front": 0.1, "back": 1.0}),
    ],
}


@pytest.fixture
def fitted() -> dict[str, Any]:
    """A real-shaped SimulationFitted: the message geometry-service publishes."""
    return {
        "simulation_id": "cafe1234deadbeef",
        "profile": PROFILE,
        "candidate": None,
        "scan": {"width_m": 4.0, "depth_m": 3.0, "height_m": 2.5, "obstacles": [OBSTACLE], "measured": True, "method": "photo", "confidence": 0.68},
        "fit": FIT,
    }
