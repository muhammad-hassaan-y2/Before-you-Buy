"""The golden set as a gate on the agent's judgement.

Same fifteen briefs as `byb_agent.eval`, run through the real journey with the pipeline replaced
by verdicts geometry-service re-derived in CI. Nothing here reaches the network: no Evolus key and
no model endpoint are configured, so what fails is the reading and the deciding, not the wiring.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from byb_agent.eval import MAX_FALSE_FITS, MIN_BRIEF_ACCURACY, MIN_DECISION_ACCURACY, load, run_all
from byb_agent.journey import PASS_VERDICTS


@pytest.fixture(scope="module")
def report() -> dict[str, Any]:
    return asyncio.run(run_all())


def result(report: dict[str, Any], case_id: str) -> dict[str, Any]:
    return next(item for item in report["results"] if item["id"] == case_id)


def golden_case(case_id: str) -> dict[str, Any]:
    return next(case for case in load() if case["id"] == case_id)


@pytest.mark.parametrize("case_id", [case["id"] for case in load()])
def test_each_brief_is_read_and_decided_as_the_labels_say(report, case_id: str) -> None:
    item = result(report, case_id)
    assert item["read_ok"], item["read_misses"]
    assert item["decision_ok"], item["decision_misses"]
    expected = golden_case(case_id)["passes"]
    assert item["passes_ok"], f"{case_id}: searched {item['passes']} pass(es), the golden set expects {expected}"


def test_the_agent_never_vouches_for_a_piece_the_engine_rejected(report) -> None:
    """The whole product is a fit claim a merchant can stand behind, so zero is the only number."""
    assert report["false_fits"] == MAX_FALSE_FITS


def test_every_recommendation_points_at_a_simulation(report) -> None:
    for item in report["results"]:
        if item["action"] == "recommend":
            assert item["verdict"] in PASS_VERDICTS, f"{item['id']} recommended {item['sku']} on a {item['verdict']}"


def test_only_the_room_the_shopper_described_is_measured(report) -> None:
    assert report["room_errors"] == 0


def test_the_gates_hold_as_one_number(report) -> None:
    assert report["brief_accuracy"] >= MIN_BRIEF_ACCURACY
    assert report["decision_accuracy"] >= MIN_DECISION_ACCURACY
    assert report["gate"] is True


def test_a_brief_that_names_no_piece_spends_no_simulation(report) -> None:
    item = result(report, "vague-living-room")
    assert item["action"] == "handoff"
    assert item["simulations"] == 0


def test_the_loop_is_a_boundary_not_a_forever(report) -> None:
    item = result(report, "nothing-clears-the-room")
    assert item["passes"] == 2
    assert item["action"] == "handoff"
