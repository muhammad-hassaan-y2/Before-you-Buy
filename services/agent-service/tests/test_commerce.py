"""The capabilities that turn a fit verdict into a commercial decision.

Each one is checked at the tool layer, because a shopper's offer, a hold and a business number
have to read the same fit report the widget shows - not a second version of it.
"""

import pytest
from conftest import StubEvolus, StubModel, StubPipeline

from byb_agent import evidence
from byb_agent.runs import Reservations, RunStore
from byb_agent.tools import Tools


def build(rows, settings, verdicts=None, crash=None, reservations=None):
    pipeline = StubPipeline(rows, verdicts=verdicts, crash=crash or set())
    # An empty store is falsy, so the passed one has to be checked against None, not `or`.
    tools = Tools(pipeline, StubEvolus(), StubModel(), RunStore(), settings, reservations if reservations is not None else Reservations())
    return tools, pipeline


async def fitted(tools, sku: str) -> str:
    """A simulation id for a product the pipeline has already measured."""
    return (await tools.simulate_product(sku=sku))["attempt"]["simulation_id"]


async def test_a_verdict_is_read_back_as_facts_a_shopper_can_use(rows, settings):
    tools, _ = build(rows, settings)
    report = await tools.explain_fit(await fitted(tools, "SOF-001"))
    assert report["verdict"] == "fits"
    assert report["tightest_walkway_m"] == 0.7
    assert report["door_pass"] == "pass"
    assert any("placements the engine tried" in line for line in report["why"])
    assert report["plain"].startswith("This piece fits the room.")


async def test_the_explanation_names_the_delivery_path_and_the_fix(rows, settings):
    tools, _ = build(rows, settings, verdicts={"SOF-003": "blocked"})
    report = await tools.explain_fit(await fitted(tools, "SOF-003"))
    assert report["walkway_m"] == {}, "no placement fits, so no walkway is quoted"
    assert any("cannot get through the doorway" in line for line in report["why"])
    assert report["plain"].endswith("Do this: try a piece no wider than 180 cm.")


async def test_a_simulation_with_no_verdict_has_nothing_to_explain(rows, settings):
    tools, _ = build(rows, settings, crash={"SOF-001"})
    with pytest.raises(ValueError, match="no fit report"):
        await tools.explain_fit(await fitted(tools, "SOF-001"))


def test_a_margin_too_thin_to_trust_is_said_out_loud():
    report = evidence.explain(
        {
            "verdict": "fits",
            "coverage_pct": 8.0,
            "placements": [{"label": "back wall", "fits": True, "footprint_m2": 1.0, "walkway_m": {"front": 0.62}}],
            "fragile": True,
            "tolerance_cm": 2.0,
            "door_pass": "tight",
        }
    )
    assert report["tightest_walkway_m"] == 0.62
    assert any("off by 2 cm" in line for line in report["why"])
    assert any("measure the opening" in line for line in report["why"])


async def test_two_pieces_are_measured_and_added_up(rows, settings):
    tools, pipeline = build(rows, settings)
    result = await tools.joint_fit(["SOF-001", "ARM-001"], room_width_m=4.2, room_depth_m=3.4)
    assert [piece["sku"] for piece in result["pieces"]] == ["SOF-001", "ARM-001"]
    assert result["combined"]["footprint_m2"] == 2.69
    assert result["combined"]["verdict"] == "fits"
    assert all(piece["placement_proved"] for piece in result["pieces"])
    assert len(pipeline.started) == 2, "every piece in the set gets its own measurement"


async def test_one_piece_that_does_not_clear_the_room_blocks_the_set(rows, settings):
    tools, _ = build(rows, settings, verdicts={"SOF-003": "too_large"})
    result = await tools.joint_fit(["SOF-001", "SOF-003"])
    assert result["combined"]["verdict"] == "blocked"
    assert "SOF-003 did not clear the room on its own." in result["combined"]["conflicts"]


async def test_a_set_that_uses_too_much_floor_is_called_tight_not_fit(rows, settings):
    settings.max_joint_coverage = 0.1
    tools, _ = build(rows, settings)
    result = await tools.joint_fit(["SOF-001", "SOF-003"])
    assert result["combined"]["verdict"] == "tight"
    assert any("past the 10% a room stays liveable at" in line for line in result["combined"]["conflicts"])


