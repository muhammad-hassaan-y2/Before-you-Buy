"""The custom MCP server.

Evolus registers this as an MCP connector; Claude, ChatGPT, Cursor or Evolus Studio can use the
same URL. It is the agency layer: the model on AMD decides, these tools do the measuring.

The tool bodies live in `tools.py` and are the ones the REST surface calls, so an agent and a
workflow step cannot get different answers. The descriptions come from the same `SPEC` table the
REST door publishes for the same reason.
"""

from __future__ import annotations

import json
import logging
import secrets
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.context import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from pydantic import BaseModel, Field

from byb_agent.settings import Settings
from byb_agent.tools import SPEC, Tools

logger = logging.getLogger("byb.mcp")

# Some clients keep only the start of a server's instructions, so the four rules that change what
# a model does - measure, use the photo, distrust an unproven piece, ask before a hold or an order
# - are said first and in as few words as they can be said. The tour of the tools follows the rules.
INSTRUCTIONS = (
    "Buy You Before measures furniture against a real room before it is bought. Four rules: "
    "(1) Never recommend from a listed dimension - run simulate_product, joint_fit or fit_catalog "
    "and quote the verdict fit_report or explain_fit returns. (2) If the shopper sent a photo of "
    "the room, pass the image_key the gateway returned for it, so the room measured from the photo "
    "is used instead of typed numbers. (3) A piece the pipeline did not settle is unproven, not a "
    "fit. (4) Ask the shopper before a hold or an order: reserve_fit and checkout take their own "
    "words, and a yes you assumed for them is refused. "
    "read_brief turns a brief into a category, a price band and a room; catalog_search finds "
    "pieces; fit_catalog answers 'which of your sofas fit me' by measuring a slice of the catalog "
    "at once and splitting it into fits, non-fits and unproven; joint_fit judges several pieces as "
    "one purchase; find_alternatives looks for no-wider pieces; add_to_cart bags a piece with the "
    "proof it came from, measure_cart measures the bag against its room and judges the pieces as "
    "one purchase, and checkout writes a draft only when every line cleared; start_journey runs "
    "the whole search behind a brief and journey_status reads its trace. proven_fit_offer backs an "
    "offer only with a fit the engine proved. Report the verdict, the floor coverage and the "
    "tightest walkway, and hand the case to a person when the decision is handoff."
)

# A client asks the human before running a tool it does not trust, and `readOnlyHint` is how it
# knows it can skip that. Reading a bag cannot hurt anything; adding to it, measuring it (a GPU job
# the merchant pays for) and ordering from it all deserve the question.
_MEASURE = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
_ACT = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}


def build_server(tools: Tools, settings: Settings | None = None) -> MCPServer:
    """The server an agent attaches to.

    Named, described and iconed because a connector is shown to a human - in ChatGPT's and
    Claude's connector lists - long before any of its tools is called.
    """
    base = settings.public_base_url.rstrip("/") if settings and settings.public_base_url else ""
    server = MCPServer(
        "buy-you-before",
        title="Buy You Before fit assurance",
        description="Measures furniture against a real room before it is bought, and holds a proven fit only on a human's own yes.",
        instructions=INSTRUCTIONS,
        website_url=base or None,
        icons=[{"src": f"{base}/favicon.ico", "sizes": ["48x48"], "mimeType": "image/vnd.microsoft.icon"}] if base else None,
    )
    register(server, tools)
    publish(server, tools)
    return server


