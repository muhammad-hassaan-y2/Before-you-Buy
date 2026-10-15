"""Shapely fit analysis: turn a product's centimetre box into room placements in metres.

Pure geometry, no I/O, so the rules can be unit-tested without a server.

Walkway rule: a furniture face may sit flush against a wall, but every face that is
*not* supported by a wall must keep at least `clearance` metres free. A face is
supported when its gap to the boundary is within the wall padding.

Anything vision-service or the shopper says is already in the room arrives as an
`Obstacle` and is subtracted from the usable floor, next to the door swing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from shapely.errors import GEOSException
from shapely.geometry import Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from byb_common.contracts import FitPlacement, FitReport, Obstacle, ProductProfile

DOOR_SWING_M = 0.85


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def shape(self) -> BaseGeometry:
        return box(self.x0, self.y0, self.x1, self.y1)

    @property
    def area(self) -> float:
        return (self.x1 - self.x0) * (self.y1 - self.y0)

    @property
    def centre(self) -> tuple[float, float]:
        return (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2

    def gaps(self, width_m: float, depth_m: float) -> dict[str, float]:
        return {"left": self.x0, "right": width_m - self.x1, "front": self.y0, "back": depth_m - self.y1}


def room_polygon(width_m: float, depth_m: float) -> BaseGeometry:
    return box(0.0, 0.0, width_m, depth_m)


def door_swing(room: BaseGeometry) -> BaseGeometry:
    """Quarter-circle sweep hinged at the left jamb of the front-wall opening."""
    hinge = Point(0.0, 0.0)
    sweep = hinge.buffer(DOOR_SWING_M, quad_segs=16).intersection(box(0.0, 0.0, DOOR_SWING_M, DOOR_SWING_M))
    return sweep.intersection(room)


def obstacle_shapes(obstacles: Sequence[Obstacle]) -> list[tuple[Obstacle, BaseGeometry]]:
    """Clip self-intersecting or degenerate photo rings out instead of failing the run."""
    kept: list[tuple[Obstacle, BaseGeometry]] = []
    for obstacle in obstacles:
        if len(obstacle.ring) < 4:
            continue
        try:
            shape = Polygon(obstacle.ring).buffer(0)
        except (GEOSException, ValueError):
            continue
        if shape.is_empty or shape.area <= 0:
            continue
        kept.append((obstacle, shape))
    return kept


def _ring(geometry: BaseGeometry) -> list[tuple[float, float]]:
    return [(round(x, 3), round(y, 3)) for x, y in geometry.exterior.coords]


def candidate_rects(
    width_m: float, depth_m: float, footprint_w: float, footprint_d: float, pad: float
) -> list[tuple[str, Rect]]:
    """Wall and floor positions, both orientations, ordered by how typical the layout is."""
    spots: list[tuple[str, Rect]] = []
    for label_w, label_d in ((footprint_w, footprint_d), (footprint_d, footprint_w)):
        if any(label_w == r.x1 - r.x0 and label_d == r.y1 - r.y0 for _, r in spots):
            continue
        orientation = "" if (label_w, label_d) == (footprint_w, footprint_d) else " (turned)"
        x_centre = (width_m - label_w) / 2
        y_centre = (depth_m - label_d) / 2
        spots.extend(
            [
                (f"centred on the back wall{orientation}", Rect(x_centre, depth_m - pad - label_d, x_centre + label_w, depth_m - pad)),
                (f"flush with the left wall{orientation}", Rect(pad, y_centre, pad + label_w, y_centre + label_d)),
                (f"flush with the right wall{orientation}", Rect(width_m - pad - label_w, y_centre, width_m - pad, y_centre + label_d)),
                (f"in the front-left corner{orientation}", Rect(pad, pad, pad + label_w, pad + label_d)),
                (f"freestanding in the middle{orientation}", Rect(x_centre, y_centre, x_centre + label_w, y_centre + label_d)),
            ]
        )
    return spots


def analyse_fit(
    room_width_m: float,
    room_depth_m: float,
    room_height_m: float,
    profile: ProductProfile,
    *,
    wall_padding_m: float = 0.05,
    min_walkway_m: float = 0.6,
    obstacles: Sequence[Obstacle] = (),
) -> FitReport:
    room = room_polygon(room_width_m, room_depth_m)
    swing = door_swing(room)
    standing = obstacle_shapes(obstacles)
    blocked = unary_union([swing, *(shape for _label, shape in standing)])
    usable = room.difference(blocked)
    clear_of_swing = room.difference(swing)

    geo = profile.geometry
    product_w = geo.width_cm / 100
    product_d = geo.depth_cm / 100
    clearance = max(geo.clearance_cm / 100, min_walkway_m)

    conflicts: list[str] = []
    if geo.height_cm / 100 > room_height_m:
        conflicts.append(f"{profile.name} is {geo.height_cm:.0f} cm tall, taller than the {room_height_m * 100:.0f} cm ceiling.")

    footprint_area = product_w * product_d
    if footprint_area > usable.area or product_w > room_width_m or product_d > room_depth_m:
        return FitReport(
            room_area_m2=round(room.area, 2),
            usable_area_m2=round(usable.area, 2),
            conflicts=[*conflicts, f"A {product_w:.2f} x {product_d:.2f} m footprint cannot sit inside {usable.area:.2f} m2 of usable floor."],
            coverage_pct=0.0,
            verdict="too_large",
            obstacles=list(obstacles),
            door_swing_m=DOOR_SWING_M,
        )

    placements: list[FitPlacement] = []
    fitted: list[BaseGeometry] = []
    landed = False
    for label, rect in candidate_rects(room_width_m, room_depth_m, product_w, product_d, wall_padding_m):
        shape = rect.shape
        gaps = {side: round(gap, 2) for side, gap in rect.gaps(room_width_m, room_depth_m).items()}
        common = {
            "label": label,
            "ring": _ring(shape),
            "footprint_m2": round(rect.area, 2),
            "centre_x_m": round(rect.centre[0], 2),
            "centre_y_m": round(rect.centre[1], 2),
            "rotation_deg": 90.0 if "turned" in label else 0.0,
            "walkway_m": gaps,
        }
        if not usable.contains(shape):
            # Anything inside room-minus-swing must have been stopped by standing furniture.
            hits = [obstacle.label for obstacle, other in standing if other.intersects(shape)]
            reason = f"lands on {', '.join(hits) or 'existing furniture'}" if clear_of_swing.contains(shape) else "collides with the door swing"
            conflicts.append(f"{label}: {reason}.")
            placements.append(FitPlacement(area_m2=round(shape.area, 2), fits=False, **common))
            continue

        landed = True
        blocked_sides = [side for side, gap in rect.gaps(room_width_m, room_depth_m).items() if gap > wall_padding_m and gap < clearance]
        fits = not blocked_sides
        if not fits:
            conflicts.append(f"{label}: only {min(rect.gaps(room_width_m, room_depth_m).values()):.2f} m of walkway on the {', '.join(blocked_sides)} side.")
        else:
            fitted.append(shape)
        envelope = shape.buffer(clearance).intersection(room)
        placements.append(FitPlacement(area_m2=round(envelope.area, 2), fits=fits, **common))

    if any(p.fits for p in placements):
        verdict = "fits"
    elif landed:
        verdict = "tight"
    else:
        verdict = "blocked"

    occupied = unary_union(fitted) if fitted else None
    coverage = round((occupied.area / usable.area) * 100, 1) if occupied is not None and not occupied.is_empty else 0.0

    return FitReport(
        room_area_m2=round(room.area, 2),
        usable_area_m2=round(usable.area, 2),
        placements=placements,
        conflicts=conflicts,
        coverage_pct=coverage,
        verdict=verdict,
        obstacles=list(obstacles),
        door_swing_m=DOOR_SWING_M,
    )
