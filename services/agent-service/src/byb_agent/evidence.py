"""What the fit evidence is worth once the verdict is in.

Three things the agent needs on top of a geometry engine to be a commerce tool rather than a
chatbot: reading a fit report back in words, judging several pieces as one purchase, and turning
a proven fit into a number a merchant can sign off on.

No language model decides anything here. The verdict is already the geometry engine's, the
combined verdict is arithmetic over the areas it reported, and the returns figure is stated
assumptions a reviewer can change. That is what keeps the forecasting honest.
"""

from __future__ import annotations

from typing import Any

from byb_agent.journey import PASS_VERDICTS, best_walkway

# Placeholder until the merchant's price feed is wired. The band always comes from the catalog,
# so the number is only ever used for the arithmetic, never claimed as a store price.
BAND_PRICE_EUR: dict[str, float] = {"$": 350.0, "$$": 750.0, "$$$": 1500.0}

# "It does not fit" is the reason most often given for a large-furniture return.
FIT_RETURN_SHARE = 0.67
HANDLING_COST_EUR = 10.0
DEFAULT_RETURN_RATE = 0.20
DEFAULT_PREVENTION = 0.25

OFFER_TTL_S = 12 * 60 * 60

HEADLINES = {
    "fits": "This piece fits the room.",
    "tight": "It fits, with no margin to spare.",
    "blocked": "It does not fit.",
    "too_large": "It is too large for this room.",
}


def explain(fit: dict[str, Any]) -> dict[str, Any]:
    """The facts a fit report carries, in the order a shopper should hear them."""
    verdict = str(fit.get("verdict") or "unknown")
    gaps = best_walkway(fit)
    tightest = round(min(gaps.values()), 2) if gaps else None
    tolerance = float(fit.get("tolerance_cm") or 2.0)
    suggestions = list(fit.get("suggestions") or [])

    why: list[str] = []
    placements = fit.get("placements") or []
    if placements:
        cleared = sum(1 for placement in placements if placement.get("fits"))
        why.append(f"{cleared} of {len(placements)} placements the engine tried clear the room; the verdict is {verdict}.")
    coverage = float(fit.get("coverage_pct") or 0.0)
    room_area = float(fit.get("room_area_m2") or 0.0)
    if coverage:
        tail = f" of the {round(room_area, 1)} m2 floor" if room_area else " of the floor"
        why.append(f"The piece covers {round(coverage, 1)}%{tail}.")
    if tightest is not None:
        why.append(f"The tightest walkway left around it is {tightest} m.")
    door = str(fit.get("door_pass") or "unknown")
    if door == "blocked":
        why.append("As measured, the box cannot get through the doorway, so delivery would fail before the room matters.")
    elif door == "tight":
        why.append(f"The doorway is inside the {tolerance:g} cm survey tolerance: measure the opening before ordering.")
    if fit.get("walkway_connected") is False:
        why.append("The entrance is cut off at that spot; no route stays walkable from the door.")
    pockets = int(fit.get("isolated_pockets") or 0)
    if pockets:
        why.append(f"That placement seals off {pockets} pocket(s) of floor behind it.")
    if fit.get("fragile"):
        why.append(f"It passes on these numbers and fails if reality is off by {tolerance:g} cm, so the room is worth measuring again.")
    why.extend(f"Conflict: {conflict}" for conflict in fit.get("conflicts") or [])

    headline = HEADLINES.get(verdict, f"The pipeline returned a {verdict} verdict.")
    parts = [headline, *why[:3]]
    if suggestions:
        parts.append(f"Do this: {suggestions[0]}.")
    return {
        "verdict": verdict,
        "coverage_pct": round(coverage, 1),
        "walkway_m": gaps,
        "tightest_walkway_m": tightest,
        "door_pass": door,
        "fragile": bool(fit.get("fragile")),
        "conflicts": list(fit.get("conflicts") or []),
        "suggestions": suggestions,
        "why": why,
        "plain": " ".join(parts),
    }


def footprint(fit: dict[str, Any], geometry: dict[str, Any] | None) -> tuple[float, bool]:
    """Floor area the piece takes, and whether it came from a placement the engine proved.

    The second value is the honesty flag: a footprint read off the catalog box is an upper
    bound, not a proof that the piece was placed there.
    """
    for placement in fit.get("placements") or []:
        if not placement.get("fits"):
            continue
        area = float(placement.get("footprint_m2") or 0.0)
        if area > 0:
            return round(area, 3), True
    geo = geometry or {}
    return round(float(geo.get("width_cm") or 0) * float(geo.get("depth_cm") or 0) / 10000.0, 3), False


