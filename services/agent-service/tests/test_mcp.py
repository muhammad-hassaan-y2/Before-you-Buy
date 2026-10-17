"""The MCP connector: what an Evolus agent sees when it attaches to /mcp.

Same capabilities as REST, reachable over JSON-RPC, with schemas the model can call.
"""

import asyncio
import json

import httpx
import pytest
from conftest import StubEvolus, StubModel, StubPipeline
from httpx import ASGITransport
from mcp.server.elicitation import AcceptedElicitation, DeclinedElicitation
from mcp.server.mcpserver.exceptions import ToolError
from mcp.shared.exceptions import NoBackChannelError

from byb_agent.mcp_server import INSTRUCTIONS, ConsentWords, _ask, build_server, connect, http_app
from byb_agent.runs import Reservations, RunStore
from byb_agent.settings import Settings
from byb_agent.tools import SPEC, Tools, _new_run_id

TOOL_NAMES = {
    "catalog_search",
    "read_brief",
    "simulate_product",
    "fit_report",
    "explain_fit",
    "joint_fit",
    "find_alternatives",
    "fit_catalog",
    "proven_fit_offer",
    "reserve_fit",
    "add_to_cart",
    "view_cart",
    "remove_from_cart",
    "measure_cart",
    "checkout",
    "order_status",
    "returns_estimate",
    "start_journey",
    "journey_status",
}
INITIALIZE = {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "evolus", "version": "test"}}
HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


@pytest.fixture
def server(rows, settings):
    tools = Tools(StubPipeline(rows, verdicts={"default": "fits"}), StubEvolus(), StubModel(), RunStore(), settings, Reservations())
    return build_server(tools, settings)


def _stub(rows, settings=None):
    return Tools(StubPipeline(rows), StubEvolus(), StubModel(), RunStore(), settings or Settings(), Reservations())


def test_the_server_is_named_and_tells_the_agent_what_to_trust(server):
    assert server.name == "buy-you-before"
    assert server.instructions == INSTRUCTIONS
    # Some clients keep only the opening of a server's instructions, so the rules that decide what
    # the model may claim are inside the first 512 characters of them.
    lead = INSTRUCTIONS[:512]
    assert "Never recommend from a listed dimension" in lead
    assert "image_key" in lead
    assert "unproven" in lead
    assert "a yes you" in INSTRUCTIONS


def test_a_public_origin_makes_it_a_connector_a_human_can_recognise(rows):
    """ChatGPT and Claude show this to a person before a single tool is called. A local run with
    no public address names itself and stops there rather than inventing a URL."""
    assert build_server(_stub(rows)).website_url is None
    assert build_server(_stub(rows)).icons is None
    hosted = build_server(_stub(rows), Settings(public_base_url="https://shop.example/"))
    assert hosted.website_url == "https://shop.example"
    assert hosted.title
    assert hosted.icons[0]["src"] == "https://shop.example/favicon.ico"


async def test_every_capability_says_whether_it_only_measures(server):
    """The read-only hint is what lets a client run a measuring tool without stopping the human,
    so it is a claim: a tool that touches stock must never be marked as if it only looked."""
    by_name = {tool.name: tool for tool in await server.list_tools()}
    for name in ("catalog_search", "simulate_product", "fit_catalog", "joint_fit", "start_journey", "returns_estimate", "view_cart", "order_status"):
        assert by_name[name].annotations.read_only_hint is True, name
    for name in ("proven_fit_offer", "reserve_fit", "add_to_cart", "remove_from_cart", "measure_cart", "checkout"):
        assert by_name[name].annotations.read_only_hint is False, name
        assert by_name[name].annotations.destructive_hint is False, name
    assert all(tool.annotations.title for tool in by_name.values())


