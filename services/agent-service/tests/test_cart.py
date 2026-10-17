"""The bag, the measured bag and the order a shopper's own yes releases.

The cart is where fit assurance stops being advice: a piece can be in a bag and still be
unproven, and nothing may be sold that way. Each test therefore checks the gate as well as the
arithmetic - and that the price on a line is the one the shop itself lists.
"""

import pytest
from conftest import StubEvolus, StubModel, StubPipeline

from byb_agent.pipeline import PipelineError
from byb_agent.runs import Carts, Orders, Reservations, RunStore
from byb_agent.tools import Tools


def build(rows, settings, verdicts=None, crash=None, carts=None, orders=None):
    pipeline = StubPipeline(rows, verdicts=verdicts, crash=crash or set())
    # An empty store is falsy, so a passed one has to be compared with None, not `or`.
    tools = Tools(
        pipeline,
        StubEvolus(),
        StubModel(),
        RunStore(),
        settings,
        Reservations(),
        carts if carts is not None else Carts(),
        orders if orders is not None else Orders(),
    )
    return tools, pipeline


def listed(row: dict, retail: float, cost: float, lead: int, freight: str, volume: float) -> dict:
    """A catalog row with the shop's own terms on it, as catalog-service sends them."""
    return {**row, "commerce": {"currency": "EUR", "retail_eur": retail, "cost_eur": cost, "lead_days": lead, "freight": freight, "volume_m3": volume}}


@pytest.fixture
def shelf(rows):
    return [
        listed(rows[0], 899.0, 503.0, 18, "pallet", 0.4),
        listed(rows[1], 349.0, 195.0, 15, "pallet", 0.3),
        listed(rows[2], 1449.0, 840.0, 24, "pallet", 0.9),
        listed(rows[3], 549.0, 285.0, 13, "parcel", 0.2),
    ]


async def fitted(tools, sku: str) -> str:
    return (await tools.simulate_product(sku=sku))["attempt"]["simulation_id"]


async def test_a_bag_starts_with_one_line_at_the_shops_own_price(shelf, settings):
    tools, _ = build(shelf, settings)
    bag = await tools.add_to_cart(sku="SOF-001")
    assert bag["room"] == {"width_m": 4.0, "depth_m": 3.5, "height_m": 2.4}
    assert [line["price_eur"] for line in bag["lines"]] == [899.0], "the cart quotes the listing, not a band guess"
    assert bag["total_eur"] == 899.0 and bag["cost_eur"] == 503.0 and bag["margin_eur"] == 396.0
    assert bag["unproven"] == ["SOF-001"], "in the bag is not the same claim as measured to fit"
    assert bag["checkout"]["ready"] is False


async def test_a_fit_the_engine_cleared_makes_the_bag_ready(shelf, settings):
    tools, _ = build(shelf, settings)
    simulation_id = await fitted(tools, "SOF-001")
    bag = await tools.add_to_cart(sku="SOF-001", simulation_id=simulation_id)
    assert bag["unproven"] == []
    assert bag["checkout"]["ready"] is True
    line = bag["lines"][0]
    assert line["verdict"] == "fits" and line["simulation_id"] == simulation_id
    assert line["footprint_m2"] == pytest.approx(2.09), "the placed footprint, not the box"


async def test_the_same_piece_added_twice_raises_the_quantity_not_the_lines(shelf, settings):
    tools, pipeline = build(shelf, settings)
    first = await tools.add_to_cart(sku="SOF-001")
    again = await tools.add_to_cart(sku="SOF-001", cart_id=first["cart_id"], quantity=2)
    assert len(again["lines"]) == 1 and again["items"] == 2
    assert again["total_eur"] == 1798.0 and again["volume_m3"] == pytest.approx(0.8)
    assert pipeline.started == [], "filling a bag is free; measuring it is not"


async def test_measuring_a_bag_spends_one_fit_per_unproven_line(shelf, settings):
    tools, pipeline = build(shelf, settings)
    bag = await tools.add_to_cart(sku="SOF-001")
    bag = await tools.add_to_cart(sku="ARM-001", cart_id=bag["cart_id"])
    measured = await tools.measure_cart(bag["cart_id"])
    assert len(pipeline.started) == 2
    assert {piece["sku"] for piece in measured["measured"]} == {"SOF-001", "ARM-001"}
    assert measured["unproven"] == []
    assert measured["set"]["verdict"] == "fits"
    assert measured["set"]["footprint_m2"] == pytest.approx(2.69), "the two placed footprints, added"
    assert measured["set"]["usable_area_m2"] == 13.3


async def test_a_bag_is_judged_as_one_purchase_not_as_two_separate_rooms(shelf, settings):
    settings.max_joint_coverage = 0.15
    tools, _ = build(shelf, settings)
    bag = await tools.add_to_cart(sku="SOF-001")
    bag = await tools.add_to_cart(sku="ARM-001", cart_id=bag["cart_id"])
    measured = await tools.measure_cart(bag["cart_id"])
    assert measured["set"]["verdict"] == "tight"
    assert any("past the 15% a room stays liveable at" in line for line in measured["set"]["conflicts"])


