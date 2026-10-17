"""The fit-assurance journey.

This is the business process the agent runs: read the shopper's brief, shortlist the
catalog, test candidates against the room in parallel, widen the search once if nothing
fits, then recommend or hand the case to a person.

Evolus owns the conversation and the reasoning - on the team's AMD-hosted model - and this
module owns the part that needs a real geometry pipeline: the fit search. Each step records
which side produced it, and a step that could not run says so instead of pretending.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from byb_agent.brief import read as read_brief
from byb_agent.contracts import AgentDecision, AgentRun, AgentStep, BriefRequest, FitAttempt, ShopperBrief
from byb_agent.evolus import Evolus, EvolusError
from byb_agent.model import AMDModel
from byb_agent.pipeline import Pipeline
from byb_agent.runs import RunStore
from byb_agent.settings import Settings
from byb_agent.shortlist import listing_url, rank, to_candidate

logger = logging.getLogger("byb.journey")

DEFAULT_ROOM = (4.0, 3.5, 2.4)
PASS_VERDICTS = {"fits", "tight"}
FAIL_VERDICTS = {"blocked", "too_large"}
# A piece resting flush against a wall leaves no gap there, and a gap of nil is not a walkway.
RESTING_TOLERANCE_M = 0.01


def _started() -> float:
    return time.perf_counter()


def _elapsed(at: float) -> int:
    return int((time.perf_counter() - at) * 1000)


def add_step(
    run: AgentRun,
    kind: str,
    *,
    status: str = "ok",
    detail: str = "",
    tool: str | None = None,
    group: str | None = None,
    iteration: int = 1,
    ms: int = 0,
    output: dict | None = None,
) -> AgentStep:
    step = AgentStep(index=len(run.steps), kind=kind, status=status, detail=detail, tool=tool, group=group, iteration=iteration, ms=ms, output=output)
    run.steps.append(step)
    return step


def new_run() -> AgentRun:
    return AgentRun(id=uuid.uuid4().hex[:16], status="running")


def room_for(brief: ShopperBrief) -> tuple[float, float, float]:
    return (
        brief.room_width_m or DEFAULT_ROOM[0],
        brief.room_depth_m or DEFAULT_ROOM[1],
        brief.room_height_m or DEFAULT_ROOM[2],
    )


def note_for(brief: ShopperBrief, candidate: dict) -> str:
    parts = [brief.raw.strip()]
    if brief.must_haves:
        parts.append("must have: " + ", ".join(brief.must_haves))
    if brief.budget_eur:
        parts.append(f"budget around {int(brief.budget_eur)}")
    parts.append(f"shortlisted {candidate.get('sku')}")
    return " | ".join(part for part in parts if part)


def best_walkway(fit: dict[str, Any]) -> dict[str, float]:
    """The roomiest walkway among the placements that actually fit - the evidence to show a shopper.

    Sides the piece rests against are left out: a wall-touching sofa reports a 0 m gap at the
    back, and quoting that to a shopper as "no walkway" would be wrong twice over.
    """
    gaps: dict[str, float] = {}
    best = -1.0
    for placement in fit.get("placements") or []:
        if not placement.get("fits"):
            continue
        walkway = {str(key): float(value) for key, value in (placement.get("walkway_m") or {}).items() if float(value) > RESTING_TOLERANCE_M}
        floor = min(walkway.values()) if walkway else 0.0
        if floor > best:
            best, gaps = floor, walkway
    return gaps


async def evaluate(
    pipeline: Pipeline, brief: ShopperBrief, row: dict, value: float, image_key: str | None = None
) -> tuple[FitAttempt, int]:
    """One candidate through the whole chain. Never raises: a failed fit is a result, not a crash."""
    attempt = FitAttempt(sku=str(row["sku"]), name=str(row["name"]), price_band=row.get("price_band"), score=round(value, 3), status="queued")
    at = _started()
    width, depth, height = room_for(brief)
    try:
        attempt.simulation_id = await pipeline.start_simulation(
            link=listing_url(row),
            notes=note_for(brief, row),
            room_width_m=width,
            room_depth_m=depth,
            room_height_m=height,
            image_key=image_key,
        )
        detail = await pipeline.wait(attempt.simulation_id)
        attempt.status = str(detail.get("status", "unknown"))
        fit = detail.get("fit_report") or {}
        attempt.verdict = fit.get("verdict")
        attempt.coverage_pct = float(fit.get("coverage_pct") or 0.0)
        attempt.walkway_m = best_walkway(fit)
        attempt.reason = "; ".join(fit.get("conflicts") or []) or detail.get("error") or None
    except Exception as exc:  # noqa: BLE001 - one stalled worker must not sink the journey
        logger.warning("candidate %s could not be evaluated: %s", row.get("sku"), exc)
        attempt.status = "failed"
        attempt.reason = str(exc)[:200]
    return attempt, _elapsed(at)


def decide(attempts: list[FitAttempt], brief: ShopperBrief, band: str | None) -> AgentDecision:
    """The branch every pass ends at: recommend, or hand the case to a person."""
    good = [attempt for attempt in attempts if attempt.verdict in PASS_VERDICTS]
    blocked = [attempt for attempt in attempts if attempt.verdict in FAIL_VERDICTS]
    if good:
        winner = max(good, key=lambda attempt: (attempt.verdict == "fits", attempt.score, min(attempt.walkway_m.values() or [0.0])))
        return AgentDecision(
            action="recommend",
            sku=winner.sku,
            simulation_id=winner.simulation_id,
            confidence=round(min(0.95, 0.6 + winner.score * 0.25 + (0.1 if winner.verdict == "fits" else 0.0)), 3),
            reason=f"{winner.name} clears the room with a {winner.verdict} verdict; {len(blocked)} candidate(s) did not.",
            evidence={
                "verdict": winner.verdict,
                "coverage_pct": winner.coverage_pct,
                "walkway_m": winner.walkway_m,
                "price_band": winner.price_band,
                "name": winner.name,
            },
        )
    if blocked:
        return AgentDecision(
            action="handoff",
            confidence=0.45,
            reason=f"Nothing in {band or 'the searched range'} fits this room; a person should propose a smaller or custom piece.",
            evidence={"tested": len(attempts), "blocked": [attempt.sku for attempt in blocked]},
        )
    if brief.confidence < 0.4:
        return AgentDecision(action="handoff", confidence=0.3, reason="The brief is too vague to spend simulations on.", evidence={"brief": brief.raw})
    return AgentDecision(
        action="handoff",
        confidence=0.3,
        reason="No fit report came back, so the candidates could not be evaluated against this room.",
        evidence={"tested": len(attempts)},
    )


def widen(band: str | None) -> str | None:
    """One loop pass outward: if the shopper's band has nothing, try the band below it."""
    order = ["$", "$$", "$$$"]
    if band not in order:
        return None
    index = order.index(band)
    return order[index - 1] if index > 0 else None


