import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE.parents[1] / "libs" / "byb-common" / "src"))


class StubResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None


class StubTransport:
    """Records outbound hops instead of calling geometry-service over real HTTP."""

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

    from byb_vision.main import app

    with TestClient(app) as test_client:
        test_client.app.state.transport = transport
        yield test_client


def _room_frame(*, width=640, height=480) -> np.ndarray:
    """A two-point drawing of the three lines `photo.py` looks for.

    Corner at x=240 spanning y=40..300, so 260 px stands for the 2.4 m ceiling.
    The floor junctions leave that corner at (0, 330) and (639, 340).
    """
    frame = np.full((height, width, 3), 255, np.uint8)
    cv2.line(frame, (240, 40), (240, 300), (0, 0, 0), 4)
    cv2.line(frame, (0, 330), (240, 300), (0, 0, 0), 4)
    cv2.line(frame, (240, 300), (639, 340), (0, 0, 0), 4)
    return frame


@pytest.fixture
def draw_room():
    return _room_frame


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    """A writable uploads directory pointed at by the service settings."""
    from byb_vision.settings import settings

    directory = tmp_path / "uploads"
    directory.mkdir()
    monkeypatch.setattr(settings, "upload_dir", str(directory))
    return directory