async def test_the_evidence_is_readable_as_context_as_well_as_callable(server):
    assert [str(resource.uri) for resource in await server.list_resources()] == ["byb://catalog"]
    assert {template.uri_template for template in await server.list_resource_templates()} == {
        "byb://fit/{simulation_id}",
        "byb://run/{run_id}",
        "byb://cart/{cart_id}",
    }
    catalog = json.loads((await server.read_resource("byb://catalog"))[0].content)
    assert {item["sku"] for item in catalog} == {"SOF-001", "SOF-002", "SOF-003", "ARM-001", "BCK-001"}
    fit = json.loads((await server.read_resource("byb://fit/sim0001"))[0].content)
    assert fit["verdict"] == "fits"
    assert (await server.read_resource("byb://fit/sim0001"))[0].mime_type == "application/json"


async def test_a_shopper_can_hand_the_agent_a_starting_point(server):
    assert {prompt.name for prompt in await server.list_prompts()} >= {"fit-my-room", "hold-the-fit"}
    first = (await server.get_prompt("fit-my-room", {"width_m": 3.6, "depth_m": 3.0, "what": "wardrobe"})).messages[0]
    assert first.role == "user"
    assert "3.6 m by 3.0 m" in first.content.text
    assert "fit_catalog" in first.content.text
    hold = (await server.get_prompt("hold-the-fit", {"run_id": "run-1"})).messages[0].content.text
    assert "never a yes you assume" in hold


async def test_the_agent_is_offered_the_same_capabilities_as_rest(server):
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
    assert by_name["explain_fit"].input_schema["required"] == ["simulation_id"]
    # A client that can ask the shopper directly does not need the agent to carry words at all.
    assert by_name["reserve_fit"].input_schema["required"] == ["simulation_id"]
    assert "confirmation" in by_name["reserve_fit"].input_schema["properties"]
    assert by_name["joint_fit"].input_schema["required"] == ["skus"]
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


async def test_a_photographed_room_is_an_argument_the_agent_can_pass(server):
    by_name = {tool.name: tool for tool in await server.list_tools()}
    for name in ("simulate_product", "joint_fit", "find_alternatives", "start_journey"):
        assert "image_key" in by_name[name].input_schema["properties"], name

    photo = "ef" * 16 + "-living-room.jpg"
    started = _payload(await server.call_tool("start_journey", {"brief": "a linen sofa for the room in my photo", "image_key": photo}))
    run = started
    for _ in range(200):
        run = _payload(await server.call_tool("journey_status", {"run_id": started["run_id"]}))
        if run["status"] != "running":
            break
        await asyncio.sleep(0.01)
    assert "room" in {step["kind"] for step in run["steps"]}, "the trace must show the photo measured the room"


async def test_two_pieces_are_judged_as_one_purchase_over_mcp(server):
    joint = _payload(await server.call_tool("joint_fit", {"skus": ["SOF-001", "ARM-001"], "room_width_m": 4.2, "room_depth_m": 3.4}))
    assert joint["tested"] == ["SOF-001", "ARM-001"]
    assert joint["combined"]["verdict"] == "fits"
    assert joint["combined"]["footprint_m2"] > 0


async def test_an_offer_and_a_hold_share_the_same_gate_over_mcp(server):
    measured = _payload(await server.call_tool("simulate_product", {"sku": "SOF-002"}))
    simulation_id = measured["attempt"]["simulation_id"]

    offer = _payload(await server.call_tool("proven_fit_offer", {"simulation_id": simulation_id}))
    assert offer["offer"]["sku"] == "SOF-002"
    assert offer["fit_evidence"]["verdict"] == "fits"

    refused = await _expect_error(server.call_tool("reserve_fit", {"simulation_id": simulation_id, "confirmation": "i think so"}))
    assert "shopper's own yes" in refused
    held = _payload(await server.call_tool("reserve_fit", {"simulation_id": simulation_id, "confirmation": "yes"}))
    assert held["status"] == "pending_merchant"
    assert held["confirmation"] == "yes"


