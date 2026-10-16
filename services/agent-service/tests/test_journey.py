from typing import Any

from conftest import StubEvolus, StubPipeline

from byb_agent.contracts import AgentRun, BriefRequest, FitAttempt, ShopperBrief
from byb_agent.journey import Journey, best_walkway, decide, plain_reply, widen


def brief(text: str = "a linen sofa for a 4.2 x 3.4 m room, budget 1200", **fields: Any) -> BriefRequest:
    return BriefRequest(brief=text, **fields)


def steps(run: AgentRun, kind: str) -> list[Any]:
    return [step for step in run.steps if step.kind == kind]


async def test_a_shopper_brief_comes_back_with_a_recommendation(pipeline, evolus, model, store, settings):
    finished = await Journey(pipeline, evolus, model, store, settings).run(brief())
    assert finished.status == "done"
    assert finished.decision.action == "recommend"
    assert finished.decision.sku in {"SOF-001", "SOF-002"}
    assert finished.reply.startswith("Good news:")
    assert [step.kind for step in finished.steps][:3] == ["intake", "agent", "brief"]


async def test_the_brief_is_read_before_anything_is_simulated(pipeline, evolus, model, store, settings):
    finished = await Journey(pipeline, evolus, model, store, settings).run(brief())
    read = steps(finished, "brief")[0]
    assert read.output["category"] == "sofa"
    assert read.output["room_width_m"] == 4.2
    assert read.tool == "heuristics", "no model endpoint is configured, so the trace must not claim one"


async def test_the_room_the_shopper_typed_is_the_room_that_is_tested(pipeline, evolus, model, store, settings):
    await Journey(pipeline, evolus, model, store, settings).run(brief())
    assert pipeline.started, "the agent must have queued work"
    assert {run["room"] for run in pipeline.started} == {(4.2, 3.4, 2.4)}


async def test_candidates_are_evaluated_in_parallel_and_tagged_with_their_pass(pipeline, evolus, model, store, settings):
    finished = await Journey(pipeline, evolus, model, store, settings).run(brief())
    fits = steps(finished, "fit")
    assert len(fits) == len(pipeline.started) <= settings.max_candidates
    assert {step.group for step in fits} == {"pass-1"}
    assert {step.iteration for step in fits} == {1}
    assert "parallel" in steps(finished, "simulate")[0].detail


async def test_a_fit_in_the_first_pass_ends_the_loop(pipeline, evolus, model, store, settings):
    finished = await Journey(pipeline, evolus, model, store, settings).run(brief())
    assert not steps(finished, "branch")
    assert {step.iteration for step in steps(finished, "fit")} == {1}


async def test_a_blocked_room_widens_the_band_once_then_loops(rows, evolus, model, store, settings):
    pipeline = StubPipeline(rows, verdicts={"default": "blocked"})
    finished = await Journey(pipeline, evolus, model, store, settings).run(brief("a linen sofa for a 4.2 x 3.4 room, budget 1500"))
    branch = steps(finished, "branch")
    assert branch, "the widening decision has to be visible in the trace"
    assert "widening" in branch[0].detail
    assert {step.iteration for step in steps(finished, "fit")} == {1, 2}
    assert finished.brief.price_band == "$$", "the trace keeps the band the shopper asked for, not the widened one"
    assert finished.decision.action == "handoff"


async def test_a_too_large_room_hands_the_case_to_a_person(rows, evolus, model, store, settings):
    pipeline = StubPipeline(rows, verdicts={"default": "too_large"})
    finished = await Journey(pipeline, evolus, model, store, settings).run(brief())
    assert finished.status == "awaiting_human"
    assert finished.decision.evidence["blocked"]


async def test_a_vague_brief_spends_no_simulations(pipeline, evolus, model, store, settings):
    finished = await Journey(pipeline, evolus, model, store, settings).run(brief("something nice for the spare room"))
    assert finished.status == "awaiting_human"
    assert pipeline.started == []
    assert steps(finished, "branch")[0].status == "branch"


