"""The MCP connector: what an Evolus agent sees when it attaches to /mcp.

Same seven capabilities as REST, reachable over JSON-RPC, with schemas the model can call.
"""

import asyncio
import json

import httpx
import pytest
from conftest import StubEvolus, StubModel, StubPipeline
from httpx import ASGITransport

from byb_agent.mcp_server import INSTRUCTIONS, build_server, http_app
from byb_agent.runs import RunStore
from byb_agent.tools import Tools, _new_run_id

TOOL_NAMES = {"catalog_search", "read_brief", "simulate_product", "fit_report", "find_alternatives", "start_journey", "journey_status"}
INITIALIZE = {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "evolus", "version": "test"}}
HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


@pytest.fixture
def server(rows, settings):
    tools = Tools(StubPipeline(rows, verdicts={"default": "fits"}), StubEvolus(), StubModel(), RunStore(), settings)
    return build_server(tools)


def test_the_server_is_named_and_tells_the_agent_what_to_trust(server):
    assert server.name == "buy-you-before"
    assert server.instructions == INSTRUCTIONS
    assert "Trust only a verdict" in INSTRUCTIONS


async def test_the_agent_is_offered_the_same_seven_capabilities_as_rest(server):
    assert {tool.name for tool in await server.list_tools()} == TOOL_NAMES


async def test_every_capability_arrives_with_a_schema_a_model_can_call(server):
    for tool in await server.list_tools():
        assert tool.description, tool.name
        assert tool.input_schema["type"] == "object"
        assert "properties" in tool.input_schema


async def test_required_arguments_are_required(server):
    by_name = {tool.name: tool for tool in await server.list_tools()}
    assert by_name["read_brief"].input_schema["required"] == ["brief"]
    assert by_name["fit_report"].input_schema["required"] == ["simulation_id"]
    assert by_name["journey_status"].input_schema["required"] == ["run_id"]
    assert "sku" in by_name["simulate_product"].input_schema["properties"]


async def test_a_tool_call_measures_a_real_candidate(server):
    payload = _payload(await server.call_tool("simulate_product", {"sku": "SOF-001", "room_width_m": 4.2, "room_depth_m": 3.4}))
    assert payload["attempt"]["sku"] == "SOF-001"
    assert payload["attempt"]["verdict"] == "fits"
    assert payload["evidence"]["has_model"] is True


async def test_a_brief_is_read_over_mcp(server):
    brief = _payload(await server.call_tool("read_brief", {"brief": "extendable oak dining table, 4 x 3 m room, under 1200"}))
    assert brief["category"] == "table"
    assert {"oak", "extendable"} == set(brief["must_haves"])
    assert brief["price_band"] == "$$"


async def test_a_journey_started_over_mcp_is_pollable_over_mcp(server):
    started = _payload(await server.call_tool("start_journey", {"brief": "a linen sofa for a 4.2 x 3.4 room, budget 1200"}))
    assert set(started) == {"run_id", "status", "poll"}
    run = started
    for _ in range(200):
        run = _payload(await server.call_tool("journey_status", {"run_id": started["run_id"]}))
        if run["status"] != "running":
            break
        await asyncio.sleep(0.01)
    assert run["status"] == "done", run
    assert run["decision"]["action"] == "recommend"
    assert {step["kind"] for step in run["steps"]} >= {"intake", "agent", "brief", "shortlist", "simulate", "fit", "compare", "reply"}


async def test_an_unknown_run_is_told_to_the_model_in_words(server):
    try:
        result = await server.call_tool("journey_status", {"run_id": _new_run_id()})
        assert result.is_error
        assert "unknown run" in str(result.content)
    except Exception as exc:  # the SDK raises an anticipated tool failure at this level
        assert "unknown run" in str(exc)


async def test_the_http_endpoint_answers_initialize(server, settings):
    app = http_app(server, settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://agent-service") as client:
            response = await client.post("/", json=_envelope("initialize", INITIALIZE), headers=HEADERS)
    assert response.status_code == 200, response.text
    payload = _jsonrpc(response.text)
    assert payload["result"]["serverInfo"]["name"] == "buy-you-before"
    assert "tools" in payload["result"]["capabilities"]


async def test_the_tools_are_listed_over_the_wire(server, settings):
    app = http_app(server, settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://agent-service") as client:
            response = await client.post("/", json=_envelope("tools/list", {}), headers=HEADERS)
    assert response.status_code == 200, response.text
    assert {tool["name"] for tool in _jsonrpc(response.text)["result"]["tools"]} == TOOL_NAMES


async def test_a_tunnel_host_is_accepted_and_another_origin_is_not(settings):
    settings.public_base_url = "https://byb-tunnel.example.com"
    app = http_app(build_server(Tools(StubPipeline([]), StubEvolus(), StubModel(), RunStore(), settings)), settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="https://byb-tunnel.example.com") as client:
            accepted = await client.post("/", json=_envelope("initialize", INITIALIZE), headers={**HEADERS, "origin": "https://byb-tunnel.example.com"})
            refused = await client.post("/", json=_envelope("initialize", INITIALIZE), headers={**HEADERS, "origin": "https://somewhere-else.test"})
    assert accepted.status_code == 200, accepted.text
    assert refused.status_code == 403, "a foreign Origin is refused, not served"


def _payload(result) -> dict:
    """The same JSON the model is handed, whichever way the SDK carried it."""
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(result.content[0].text)


def _envelope(method: str, params: dict) -> dict:
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}


def _jsonrpc(text: str) -> dict:
    """The endpoint answers with a body or an SSE frame, depending on the Accept header."""
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return json.loads(text)
