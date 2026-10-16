"""Shortlisting: which catalog SKUs are worth spending a simulation on.

Scoring is explainable and cheap - category, price band, must-have words, then smallest
footprint first, because a thing that can fit should be tested before a thing that cannot.
The verdict itself always comes from the geometry pipeline, never from here.
"""

from __future__ import annotations

import re

from byb_common.contracts import CatalogCandidate, ProductGeometry, ProductPart
from byb_common.parts import build_parts

BANDS = {"$": 1, "$$": 2, "$$$": 3}
DEFAULT_ROOM = (4.0, 3.5, 2.4)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def listing_url(row: dict) -> str:
    """A link the catalog resolver reads back as this same SKU, so a simulated product and a
    recommended product cannot drift apart."""
    words = " ".join(str(row.get(key) or "") for key in ("name", "category", "brand", "material"))
    return f"https://shop.example.com/p/{slugify(words)}/"


def score(row: dict, category: str | None, price_band: str | None, must_haves: list[str]) -> float:
    haystack = " ".join(str(row.get(key) or "") for key in ("name", "brand", "category", "material", "price_band")).lower()
    value = 0.0
    if category and str(row.get("category", "")).lower() == category.lower():
        value += 0.5
    elif category and category.split()[0] in haystack:
        value += 0.25
    if price_band and row.get("price_band") == price_band:
        value += 0.25
    hits = [word for word in must_haves if word in haystack]
    value += 0.15 * min(len(hits), 2)
    return min(value, 1.0)


def to_candidate(row: dict, value: float) -> CatalogCandidate:
    geometry = ProductGeometry.model_validate(row["geometry"])
    parts = [ProductPart.model_validate(part) for part in row.get("parts") or []]
    if not parts:
        parts = build_parts(str(row.get("category") or "furniture"), geometry.width_cm, geometry.depth_cm, geometry.height_cm)
    return CatalogCandidate(
        sku=str(row["sku"]),
        name=str(row["name"]),
        brand=str(row.get("brand") or ""),
        category=str(row.get("category") or "furniture"),
        material=row.get("material"),
        price_band=row.get("price_band"),
        geometry=geometry,
        parts=parts,
        score=round(value, 3),
        source="catalog",
    )


def rank(rows: list[dict], *, category: str | None, price_band: str | None, must_haves: list[str], limit: int, room=(4.0, 3.5)) -> list[tuple[dict, float]]:
    """Ranked by match, then by fit likelihood: a SKU wider than the room is last, not first."""
    width_m, depth_m = room
    scored = [(row, score(row, category, price_band, must_haves)) for row in rows]
    if category:
        scored = [pair for pair in scored if pair[1] > 0]

    def sort_key(pair: tuple[dict, float]) -> tuple[float, float, int]:
        row, value = pair
        geometry = row.get("geometry") or {}
        width_cm = float(geometry.get("width_cm") or 0)
        depth_cm = float(geometry.get("depth_cm") or 0)
        oversized = 1 if (width_cm / 100 > width_m - 0.9 or depth_cm / 100 > depth_m - 0.9) else 0
        band = BANDS.get(str(row.get("price_band")), 2)
        return (-value, oversized * 1e6 + width_cm * 10 + band, 0)

    return sorted(scored, key=sort_key)[:limit]
