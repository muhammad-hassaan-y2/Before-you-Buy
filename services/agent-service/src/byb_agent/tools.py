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
from datetime import UTC, datetime, timedelta
from typing import Any

from byb_agent import evidence
from byb_agent.brief import read as read_brief
from byb_agent.contracts import AgentRun, BriefRequest, FitAttempt, Reservation, ShopperBrief
from byb_agent.evolus import Evolus
from byb_agent.journey import PASS_VERDICTS, Journey, evaluate
from byb_agent.model import AMDModel
from byb_agent.pipeline import Pipeline
from byb_agent.runs import Reservations, RunStore
from byb_agent.settings import Settings
from byb_agent.shortlist import listing_url, rank, score, to_candidate

logger = logging.getLogger("byb.tools")

# The words a shopper can say that mean "yes, hold it". Anything else is treated as no,
# because the cost of a wrong yes is a truck and a restocking fee.
CONFIRMATIONS = {"yes", "y", "yeah", "yep", "ok", "okay", "confirm", "confirmed", "i confirm", "hold it", "hold this", "please hold it", "approved", "go ahead"}
CONFIRM_QUESTION = 'Ask the shopper plainly: "Shall I hold this piece for you until the shop confirms?" Then pass their own words as confirmation.'


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
    ) -> None:
        self._pipeline = pipeline
        self._evolus = evolus
        self._model = model
        self._store = store
        self._settings = settings
        self._reservations = reservations if reservations is not None else Reservations()
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
    ) -> dict[str, Any]:
        """Measure one product against one room and wait for the fit verdict."""
        row = await self._row(sku, link)
        if row is None:
            raise ValueError("give a sku from catalog_search, or a product link")
        attempt, ms = await evaluate(self._pipeline, _room_brief(notes, room_width_m, room_depth_m, room_height_m), row, 1.0)
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
            "model_download": f"/api/v1/simulations/{simulation_id}/model" if detail.get("has_model") else None,
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
                attempt, _ = await evaluate(self._pipeline, brief, row, 1.0)
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
                attempt, ms = await evaluate(self._pipeline, brief, candidate, value)
                return {**attempt.model_dump(), "ms": ms}

        return list(await asyncio.gather(*(test(candidate, value) for candidate, value in ranked)))

    async def start_journey(
        self,
        brief: str,
        room_width_m: float | None = None,
        room_depth_m: float | None = None,
        room_height_m: float | None = None,
    ) -> dict[str, Any]:
        """Run the whole fit-assurance process for a shopper and return the run id to poll."""
        request = BriefRequest(brief=brief, room_width_m=room_width_m, room_depth_m=room_depth_m, room_height_m=room_height_m)
        run = AgentRun(id=_new_run_id(), status="running")
        self._store.put(run)
        task = asyncio.create_task(self._journey.run(request, run))
        task.add_done_callback(lambda finished: self._failed(run, finished))
        return {"run_id": run.id, "status": run.status, "poll": f"/agent/runs/{run.id}"}

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
                "verify": f"/api/v1/simulations/{simulation_id}",
                "model_download": f"/api/v1/simulations/{simulation_id}/model" if detail.get("has_model") else None,
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
        self._reservations.put(reservation)
        return {
            **reservation.model_dump(),
            "holds_until": _holds_until(evidence.OFFER_TTL_S),
            "next": "A person at the shop accepts or releases it. Nothing is charged and nothing ships from this service.",
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
    "simulate_product": "Measure one product against one room and wait for the fit verdict.",
    "fit_report": "The verdict, placements and walkways for a simulation already run.",
    "explain_fit": "Read a fit report back in words: the facts behind the verdict and what to change.",
    "joint_fit": "Judge two or more pieces as one purchase, measuring each and combining the footprints.",
    "find_alternatives": "Pieces in the same category that are no wider, each tested against the room.",
    "proven_fit_offer": "An agent-readable offer that only a proven fit can back.",
    "reserve_fit": "Hold a proven-fitting piece, gated behind the shopper's own confirmation.",
    "returns_estimate": "What a fit check is worth, as arithmetic over stated assumptions.",
    "start_journey": "Run the whole fit-assurance process for a shopper brief.",
    "journey_status": "The trace of a journey, including the final decision.",
}
