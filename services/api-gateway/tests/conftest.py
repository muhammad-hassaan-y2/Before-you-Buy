"""Sets the test environment before the app module (and therefore the engine) is imported."""

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE.parents[1] / "libs" / "byb-common" / "src"))

TMP = tempfile.mkdtemp(prefix="byb-gateway-")
os.environ["DATABASE_URL"] = f"sqlite:///{TMP}/test.db"
os.environ["UPLOAD_DIR"] = TMP
os.environ["INTERNAL_TOKEN"] = "test-token"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"

import pytest  # noqa: E402

from byb_gateway import database, models  # noqa: E402


class RecordingDispatcher:
    def __init__(self) -> None:
        self.messages = []

    async def start(self, message) -> None:
        self.messages.append(message)


@pytest.fixture(autouse=True)
def fresh_schema():
    models.Base.metadata.drop_all(database.engine)
    models.Base.metadata.create_all(database.engine)
    yield


@pytest.fixture
def dispatcher():
    return RecordingDispatcher()


@pytest.fixture
def client(dispatcher):
    from fastapi.testclient import TestClient

    from byb_gateway.main import app

    with TestClient(app) as test_client:
        test_client.app.state.dispatch = dispatcher
        yield test_client
