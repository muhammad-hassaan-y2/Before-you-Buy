"""The REST surface, with the pipeline and Evolus behind stubs.

The service is assembled at import, so the tests swap its module-level collaborators instead
of starting six real services. What is under test is the contract the Evolus workspace and the
shop's own UI call against.
"""

import time
from types import SimpleNamespace

import httpx
import pytest
from conftest import StubEvolus, StubModel, StubPipeline
from fastapi.testclient import TestClient

from byb_agent import main
from byb_agent.contracts import AgentRun
from byb_agent.runs import Reservations, RunStore
from byb_agent.tools import SPEC, Tools


@pytest.fixture(scope="module")
def client():
    """One TestClient for the module: the MCP session manager can only run once per mounted app."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(main, "HTTP", httpx.AsyncClient())
    with TestClient(main.app) as test_client:
        yield test_client
    monkeypatch.undo()


@pytest.fixture
def api(client, rows, settings, monkeypatch):
    pipeline = StubPipeline(rows, verdicts={"default": "fits"})
    evolus = StubEvolus()
    model = StubModel()
    store = RunStore()
    reservations = Reservations()
    monkeypatch.setattr(main, "STORE", store)
    monkeypatch.setattr(main, "RESERVATIONS", reservations)
    monkeypatch.setattr(main, "PIPELINE", pipeline)
    monkeypatch.setattr(main, "EVOLUS", evolus)
    monkeypatch.setattr(main, "MODEL", model)
    monkeypatch.setattr(main, "TOOLS", Tools(pipeline, evolus, model, store, settings, reservations))
    return SimpleNamespace(client=client, pipeline=pipeline, evolus=evolus, model=model, store=store, reservations=reservations)


def settled(client: TestClient, run_id: str, timeout: float = 5.0) -> dict:
    """A journey runs in the background; wait for the trace to stop growing."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f"/agent/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} never settled: {run['status']}")


def test_health_says_which_brains_are_connected(api):
    body = api.client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["evolus"] == "connected"
    assert body["model"] == "heuristic", "no AMD endpoint is configured, so the health check must not claim one"
    assert body["mcp"] == "/mcp"
    assert int(body["tools"]) == len(SPEC)


def test_health_notices_a_missing_workspace(api):
    api.evolus.credentials = False
    assert api.client.get("/healthz").json()["evolus"] == "not configured"


def test_the_tool_catalog_is_what_the_agent_sees(api):
    tools = api.client.get("/agent/tools").json()["tools"]
    assert {tool["name"] for tool in tools} == set(SPEC)
    assert all(tool["description"] for tool in tools)


def test_an_unknown_tool_is_a_404(api):
    assert api.client.post("/agent/tools/measure_the_moon", json={}).status_code == 404


def test_a_capability_answers_through_rest(api):
    body = api.client.post("/agent/tools/catalog_search", json={"query": "linen sofa", "limit": 2}).json()
    assert body["tool"] == "catalog_search"
    assert {row["sku"] for row in body["result"]} == {"SOF-001", "SOF-002"}


def test_a_tool_only_gets_the_arguments_it_declares(api):
    body = api.client.post("/agent/tools/read_brief", json={"brief": "a 4.2 x 3.4 room for a linen sofa", "ignored": True}).json()
    assert body["result"]["category"] == "sofa"
    assert body["result"]["room_width_m"] == 4.2


def test_a_tool_that_needs_a_product_says_what_is_missing(api):
    response = api.client.post("/agent/tools/simulate_product", json={})
    assert response.status_code == 422
    assert "sku" in response.json()["detail"]


def test_a_workflow_tool_takes_the_room_photo_too(api):
    """The JSON door forwards image_key, so an external agent fits into the photographed room."""
    photo = "cd" * 16 + "-room.jpg"
    measured = api.client.post("/agent/tools/simulate_product", json={"sku": "SOF-001", "image_key": photo}).json()["result"]
    assert measured["attempt"]["verdict"] == "fits"
    assert api.pipeline.started[-1]["image_key"] == photo


def test_the_new_capabilities_are_callable_over_rest(api):
    """Same numbers through the workflow door as through the connector, including the human gate."""
    measured = api.client.post("/agent/tools/simulate_product", json={"sku": "SOF-001"}).json()["result"]
    simulation_id = measured["attempt"]["simulation_id"]

    explained = api.client.post("/agent/tools/explain_fit", json={"simulation_id": simulation_id}).json()["result"]
    assert explained["verdict"] == "fits"
    assert explained["door_pass"] == "pass"

    offer = api.client.post("/agent/tools/proven_fit_offer", json={"simulation_id": simulation_id}).json()["result"]
    assert offer["offer"]["sku"] == "SOF-001"
    assert offer["fit_evidence"]["verify"] == f"/api/v1/simulations/{simulation_id}"

    refused = api.client.post("/agent/tools/reserve_fit", json={"simulation_id": simulation_id, "confirmation": "maybe?"})
    assert refused.status_code == 422
    assert "own yes" in refused.json()["detail"]

    held = api.client.post("/agent/tools/reserve_fit", json={"simulation_id": simulation_id, "confirmation": "yes"}).json()["result"]
    assert held["status"] == "pending_merchant"
    assert [item["id"] for item in api.client.get("/agent/reservations").json()] == [held["id"]]
    assert api.client.get("/healthz").json()["reservations"] == "1"