async def test_a_lone_piece_is_sent_back_to_the_single_product_tool(rows, settings):
    tools, _ = build(rows, settings)
    with pytest.raises(ValueError, match="two or more"):
        await tools.joint_fit(["SOF-001"])


async def test_an_invented_sku_is_refused_before_a_simulation_is_spent(rows, settings):
    tools, pipeline = build(rows, settings)
    with pytest.raises(ValueError, match="catalog_search"):
        await tools.joint_fit(["SOF-001", "NOPE-999"])
    assert pipeline.started == []


async def test_a_long_wishlist_is_capped_at_the_configured_pieces(rows, settings):
    tools, pipeline = build(rows, settings)
    wanted = ["SOF-001", "SOF-002", "SOF-003", "ARM-001", "BCK-001"]
    result = await tools.joint_fit(wanted)
    assert result["requested"] == wanted
    assert result["tested"] == wanted[: settings.max_joint_pieces]
    assert len(pipeline.started) == settings.max_joint_pieces


async def test_an_offer_carries_the_proof_next_to_the_price(rows, settings):
    tools, _ = build(rows, settings)
    simulation_id = await fitted(tools, "SOF-001")
    offer = await tools.proven_fit_offer(simulation_id)
    assert offer["offer"]["sku"] == "SOF-001"
    assert offer["offer"]["price_band"] == "$$"
    assert offer["offer"]["price_eur"] == 750.0
    assert offer["fit_evidence"]["verdict"] == "fits"
    assert offer["fit_evidence"]["verify"] == f"/api/v1/simulations/{simulation_id}"
    assert offer["fit_evidence"]["model_download"] == f"/api/v1/simulations/{simulation_id}/model"
    assert offer["assurance"]["covered_return_reason"] == "does_not_fit"
    assert offer["reserve"]["tool"] == "reserve_fit"


async def test_nothing_the_engine_did_not_prove_is_offered(rows, settings):
    tools, _ = build(rows, settings, verdicts={"SOF-003": "blocked"})
    with pytest.raises(ValueError, match="no offer"):
        await tools.proven_fit_offer(await fitted(tools, "SOF-003"))


async def test_a_hold_needs_the_shoppers_own_yes_not_an_agents_guess(rows, settings):
    reservations = Reservations()
    tools, _ = build(rows, settings, reservations=reservations)
    simulation_id = await fitted(tools, "SOF-001")
    with pytest.raises(ValueError, match="own yes"):
        await tools.reserve_fit(simulation_id, "the shopper seemed keen")
    assert len(reservations) == 0


async def test_a_confirmed_hold_is_recorded_for_a_person_to_accept(rows, settings):
    reservations = Reservations()
    tools, _ = build(rows, settings, reservations=reservations)
    simulation_id = await fitted(tools, "SOF-001")
    held = await tools.reserve_fit(simulation_id, "yes, hold it")
    assert held["status"] == "pending_merchant"
    assert held["sku"] == "SOF-001"
    assert held["holds_until"] > held["created_at"]
    assert reservations.get(held["id"]).confirmation == "yes, hold it"
    assert [item["id"] for item in tools.list_reservations()] == [held["id"]]


async def test_a_piece_the_pipeline_never_placed_cannot_be_held(rows, settings):
    tools, _ = build(rows, settings, crash={"SOF-001"})
    with pytest.raises(ValueError, match="nothing to hold"):
        await tools.reserve_fit(await fitted(tools, "SOF-001"), "yes")


async def test_the_business_case_is_arithmetic_a_reviewer_can_check(rows, settings):
    tools, _ = build(rows, settings)
    figures = await tools.returns_estimate(orders_per_month=1000)
    assert figures["fit_driven_returns_per_month"] == 134
    assert figures["returns_prevented_per_month"] == 33.5
    assert figures["handling_saved_eur_per_month"] == 335.0
    assert figures["revenue_kept_eur_per_month"] == 25125.0
    assert figures["assumptions"]["fit_driven_share_of_returns"] == pytest.approx(0.67)
    assert "stand in for the merchant feed" in figures["assumptions"]["note"]


async def test_a_merchants_own_numbers_replace_the_defaults(rows, settings):
    tools, _ = build(rows, settings)
    figures = await tools.returns_estimate(orders_per_month=500, price_eur=900, return_rate=0.4, prevention=0.5)
    assert figures["returns_prevented_per_month"] == 67.0
    assert figures["revenue_kept_eur_per_month"] == 60300.0
    assert figures["assumptions"]["average_order_value_eur"] == 900.0
    assert figures["assumptions"]["return_rate"] == 0.4