def plain_reply(decision: AgentDecision, brief: ShopperBrief | None) -> str:
    evidence = decision.evidence or {}
    if decision.action == "recommend":
        walkway = evidence.get("walkway_m") or {}
        return (
            f"Good news: {evidence.get('name', decision.sku)} fits your room. The fit report says "
            f"{evidence.get('verdict', 'fits')}, it covers {evidence.get('coverage_pct', 0)}% of the floor and keeps "
            f"{round(min(walkway.values() or [0.0]), 2)} m of walkway at the tightest side."
        )
    if decision.action == "handoff" and evidence.get("blocked"):
        return f"I tested {evidence['tested']} options and none clears your room ({decision.reason}). A colleague will send alternatives."
    return decision.reason


async def draft_reply(decision: AgentDecision, brief: ShopperBrief | None, evolus: Evolus, settings: Settings) -> str:
    text = plain_reply(decision, brief)
    if not (evolus.credentials and settings.evolus_reply_tool):
        return text
    try:
        polished = await evolus.run_tool(settings.evolus_reply_tool, text, {"style": "friendly"})
    except EvolusError as exc:
        logger.info("reply left unpolished, Evolus AI Tool unavailable: %s", exc)
        return text
    return polished.strip() or text


class Journey:
    def __init__(self, pipeline: Pipeline, evolus: Evolus, model: AMDModel, store: RunStore, settings: Settings) -> None:
        self._pipeline = pipeline
        self._evolus = evolus
        self._model = model
        self._store = store
        self._settings = settings

    async def run(self, request: BriefRequest, run: AgentRun | None = None) -> AgentRun:
        run = self._store.put(run or new_run())
        add_step(run, "intake", detail=request.brief[:300], tool="agent-service /agent/brief")
        if request.image_key:
            add_step(
                run,
                "room",
                detail="every candidate is fitted into the room measured from the shopper's photo, not the typed numbers",
            )
        try:
            await self._evolus_handoff(run, request)
            brief = await self._read_brief(run, request)
            run.brief = brief
            if self._is_too_vague(brief):
                await self._handoff_early(run, brief)
                return run
            await self._search(run, brief, request.image_key)
            await self._decide(run, brief)
        except Exception as exc:  # noqa: BLE001 - a run must always come back with a reason
            logger.exception("journey %s failed", run.id)
            run.status = "failed"
            run.error = str(exc)[:300]
            return run
        if run.status == "running":
            run.status = "done"
        return run

    def _is_too_vague(self, brief: ShopperBrief) -> bool:
        """A simulation costs a full pipeline run, so an unread brief goes to a person instead."""
        return brief.category is None and brief.confidence < self._settings.handoff_confidence

    async def _handoff_early(self, run: AgentRun, brief: ShopperBrief) -> None:
        decision = AgentDecision(
            action="handoff",
            confidence=round(brief.confidence, 3),
            reason="The brief does not name a piece of furniture; a person should ask what the shopper wants.",
            evidence={"brief": brief.raw},
        )
        run.decision = decision
        add_step(run, "branch", status="branch", detail="no category, so no simulations were spent")
        run.reply = plain_reply(decision, brief)
        add_step(run, "reply", detail=run.reply[:200], tool="template")
        run.status = "awaiting_human"

    async def _evolus_handoff(self, run: AgentRun, request: BriefRequest) -> None:
        """Tell Evolus the case exists, so the conversation, the workflow and this run share one id."""
        at = _started()
        if not (self._evolus.credentials and self._settings.evolus_agent_id):
            add_step(run, "agent", status="skipped", detail="no Evolus agent id configured", tool="POST /v1/chat/completions")
            return
        prompt = (
            f"Shopper brief: {request.brief}\n"
            f"Room: {request.room_width_m or 'unknown'} x {request.room_depth_m or 'unknown'} m. "
            "I will run the fit search against the catalogue and report back."
        )
        try:
            answer, conversation_id = await self._evolus.ask(prompt)
        except EvolusError as exc:
            add_step(run, "agent", status="failed", detail=str(exc)[:200], tool="POST /v1/chat/completions", ms=_elapsed(at))
            return
        run.conversation_id = conversation_id
        add_step(run, "agent", detail=answer[:200], tool="POST /v1/chat/completions", ms=_elapsed(at))

    async def _read_brief(self, run: AgentRun, request: BriefRequest) -> ShopperBrief:
        at = _started()
        brief = await read_brief(request.brief, self._model)
        if request.room_width_m:
            brief.room_width_m = request.room_width_m
        if request.room_depth_m:
            brief.room_depth_m = request.room_depth_m
        if request.room_height_m:
            brief.room_height_m = request.room_height_m
        add_step(
            run,
            "brief",
            detail=f"{brief.category or 'unclassified'}, band {brief.price_band or '-'}, room {room_for(brief)} m, read by {brief.source}",
            tool=self._model.name or "heuristics",
            ms=_elapsed(at),
            output=brief.model_dump(),
        )
        return brief

    async def _search(self, run: AgentRun, brief: ShopperBrief, image_key: str | None = None) -> None:
        """Two passes at most - the shopper's band, then the band below it - and at most
        `max_candidates` simulations per pass.

        The second pass searches a copy. The brief in the run trace is what the shopper asked
        for, and widening the search must not quietly rewrite what they said.
        """
        original_band = brief.price_band
        for iteration in (1, 2):
            search = brief
            if iteration == 2:
                next_band = widen(original_band)
                if next_band is None:
                    add_step(run, "shortlist", status="skipped", iteration=iteration, detail="no lower price band to widen into")
                    return
                search = brief.model_copy(update={"price_band": next_band})
                add_step(run, "branch", status="branch", iteration=iteration, detail=f"nothing in {original_band} fit; widening to {next_band}")

            at = _started()
            try:
                ranked = await self._rank(search)
            except Exception as exc:  # noqa: BLE001 - catalog down is a failed step, not a crash
                add_step(run, "shortlist", status="failed", iteration=iteration, detail=str(exc)[:200], tool="GET /api/v1/catalog", ms=_elapsed(at))
                return
            if not ranked:
                add_step(run, "shortlist", status="failed", iteration=iteration, detail="the catalog has nothing for this brief")
                return
            run.candidates = [to_candidate(row, value) for row, value in ranked]
            add_step(
                run,
                "shortlist",
                iteration=iteration,
                detail=f"{len(ranked)} candidates: {', '.join(str(row['sku']) for row, _ in ranked)}",
                tool="GET /api/v1/catalog",
                ms=_elapsed(at),
            )

            group = f"pass-{iteration}"
            at = _started()
            results = await self._fan(ranked, brief, image_key)
            add_step(
                run,
                "simulate",
                iteration=iteration,
                group=group,
                detail=f"{len(results)} candidates evaluated in parallel, {self._settings.parallel_fits} simulations at a time",
                tool="POST /api/v1/simulations",
                ms=_elapsed(at),
            )
            for attempt, ms in results:
                run.attempts.append(attempt)
                add_step(
                    run,
                    "fit",
                    iteration=iteration,
                    group=group,
                    status="ok" if attempt.verdict else "failed",
                    detail=f"{attempt.sku} -> {attempt.verdict or attempt.status}",
                    tool="geometry-service",
                    ms=ms,
                    output={"simulation_id": attempt.simulation_id, "reason": attempt.reason},
                )
            if any(attempt.verdict in PASS_VERDICTS for attempt, _ in results):
                return

    async def _rank(self, brief: ShopperBrief) -> list[tuple[dict, float]]:
        rows = await self._pipeline.catalog()
        width, depth, _ = room_for(brief)
        return rank(
            rows,
            category=brief.category,
            price_band=brief.price_band,
            must_haves=brief.must_haves,
            limit=self._settings.max_candidates,
            room=(width, depth),
        )

    async def _fan(
        self, ranked: list[tuple[dict, float]], brief: ShopperBrief, image_key: str | None
    ) -> list[tuple[FitAttempt, int]]:
        semaphore = asyncio.Semaphore(self._settings.parallel_fits)

        async def one(row: dict, value: float) -> tuple[FitAttempt, int]:
            async with semaphore:
                return await evaluate(self._pipeline, brief, row, value, image_key)

        return list(await asyncio.gather(*(one(row, value) for row, value in ranked)))

    async def _decide(self, run: AgentRun, brief: ShopperBrief) -> None:
        decision = decide(run.attempts, brief, brief.price_band)
        run.decision = decision
        add_step(run, "compare", detail=decision.reason, tool="policy", output=decision.model_dump())
        at = _started()
        run.reply = await draft_reply(decision, brief, self._evolus, self._settings)
        add_step(run, "reply", detail=run.reply[:200], tool=self._settings.evolus_reply_tool or "template", ms=_elapsed(at))
        if decision.action == "handoff":
            run.status = "awaiting_human"