def register(server: MCPServer, tools: Tools) -> None:
    def tool(name: str, title: str, *, acts: bool = False, fetching: bool = False) -> Callable:
        hints = dict(_ACT if acts else _MEASURE)
        hints["title"] = title
        if fetching:
            hints["openWorldHint"] = True
        return server.tool(name=name, title=title, description=SPEC[name], annotations=hints)

    @tool("catalog_search", "Search the shop's catalog")
    async def catalog_search(query: str = "", category: str | None = None, price_band: str | None = None, limit: int = 5) -> dict[str, Any]:
        return {"candidates": await _answer(tools.catalog_search, query=query, category=category, price_band=price_band, limit=limit)}

    @tool("read_brief", "Read the shopper's words")
    async def read_brief(brief: str) -> dict[str, Any]:
        return await _answer(tools.read_brief, brief=brief)

    @tool("simulate_product", "Measure one product in one room", fetching=True)
    async def simulate_product(
        room_width_m: float = 4.0,
        room_depth_m: float = 3.5,
        room_height_m: float = 2.4,
        sku: str | None = None,
        link: str | None = None,
        notes: str = "",
        image_key: str | None = None,
    ) -> dict[str, Any]:
        room = {"room_width_m": room_width_m, "room_depth_m": room_depth_m, "room_height_m": room_height_m}
        return await _answer(tools.simulate_product, link=link, sku=sku, notes=notes, image_key=image_key, **room)

    @tool("fit_report", "Read a fit report")
    async def fit_report(simulation_id: str) -> dict[str, Any]:
        return await _answer(tools.fit_report, simulation_id=simulation_id)

    @tool("explain_fit", "Explain a verdict in words")
    async def explain_fit(simulation_id: str) -> dict[str, Any]:
        return await _answer(tools.explain_fit, simulation_id=simulation_id)

    @tool("joint_fit", "Judge several pieces as one purchase", fetching=True)
    async def joint_fit(
        skus: list[str],
        room_width_m: float = 4.0,
        room_depth_m: float = 3.5,
        room_height_m: float = 2.4,
        notes: str = "",
        image_key: str | None = None,
    ) -> dict[str, Any]:
        return await _answer(
            tools.joint_fit,
            skus=skus,
            notes=notes,
            room_width_m=room_width_m,
            room_depth_m=room_depth_m,
            room_height_m=room_height_m,
            image_key=image_key,
        )

    @tool("find_alternatives", "Find pieces that might fit instead", fetching=True)
    async def find_alternatives(
        room_width_m: float = 4.0,
        room_depth_m: float = 3.5,
        room_height_m: float = 2.4,
        sku: str | None = None,
        link: str | None = None,
        notes: str = "",
        limit: int = 3,
        image_key: str | None = None,
    ) -> dict[str, Any]:
        room = {"room_width_m": room_width_m, "room_depth_m": room_depth_m, "room_height_m": room_height_m}
        found = await _answer(
            tools.find_alternatives, sku=sku, link=link, notes=notes, limit=limit, image_key=image_key, **room
        )
        return {"alternatives": found}

    @tool("fit_catalog", "Which of the catalog fits this room", fetching=True)
    async def fit_catalog(
        room_width_m: float = 4.0,
        room_depth_m: float = 3.5,
        room_height_m: float = 2.4,
        category: str | None = None,
        price_band: str | None = None,
        query: str = "",
        limit: int = 6,
        image_key: str | None = None,
    ) -> dict[str, Any]:
        return await _answer(
            tools.fit_catalog,
            category=category,
            price_band=price_band,
            query=query,
            room_width_m=room_width_m,
            room_depth_m=room_depth_m,
            room_height_m=room_height_m,
            limit=limit,
            image_key=image_key,
        )

    @tool("start_journey", "Run the whole fit search")
    async def start_journey(
        brief: str,
        room_width_m: float | None = None,
        room_depth_m: float | None = None,
        room_height_m: float | None = None,
        image_key: str | None = None,
    ) -> dict[str, Any]:
        return await _answer(
            tools.start_journey,
            brief=brief,
            room_width_m=room_width_m,
            room_depth_m=room_depth_m,
            room_height_m=room_height_m,
            image_key=image_key,
        )

    @tool("journey_status", "Read a journey's trace")
    async def journey_status(run_id: str) -> dict[str, Any]:
        return await _answer(tools.journey_status, run_id=run_id)

    @tool("returns_estimate", "Price the fit check")
    async def returns_estimate(
        orders_per_month: float = 1000,
        price_band: str | None = None,
        price_eur: float | None = None,
        return_rate: float | None = None,
        fit_share: float | None = None,
        prevention: float | None = None,
    ) -> dict[str, Any]:
        return await _answer(
            tools.returns_estimate,
            orders_per_month=orders_per_month,
            price_band=price_band,
            price_eur=price_eur,
            return_rate=return_rate,
            fit_share=fit_share,
            prevention=prevention,
        )

    @tool("proven_fit_offer", "Put a proven fit on the table", acts=True)
    async def proven_fit_offer(simulation_id: str) -> dict[str, Any]:
        return await _answer(tools.proven_fit_offer, simulation_id=simulation_id)

    @tool("reserve_fit", "Hold a proven fit for the shopper", acts=True)
    async def reserve_fit(simulation_id: str, confirmation: str = "", ctx: Context | None = None) -> dict[str, Any]:
        words, through = await _ask(
            ctx,
            f"Shall I hold the piece from simulation {simulation_id} for you until someone at the shop "
            "confirms it? Nothing is charged and nothing ships.",
            "reserved",
            confirmation,
        )
        held = await _answer(tools.reserve_fit, simulation_id=simulation_id, confirmation=words)
        return {"confirmed_through": through, **held}

    @tool("add_to_cart", "Put a piece in the bag", acts=True)
    async def add_to_cart(
        sku: str | None = None,
        link: str | None = None,
        cart_id: str | None = None,
        quantity: int = 1,
        simulation_id: str | None = None,
        room_width_m: float | None = None,
        room_depth_m: float | None = None,
        room_height_m: float | None = None,
    ) -> dict[str, Any]:
        return await _answer(
            tools.add_to_cart,
            sku=sku,
            link=link,
            cart_id=cart_id,
            quantity=quantity,
            simulation_id=simulation_id,
            room_width_m=room_width_m,
            room_depth_m=room_depth_m,
            room_height_m=room_height_m,
        )

    @tool("view_cart", "Read the bag")
    async def view_cart(cart_id: str) -> dict[str, Any]:
        return await _answer(tools.view_cart, cart_id=cart_id)

    @tool("remove_from_cart", "Take a piece out of the bag", acts=True)
    async def remove_from_cart(cart_id: str, sku: str) -> dict[str, Any]:
        return await _answer(tools.remove_from_cart, cart_id=cart_id, sku=sku)

    @tool("measure_cart", "Measure the bag as one purchase", acts=True, fetching=True)
    async def measure_cart(
        cart_id: str,
        room_width_m: float | None = None,
        room_depth_m: float | None = None,
        room_height_m: float | None = None,
        image_key: str | None = None,
    ) -> dict[str, Any]:
        return await _answer(
            tools.measure_cart,
            cart_id=cart_id,
            room_width_m=room_width_m,
            room_depth_m=room_depth_m,
            room_height_m=room_height_m,
            image_key=image_key,
        )

    @tool("order_status", "Read an order draft")
    async def order_status(order_id: str) -> dict[str, Any]:
        return await _answer(tools.order_status, order_id=order_id)

    @tool("checkout", "Place the order draft", acts=True)
    async def checkout(cart_id: str, confirmation: str = "", ctx: Context | None = None) -> dict[str, Any]:
        """Ask the shopper about an order they can see, not one the agent described.

        The bag is read first because a consent line naming no pieces and no number is not
        consent, and `Tools.checkout` then refuses anything the engine has not cleared.
        """
        bag = await _answer(tools.view_cart, cart_id=cart_id)
        names = ", ".join(f"{line['name']} x{line['quantity']}" for line in bag["lines"]) or "nothing yet"
        words, through = await _ask(
            ctx,
            f"Shall I place this order for {names} - EUR {bag['total_eur']} for {bag['items']} "
            f"piece(s), about {bag['lead_days']} days by {bag['freight']} freight? No card is taken: "
            "a person at the shop confirms the draft.",
            "ordered",
            confirmation,
        )
        placed = await _answer(tools.checkout, cart_id=cart_id, confirmation=words)
        return {"confirmed_through": through, **placed}


