"""The custom MCP server.

Evolus registers this as an MCP connector; Claude Code, Cursor or Evolus Studio can use the
same URL. It is the agency layer: the model on AMD decides, these tools do the measuring.

The tool bodies live in `tools.py` and are the ones the REST surface calls, so an agent and a
workflow step cannot get different answers.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings

from byb_agent.settings import Settings
from byb_agent.tools import Tools

logger = logging.getLogger("byb.mcp")

INSTRUCTIONS = (
    "Buy You Before checks whether a piece of furniture fits a real room before it is bought. "
    "Read a shopper's brief with read_brief, search catalog_search, then measure with "
    "simulate_product, joint_fit or start_journey. Trust only a verdict that came back from "
    "simulate_product, fit_report or journey_status: those run a geometry engine over the "
    "measured room, the doorway, the door swing and the walkways. explain_fit turns a verdict "
    "into the facts behind it. proven_fit_offer issues a purchasable offer only over a fit the "
    "engine proved, and reserve_fit holds that piece only on the shopper's own confirmation - "
    "never invent those words. Report the verdict, the coverage percentage and the tightest "
    "walkway, and hand the case to a person when the decision is handoff."
)


def build_server(tools: Tools) -> MCPServer:
    server = MCPServer("buy-you-before", instructions=INSTRUCTIONS)
    register(server, tools)
    return server


def register(server: MCPServer, tools: Tools) -> None:
    @server.tool(name="catalog_search", description="Find furniture in the shop's catalog by words, category ($, $$, $$$) or price band.")
    async def catalog_search(query: str = "", category: str | None = None, price_band: str | None = None, limit: int = 5) -> dict[str, Any]:
        return {"candidates": await _answer(tools.catalog_search, query=query, category=category, price_band=price_band, limit=limit)}

    @server.tool(name="read_brief", description="Read a shopper's own words into a category, a price band and a room size.")
    async def read_brief(brief: str) -> dict[str, Any]:
        return await _answer(tools.read_brief, brief=brief)

    @server.tool(name="simulate_product", description="Measure one product against one room and wait for the fit verdict.")
    async def simulate_product(
        room_width_m: float = 4.0,
        room_depth_m: float = 3.5,
        room_height_m: float = 2.4,
        sku: str | None = None,
        link: str | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        room = {"room_width_m": room_width_m, "room_depth_m": room_depth_m, "room_height_m": room_height_m}
        return await _answer(tools.simulate_product, link=link, sku=sku, notes=notes, **room)

    @server.tool(name="fit_report", description="The verdict, placements and walkways for a simulation already run.")
    async def fit_report(simulation_id: str) -> dict[str, Any]:
        return await _answer(tools.fit_report, simulation_id=simulation_id)

    @server.tool(name="explain_fit", description="Read a fit report back in words: the facts behind the verdict and what to change.")
    async def explain_fit(simulation_id: str) -> dict[str, Any]:
        return await _answer(tools.explain_fit, simulation_id=simulation_id)

    @server.tool(name="joint_fit", description="Two or more pieces the shopper wants together, judged as one purchase.")
    async def joint_fit(
        skus: list[str],
        room_width_m: float = 4.0,
        room_depth_m: float = 3.5,
        room_height_m: float = 2.4,
        notes: str = "",
    ) -> dict[str, Any]:
        return await _answer(tools.joint_fit, skus=skus, notes=notes, room_width_m=room_width_m, room_depth_m=room_depth_m, room_height_m=room_height_m)

    @server.tool(name="find_alternatives", description="Same-category pieces no wider than this one, each measured against the room.")
    async def find_alternatives(
        room_width_m: float = 4.0,
        room_depth_m: float = 3.5,
        room_height_m: float = 2.4,
        sku: str | None = None,
        link: str | None = None,
        notes: str = "",
        limit: int = 3,
    ) -> dict[str, Any]:
        room = {"room_width_m": room_width_m, "room_depth_m": room_depth_m, "room_height_m": room_height_m}
        found = await _answer(tools.find_alternatives, sku=sku, link=link, notes=notes, limit=limit, **room)
        return {"alternatives": found}

    @server.tool(name="proven_fit_offer", description="A purchasable offer over a fit the geometry engine proved. Refuses an unproven piece.")
    async def proven_fit_offer(simulation_id: str) -> dict[str, Any]:
        return await _answer(tools.proven_fit_offer, simulation_id=simulation_id)

    @server.tool(name="reserve_fit", description="Hold a proven-fitting piece. Needs the shopper's own yes, never the agent's.")
    async def reserve_fit(simulation_id: str, confirmation: str) -> dict[str, Any]:
        return await _answer(tools.reserve_fit, simulation_id=simulation_id, confirmation=confirmation)

    @server.tool(name="returns_estimate", description="What a fit check is worth, as arithmetic over assumptions the caller can change.")
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

    @server.tool(name="start_journey", description="Run the whole fit-assurance process for a shopper brief. Returns a run id to poll.")
    async def start_journey(
        brief: str,
        room_width_m: float | None = None,
        room_depth_m: float | None = None,
        room_height_m: float | None = None,
    ) -> dict[str, Any]:
        return await _answer(tools.start_journey, brief=brief, room_width_m=room_width_m, room_depth_m=room_depth_m, room_height_m=room_height_m)

    @server.tool(name="journey_status", description="The trace of a journey: every step, its tool, its duration, and the final decision.")
    async def journey_status(run_id: str) -> dict[str, Any]:
        return await _answer(tools.journey_status, run_id=run_id)


async def _answer(method: Callable[..., Awaitable[Any]], **arguments: Any) -> Any:
    """A foreseeable failure is told to the model in words; only a real bug is a crash."""
    try:
        return await method(**arguments)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


def http_app(server: MCPServer, settings: Settings) -> Any:
    """The ASGI app to mount at /mcp.

    DNS-rebinding protection is on only when the public origin is known, because a tunnel
    hands the server a Host header it was not configured to expect.
    """
    security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    if settings.public_base_url:
        origin = settings.public_base_url.split("//", 1)[-1].rstrip("/")
        security = TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=[origin], allowed_origins=[settings.public_base_url])
    return server.streamable_http_app(streamable_http_path="/", stateless_http=True, json_response=True, transport_security=security, host="0.0.0.0")