def combine(pieces: list[dict[str, Any]], *, usable_area_m2: float, min_walkway_m: float, max_coverage: float) -> dict[str, Any]:
    """Several pieces as one purchase: the areas add up, the walkways are shared, the worst verdict wins.

    Not a combined layout search - the pipeline measures one product per simulation - so the
    verdict is deliberately conservative: the set only passes if every piece passes on its own,
    the footprints together leave the room liveable, and the tightest walkway still clears it.
    """
    blocked = [str(piece["sku"]) for piece in pieces if piece.get("verdict") not in PASS_VERDICTS]
    estimated = [str(piece["sku"]) for piece in pieces if not piece.get("placement_proved")]

    area = round(sum(float(piece.get("footprint_m2") or 0.0) for piece in pieces), 3)
    coverage = round(area / usable_area_m2 * 100, 1) if usable_area_m2 > 0 else 0.0
    walkways = [min(piece["walkway_m"].values()) for piece in pieces if piece.get("walkway_m")]
    tightest = round(min(walkways), 2) if walkways else None

    conflicts: list[str] = []
    if blocked:
        conflicts.append(f"{', '.join(blocked)} did not clear the room on its own.")
    if usable_area_m2 > 0 and coverage > max_coverage * 100:
        conflicts.append(f"The set covers {coverage}% of the usable floor, past the {round(max_coverage * 100)}% a room stays liveable at.")
    if tightest is not None and tightest < min_walkway_m:
        conflicts.append(f"The tightest walkway would be {tightest} m, under the {min_walkway_m} m a shopper has to reach the far side at.")

    verdict = "blocked" if blocked else ("tight" if conflicts else "fits")
    return {
        "verdict": verdict,
        "footprint_m2": area,
        "usable_area_m2": round(usable_area_m2, 2),
        "coverage_pct": coverage,
        "tightest_walkway_m": tightest,
        "conflicts": conflicts,
        "footprint_estimated_from_listing": estimated,
        "note": "Each piece was measured alone against this room; the set verdict adds the footprints and the walkways up, not a combined layout search.",
    }


def price_for(band: str | None, override: float | None = None) -> float:
    if override is not None:
        return round(float(override), 2)
    return BAND_PRICE_EUR.get(str(band), BAND_PRICE_EUR["$$"])


def returns_estimate(
    *,
    orders_per_month: float = 1000,
    price_eur: float | None = None,
    price_band: str | None = None,
    return_rate: float | None = None,
    fit_share: float | None = None,
    handling_cost_eur: float | None = None,
    prevention: float | None = None,
) -> dict[str, Any]:
    """Arithmetic on stated assumptions: what a fit check is worth, not a forecast of this shop's month."""
    rate = DEFAULT_RETURN_RATE if return_rate is None else float(return_rate)
    share = FIT_RETURN_SHARE if fit_share is None else float(fit_share)
    handling = HANDLING_COST_EUR if handling_cost_eur is None else float(handling_cost_eur)
    kept = DEFAULT_PREVENTION if prevention is None else float(prevention)
    unit = price_for(price_band, price_eur)

    orders = max(float(orders_per_month), 0.0)
    returns = orders * rate
    fit_returns = returns * share
    prevented = fit_returns * kept
    return {
        "orders_per_month": round(orders),
        "returns_per_month": round(returns),
        "fit_driven_returns_per_month": round(fit_returns),
        "returns_prevented_per_month": round(prevented, 1),
        "handling_saved_eur_per_month": round(prevented * handling, 2),
        "revenue_kept_eur_per_month": round(prevented * unit, 2),
        "per_simulation_value_eur": round((prevented * (unit + handling)) / orders, 4) if orders else 0.0,
        "assumptions": {
            "return_rate": round(rate, 3),
            "fit_driven_share_of_returns": round(share, 3),
            "handling_cost_eur_per_return": handling,
            "average_order_value_eur": unit,
            "share_of_fit_returns_prevented": round(kept, 3),
            "note": "Band prices stand in for the merchant feed until it is wired; every input above can be overridden by the caller.",
        },
    }