async def test_which_of_the_catalog_fits_is_measured_not_guessed(rows, settings):
    tools, pipeline = build(rows, settings, verdicts={"SOF-003": "blocked"})
    answer = await tools.fit_catalog(category="sofa", room_width_m=4.0, room_depth_m=3.5, limit=3)
    assert {piece["sku"] for piece in answer["fits"]} == {"SOF-001", "SOF-002"}
    assert [piece["sku"] for piece in answer["does_not_fit"]] == ["SOF-003"]
    assert answer["unproven"] == []
    assert answer["checked"] == len(pipeline.started) == 3
    # The sizes an agent quotes come from the catalog row, the verdict from the engine.
    assert answer["fits"][0]["size_cm"] == {"width_cm": 160, "depth_cm": 88, "height_cm": 80}
    assert all(set(piece["size_cm"]) == {"width_cm", "depth_cm", "height_cm"} for piece in answer["fits"])
    assert all(piece["verify"] for piece in answer["fits"])


async def test_a_piece_that_never_settled_is_reported_as_unproven(rows, settings):
    tools, _ = build(rows, settings, crash={"SOF-002"})
    answer = await tools.fit_catalog(category="sofa", limit=3)
    assert [piece["sku"] for piece in answer["unproven"]] == ["SOF-002"]
    assert all(piece["sku"] != "SOF-002" for piece in answer["fits"]), "a crash is not a fit"


async def test_a_sweep_is_capped_because_every_fit_costs_a_gpu_job(rows, settings):
    settings.max_catalog_fits = 2
    tools, pipeline = build(rows, settings)
    answer = await tools.fit_catalog(limit=50)
    assert answer["checked"] == 2 == len(pipeline.started)


async def test_a_photo_room_is_swept_as_the_measured_room(rows, settings):
    tools, pipeline = build(rows, settings)
    photo = f"{'ab' * 16}-living-room.jpg"
    answer = await tools.fit_catalog(category="sofa", image_key=photo, limit=2)
    assert answer["room"]["measured_from_photo"] is True
    assert {run["image_key"] for run in pipeline.started} == {photo}


async def test_a_hold_takes_its_unit_off_the_shelf(rows, settings):
    tools, pipeline = build(rows, settings)
    held = await tools.reserve_fit(await fitted(tools, "SOF-001"), "yes, hold it")
    assert held["stock"]["claimed"] is True
    assert pipeline.claims[0]["key"] == f"hold:{held['id']}"
    assert pipeline.claims[0]["lines"] == [{"sku": "SOF-001", "qty": 1}]


async def test_a_hold_the_shelf_refuses_is_not_written(rows, settings):
    tools, pipeline = build(rows, settings)
    simulation_id = await fitted(tools, "SOF-001")
    pipeline.short.add("SOF-001")
    with pytest.raises(ValueError, match="cannot supply"):
        await tools.reserve_fit(simulation_id, "yes, hold it")
    assert tools.list_reservations() == []


async def test_the_sweep_hands_over_each_verdict_the_moment_it_settles(rows, settings):
    tools, _ = build(rows, settings)
    events = [event async for event in tools.sweep(category="sofa", limit=3)]

    assert events[0]["event"] == "start" and events[0]["total"] == 3
    verdicts = [event for event in events if event["event"] == "verdict"]
    assert [event["of"] for event in verdicts] == [1, 2, 3], "one event per piece, as it lands"
    assert all({"sku", "verdict", "simulation_id"} <= set(event) for event in verdicts)
    done = events[-1]
    assert done["event"] == "done" and done["checked"] == 3
    assert len(done["fits"]) + len(done["does_not_fit"]) + len(done["unproven"]) == 3


async def test_the_streamed_sweep_and_the_tool_answer_are_the_one_sweep(rows, settings):
    tools, _ = build(rows, settings)
    answer = await tools.fit_catalog(category="sofa", limit=3)
    streamed = [event async for event in tools.sweep(category="sofa", limit=3)]
    measured = {event["sku"] for event in streamed if event["event"] == "verdict"}
    assert measured == {item["sku"] for item in answer["fits"] + answer["does_not_fit"] + answer["unproven"]}
