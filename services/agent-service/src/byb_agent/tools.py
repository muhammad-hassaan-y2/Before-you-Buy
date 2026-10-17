"""The tools the agent is given agency with.

One implementation, two doors: `/agent/tools/{name}` for an Evolus workflow step or webhook,
and the MCP server for the agent itself. Same numbers either way, which is the point - a
shopper should not get a different answer in Teams than in the widget.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

from byb_agent import evidence
from byb_agent.brief import read as read_brief
from byb_agent.contracts import AgentRun, BriefRequest, Cart, CartLine, FitAttempt, Order, Reservation, ShopperBrief
from byb_agent.evolus import Evolus
from byb_agent.journey import FAIL_VERDICTS, PASS_VERDICTS, Journey, best_walkway, evaluate
from byb_agent.model import AMDModel
from byb_agent.pipeline import Pipeline, PipelineError, StockShort
from byb_agent.runs import Carts, Orders, Reservations, RunStore
from byb_agent.settings import Settings
from byb_agent.shortlist import listing_url, rank, score, to_candidate

logger = logging.getLogger("byb.tools")

# The words a shopper can say that mean "yes, hold it". Anything else is treated as no,
# because the cost of a wrong yes is a truck and a restocking fee.
CONFIRMATIONS = {"yes", "y", "yeah", "yep", "ok", "okay", "confirm", "confirmed", "i confirm", "hold it", "hold this", "please hold it", "approved", "go ahead"}
CONFIRM_QUESTION = 'Ask the shopper plainly: "Shall I hold this piece for you until the shop confirms?" Then pass their own words as confirmation.'
CHECKOUT_QUESTION = 'Ask the shopper plainly: "Shall I place this order for the pieces the engine cleared?" Then pass their own words as confirmation.'


def _confirmed(confirmation: str) -> bool:
    """An explicit yes in the shopper's own words; anything ambiguous or half-said is a no."""
    words = str(confirmation or "").strip().lower()
    if words in CONFIRMATIONS:
        return True
    return any(token in CONFIRMATIONS for token in re.split(r"[^a-z0-9']+", words))