class ConsentWords(BaseModel):
    """One flat string, because an elicitation form only carries primitives: the client renders it
    as a field, not as a nested editor."""

    confirmation: str = Field(description="Your own words, kept verbatim so the shop can audit the decision. For example: yes, go ahead.")


# A client that is not agreeing says so with one of these words, and the shopper's answer belongs
# in the refusal in their own language rather than as a stem with "ed" glued on.
_ANSWERS = {"decline": "declined", "cancel": "cancelled"}


async def _ask(ctx: Context | None, question: str, past: str, relayed: str) -> tuple[str, str]:
    """Put the question in front of the shopper themselves whenever the client can.

    Elicitation is the difference between a human's yes and a model's guess of one, so it is
    tried first and its answer wins over whatever the agent relays. A client that cannot answer
    - no back-channel, no elicitation capability, or a decline we should not misread - falls back
    to the shopper's words as the agent heard them, and the tool behind this door still refuses a
    hold or an order that is not an explicit yes.
    """
    if ctx is not None:
        try:
            result = await ctx.elicit(question, ConsentWords)
        except (MCPError, ValueError, RuntimeError) as exc:
            logger.debug("client cannot ask the shopper (%s), using the words the agent relayed", type(exc).__name__)
        else:
            if result.action != "accept":
                said = _ANSWERS.get(result.action, str(result.action))
                raise ToolError(f"the shopper {said} the question, so nothing was {past}.")
            return result.data.confirmation, "asked in the client"
    return relayed, "relayed by the agent"