class _Client:
    """A context that stands in for a client which can, or cannot, show the shopper a question."""

    def __init__(self, result=None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.asked: list[str] = []

    async def elicit(self, message, schema):
        self.asked.append(message)
        if self._error is not None:
            raise self._error
        return self._result


async def test_the_shopper_is_asked_in_their_own_client_when_the_client_can_ask():
    """A hold and an order cost the merchant stock, so an elicitation-capable client is asked to put
    the question to the human, and the words that come back are the gate's input."""
    client = _Client(AcceptedElicitation(data=ConsentWords(confirmation="yes, hold it for me")))
    words, through = await _ask(client, "Shall I hold the piece from sim0001?", "reserved", "the agent swears they said yes")
    assert words == "yes, hold it for me"
    assert through == "asked in the client"
    assert "sim0001" in client.asked[0]


async def test_a_shopper_who_declines_in_the_client_gets_no_hold():
    with pytest.raises(ToolError, match="declined"):
        await _ask(_Client(DeclinedElicitation()), "Shall I place this order?", "ordered", "yes")


@pytest.mark.parametrize("error", [NoBackChannelError("elicitation/create"), ValueError("not in a request"), RuntimeError("closed")])
async def test_a_client_that_cannot_ask_falls_back_to_the_words_the_agent_relayed(error):
    """The gate cannot depend on a client feature ChatGPT or an older Claude may not have: when the
    question cannot be put, the shopper's relayed words are still checked, not trusted."""
    words, through = await _ask(_Client(error=error), "Shall I hold it?", "reserved", "yes hold it")
    assert (words, through) == ("yes hold it", "relayed by the agent")


async def test_a_stateless_connector_still_refuses_a_hold_it_cannot_ask_about(server, settings):
    """Stateless JSON has no back-channel, so an agent that calls reserve_fit without the
    shopper's words must be refused rather than left to guess them."""
    measured = _payload(await server.call_tool("simulate_product", {"sku": "SOF-002"}))
    refused = await _expect_error(server.call_tool("reserve_fit", {"simulation_id": measured["attempt"]["simulation_id"]}))
    assert "shopper's own yes" in refused


async def test_a_bag_can_be_filled_measured_and_bought_over_mcp(server):
    """The whole purchase, through the door an shopper's ChatGPT or Claude actually uses: a piece the
    engine cleared goes in the bag, the bag is judged as one purchase, and the order is a draft."""
    measured = _payload(await server.call_tool("simulate_product", {"sku": "SOF-002"}))
    bag = _payload(
        await server.call_tool("add_to_cart", {"sku": "SOF-002", "simulation_id": measured["attempt"]["simulation_id"]})
    )
    assert bag["lines"][0]["verdict"] == "fits"
    assert bag["checkout"]["ready"] is True

    swept = _payload(await server.call_tool("measure_cart", {"cart_id": bag["cart_id"]}))
    assert swept["measured"] == [], "a line already proved for this room is not measured twice"
    assert swept["set"]["verdict"] == "fits"

    refused = await _expect_error(server.call_tool("checkout", {"cart_id": bag["cart_id"]}))
    assert "shopper's own yes" in refused
    placed = _payload(await server.call_tool("checkout", {"cart_id": bag["cart_id"], "confirmation": "yes, place it"}))
    assert placed["status"] == "awaiting_merchant"
    assert placed["confirmation"] == "yes, place it"
    assert placed["confirmed_through"] == "relayed by the agent"
    order = _payload(await server.call_tool("order_status", {"order_id": placed["id"]}))
    assert order["proofs"][0]["simulation_id"] == measured["attempt"]["simulation_id"]


async def test_an_unmeasured_bag_is_not_sellable_over_mcp(server):
    bag = _payload(await server.call_tool("add_to_cart", {"sku": "SOF-002"}))
    assert bag["unproven"] == ["SOF-002"]
    refused = await _expect_error(server.call_tool("checkout", {"cart_id": bag["cart_id"], "confirmation": "yes"}))
    assert "nothing is sold unchecked" in refused


async def test_the_bag_is_readable_as_context_as_well_as_callable(server):
    bag = _payload(await server.call_tool("add_to_cart", {"sku": "ARM-001", "room_width_m": 3.0}))
    attached = json.loads((await server.read_resource(f"byb://cart/{bag['cart_id']}"))[0].content)
    assert [line["sku"] for line in attached["lines"]] == ["ARM-001"]
    assert attached["room"]["width_m"] == 3.0


async def test_a_shopper_can_hand_the_agent_the_whole_purchase(server):
    filled = (await server.get_prompt("fill-a-cart", {"width_m": 3.6, "depth_m": 3.0, "what": "sofa"})).messages[0].content.text
    assert "add_to_cart" in filled and "measure_cart" in filled and "checkout" in filled
    assert "my own words" in filled, "the prompt has to keep the yes on the shopper, not the model"


async def test_the_business_math_is_a_tool_the_agent_can_quote(server):
    figures = _payload(await server.call_tool("returns_estimate", {"orders_per_month": 500, "price_band": "$$$"}))
    assert figures["returns_prevented_per_month"] == 16.8
    assert figures["assumptions"]["average_order_value_eur"] == 1500.0


async def test_an_unknown_run_is_told_to_the_model_in_words(server):
    refused = await _expect_error(server.call_tool("journey_status", {"run_id": _new_run_id()}))
    assert "unknown run" in refused


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


async def test_the_wire_carries_the_hints_and_the_context(server, settings):
    """A client decides whether to ask the human for permission from what `tools/list` says, and
    fills its @-menu from `resources/list`, so both have to survive the HTTP transport."""
    app = http_app(server, settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://agent-service") as client:
            tools = _jsonrpc((await client.post("/", json=_envelope("tools/list", {}), headers=HEADERS)).text)["result"]["tools"]
            resources = _jsonrpc((await client.post("/", json=_envelope("resources/list", {}), headers=HEADERS)).text)["result"]["resources"]
            prompts = _jsonrpc((await client.post("/", json=_envelope("prompts/list", {}), headers=HEADERS)).text)["result"]["prompts"]
    by_name = {tool["name"]: tool for tool in tools}
    assert by_name["reserve_fit"]["annotations"]["readOnlyHint"] is False
    assert by_name["fit_catalog"]["annotations"]["readOnlyHint"] is True
    assert [resource["uri"] for resource in resources] == ["byb://catalog"]
    assert {"fit-my-room", "hold-the-fit"} <= {prompt["name"] for prompt in prompts}


async def test_a_keyed_connector_refuses_an_agent_that_cannot_produce_it(rows, settings):
    """A connector is a public door onto a GPU. A key is what stops anyone's ChatGPT from
    spending the merchant's credits, and it is only ever asked for when the shop sets one."""
    settings.mcp_connect_token = "shop-key"
    app = http_app(build_server(_stub(rows, settings), settings), settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://agent-service") as client:
            bare = await client.post("/", json=_envelope("tools/list", {}), headers=HEADERS)
            keyed = await client.post("/", json=_envelope("tools/list", {}), headers={**HEADERS, "authorization": "Bearer shop-key"})
    assert bare.status_code == 401
    assert "WWW-Authenticate" in bare.headers and bare.headers["www-authenticate"].startswith("Bearer")
    assert keyed.status_code == 200, keyed.text
    assert _jsonrpc(keyed.text)["result"]["tools"]


async def test_a_tunnel_host_is_accepted_and_another_origin_is_not(settings):
    settings.public_base_url = "https://byb-tunnel.example.com"
    app = http_app(build_server(Tools(StubPipeline([]), StubEvolus(), StubModel(), RunStore(), settings)), settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="https://byb-tunnel.example.com") as client:
            accepted = await client.post("/", json=_envelope("initialize", INITIALIZE), headers={**HEADERS, "origin": "https://byb-tunnel.example.com"})
            refused = await client.post("/", json=_envelope("initialize", INITIALIZE), headers={**HEADERS, "origin": "https://somewhere-else.test"})
    assert accepted.status_code == 200, accepted.text
    assert refused.status_code == 403, "a foreign Origin is refused, not served"


async def test_a_session_connector_keeps_a_conversation(rows, settings):
    """Sessions are the mode a client needs in order to answer a question while a tool runs, and
    they cost a standing conversation per client, so the switch has to be real in both directions."""
    settings.mcp_sessions = True
    app = http_app(build_server(_stub(rows, settings), settings), settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://agent-service") as client:
            opened = await client.post("/", json=_envelope("initialize", INITIALIZE), headers=HEADERS)
            session = opened.headers.get("mcp-session-id")
            await client.post("/", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers={**HEADERS, "mcp-session-id": session or ""})
            listed = await client.post("/", json=_envelope("tools/list", {}), headers={**HEADERS, "mcp-session-id": session or ""})
    assert session, "a session app hands back the id the client has to keep"
    assert listed.status_code == 200, listed.text
    assert {tool["name"] for tool in _jsonrpc(listed.text)["result"]["tools"]} == TOOL_NAMES


def test_the_install_guide_tells_each_client_how_to_add_the_connector(settings):
    settings.public_base_url = "https://byb-tunnel.example.com"
    guide = connect(settings)
    assert guide["url"] == "https://byb-tunnel.example.com/mcp/"
    assert guide["public"] is True and guide["transport"] == "streamable-http"
    assert set(guide["clients"]) == {"chatgpt", "claude", "claude-code", "cursor", "evolus"}
    assert guide["auth"]["type"] == "none"
    assert guide["capabilities"]["tools"] == sorted(SPEC)
    assert guide["capabilities"]["prompts"] == ["fit-my-room", "hold-the-fit", "fill-a-cart"]
    assert "byb://cart/{cart_id}" in guide["capabilities"]["resources"]
    assert "Add custom MCP server" in " ".join(guide["clients"]["chatgpt"]["steps"])
    assert "Add custom connector" in " ".join(guide["clients"]["claude"]["steps"])
    # Buying is now a thing a person can do through this connector, so both app doors say so.
    assert any("check out" in step for step in guide["clients"]["chatgpt"]["steps"])
    assert any("check out" in step for step in guide["clients"]["claude"]["steps"])
    assert "checkout" in guide["clients"]["chatgpt"]["note"]
    assert guide["clients"]["claude-code"]["command"].startswith("claude mcp add --transport http")
    # Asking a shopper a question mid-tool is only possible over a session, and that is opt-in.
    assert guide["elicitation"] is False


def test_a_keyed_guide_says_where_a_key_works_and_where_it_does_not(settings):
    """ChatGPT cannot be given a static header, so a keyed connector is a Claude Code and Cursor
    connector. A guide that hid that would send a shopper down a door that never opens."""
    settings.mcp_connect_token = "shop-key"
    guide = connect(settings)
    assert guide["auth"]["type"] == "bearer"
    assert "chatgpt" in guide["auth"]["does_not_work_in"]
    assert "--header" in guide["clients"]["claude-code"]["command"]
    assert guide["clients"]["cursor"]["config"]["mcpServers"]["buy-you-before"]["headers"]["Authorization"]


def test_a_local_guide_admits_it_has_no_url_to_give(settings):
    guide = connect(settings)
    assert guide["public"] is False
    assert guide["url"] == "/mcp/"
    assert "PUBLIC_BASE_URL" in " ".join(guide["clients"]["chatgpt"]["steps"])


async def _expect_error(call) -> str:
    """The words a refused tool call puts in front of the model, whichever way the SDK carried it."""
    try:
        result = await call
    except Exception as exc:  # the SDK raises an anticipated tool failure at this level
        return str(exc)
    assert result.is_error, "the tool answered instead of refusing"
    return str(result.content)


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
