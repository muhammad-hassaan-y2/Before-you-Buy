from conftest import StubModel

from byb_agent.brief import heuristic
from byb_agent.brief import read as read_brief
from byb_agent.model import extract_json


def test_reads_the_room_from_shopper_words():
    brief = heuristic("need a sofa for a 4.2 x 3.4 m room, ceilings 2.5 m")
    assert brief.category == "sofa"
    assert (brief.room_width_m, brief.room_depth_m) == (4.2, 3.4)
    assert brief.room_height_m == 2.5


def test_wider_number_becomes_the_width():
    brief = heuristic("my room is 3.4 by 4.2")
    assert brief.room_width_m == 4.2
    assert brief.room_depth_m == 3.4


def test_a_room_written_in_centimetres_is_still_the_room():
    assert heuristic("a shelf unit for a 220cm x 180cm hallway").room_width_m == 2.2
    brief = heuristic("a sofa for a room that is 420 cm by 340 cm")
    assert (brief.room_width_m, brief.room_depth_m) == (4.2, 3.4)


def test_budget_sets_the_price_band():
    assert heuristic("a bookcase under 400").price_band == "$"
    assert heuristic("bookcase under 1500").price_band == "$$"
    assert heuristic("bookcase under 5000").price_band == "$$$"


def test_words_of_taste_set_the_band_when_no_number_appears():
    assert heuristic("cheap desk for a first flat").price_band == "$"
    assert heuristic("a premium walnut dining table").price_band == "$$$"


def test_no_category_is_a_low_confidence_brief():
    brief = heuristic("something nice for the spare room")
    assert brief.category is None
    assert brief.confidence < 0.4


def test_must_haves_survive_the_read():
    brief = heuristic("extendable oak dining table for 6")
    assert "extendable" in brief.must_haves
    assert "oak" in brief.must_haves


async def test_the_model_fills_gaps_without_overwriting_the_shopper():
    model = StubModel(configured=True, data={"room_width_m": 9.9, "category": "armchair", "price_band": "$$$"})
    brief = await read_brief("a sofa 4.2 x 3.4 room", model)
    # The shopper typed the room and the product; the model only gets to add what was missing.
    assert brief.room_width_m == 4.2
    assert brief.category == "sofa"
    assert brief.price_band == "$$$"
    assert brief.source == "model"


async def test_an_unreachable_model_leaves_the_heuristics_in_charge():
    model = StubModel(configured=True, data=None)
    brief = await read_brief("a sofa for a 4 x 3 room", model)
    assert brief.source == "heuristic"
    assert brief.category == "sofa"


def test_json_survives_the_prose_models_insist_on():
    assert extract_json('{"category": "sofa"}') == {"category": "sofa"}
    assert extract_json('Here you go:\n```json\n{"category": "bed"}\n```') == {"category": "bed"}
    assert extract_json('answer: {"price_band": "$$"} done') == {"price_band": "$$"}
    assert extract_json("no object here") is None