def publish(server: MCPServer, tools: Tools) -> None:
    """The same evidence, readable as context rather than callable as a tool.

    A shopper can attach the catalog or one run's fit report to a conversation in Claude, so the
    agent quotes the file the engine wrote instead of quoting a tool call it already made.
    """

    @server.resource(
        "byb://catalog",
        name="catalog",
        title="The shop's catalog",
        description="Every piece the agent may shortlist from, with its box size.",
        mime_type="application/json",
    )
    async def catalog() -> str:
        return json.dumps(await tools.catalog_search(limit=100), indent=2)

    @server.resource(
        "byb://fit/{simulation_id}",
        name="fit",
        title="One fit report",
        description="The verdict the geometry engine gave for one simulation.",
        mime_type="application/json",
    )
    async def fit(simulation_id: str) -> str:
        return json.dumps(await _answer(tools.explain_fit, simulation_id=simulation_id), indent=2)

    @server.resource(
        "byb://run/{run_id}",
        name="run",
        title="One journey trace",
        description="Every step a fit search took, with the tool and the milliseconds behind each.",
        mime_type="application/json",
    )
    async def run(run_id: str) -> str:
        return json.dumps(await _answer(tools.journey_status, run_id=run_id), indent=2)

    @server.resource(
        "byb://cart/{cart_id}",
        name="cart",
        title="One shopping bag",
        description="The bag, its room, every line's price and the fit verdict behind it.",
        mime_type="application/json",
    )
    async def cart(cart_id: str) -> str:
        return json.dumps(await _answer(tools.view_cart, cart_id=cart_id), indent=2)

    @server.prompt(name="fit-my-room", title="Fit my room", description="Work out what of this shop fits a room the shopper describes.")
    async def fit_my_room(width_m: float = 4.0, depth_m: float = 3.5, what: str = "sofa") -> list[dict[str, str]]:
        return [
            {
                "role": "user",
                "content": (
                    f"My room is {width_m} m by {depth_m} m. Use fit_catalog to measure which {what} in this "
                    "shop actually fit it, then for each one tell me the verdict, how much floor it takes and "
                    "the tightest walkway it leaves. Do not recommend a piece the engine did not measure."
                ),
            }
        ]

    @server.prompt(name="hold-the-fit", title="Hold the one that fits", description="Turn the best proven fit into a hold a person at the shop confirms.")
    async def hold_the_fit(run_id: str) -> list[dict[str, str]]:
        return [
            {
                "role": "user",
                "content": (
                    f"Read journey {run_id} with journey_status. If it ended in a proven fit, raise a "
                    "proven_fit_offer for it and then ask me plainly whether to hold that piece - my own "
                    "answer is what reserve_fit needs, never a yes you assume for me."
                ),
            }
        ]

    @server.prompt(name="fill-a-cart", title="Fill a cart with what fits", description="Buy the pieces the engine cleared, checking out on my own yes.")
    async def fill_a_cart(width_m: float = 4.0, depth_m: float = 3.5, what: str = "sofa") -> list[dict[str, str]]:
        return [
            {
                "role": "user",
                "content": (
                    f"My room is {width_m} m by {depth_m} m. Run fit_catalog for {what} in it, add the pieces that "
                    "cleared to one cart with add_to_cart - pass each simulation_id so the bag carries its proof - "
                    "then call measure_cart to judge the set as one purchase and tell me the combined verdict and "
                    "total. Ask me plainly whether to place the order: checkout takes my own words, never a yes you "
                    "assume for me, and nothing the engine did not clear goes in the bag."
                ),
            }
        ]


RESOURCES = ("byb://catalog", "byb://fit/{simulation_id}", "byb://run/{run_id}", "byb://cart/{cart_id}")
PROMPTS = ("fit-my-room", "hold-the-fit", "fill-a-cart")