async def test_the_bag_holds_one_room_and_re_measures_a_proof_from_another(shelf, settings):
    tools, pipeline = build(shelf, settings)
    bag = await tools.add_to_cart(sku="SOF-001")
    measured = await tools.measure_cart(bag["cart_id"])
    assert measured["already_proven"] == [], "the first pass measures everything"
    assert len(pipeline.started) == 1

    moved = await tools.measure_cart(bag["cart_id"], room_width_m=3.2, room_depth_m=2.8)
    assert len(pipeline.started) == 2, "a proof for a 4.0 m room says nothing about a 3.2 m one"
    assert moved["room"] == {"width_m": 3.2, "depth_m": 2.8, "height_m": 2.4}
    assert all(line["room"] == moved["room"] for line in moved["lines"])


async def test_a_measured_bag_is_not_measured_again(shelf, settings):
    tools, pipeline = build(shelf, settings)
    bag = await tools.add_to_cart(sku="SOF-001")
    await tools.measure_cart(bag["cart_id"])
    again = await tools.measure_cart(bag["cart_id"])
    assert len(pipeline.started) == 1, "each GPU job is the merchant's, so a settled line is left alone"
    assert again["measured"] == [] and again["already_proven"] == ["SOF-001"]


async def test_a_photo_measures_the_bag_it_was_asked_about(shelf, settings):
    tools, pipeline = build(shelf, settings)
    bag = await tools.add_to_cart(sku="SOF-001")
    photo = f"{'ab' * 16}-living-room.jpg"
    measured = await tools.measure_cart(bag["cart_id"], image_key=photo)
    assert {run["image_key"] for run in pipeline.started} == {photo}
    assert measured["lines"][0]["verdict"] == "fits"
    assert measured["lines"][0]["room"] == measured["room"], "the photo room becomes the bag's room"


async def test_checkout_refuses_an_agents_assumed_yes(shelf, settings):
    orders = Orders()
    tools, _ = build(shelf, settings, orders=orders)
    bag = await tools.add_to_cart(sku="SOF-001", simulation_id=await fitted(tools, "SOF-001"))
    with pytest.raises(ValueError, match="own yes"):
        await tools.checkout(bag["cart_id"], "the shopper was very keen on it")
    assert len(orders) == 0


async def test_checkout_refuses_a_bag_with_an_unproven_line(shelf, settings):
    tools, _ = build(shelf, settings)
    bag = await tools.add_to_cart(sku="SOF-001", simulation_id=await fitted(tools, "SOF-001"))
    bag = await tools.add_to_cart(sku="ARM-001", cart_id=bag["cart_id"])
    with pytest.raises(ValueError, match="nothing is sold unchecked") as refused:
        await tools.checkout(bag["cart_id"], "yes, place the order")
    assert "ARM-001" in str(refused.value)
    assert "measure_cart" in str(refused.value)


async def test_a_piece_the_engine_blocked_can_be_bagged_but_never_ordered(shelf, settings):
    tools, _ = build(shelf, settings, verdicts={"SOF-003": "blocked"})
    bag = await tools.add_to_cart(sku="SOF-001", simulation_id=await fitted(tools, "SOF-001"))
    bag = await tools.add_to_cart(sku="SOF-003", cart_id=bag["cart_id"])
    measured = await tools.measure_cart(bag["cart_id"])
    assert measured["unproven"] == ["SOF-003"], "a blocked verdict is not a fit the bag can be sold on"
    assert measured["set"]["verdict"] == "blocked"
    with pytest.raises(ValueError, match="nothing is sold unchecked"):
        await tools.checkout(bag["cart_id"], "yes")


async def test_a_confirmed_order_is_a_draft_with_its_proofs(shelf, settings):
    orders = Orders()
    tools, _ = build(shelf, settings, orders=orders)
    simulation_id = await fitted(tools, "SOF-001")
    bag = await tools.add_to_cart(sku="SOF-001", simulation_id=simulation_id)
    placed = await tools.checkout(bag["cart_id"], "yes, place the order")

    assert placed["status"] == "awaiting_merchant"
    assert placed["confirmation"] == "yes, place the order"
    assert placed["total_eur"] == 899.0 and placed["margin_eur"] == 396.0
    assert placed["lead_days"] == 18 and placed["freight"] == "pallet"
    assert placed["proofs"][0]["simulation_id"] == simulation_id
    assert placed["proofs"][0]["verify"] == f"/api/v1/simulations/{simulation_id}"
    assert placed["combined"]["verdict"] == "fits"
    assert orders.get(placed["id"]) is not None
    assert [item["id"] for item in tools.list_orders()] == [placed["id"]]


