"""Bridge the metres-based contract onto the centimetre fit engine and read back what only it checks.

`layout.py` already decides whether the footprint lands on free floor. This adds the two
questions a shopper actually gets charged for: whether the box can be carried in through the
door at all, and whether the room is still walkable once it stands there - plus the tolerance
view of both, because a photo measurement is never exact.

The engine wants axis-aligned obstacles, so polygon rings go in as their bounding box; the
placement itself comes from the report, so the two never disagree about where the item sits.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shapely.errors import GEOSException
from shapely.geometry import Polygon

from byb_common.contracts import FitPlacement, ProductProfile, RoomScan
from byb_geometry.fit_engine import Door, FurnitureItem, Room, SimulationEngine
from byb_geometry.fit_engine import Obstacle as Standing

FRONT_WALL = "-y"
SIDES = ("+x", "-x", "+y", "-y")


@dataclass(frozen=True)
class Access:
    door_pass: str = "unknown"
    walkway_connected: bool = True
    isolated_pockets: int = 0
    fragile: bool = False
    tolerance_cm: float = 2.0
    suggestions: list[str] = field(default_factory=list)


def _standing(obstacles) -> list[Standing]:
    kept: list[Standing] = []
    for index, obstacle in enumerate(obstacles):
        if len(obstacle.ring) < 3:
            continue
        try:
            shape = Polygon(obstacle.ring).buffer(0)
        except (GEOSException, ValueError):
            continue
        if shape.is_empty:
            continue
        x0, y0, x1, y1 = shape.bounds
        if x1 - x0 <= 0 or y1 - y0 <= 0:
            continue
        kept.append(
            Standing(
                name=obstacle.label or f"obstacle {index + 1}",
                x_cm=x0 * 100,
                y_cm=y0 * 100,
                length_cm=(x1 - x0) * 100,
                width_cm=(y1 - y0) * 100,
            )
        )
    return kept


def _rect(ring: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in ring]
    ys = [point[1] for point in ring]
    return min(xs), min(ys), max(xs), max(ys)


def _facing(gaps: dict[str, float], wall_padding_m: float) -> str:
    """The item looks away from the wall it rests against; that is where drawers pull out to.

    A piece standing free of every wall faces the door, which is how a shopper leaves it.
    """
    opposite = {"front": "-y", "back": "+y", "left": "+x", "right": "-x"}
    resting = min(gaps, key=lambda side: gaps[side])
    if gaps[resting] > wall_padding_m:
        return "-y"
    return opposite[resting]


def _door_pass(checks: list[dict[str, str]]) -> str:
    codes = {check["code"] for check in checks}
    if "doorway" in codes:
        return "blocked"
    if "doorway_tight" in codes:
        return "tight"
    return "pass"


def check_access(
    scan: RoomScan,
    profile: ProductProfile,
    placements: list[FitPlacement],
    *,
    wall_padding_m: float = 0.05,
    min_walkway_m: float = 0.6,
    tolerance_cm: float = 2.0,
) -> Access:
    geo = profile.geometry
    clearance_m = max(geo.clearance_cm / 100, min_walkway_m)
    door_width = min(scan.door_width_m, max(scan.width_m - 0.05, 0.05))
    door_offset = min(scan.door_offset_m, max(scan.width_m - door_width, 0.0))

    room = Room(
        length_cm=scan.width_m * 100,
        width_cm=scan.depth_m * 100,
        door=Door(
            wall=FRONT_WALL,
            offset_cm=door_offset * 100,
            width_cm=door_width * 100,
            height_cm=scan.door_height_m * 100,
        ),
        ceiling_height_cm=scan.height_m * 100,
        min_walkway_clearance_cm=clearance_m * 100,
        tolerance_margin_cm=tolerance_cm,
        obstacles=_standing(scan.obstacles),
    )
    item = FurnitureItem(
        name=profile.name or "this piece",
        length_cm=geo.width_cm,
        width_cm=geo.depth_cm,
        height_cm=geo.height_cm,
        drawer_depth_cm=geo.drawer_depth_cm,
    )
    engine = SimulationEngine(room)

    spot = next((placement for placement in placements if placement.fits), None) or (placements[0] if placements else None)
    if spot is None or len(spot.ring) < 3:
        x_cm = wall_padding_m * 100
        y_cm = wall_padding_m * 100
        gaps = {
            "left": x_cm / 100,
            "right": scan.width_m - x_cm / 100 - geo.width_cm / 100,
            "front": y_cm / 100,
            "back": scan.depth_m - y_cm / 100 - geo.depth_cm / 100,
        }
        rotation = 0
    else:
        x0, y0, x1, y1 = _rect(spot.ring)
        x_cm, y_cm = x0 * 100, y0 * 100
        gaps = {"left": x0, "right": scan.width_m - x1, "front": y0, "back": scan.depth_m - y1}
        rotation = 90 if spot.rotation_deg else 0
    item.front_faces = _facing(gaps, wall_padding_m)

    try:
        result = engine.evaluate_fit(item, x_cm, y_cm, rotation)
        reach = engine.walkway_reach(item, x_cm, y_cm, rotation)
    except (ValueError, GEOSException):
        return Access(tolerance_cm=tolerance_cm)

    return Access(
        door_pass=_door_pass(result["checks"]),
        walkway_connected=reach["entrance_walkable"] and not reach["skipped"],
        isolated_pockets=reach["isolated_pockets"],
        fragile=any(check["severity"] == "fragile" for check in result["checks"]),
        tolerance_cm=tolerance_cm,
        suggestions=[tip for tip in result["suggestions"] if tip],
    )