def connect(settings: Settings) -> dict[str, Any]:
    """How to add this connector, in the words a person in ChatGPT or Claude needs.

    Served as JSON because the honest answer differs per client: ChatGPT takes an unauthenticated
    or OAuth URL and no static key, Claude Code and Cursor take a header, and none of them can
    reach a laptop behind a `localhost` URL.
    """
    base = settings.public_base_url.rstrip("/")
    url = f"{base}/mcp/" if base else "/mcp/"
    keyed = bool(settings.mcp_connect_token)
    auth = (
        {
            "type": "bearer",
            "header": "Authorization: Bearer <MCP_CONNECT_TOKEN>",
            "works_in": ["claude-code", "cursor", "evolus"],
            "does_not_work_in": ["chatgpt", "claude.ai"],
            "why": "ChatGPT and Claude's web app add a connector with no auth or with OAuth 2.1; a "
                   "static key is only offered by Claude Code and Cursor.",
        }
        if keyed
        else {
            "type": "none",
            "header": None,
            "works_in": ["chatgpt", "claude.ai", "claude-code", "cursor", "evolus"],
            "does_not_work_in": [],
            "why": "Anyone with the URL can spend the shop's GPU jobs, so this is a demo setting. "
                   "Set MCP_CONNECT_TOKEN for a key, or put OAuth in front for a live shop.",
        }
    )
    clients: dict[str, Any] = {
        "chatgpt": {
            "label": "ChatGPT (web)",
            "requires_https": True,
            "steps": [
                "Set PUBLIC_BASE_URL to the https tunnel URL and restart agent-service.",
                "Turn on Developer mode: Settings -> Security, or Workspace settings -> "
                "Permissions & roles if your account has a workspace. Reload the tab.",
                "Open the Apps directory -> Advanced -> Add custom MCP server.",
                "Name it Buy You Before and paste the URL below - the shop's own origin, /mcp/.",
                "Leave authentication on No authentication, or on OAuth if the shop put OAuth in front.",
                "Create it, then @-mention Buy You Before in a chat and give it a room to measure.",
                "Finish the purchase in the same chat: ask it to add what cleared to a cart, measure the "
                "bag and check out - an order is refused until every line carries a cleared verdict.",
            ],
            "note": "ChatGPT reaches the connector through the shop's own origin, so one https tunnel "
                    "is enough; it will not accept a static bearer header, so this door only opens "
                    "while MCP_CONNECT_TOKEN is empty or the shop speaks OAuth. The demo is a whole "
                    "purchase: it calls fit_catalog, adds what cleared to a cart, measures the bag and "
                    "comes back to the shopper for the yes before checkout - ChatGPT shows that question "
                    "as its own confirmation card, since a stateless door has no back-channel to ask on.",
        },
        "claude": {
            "label": "Claude (claude.ai)",
            "requires_https": True,
            "steps": [
                "Open Customize -> Connectors, or Settings -> Connectors on the desktop app.",
                "Click + and choose Add custom connector.",
                "Name it Buy You Before and paste the URL below - the shop's own origin, /mcp/.",
                "Connect it as-is, or set an OAuth Client ID under Advanced settings when the shop "
                "speaks OAuth; Claude takes no typed key the way Claude Code does.",
                "Switch the connector on inside the chat, then ask it which sofas fit the room.",
                "Ask it to add the ones that cleared to a cart and check out: an order is only written "
                "once every line in the bag has a verdict the engine actually gave.",
            ],
            "note": "claude.ai adds a connector unauthenticated or through OAuth; it cannot send a "
                    "header you typed. Keys belong to Claude Code below. On a Team or Enterprise "
                    "workspace an admin may have to allow custom connectors first.",
        },
        "claude-code": {
            "label": "Claude Code",
            "requires_https": False,
            "command": " ".join(
                [
                    "claude mcp add --transport http buy-you-before",
                    url if base else "https://<tunnel>.trycloudflare.com/mcp/",
                    '--header "Authorization: Bearer <MCP_CONNECT_TOKEN>"' if keyed else "",
                ]
            ).replace("  ", " ").strip(),
            "steps": [
                "Run the command below, or add the same block to ~/.claude.json.",
                "Type /mcp to confirm it connected, then /-mention the fit-my-room prompt.",
            ],
            "note": "Claude Code is where the resources and prompts on this connector show up: "
                    "@byb://catalog attaches the shop's catalog as context and @byb://cart/<id> the bag "
                    "it is holding, so a terminal conversation quotes the same file the page does.",
        },
        "cursor": {
            "label": "Cursor",
            "requires_https": False,
            "config": {
                "mcpServers": {
                    "buy-you-before": {"url": url, "headers": {"Authorization": "Bearer <MCP_CONNECT_TOKEN>"}}
                    if keyed
                    else {"url": url}
                }
            },
            "steps": [
                "Put the config below in .cursor/mcp.json, or in Settings -> MCP Servers -> Add.",
                "Press the refresh icon until the tools list appears.",
            ],
        },
        "evolus": {
            "label": "Evolus Studio",
            "requires_https": True,
            "steps": [
                "In the Evolus workspace, add an MCP connector and paste the URL below.",
                f"Point the agent at it, then check that all {len(SPEC)} tools are listed.",
            ],
            "note": "The agent-service tools surface and this connector call the same functions, so a "
                    "Teams conversation and a ChatGPT conversation get the same verdict.",
        },
    }
    return {
        "name": "buy-you-before",
        "title": "Buy You Before fit assurance",
        "url": url,
        "transport": "streamable-http",
        "public": bool(base),
        "auth": auth,
        "mode": "sessions" if settings.mcp_sessions else "stateless",
        "capabilities": {"tools": sorted(SPEC), "resources": list(RESOURCES), "prompts": list(PROMPTS)},
        "elicitation": settings.mcp_sessions,
        "clients": clients,
        "wiring": {
            "PUBLIC_BASE_URL": "the https origin a client can reach; without it every URL here is relative",
            "MCP_CONNECT_TOKEN": "the bearer key an outside agent must send; empty means open",
            "MCP_SESSIONS": "true gives clients a real session, which is how a hold asks the shopper in their own app",
        },
    }