def test_a_multi_piece_brief_is_answered_over_rest(api):
    body = api.client.post("/agent/tools/joint_fit", json={"skus": ["SOF-001", "BCK-001"]}).json()["result"]
    assert [piece["sku"] for piece in body["pieces"]] == ["SOF-001", "BCK-001"]
    assert body["combined"]["verdict"] == "fits"


def test_a_brief_starts_a_journey_the_browser_can_poll(api):
    started = api.client.post("/agent/brief", json={"brief": "a linen sofa for a 4.2 x 3.4 m room, budget 1200"})
    assert started.status_code == 202
    body = started.json()
    assert body["poll"] == f"/agent/runs/{body['run_id']}"

    run = settled(api.client, body["run_id"])
    assert run["status"] == "done"
    assert run["decision"]["action"] == "recommend"
    assert [step["kind"] for step in run["steps"]][:3] == ["intake", "agent", "brief"]
    assert api.pipeline.started, "the journey must queue real simulations"


def test_a_brief_with_a_room_photo_fits_every_candidate_into_that_room(api):
    photo = "ab" * 16 + "-living-room.jpg"
    started = api.client.post(
        "/agent/brief",
        json={"brief": "will a linen sofa fit the room in my photo", "image_key": photo},
    )
    assert started.status_code == 202
    run = settled(api.client, started.json()["run_id"])
    assert {step["kind"] for step in run["steps"]} >= {"room", "fit"}
    assert {simulation["image_key"] for simulation in api.pipeline.started} == {photo}


def test_the_runs_are_listed_newest_first(api):
    run = AgentRun(id="run-old", status="done")
    other = AgentRun(id="run-new", status="done")
    api.store.put(run)
    api.store.put(other)
    assert [item["id"] for item in api.client.get("/agent/runs").json()] == ["run-new", "run-old"]


def test_a_run_that_never_happened_is_a_404(api):
    assert api.client.get("/agent/runs/ghost").status_code == 404


def test_a_workflow_result_lands_on_the_run_it_belongs_to(api):
    api.store.put(AgentRun(id="run-77", status="running"))
    response = api.client.post(
        "/agent/webhooks/evolus?run=run-77", json={"verdict": "fits"}, headers={"X-Workflow-Execution-Id": "exec-3"}
    )
    assert response.status_code == 202
    assert response.json()["attached"] is True
    stored = api.store.get("run-77")
    assert stored.callback == {"verdict": "fits"}
    assert stored.evolus_execution_id == "exec-3"


def test_a_webhook_for_a_run_that_is_not_here_is_still_taken(api):
    assert api.client.post("/agent/webhooks/evolus?run=ghost", json={}).json() == {"received": True, "attached": False}


INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "evolus", "version": "test"}},
}


def test_the_mcp_door_is_mounted_on_the_same_service(api):
    """One app, two doors: the connector Evolus attaches to lives beside the REST tools."""
    response = api.client.post(
        "/mcp/",
        json=INITIALIZE,
        headers={"accept": "application/json, text/event-stream", "content-type": "application/json"},
    )
    assert response.status_code == 200, response.text
    assert "buy-you-before" in response.text


def test_chat_goes_to_the_agent_and_keeps_the_key_server_side(api):
    body = api.client.post("/agent/chat", json={"messages": [{"role": "user", "content": "will it fit?"}]}).json()
    assert body["answered_by"] == "evolus"
    assert body["conversation_id"] == "conv-9"
    assert api.evolus.prompts == ["will it fit?"]


def test_chat_carries_the_conversation_from_a_header(api):
    api.client.post("/agent/chat", json={"messages": [{"content": "and the walkway?"}]}, headers={"X-Conversation-Id": "conv-4"})
    body = api.client.post("/agent/chat", json={"messages": [{"content": "and the door?"}], "conversation_id": "conv-4"}).json()
    assert body["conversation_id"] == "conv-4"


def test_chat_falls_back_to_the_amd_model_and_says_which_one_spoke(api):
    api.evolus.fail = True
    api.model.configured = True
    body = api.client.post("/agent/chat", json={"messages": [{"content": "will it fit?"}]}).json()
    assert body["answered_by"] == "Qwen/Qwen2.5-7B-Instruct"
    assert body["answer"] == "the sofa will fit"


def test_chat_with_no_brain_at_all_refuses(api):
    api.evolus.fail = True
    assert api.client.post("/agent/chat", json={"messages": [{"content": "hi"}]}).status_code == 503


def test_chat_needs_something_to_say(api):
    assert api.client.post("/agent/chat", json={"messages": []}).status_code == 422
