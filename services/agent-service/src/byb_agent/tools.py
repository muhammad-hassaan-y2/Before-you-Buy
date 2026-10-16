"""The tools the agent is given agency with.

One implementation, two doors: `/agent/tools/{name}` for an Evolus workflow step or webhook,
and the MCP server for the agent itself. Same numbers either way, which is the point - a
shopper should not get a different answer in Teams than in the widget.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from byb_agent.brief import read as read_brief
from byb_agent.contracts import AgentRun, BriefRequest, ShopperBrief
from byb_agent.evolus import Evolus
from byb_agent.journey import Journey, evaluate
from byb_agent.model import AMDModel
from byb_agent.pipeline import Pipeline
from byb_agent.runs import RunStore
from byb_agent.settings import Settings
from byb_agent.shortlist import rank, score, to_candidate

logger = logging.getLogger("byb.tools")


class Tools:
    def __init__(self, pipeline: Pipeline, evolus: Evolus, model: AMDModel, store: RunStore, settings: Settings) -> None:
        self._pipeline = pipeline
        self._evolus = evolus
        self._model = model
        self._store = store
        self._settings = settings
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


SPEC: dict[str, str] = {
    "catalog_search": "Find furniture in the shop's catalog by words, category or price band.",
    "read_brief": "Turn a shopper's own words into a category, a price band and a room size.",
    "simulate_product": "Measure one product against one room and wait for the fit verdict.",
    "fit_report": "The verdict, placements and walkways for a simulation already run.",
    "find_alternatives": "Pieces in the same category that are no wider, each tested against the room.",
    "start_journey": "Run the whole fit-assurance process for a shopper brief.",
    "journey_status": "The trace of a journey, including the final decision.",
}