async def _answer(method: Callable[..., Awaitable[Any]], **arguments: Any) -> Any:
    """A foreseeable failure is told to the model in words; only a real bug is a crash."""
    try:
        return await method(**arguments)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


def http_app(server: MCPServer, settings: Settings) -> Any:
    """The ASGI app to mount at /mcp.

    DNS-rebinding protection is on only when the public origin is known, because a tunnel
    hands the server a Host header it was not configured to expect. A key, when the shop sets
    one, is what keeps a stranger's agent from spending the merchant's GPU credits.

    Stateless JSON is one request per call and no stream to keep open, which is what an Evolus
    connector and a demo tunnel want. Sessions are opt-in because they are what a client needs to
    be able to answer a question mid-tool - see `_ask`.
    """
    security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    if settings.public_base_url:
        origin = settings.public_base_url.split("//", 1)[-1].rstrip("/")
        security = TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=[origin], allowed_origins=[settings.public_base_url])
    app = server.streamable_http_app(
        streamable_http_path="/",
        stateless_http=not settings.mcp_sessions,
        json_response=not settings.mcp_sessions,
        transport_security=security,
        host="0.0.0.0",
    )
    # ChatGPT adds a connector with no auth or with OAuth; a static key is a Claude Code and
    # Cursor thing. So the gate stays off until a shop asks for it.
    if settings.mcp_connect_token:
        app.add_middleware(BearerGate, token=settings.mcp_connect_token)
    return app


class BearerGate:
    """One header check, as ASGI middleware: it wraps the connector without re-implementing it,
    so the session manager's lifespan stays the one the mounted app is started with."""

    def __init__(self, app: Any, *, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        # A preflight carries no credentials by design, so CORS answers it and this does not.
        if scope["type"] == "http" and scope.get("method", "").upper() != "OPTIONS":
            header = next((value.decode() for key, value in scope.get("headers", []) if key == b"authorization"), "")
            supplied = header.split(" ", 1)[1].strip() if header.lower().startswith("bearer ") else ""
            if not secrets.compare_digest(supplied, self.token):
                body = json.dumps(
                    {"error": "this connector is keyed", "how": "Authorization: Bearer <the key the shop gave you>"}
                ).encode()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode()),
                            (b"www-authenticate", b'Bearer realm="buy-you-before"'),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)
