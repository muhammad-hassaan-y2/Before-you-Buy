"""The golden set, run as an evaluation.

`evals/golden_briefs.json` holds fifteen shopper briefs, the catalog rows each one shortlists,
and the verdict geometry-service gave each of those boxes in each of those rooms. This module
drives the real journey over that file with the pipeline replaced by the labels, and answers
two questions:

* did the agent read the brief and decide as the labels say it should, and
* how often did it recommend a piece the engine rejected.

The second number is the one that decides whether this product can be trusted, so it is the
gate: a false fit is a return, and a return is the cost the whole demo claims to prevent.

Run it as a report with `poetry run eval`, or as a test with `pytest tests/test_golden_eval.py`.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from byb_agent.contracts import BriefRequest
from byb_agent.evolus import Evolus
from byb_agent.journey import PASS_VERDICTS, Journey
from byb_agent.model import AMDModel
from byb_agent.runs import RunStore
from byb_agent.settings import Settings

GOLDEN_SET = Path(__file__).resolve().parents[4] / "evals" / "golden_briefs.json"
READ_FIELDS = ("category", "price_band", "budget_eur", "room_width_m", "room_depth_m", "room_height_m")
MAX_FALSE_FITS = 0
MIN_BRIEF_ACCURACY = 0.9
MIN_DECISION_ACCURACY = 0.9


def load(path: Path = GOLDEN_SET) -> list[dict[str, Any]]:
    return list(json.loads(path.read_text(encoding="utf-8"))["cases"])


def eval_settings() -> Settings:
    """The boundaries the demo runs on, with the network taken out of the loop."""
    return Settings(
        gateway_url="http://gateway",
        catalog_url="http://catalog",
        max_candidates=4,
        parallel_fits=2,
        settle_timeout_s=6,
        poll_interval_s=0.01,
    )


def _same(expected: Any, actual: Any) -> bool:
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) < 0.005
    return expected == actual


class GoldenPipeline:
    """The pipeline as the golden set says it behaves: a catalog, and one verdict per SKU.

    It answers the three calls the journey makes and records the room each simulation was
    queued for, because measuring the wrong room is how a false fit gets made.
    """

    def __init__(self, rows: list[dict[str, Any]], labels: dict[str, dict[str, Any]], room: tuple[float, float, float]) -> None:
        self._rows = rows
        self._labels = labels
        self._room_area = round(room[0] * room[1], 2)
        self.queued: list[tuple[str, tuple[float, float, float]]] = []
        self._ids: dict[str, str] = {}
        self._next = 0

    async def catalog(self) -> list[dict[str, Any]]:
        return self._rows

    async def start_simulation(
        self,
        *,
        link: str | None = None,
        notes: str | None = None,
        room_width_m: float,
        room_depth_m: float,
        room_height_m: float,
        image_key: str | None = None,
    ) -> str:
        self._next += 1
        simulation_id = f"golden{self._next:04d}"
        for row in self._rows:
            if notes and f"shortlisted {row['sku']}" in notes:
                self._ids[simulation_id] = str(row["sku"])
        self.queued.append((simulation_id, (room_width_m, room_depth_m, room_height_m)))
        return simulation_id

    async def simulation(self, simulation_id: str) -> dict[str, Any]:
        sku = self._ids.get(simulation_id)
        label = self._labels.get(str(sku))
        if label is None:
            return {"id": simulation_id, "status": "failed", "error": f"the golden set has no verdict for {sku}"}
        engine = label["engine"]
        fits = str(engine["verdict"]) in PASS_VERDICTS
        return {
            "id": simulation_id,
            "status": "completed",
            "catalog_candidate": {key: value for key, value in label.items() if key != "engine"},
            "fit_report": {
                "room_area_m2": self._room_area,
                "usable_area_m2": self._room_area,
                "coverage_pct": engine["coverage_pct"],
                "verdict": engine["verdict"],
                "door_pass": engine["door_pass"],
                "fragile": engine["fragile"],
                "conflicts": engine["conflicts"],
                "suggestions": engine["suggestions"],
                "placements": [{"label": str(label["name"]), "fits": fits, "walkway_m": engine["walkway_m"]}],
            },
        }

    async def wait(self, simulation_id: str) -> dict[str, Any]:
        return await self.simulation(simulation_id)


async def run_case(case: dict[str, Any], settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or eval_settings()
    rows = [{key: value for key, value in item.items() if key != "engine"} for item in case["candidates"]]
    labels = {str(item["sku"]): item for item in case["candidates"]}
    room = (case["room"]["width_m"], case["room"]["depth_m"], case["room"]["height_m"])
    pipeline = GoldenPipeline(rows, labels, room)
    async with httpx.AsyncClient() as client:
        journey = Journey(pipeline, Evolus(client, settings), AMDModel(client, settings), RunStore(), settings)
        run = await journey.run(BriefRequest(brief=case["brief"]))

    read = run.brief.model_dump() if run.brief else {}
    expected_read = case["read"]
    read_misses = [
        f"{field}: expected {expected_read.get(field)!r}, read {read.get(field)!r}"
        for field in READ_FIELDS
        if not _same(expected_read.get(field), read.get(field))
    ]
    expected_haves = sorted(case["read"].get("must_haves") or [])
    if sorted(read.get("must_haves") or []) != expected_haves:
        read_misses.append(f"must_haves: expected {expected_haves}, read {sorted(read.get('must_haves') or [])}")

    decision = run.decision
    chosen = next((attempt for attempt in run.attempts if decision and attempt.sku == decision.sku), None)
    verdict = chosen.verdict if chosen else None
    false_fit = bool(decision and decision.action == "recommend" and verdict not in PASS_VERDICTS)

    decision_misses = []
    if not decision:
        decision_misses.append(f"action: expected {case['decision']['action']}, the run produced no decision")
    else:
        if decision.action != case["decision"]["action"]:
            decision_misses.append(f"action: expected {case['decision']['action']}, decided {decision.action!r}")
        if case["decision"].get("sku") and decision.sku != case["decision"]["sku"]:
            decision_misses.append(f"sku: expected {case['decision']['sku']}, recommended {decision.sku!r}")
        if decision.action == "recommend" and not decision.simulation_id:
            decision_misses.append("a recommendation with no simulation behind it")
    if false_fit:
        decision_misses.append(f"recommended {decision.sku}, which the engine called {verdict}")

    wrong_rooms = sorted({measured for _id, measured in pipeline.queued if measured != room})
    searched = [step.iteration for step in run.steps if step.kind in {"shortlist", "simulate", "fit"}]
    passes = max(searched, default=0)

    return {
        "id": case["id"],
        "brief": case["brief"],
        "read_ok": not read_misses,
        "read_misses": read_misses,
        "decision_ok": not decision_misses and not false_fit,
        "decision_misses": decision_misses,
        "false_fit": false_fit,
        "action": getattr(decision, "action", None),
        "sku": getattr(decision, "sku", None),
        "verdict": verdict,
        "fragile": bool((labels.get(str(getattr(decision, "sku", None)), {}).get("engine") or {}).get("fragile")),
        "simulations": len(pipeline.queued),
        "passes": passes,
        "passes_ok": passes == case["passes"],
        "rooms_ok": not wrong_rooms,
        "wrong_rooms": wrong_rooms,
        "reply": (run.reply or "")[:160],
        "status": run.status,
    }


async def run_all(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    cases = cases if cases is not None else load()
    settings = eval_settings()
    results = [await run_case(case, settings) for case in cases]
    total = len(results) or 1
    read_hits = sum(1 for item in results if item["read_ok"])
    decision_hits = sum(1 for item in results if item["decision_ok"])
    false_fits = sum(1 for item in results if item["false_fit"])
    brief_accuracy = round(read_hits / total, 3)
    decision_accuracy = round(decision_hits / total, 3)
    return {
        "cases": len(results),
        "brief_accuracy": brief_accuracy,
        "decision_accuracy": decision_accuracy,
        "false_fits": false_fits,
        "loop_accuracy": round(sum(1 for item in results if item["passes_ok"]) / total, 3),
        "room_errors": sum(len(item["wrong_rooms"]) for item in results),
        "recommendations": sum(1 for item in results if item["action"] == "recommend"),
        "handoffs": sum(1 for item in results if item["action"] == "handoff"),
        "fragile_recommended": sum(1 for item in results if item["action"] == "recommend" and item["fragile"]),
        "gate": false_fits <= MAX_FALSE_FITS and brief_accuracy >= MIN_BRIEF_ACCURACY and decision_accuracy >= MIN_DECISION_ACCURACY,
        "results": results,
    }


def format_report(report: dict[str, Any]) -> str:
    lines = [f"golden set: {report['cases']} briefs, {report['recommendations']} recommendations, {report['handoffs']} handoffs"]
    for item in report["results"]:
        flag = "ok  " if item["read_ok"] and item["decision_ok"] else "MISS"
        lines.append(
            f"  [{flag}] {item['id']:<26} {item['action'] or '-':<9} {item['sku'] or '-':<10} "
            f"verdict={item['verdict'] or '-':<9} {item['simulations']} sim(s) across {item['passes']} pass(es)"
        )
        for miss in [*item["read_misses"], *item["decision_misses"]]:
            lines.append(f"         {miss}")
        for measured in item["wrong_rooms"]:
            lines.append(f"         measured {measured} instead of the room the brief gave")
    lines.append(
        f"brief accuracy {report['brief_accuracy']:.2f} (gate {MIN_BRIEF_ACCURACY:.2f}) - "
        f"decision accuracy {report['decision_accuracy']:.2f} (gate {MIN_DECISION_ACCURACY:.2f}) - "
        f"false fits {report['false_fits']} (gate {MAX_FALSE_FITS}) - loop accuracy {report['loop_accuracy']:.2f}"
    )
    if report["fragile_recommended"]:
        lines.append(
            f"note: {report['fragile_recommended']} recommendation(s) fit on the stated numbers but not inside the "
            "survey tolerance; explain_fit says so to the shopper."
        )
    return "\n".join(lines)


def main() -> int:
    report = asyncio.run(run_all())
    print(format_report(report))
    return 0 if report["gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