async def test_the_quantity_ordered_is_the_quantity_priced(shelf, settings):
    tools, _ = build(shelf, settings)
    bag = await tools.add_to_cart(sku="SOF-002", simulation_id=await fitted(tools, "SOF-002"))
    bag = await tools.add_to_cart(sku="SOF-002", cart_id=bag["cart_id"], quantity=3)
    placed = await tools.checkout(bag["cart_id"], "yes")
    assert placed["lines"][0]["quantity"] == 3
    assert placed["total_eur"] == 1047.0 == 349.0 * 3
    assert placed["combined"]["footprint_m2"] == pytest.approx(3 * 1.408), "three of a piece take three of its floor"


async def test_a_piece_comes_out_of_the_bag_and_an_unknown_one_is_refused(shelf, settings):
    tools, _ = build(shelf, settings)
    bag = await tools.add_to_cart(sku="SOF-001")
    bag = await tools.add_to_cart(sku="ARM-001", cart_id=bag["cart_id"])
    trimmed = await tools.remove_from_cart(bag["cart_id"], "SOF-001")
    assert [line["sku"] for line in trimmed["lines"]] == ["ARM-001"]
    with pytest.raises(ValueError, match="not in cart"):
        await tools.remove_from_cart(bag["cart_id"], "SOF-001")


async def test_a_bag_is_bounded_because_every_line_costs_a_fit(shelf, settings):
    settings.max_cart_lines = 2
    tools, pipeline = build(shelf, settings)
    bag = await tools.add_to_cart(sku="SOF-001")
    bag = await tools.add_to_cart(sku="ARM-001", cart_id=bag["cart_id"])
    with pytest.raises(ValueError, match="at most 2 pieces"):
        await tools.add_to_cart(sku="SOF-002", cart_id=bag["cart_id"])
    assert len(pipeline.started) == 0, "a bag is filled without spending a measurement until it is measured"


async def test_a_stale_bag_id_is_said_rather_than_silently_replaced(shelf, settings):
    tools, _ = build(shelf, settings)
    with pytest.raises(ValueError, match="not in this process"):
        await tools.add_to_cart(sku="SOF-001", cart_id="deadbeefdeadbeef")
    with pytest.raises(ValueError, match="unknown cart"):
        await tools.view_cart("deadbeefdeadbeef")
    with pytest.raises(ValueError, match="unknown order"):
        await tools.order_status("deadbeefdeadbeef")


async def test_an_empty_bag_is_refused_before_a_fit_is_spent(shelf, settings):
    tools, pipeline = build(shelf, settings)
    bag = await tools.add_to_cart(sku="SOF-001")
    await tools.remove_from_cart(bag["cart_id"], "SOF-001")
    with pytest.raises(ValueError, match="empty"):
        await tools.measure_cart(bag["cart_id"])
    with pytest.raises(ValueError, match="empty"):
        await tools.checkout(bag["cart_id"], "yes")
    assert pipeline.started == []


async def test_an_order_takes_its_units_off_the_shelf(shelf, settings):
    tools, pipeline = build(shelf, settings)
    bag = await tools.add_to_cart(sku="SOF-001", simulation_id=await fitted(tools, "SOF-001"))
    bag = await tools.add_to_cart(
        sku="SOF-002", cart_id=bag["cart_id"], quantity=2, simulation_id=await fitted(tools, "SOF-002")
    )
    placed = await tools.checkout(bag["cart_id"], "yes, order it")

    assert placed["stock"]["claimed"] is True
    assert pipeline.claims[0]["key"] == f"order:{placed['id']}"
    assert pipeline.claims[0]["lines"] == [{"sku": "SOF-001", "qty": 1}, {"sku": "SOF-002", "qty": 2}]


async def test_a_bag_the_shop_cannot_supply_is_refused_by_the_shelf(shelf, settings):
    tools, pipeline = build(shelf, settings)
    bag = await tools.add_to_cart(sku="SOF-001", simulation_id=await fitted(tools, "SOF-001"))
    pipeline.short.add("SOF-001")
    with pytest.raises(ValueError, match="cannot supply"):
        await tools.checkout(bag["cart_id"], "yes, order it")
    assert pipeline.claims == [], "an order that never happened claims nothing"


async def test_an_unreachable_shelf_is_said_rather_than_read_as_empty(shelf, settings):
    tools, pipeline = build(shelf, settings)
    bag = await tools.add_to_cart(sku="SOF-001", simulation_id=await fitted(tools, "SOF-001"))

    async def down(**_kwargs):
        raise PipelineError("could not reach the shelf: connection refused")

    pipeline.claim_stock = down
    placed = await tools.checkout(bag["cart_id"], "yes, order it")
    assert placed["stock"]["claimed"] is False
    assert "connection refused" in placed["stock"]["why"], "a count nobody read is not a zero"
