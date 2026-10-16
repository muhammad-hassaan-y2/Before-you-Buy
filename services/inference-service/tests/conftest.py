import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE.parents[1] / "libs" / "byb-common" / "src"))


class StubResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None


class StubTransport:
    """Records outbound hops instead of calling vision-service over real HTTP."""

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

    from byb_inference.main import app

    with TestClient(app) as test_client:
        test_client.app.state.transport = transport
        yield test_client
