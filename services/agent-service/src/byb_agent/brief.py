"""Reading a shopper's brief.

Two readers, in a fixed order: heuristics first, because they are explainable and free, then
the AMD-hosted model for whatever the heuristics left blank. A number the shopper typed
themselves is never overwritten by a guess.
"""

from __future__ import annotations

import re

from byb_agent.contracts import ShopperBrief
from byb_agent.model import AMDModel

CATEGORIES = {
    "sofa": ("sofa", "couch", "settee", "3 seater", "three seater", "2 seater", "two seater"),
    "sectional": ("sectional", "corner sofa", "l-shape"),
    "armchair": ("armchair", "arm chair", "accent chair", "reading chair"),
    "bookcase": ("bookcase", "bookcase", "book shelf", "bookshelf"),
    "shelf": ("shelf", "shelves", "wall unit"),
    "tv unit": ("tv unit", "tv stand", "media unit", "credenza"),
    "sideboard": ("sideboard", "buffet", "server"),
    "cabinet": ("cabinet", "cupboard"),
    "wardrobe": ("wardrobe", "closet"),
    "bed": ("bed", "double bed", "queen bed", "king bed", "single bed"),
    "desk": ("desk", "writing desk", "computer desk"),
    "table": ("table", "dining table", "coffee table", "console table"),
    "stool": ("stool", "bar stool"),
    "ottoman": ("ottoman", "footstool", "pouffe"),
    "rug": ("rug", "carpet"),
}
BUDGET = re.compile(r"(?:under|below|max|maximum|up to|budget(?:\s+of)?|less than)\s*[^\d]{0,4}(\d{2,5})", re.I)
ROOM = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:m|meter|metre|meters|metres|x|by|\*)\s*(\d+(?:[.,]\d+)?)", re.I)
HEIGHT = re.compile(r"(?:ceilings?|height)\s*(?:of)?\s*(\d+(?:[.,]\d+)?)\s*(?:m|meter|metre|meters|metres)", re.I)
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
MUST_HAVES = {
    "solid wood": "solid wood",
    "oak": "oak",
    "extendable": "extendable",
    "storage": "storage",
    "pet friendly": "pet friendly",
    "small space": "small space",
}


def _metric(text: str) -> float:
    return float(NUMBER.search(text).group().replace(",", "."))


def heuristic(text: str) -> ShopperBrief:
    lowered = text.lower()
    category = None
    for name, needles in CATEGORIES.items():
        if any(needle in lowered for needle in needles):
            category = name
            break

    width_m = depth_m = height_m = None
    if match := ROOM.search(lowered):
        first, second = _metric(match.group(1)), _metric(match.group(2))
        # A room is written wide-first by most people; the larger of the two is the width.
        width_m, depth_m = max(first, second), min(first, second)
    if match := HEIGHT.search(lowered):
        height_m = _metric(match.group(1))

    budget = float(BUDGET.search(text).group(1)) if BUDGET.search(text) else None
    band = None
    if budget is not None:
        band = "$" if budget <= 600 else "$$" if budget <= 1800 else "$$$"
    elif any(word in lowered for word in ("cheap", "budget", "affordable", "first flat")):
        band = "$"
    elif any(word in lowered for word in ("premium", "designer", "solid", "walnut", "forever")):
        band = "$$$"

    return ShopperBrief(
        raw=text,
        category=category,
        price_band=band,
        budget_eur=budget,
        room_width_m=width_m,
        room_depth_m=depth_m,
        room_height_m=height_m,
        must_haves=[label for needle, label in MUST_HAVES.items() if needle in lowered],
        confidence=0.55 if category else 0.25,
        source="heuristic",
    )


PROMPT = """Read this furniture-shopping brief and return one JSON object.

Keys, all optional: category (one of {categories}), price_band ("$", "$$" or "$$$"),
budget_eur (number), room_width_m, room_depth_m, room_height_m (numbers, metres),
must_haves (array of short strings).
Omit a key rather than inventing a value.

BRIEF: {brief}"""


async def read(text: str, model: AMDModel) -> ShopperBrief:
    """Heuristics first, then the AMD-hosted model for the gaps only."""
    brief = heuristic(text)
    if not model.configured:
        return brief
    wanted = [key for key in ("category", "price_band", "room_width_m", "room_depth_m", "room_height_m") if getattr(brief, key) is None]
    if not wanted:
        return brief
    data = await model.read_json(PROMPT.replace("{categories}", ", ".join(sorted(CATEGORIES))).replace("{brief}", text))
    if not data:
        return brief
    for key in wanted:
        value = data.get(key)
        if value is None or value == "":
            continue
        if key in ("room_width_m", "room_depth_m", "room_height_m", "budget_eur"):
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if not 0.3 <= value <= 30:
                continue
        if key == "must_haves" and not isinstance(value, list):
            continue
        setattr(brief, key, value)
    if brief.category:
        brief.confidence = max(brief.confidence, 0.7)
    brief.source = "model"
    return brief