async def test_a_stalled_candidate_is_a_result_not_a_crash(rows, evolus, model, store, settings):
    pipeline = StubPipeline(rows, verdicts={"default": "fits"}, crash={"SOF-002"})
    finished = await Journey(pipeline, evolus, model, store, settings).run(brief("a sofa for a 4.2 x 3.4 room under 600"))
    failed = [step for step in steps(finished, "fit") if step.status == "failed"]
    assert failed, "a crashed candidate must show up as failed, not vanish"
    assert failed[0].output["reason"] == "geometry-service unavailable"


async def test_the_agent_is_told_about_the_case_before_it_is_worked(pipeline, evolus, model, store, settings):
    finished = await Journey(pipeline, evolus, model, store, settings).run(brief())
    assert steps(finished, "agent")[0].status == "ok"
    assert finished.conversation_id == "conv-9"
    assert "Shopper brief" in evolus.prompts[0]


async def test_an_unreachable_evolus_does_not_stop_the_fit_search(pipeline, model, store, settings):
    finished = await Journey(pipeline, StubEvolus(fail=True), model, store, settings).run(brief())
    assert steps(finished, "agent")[0].status == "failed"
    assert finished.status == "done"
    assert finished.decision.action == "recommend"


async def test_no_evolus_credentials_are_recorded_as_skipped(pipeline, model, store, settings):
    finished = await Journey(pipeline, StubEvolus(credentials=False), model, store, settings).run(brief())
    assert steps(finished, "agent")[0].status == "skipped"


async def test_an_evolus_ai_tool_polishes_the_reply(rows, model, store, settings):
    settings.evolus_reply_tool = "email_write"
    evolus = StubEvolus()
    finished = await Journey(StubPipeline(rows), evolus, model, store, settings).run(brief())
    assert evolus.tools == ["email_write"]
    assert finished.reply.startswith("[email_write]")


async def test_a_failed_ai_tool_leaves_the_agents_own_wording(rows, model, store, settings):
    settings.evolus_reply_tool = "email_write"
    finished = await Journey(StubPipeline(rows), StubEvolus(fail=True), model, store, settings).run(brief())
    assert finished.reply.startswith("Good news:")


def test_the_widen_step_only_goes_downhill():
    assert widen("$$") == "$"
    assert widen("$") is None
    assert widen(None) is None


def test_fits_beats_tight_even_when_the_tight_one_matched_better():
    attempts = [
        FitAttempt(sku="TIGHT", name="Tight one", score=0.9, verdict="tight", walkway_m={"left": 0.4}),
        FitAttempt(sku="FITS", name="Roomy one", score=0.4, verdict="fits", walkway_m={"left": 1.1, "right": 1.2}),
    ]
    decision = decide(attempts, ShopperBrief(raw="sofa"), "$$")
    assert decision.action == "recommend"
    assert decision.sku == "FITS"


def test_the_evidence_shown_is_the_roomiest_placement_that_fits():
    fit = {
        "placements": [
            {"fits": True, "walkway_m": {"left": 0.3, "right": 0.3}},
            {"fits": True, "walkway_m": {"left": 1.0, "right": 0.9}},
            {"fits": False, "walkway_m": {"left": 5.0, "right": 5.0}},
        ]
    }
    assert best_walkway(fit) == {"left": 1.0, "right": 0.9}


def test_a_recommendation_quotes_the_numbers_a_shopper_asks_about():
    decision = decide(
        [FitAttempt(sku="SOF-002", name="Compact two-seater sofa", verdict="fits", coverage_pct=11.0, walkway_m={"front": 0.86, "left": 1.2})],
        ShopperBrief(raw="sofa"),
        "$",
    )
    text = plain_reply(decision, None)
    assert "Compact two-seater sofa" in text
    assert "11.0%" in text
    assert "0.86 m" in text


def test_an_untestable_room_says_so_instead_of_recommending_nothing():
    decision = decide([], ShopperBrief(raw="sofa", confidence=0.8), "$")
    assert decision.action == "handoff"
    assert "could not be evaluated" in decision.reason