class Tools:
    def __init__(
        self,
        pipeline: Pipeline,
        evolus: Evolus,
        model: AMDModel,
        store: RunStore,
        settings: Settings,
        reservations: Reservations | None = None,
        carts: Carts | None = None,
        orders: Orders | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._evolus = evolus
        self._model = model
        self._store = store
        self._settings = settings
        self._reservations = reservations if reservations is not None else Reservations()
        self._carts = carts if carts is not None else Carts()
        self._orders = orders if orders is not None else Orders()
        self._journey = Journey(pipeline, evolus, model, store, settings)

    async def catalog_search(self, query: str = "", category: str | None = None, price_band: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        """Find furniture in the shop's catalog by words, category or price band."""
        rows = await self._pipeline.catalog()
        ranked = rank(rows, category=category, price_band=price_band, must_haves=_words(query), limit=limit)
        return [to_candidate(row, value).model_dump() for row, value in ranked]

    async def read_brief(self, brief: str) -> dict[str, Any]:
        """Turn a shopper's own words into a category, a price band and a room size."""
        return (await read_brief(brief, self._model)).model_dump()

    async def simulate_product(
        self,
        link: str | None = None,
        sku: str | None = None,
        notes: str = "",
        room_width_m: float = 4.0,
        room_depth_m: float = 3.5,
        room_height_m: float = 2.4,
        image_key: str | None = None,
    ) -> dict[str, Any]:
        """Measure one product against one room and wait for the fit verdict."""
        row = await self._row(sku, link)
        if row is None:
            raise ValueError("give a sku from catalog_search, or a product link")
        attempt, ms = await evaluate(
            self._pipeline, _room_brief(notes, room_width_m, room_depth_m, room_height_m), row, 1.0, image_key
        )
        detail = await self._pipeline.simulation(attempt.simulation_id) if attempt.simulation_id else {}
        return {"attempt": attempt.model_dump(), "ms": ms, "evidence": _evidence(detail)}

    async def fit_report(self, simulation_id: str) -> dict[str, Any]:
        """The verdict and the placements for a simulation already run."""
        detail = await self._pipeline.simulation(simulation_id)
        fit = detail.get("fit_report") or {}
        return {
            "status": detail.get("status"),
            "verdict": fit.get("verdict"),
            "coverage_pct": fit.get("coverage_pct"),
            "conflicts": fit.get("conflicts") or [],
            "placements": fit.get("placements") or [],
            "door_swing_m": fit.get("door_swing_m"),
            "room": {"width_m": detail.get("room_width_m"), "depth_m": detail.get("room_depth_m"), "height_m": detail.get("room_height_m")},
            "model_download": self._link(f"/api/v1/simulations/{simulation_id}/model") if detail.get("has_model") else None,
        }

    async def explain_fit(self, simulation_id: str) -> dict[str, Any]:
        """Read a fit report back in words: the facts behind the verdict and what to do about them."""
        detail = await self._pipeline.simulation(simulation_id)
        fit = detail.get("fit_report") or {}
        if not fit:
            raise ValueError(f"simulation {simulation_id} has no fit report to explain")
        return {"simulation_id": simulation_id, "status": detail.get("status"), **evidence.explain(fit)}

    async def joint_fit(
        self,
        skus: list[str],
        notes: str = "",
        room_width_m: float = 4.0,
        room_depth_m: float = 3.5,
        room_height_m: float = 2.4,
        image_key: str | None = None,
    ) -> dict[str, Any]:
        """Several pieces the shopper wants in one room, judged as one purchase."""
        wanted = [str(sku).strip() for sku in skus if str(sku).strip()]
        if len(wanted) < 2:
            raise ValueError("joint_fit is for two or more pieces; use simulate_product for one")
        known = {str(row["sku"]).lower(): row for row in await self._pipeline.catalog()}
        unknown = [sku for sku in wanted if sku.lower() not in known]
        if unknown:
            raise ValueError(f"not in the catalog: {', '.join(unknown)}. Find the right skus with catalog_search first.")
        pieces = wanted[: self._settings.max_joint_pieces]
        brief = _room_brief(notes, room_width_m, room_depth_m, room_height_m)
        semaphore = asyncio.Semaphore(self._settings.parallel_fits)

        async def test(sku: str) -> tuple[FitAttempt, dict, dict]:
            row = known[sku.lower()]
            async with semaphore:
                attempt, _ = await evaluate(self._pipeline, brief, row, 1.0, image_key)
            detail = await self._pipeline.simulation(attempt.simulation_id) if attempt.simulation_id else {}
            return attempt, row, detail.get("fit_report") or {}

        results = list(await asyncio.gather(*(test(sku) for sku in pieces)))
        tested: list[dict[str, Any]] = []
        usable = 0.0
        for attempt, row, fit in results:
            area, proved = evidence.footprint(fit, row.get("geometry"))
            usable = max(usable, float(fit.get("usable_area_m2") or 0.0))
            tested.append(
                {
                    "sku": attempt.sku,
                    "name": attempt.name,
                    "price_band": attempt.price_band,
                    "verdict": attempt.verdict or "unknown",
                    "coverage_pct": attempt.coverage_pct,
                    "walkway_m": attempt.walkway_m,
                    "footprint_m2": area,
                    "placement_proved": proved,
                    "conflicts": fit.get("conflicts") or [],
                    "simulation_id": attempt.simulation_id,
                }
            )
        combined = evidence.combine(
            tested,
            usable_area_m2=usable or room_width_m * room_depth_m,
            min_walkway_m=self._settings.min_walkway_m,
            max_coverage=self._settings.max_joint_coverage,
        )
        return {
            "room": {"width_m": room_width_m, "depth_m": room_depth_m, "height_m": room_height_m},
            "requested": wanted,
            "tested": [piece["sku"] for piece in tested],
            "pieces": tested,
            "combined": combined,
        }

    async def find_alternatives(
        self,
        sku: str | None = None,
        link: str | None = None,
        notes: str = "",
        room_width_m: float = 4.0,
        room_depth_m: float = 3.5,
        room_height_m: float = 2.4,
        limit: int = 3,
        image_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """When a product does not fit, the pieces that might: same category, no wider, and tested."""
        row = await self._row(sku, link)
        if row is None:
            raise ValueError("give a sku or a product link to find alternatives for")
        rows = await self._pipeline.catalog()
        width_cm = float((row.get("geometry") or {}).get("width_cm") or 0)
        pool = [
            candidate
            for candidate in rows
            if candidate.get("category") == row.get("category")
            and candidate.get("sku") != row.get("sku")
            and float((candidate.get("geometry") or {}).get("width_cm") or 9999) <= width_cm
        ]
        brief = _room_brief(notes, room_width_m, room_depth_m, room_height_m)
        ranked = rank(
            pool,
            category=row.get("category"),
            price_band=None,
            must_haves=brief.must_haves,
            limit=min(limit, self._settings.max_candidates),
            room=(room_width_m, room_depth_m),
        )
        semaphore = asyncio.Semaphore(self._settings.parallel_fits)

        async def test(candidate: dict, value: float) -> dict[str, Any]:
            async with semaphore:
                attempt, ms = await evaluate(self._pipeline, brief, candidate, value, image_key)
                return {**attempt.model_dump(), "ms": ms}

        return list(await asyncio.gather(*(test(candidate, value) for candidate, value in ranked)))

    async def sweep(
        self,
        *,
        category: str | None = None,
        price_band: str | None = None,
        query: str = "",
        room_width_m: float = 4.0,
        room_depth_m: float = 3.5,
        room_height_m: float = 2.4,
        limit: int = 6,
        image_key: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Measure the ranked candidates, yielding each verdict the moment its own simulation settles.

        One fan-out, two doors: `fit_catalog` folds this into a single answer for an agent, and
        `/agent/fit/stream` prints it as it goes so a storefront flips a card the second the engine
        clears that piece instead of waiting for the slowest one in the sweep.
        """
        rows = await self._pipeline.catalog()
        brief = _room_brief(query, room_width_m, room_depth_m, room_height_m)
        ranked = rank(
            rows,
            category=category,
            price_band=price_band,
            must_haves=_words(query),
            limit=min(limit, self._settings.max_catalog_fits),
            room=(room_width_m, room_depth_m),
        )
        if not ranked:
            raise ValueError("nothing in the catalog matches that. Widen it with catalog_search before spending a fit on it.")
        room = {
            "width_m": room_width_m,
            "depth_m": room_depth_m,
            "height_m": room_height_m,
            "measured_from_photo": bool(image_key),
        }
        yield {"event": "start", "room": room, "total": len(ranked), "skus": [str(row["sku"]) for row, _ in ranked]}
        semaphore = asyncio.Semaphore(self._settings.parallel_fits)
        settled: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        async def test(row: dict, value: float) -> None:
            async with semaphore:
                attempt, ms = await evaluate(self._pipeline, brief, row, value, image_key)
            geometry = row.get("geometry") or {}
            await settled.put(
                {
                    **attempt.model_dump(),
                    "ms": ms,
                    "size_cm": {key: geometry.get(key) for key in ("width_cm", "depth_cm", "height_cm")},
                    "tightest_walkway_m": round(min(attempt.walkway_m.values()), 2) if attempt.walkway_m else None,
                    "verify": self._link(f"/api/v1/simulations/{attempt.simulation_id}") if attempt.simulation_id else None,
                }
            )

        tasks = [asyncio.create_task(test(row, value)) for row, value in ranked]
        tested: list[dict[str, Any]] = []
        try:
            while len(tested) < len(ranked):
                item = await settled.get()
                tested.append(item)
                yield {"event": "verdict", "of": len(tested), "total": len(ranked), **item}
        finally:
            # A shopper who closes the tab stops the sweep; a GPU job nobody is waiting for is waste.
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        verdicts = {item["verdict"] for item in tested}
        yield {
            "event": "done",
            "room": room,
            "checked": len(tested),
            "fits": [item for item in tested if item["verdict"] in PASS_VERDICTS],
            "does_not_fit": [item for item in tested if item["verdict"] in FAIL_VERDICTS],
            "unproven": [item for item in tested if item["verdict"] not in PASS_VERDICTS | FAIL_VERDICTS],
            "note": (
                "Only the geometry engine's own verdict is reported here: fits and tight clear the "
                "walkway, blocked and too_large do not, and unproven means the pipeline never settled "
                "so nothing is claimed about that piece."
                if verdicts - {None}
                else "No candidate settled, so nothing here is a fit."
            ),
        }

    async def fit_catalog(
        self,
        category: str | None = None,
        price_band: str | None = None,
        query: str = "",
        room_width_m: float = 4.0,
        room_depth_m: float = 3.5,
        room_height_m: float = 2.4,
        limit: int = 6,
        image_key: str | None = None,
    ) -> dict[str, Any]:
        """Answer the question a shopper actually asks a shop: which of your pieces fit my room."""
        final: dict[str, Any] = {}
        async for event in self.sweep(
            category=category,
            price_band=price_band,
            query=query,
            room_width_m=room_width_m,
            room_depth_m=room_depth_m,
            room_height_m=room_height_m,
            limit=limit,
            image_key=image_key,
        ):
            final = event
        return {key: value for key, value in final.items() if key != "event"}

    async def start_journey(
        self,
        brief: str,
        room_width_m: float | None = None,
        room_depth_m: float | None = None,
        room_height_m: float | None = None,
        image_key: str | None = None,
    ) -> dict[str, Any]:
        """Run the whole fit-assurance process for a shopper and return the run id to poll."""
        request = BriefRequest(
            brief=brief,
            room_width_m=room_width_m,
            room_depth_m=room_depth_m,
            room_height_m=room_height_m,
            image_key=image_key,
        )
        run = AgentRun(id=_new_run_id(), status="running")
        self._store.put(run)
        task = asyncio.create_task(self._journey.run(request, run))
        task.add_done_callback(lambda finished: self._failed(run, finished))
        return {"run_id": run.id, "status": run.status, "poll": self._link(f"/agent/runs/{run.id}")}

    async def journey_status(self, run_id: str) -> dict[str, Any]:
        """The trace of a journey: every step, its tool, its duration and the final decision."""
        run = self._store.get(run_id)
        if run is None:
            raise ValueError(f"unknown run {run_id!r}")
        return run.model_dump()

    async def proven_fit_offer(self, simulation_id: str) -> dict[str, Any]:
        """Turn a proven fit into an offer another agent, or a checkout, can act on."""
        detail = await self._pipeline.simulation(simulation_id)
        fit = detail.get("fit_report") or {}
        verdict = str(fit.get("verdict") or "")
        if verdict not in PASS_VERDICTS:
            raise ValueError(
                f"no offer: this piece comes back {verdict or 'unknown'} in that room. "
                "Run find_alternatives and put a proven fit on the table instead."
            )
        candidate = detail.get("catalog_candidate") or {}
        profile = detail.get("product_profile") or {}
        sku = candidate.get("sku") or profile.get("sku")
        row = await self._row(sku, None) if sku else None
        band = candidate.get("price_band") or profile.get("price_band") or (row or {}).get("price_band")
        explained = evidence.explain(fit)
        return {
            "offer": {
                "kind": "buy-you-before/fit-assured-offer",
                "sku": sku,
                "name": candidate.get("name") or profile.get("name") or "this piece",
                "price_band": band,
                "price_eur": evidence.price_for(band),
                "currency": "EUR",
                "item_link": listing_url(row) if row else detail.get("product_link"),
                "issued_at": _now(),
                "expires_in_s": evidence.OFFER_TTL_S,
            },
            "fit_evidence": {
                "simulation_id": simulation_id,
                "verdict": verdict,
                "coverage_pct": explained["coverage_pct"],
                "tightest_walkway_m": explained["tightest_walkway_m"],
                "door_pass": explained["door_pass"],
                "fragile": explained["fragile"],
                "room": {"width_m": detail.get("room_width_m"), "depth_m": detail.get("room_depth_m"), "height_m": detail.get("room_height_m")},
                "verify": self._link(f"/api/v1/simulations/{simulation_id}"),
                "model_download": self._link(f"/api/v1/simulations/{simulation_id}/model") if detail.get("has_model") else None,
            },
            "assurance": {
                "promise": "Measured against this room before the order was placed.",
                "covered_return_reason": "does_not_fit",
                "caveats": explained["suggestions"],
            },
            "reserve": {"tool": "reserve_fit", "needs": "the shopper's own confirmation words", "how": CONFIRM_QUESTION},
        }

    async def reserve_fit(self, simulation_id: str, confirmation: str) -> dict[str, Any]:
        """Hold a proven-fitting piece for a shopper - only on a human's own yes."""
        words = str(confirmation or "").strip()
        if not _confirmed(words):
            raise ValueError(f"A hold needs the shopper's own yes, not the agent's. {CONFIRM_QUESTION}")
        detail = await self._pipeline.simulation(simulation_id)
        fit = detail.get("fit_report") or {}
        verdict = str(fit.get("verdict") or "")
        if verdict not in PASS_VERDICTS:
            raise ValueError(f"nothing to hold: that simulation comes back {verdict or 'unknown'}, not a fit.")
        candidate = detail.get("catalog_candidate") or {}
        profile = detail.get("product_profile") or {}
        reservation = Reservation(
            id=_new_run_id(),
            simulation_id=simulation_id,
            sku=candidate.get("sku") or profile.get("sku"),
            name=candidate.get("name") or profile.get("name"),
            verdict=verdict,
            confirmation=words,
            created_at=_now(),
        )
        if reservation.sku:
            reservation.stock = await self._claim(
                f"hold:{reservation.id}", [reservation], reason=f"hold {reservation.id} on {reservation.sku}"
            )
        self._reservations.put(reservation)
        return {
            **reservation.model_dump(),
            "holds_until": _holds_until(evidence.OFFER_TTL_S),
            "next": "A person at the shop accepts or releases it. Nothing is charged and nothing ships from this service.",
        }

    async def add_to_cart(
        self,
        sku: str | None = None,
        link: str | None = None,
        cart_id: str | None = None,
        quantity: int = 1,
        simulation_id: str | None = None,
        room_width_m: float | None = None,
        room_depth_m: float | None = None,
        room_height_m: float | None = None,
    ) -> dict[str, Any]:
        """Put a piece in the bag at the shop's own listed price, with the fit proof attached when one exists."""
        row = await self._row(sku, link)
        if row is None:
            raise ValueError("give a sku from catalog_search, or a product link")
        cart = self._carts.get(cart_id) if cart_id else None
        if cart_id and cart is None:
            raise ValueError(f"cart {cart_id!r} is not in this process - a restart drops bags. Start a fresh one and give the shopper the new id.")
        if cart is None:
            cart = Cart(id=_new_run_id(), room=_room(room_width_m, room_depth_m, room_height_m), updated_at=_now())
        listed = str(row["sku"])
        line = next((item for item in cart.lines if item.sku.lower() == listed.lower()), None)
        if line is None:
            if len(cart.lines) >= self._settings.max_cart_lines:
                raise ValueError(
                    f"a bag here holds at most {self._settings.max_cart_lines} pieces; check out or clear one with remove_from_cart."
                )
            commerce = row.get("commerce") or {}
            line = CartLine(
                sku=listed,
                name=str(row.get("name") or listed),
                price_eur=float(commerce.get("retail_eur") or evidence.price_for(row.get("price_band"))),
                cost_eur=float(commerce.get("cost_eur") or 0.0),
                lead_days=int(commerce.get("lead_days") or 0),
                freight=str(commerce.get("freight") or "parcel"),
                volume_m3=float(commerce.get("volume_m3") or 0.0),
                added_at=_now(),
            )
            cart.lines.append(line)
        line.quantity = max(int(quantity), 1)
        if simulation_id:
            self._attach(cart, line, simulation_id, await self._pipeline.simulation(simulation_id), row.get("geometry"))
        cart.updated_at = _now()
        self._carts.put(cart)
        return self._view(cart)

    async def view_cart(self, cart_id: str) -> dict[str, Any]:
        """What is in the bag, what it costs the shopper and the shop, and which lines are still unproven."""
        return self._view(self._cart(cart_id))

    async def remove_from_cart(self, cart_id: str, sku: str) -> dict[str, Any]:
        """Take one piece out of the bag."""
        cart = self._cart(cart_id)
        wanted = str(sku).strip().lower()
        kept = [line for line in cart.lines if line.sku.lower() != wanted]
        if len(kept) == len(cart.lines):
            raise ValueError(f"{sku!r} is not in cart {cart.id}. Read the bag with view_cart first.")
        cart.lines = kept
        cart.updated_at = _now()
        self._carts.put(cart)
        return self._view(cart)

    async def measure_cart(
        self,
        cart_id: str,
        room_width_m: float | None = None,
        room_depth_m: float | None = None,
        room_height_m: float | None = None,
        image_key: str | None = None,
    ) -> dict[str, Any]:
        """Measure what is in the bag against its room, and judge the pieces together as one purchase."""
        cart = self._cart(cart_id)
        if not cart.lines:
            raise ValueError("the bag is empty; add_to_cart before measuring it.")
        if room_width_m or room_depth_m or room_height_m:
            cart.room = _room(room_width_m, room_depth_m, room_height_m)
        room = dict(cart.room or _room(None, None, None))
        cart.room = room
        brief = _room_brief("cart", room["width_m"], room["depth_m"], room["height_m"])
        rows = {str(row["sku"]).lower(): row for row in await self._pipeline.catalog()}
        stale = [line for line in cart.lines if line.simulation_id is None or line.room != room]
        semaphore = asyncio.Semaphore(self._settings.parallel_fits)

        async def measure(line: CartLine) -> dict[str, Any]:
            row = rows.get(line.sku.lower())
            if row is None:
                return {"sku": line.sku, "verdict": None, "reason": "no longer in the catalog"}
            async with semaphore:
                attempt, ms = await evaluate(self._pipeline, brief, row, 1.0, image_key)
            detail = await self._pipeline.simulation(attempt.simulation_id) if attempt.simulation_id else {}
            self._attach(cart, line, attempt.simulation_id, detail, row.get("geometry"))
            return {
                "sku": line.sku,
                "name": line.name,
                "verdict": line.verdict,
                "quantity": line.quantity,
                "tightest_walkway_m": round(min(line.walkway_m.values()), 2) if line.walkway_m else None,
                "ms": ms,
                "verify": self._link(f"/api/v1/simulations/{line.simulation_id}") if line.simulation_id else None,
            }

        measured = list(await asyncio.gather(*(measure(line) for line in stale)))
        cart.updated_at = _now()
        self._carts.put(cart)
        rest = {id(line) for line in stale}
        return {
            "measured": measured,
            "already_proven": [line.sku for line in cart.lines if id(line) not in rest],
            **self._view(cart, combined=self._combine(cart)),
        }

    async def checkout(self, cart_id: str, confirmation: str) -> dict[str, Any]:
        """Turn a bag of proven fits into an order draft - on the shopper's own yes, and on nothing less."""
        words = str(confirmation or "").strip()
        if not _confirmed(words):
            raise ValueError(f"An order needs the shopper's own yes, not the agent's. {CHECKOUT_QUESTION}")
        cart = self._cart(cart_id)
        if not cart.lines:
            raise ValueError("the bag is empty; add_to_cart before checking out.")
        unproven = [line.sku for line in cart.lines if line.verdict not in PASS_VERDICTS]
        if unproven:
            raise ValueError(
                f"nothing is sold unchecked: {', '.join(unproven)} has no cleared fit report. "
                "Run measure_cart on this bag, then put only what the engine clears in the order."
            )
        combined = self._combine(cart)
        totals = _totals(cart.lines)
        order_id = _new_run_id()
        claim = await self._claim(f"order:{order_id}", cart.lines, reason=f"order draft {order_id}")
        order = Order(
            id=order_id,
            cart_id=cart.id,
            lines=[line.model_copy(deep=True) for line in cart.lines],
            currency="EUR",
            confirmation=words,
            created_at=_now(),
            proofs=[
                {
                    "sku": line.sku,
                    "simulation_id": line.simulation_id,
                    "verdict": line.verdict,
                    "quantity": line.quantity,
                    "tightest_walkway_m": round(min(line.walkway_m.values()), 2) if line.walkway_m else None,
                    "verify": self._link(f"/api/v1/simulations/{line.simulation_id}") if line.simulation_id else None,
                }
                for line in cart.lines
            ],
            combined=combined,
            room=dict(cart.room or {}),
            stock=claim,
            **totals,
        )
        self._orders.put(order)
        return {
            **order.model_dump(),
            "next": "A person at the shop accepts or releases this draft. No card is taken and nothing ships from this service.",
        }

    async def order_status(self, order_id: str) -> dict[str, Any]:
        """One order draft, with the fit proofs and the words that let it be placed."""
        order = self._orders.get(order_id)
        if order is None:
            raise ValueError(f"unknown order {order_id!r}")
        return order.model_dump()

    def list_orders(self, limit: int = 20) -> list[dict[str, Any]]:
        """Order drafts waiting on a person at the shop, newest first."""
        shown = {"id", "cart_id", "status", "total_eur", "margin_eur", "confirmation", "created_at"}
        return [order.model_dump(include=shown) for order in self._orders.recent(limit)]

    def _cart(self, cart_id: str) -> Cart:
        cart = self._carts.get(cart_id)
        if cart is None:
            raise ValueError(f"unknown cart {cart_id!r}. Bags live in this process; start one with add_to_cart.")
        return cart

    async def _claim(self, key: str, lines: list[Any], *, reason: str) -> dict[str, Any]:
        """Ask the shelf for the units a hold or a draft commits, keyed so a retry does not take twice.

        A short shelf stops the order — the shop cannot sell what it does not have. A shelf that
        cannot be read does not: an unreachable count is not an empty one, and what the merchant
        sees is the difference.
        """
        wanted = [{"sku": str(line.sku), "qty": int(getattr(line, "quantity", 1) or 1)} for line in lines]
        try:
            claim = await self._pipeline.claim_stock(key=key, lines=wanted, reason=reason)
        except StockShort as short:
            raise ValueError(f"the shop cannot supply it: {short}") from short
        except PipelineError as unreachable:
            logger.warning("stock claim %s: %s", key, unreachable)
            return {"claimed": False, "key": key, "units": wanted, "why": str(unreachable)}
        return {"claimed": True, "key": key, "units": claim.get("lines"), "at": claim.get("at")}

    def _attach(self, cart: Cart, line: CartLine, simulation_id: str | None, detail: dict[str, Any], geometry: dict | None) -> None:
        """Copy the engine's own word for a piece onto the line, so a bag can be checked out without re-measuring it."""
        fit = detail.get("fit_report") or {}
        verdict = str(fit.get("verdict") or "")
        if not verdict or not simulation_id:
            return
        line.simulation_id = str(simulation_id)
        line.verdict = verdict
        line.coverage_pct = round(float(fit.get("coverage_pct") or 0.0), 1)
        line.footprint_m2, line.placement_proved = evidence.footprint(fit, geometry)
        line.walkway_m = best_walkway(fit)
        # The proof carries the room it was made in, and that is the report's own numbers rather
        # than whatever the bag says: a sofa cleared for a 4.0 m room proves nothing about a 3.4 m
        # one, and `measure_cart` re-measures a line the moment the two disagree.
        line.room = _room(detail.get("room_width_m"), detail.get("room_depth_m"), detail.get("room_height_m"))
        cart.usable_area_m2 = max(cart.usable_area_m2, float(fit.get("usable_area_m2") or 0.0))

    def _pieces(self, cart: Cart) -> list[dict[str, Any]]:
        """The bag as one purchase: the box the engine cleared, times the quantity in the bag."""
        return [
            {
                "sku": line.sku,
                "name": line.name,
                "price_band": None,
                "verdict": line.verdict or "unknown",
                "coverage_pct": line.coverage_pct,
                "walkway_m": line.walkway_m,
                "footprint_m2": round(line.footprint_m2 * line.quantity, 3),
                "placement_proved": line.placement_proved,
            }
            for line in cart.lines
        ]

    def _combine(self, cart: Cart) -> dict[str, Any]:
        room = cart.room or _room(None, None, None)
        return evidence.combine(
            self._pieces(cart),
            usable_area_m2=cart.usable_area_m2 or room["width_m"] * room["depth_m"],
            min_walkway_m=self._settings.min_walkway_m,
            max_coverage=self._settings.max_joint_coverage,
        )

    def _view(self, cart: Cart, *, combined: dict | None = None) -> dict[str, Any]:
        unproven = [line.sku for line in cart.lines if line.verdict not in PASS_VERDICTS]
        return {
            "cart_id": cart.id,
            "room": cart.room,
            "lines": [line.model_dump() for line in cart.lines],
            "items": sum(line.quantity for line in cart.lines),
            **_totals(cart.lines),
            "unproven": unproven,
            "set": combined,
            "checkout": {
                "tool": "checkout",
                "ready": not unproven and bool(cart.lines),
                "needs": "the shopper's own confirmation words",
                "how": CHECKOUT_QUESTION,
                "refuses": "a bag with any line the engine has not cleared, so measure_cart comes before it",
            },
            "note": "Prices are the catalog's own listed terms. Nothing is charged here: checkout writes a draft a person at the shop accepts.",
        }

    async def returns_estimate(
        self,
        orders_per_month: float = 1000,
        price_band: str | None = None,
        price_eur: float | None = None,
        return_rate: float | None = None,
        fit_share: float | None = None,
        prevention: float | None = None,
    ) -> dict[str, Any]:
        """What the fit check is worth, as arithmetic over assumptions the caller can change."""
        return evidence.returns_estimate(
            orders_per_month=orders_per_month,
            price_band=price_band,
            price_eur=price_eur,
            return_rate=return_rate,
            fit_share=fit_share,
            prevention=prevention,
        )

    def list_reservations(self, limit: int = 20) -> list[dict[str, Any]]:
        """The holds waiting on a person at the shop, newest first."""
        return [reservation.model_dump() for reservation in self._reservations.recent(limit)]

    def _link(self, path: str) -> str:
        """An agent in ChatGPT or Claude can only follow an absolute link, so the public origin is
        used when it is configured and a relative path stays honest about a local run."""
        base = (self._settings.public_base_url or "").rstrip("/")
        return f"{base}{path}" if base else path

    async def _row(self, sku: str | None, link: str | None) -> dict | None:
        rows = await self._pipeline.catalog()
        if sku:
            return next((row for row in rows if str(row.get("sku")).lower() == sku.lower()), None)
        if link:
            best = max(rows, key=lambda row: score(row, None, None, _words(link)), default=None)
            if best is not None and score(best, None, None, _words(link)) >= 0.2:
                return best
        return None

    @staticmethod
    def _failed(run: AgentRun, task: asyncio.Task) -> None:
        if task.cancelled():
            run.status = "failed"
            run.error = "cancelled"
            return
        error = task.exception()
        if error is not None:
            logger.exception("journey %s crashed", run.id, exc_info=error)
            run.status = "failed"
            run.error = str(error)[:300]


def _words(text: str) -> list[str]:
    return [word for word in (text or "").lower().replace("/", " ").replace("-", " ").split() if len(word) > 2]


def _room_brief(notes: str, width: float, depth: float, height: float) -> ShopperBrief:
    return ShopperBrief(raw=notes or "agent simulation", room_width_m=width, room_depth_m=depth, room_height_m=height, source="agent", confidence=0.8)


def _room(width: float | None, depth: float | None, height: float | None) -> dict[str, float]:
    """One shape for a room, so a line's room and the bag's room can be compared at all.

    Not rounded: a line is stale when its room and the bag's differ, and rounding would hide a
    5 cm change of mind behind a proof that no longer describes the room being bought for.
    """
    return {"width_m": float(width or 4.0), "depth_m": float(depth or 3.5), "height_m": float(height or 2.4)}


def _totals(lines: list[CartLine]) -> dict[str, Any]:
    """Money and freight for a bag. The lead is the slowest piece and the freight is the heaviest.

    Quantity moves the price and the volume; the engine measures one of a kind, so a bag of four
    identical chairs is quoted as four boxes of floor and one verdict for the shape.
    """
    total = round(sum(line.price_eur * line.quantity for line in lines), 2)
    cost = round(sum(line.cost_eur * line.quantity for line in lines), 2)
    return {
        "total_eur": total,
        "cost_eur": cost,
        "margin_eur": round(total - cost, 2),
        "volume_m3": round(sum(line.volume_m3 * line.quantity for line in lines), 3),
        "lead_days": max((line.lead_days for line in lines), default=0),
        "freight": "pallet" if any(line.freight == "pallet" for line in lines) else "parcel",
    }


def _evidence(detail: dict[str, Any]) -> dict[str, Any]:
    fit = detail.get("fit_report") or {}
    return {
        "verdict": fit.get("verdict"),
        "coverage_pct": fit.get("coverage_pct"),
        "conflicts": fit.get("conflicts") or [],
        "placements": len(fit.get("placements") or []),
        "has_model": bool(detail.get("has_model")),
    }


def _new_run_id() -> str:
    return uuid.uuid4().hex[:16]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _holds_until(seconds: int) -> str:
    return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat(timespec="seconds")


SPEC: dict[str, str] = {
    "catalog_search": "Find furniture in the shop's catalog by words, category or price band.",
    "read_brief": "Turn a shopper's own words into a category, a price band and a room size.",
    "simulate_product": "Measure one product against one room and wait for the fit verdict. Pass image_key to use a room measured from a photo.",
    "fit_report": "The verdict, placements and walkways for a simulation already run.",
    "explain_fit": "Read a fit report back in words: the facts behind the verdict and what to change.",
    "joint_fit": "Judge two or more pieces as one purchase, measuring each and combining the footprints.",
    "find_alternatives": "Pieces in the same category that are no wider, each tested against the room.",
    "fit_catalog": "Which of the shop's pieces actually fit this room, measured in parallel and split into fits, does-not-fit and unproven.",
    "proven_fit_offer": "An agent-readable offer that only a proven fit can back.",
    "reserve_fit": "Hold a proven-fitting piece, gated behind the shopper's own confirmation; the MCP door asks them in their own client when it can.",
    "add_to_cart": "Put a piece in the bag at the shop's listed price, carrying a simulation's verdict when one is given.",
    "view_cart": "Read the bag: lines, quantities, totals and margin, which lines are unproven, and whether checkout would accept it.",
    "remove_from_cart": "Take one piece out of the bag.",
    "measure_cart": "Measure every line the bag has no cleared proof for against the bag's room, then judge the pieces as one purchase.",
    "checkout": "Write an order draft for a bag whose every line the engine cleared, gated behind the shopper's own yes.",
    "order_status": "Read an order draft, its fit proofs and the words that let it be placed.",
    "returns_estimate": "What a fit check is worth, as arithmetic over stated assumptions.",
    "start_journey": "Run the whole fit-assurance process for a shopper brief, against a photo-measured room when image_key is given.",
    "journey_status": "The trace of a journey, including the final decision.",
}
