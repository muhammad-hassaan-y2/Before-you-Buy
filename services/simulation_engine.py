"""
BeforeYouBuy AI - Simulation & Geometry Engine

Deterministic checks:
  1. Room boundary (all four walls) + tight-fit tolerance
  2. Ceiling height
  3. Doorway pass-through (item may be tilted; height-aware)
  4. Drawer extension zone in the direction the item faces
  5. Door swing arc
  6. Collisions / near-misses with other obstacles
  7. Walkway: door -> room must stay connected at the minimum walkway width

Coordinates: x runs along room length, y along room width, origin at the
bottom-left corner. An item is placed by its bottom-left corner (x_cm, y_cm).
All distances are in cm.

Statuses: FAIL < FRAGILE PASS < PASS WITH WARNINGS < PASS
  FRAGILE PASS = passes with the stated measurements but fails if reality is
                 off by the tolerance margin (default +/-2 cm).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

EPS = 1e-6
SIDES = ("+x", "-x", "+y", "-y")
_ROTATE_CW = {"+y": "+x", "+x": "-y", "-y": "-x", "-x": "+y"}  # 90 deg clockwise



# Data models

@dataclass
class Door:
    wall: str = "-y"                 # which wall the door is on
    offset_cm: float = 0.0           # distance from the wall's start corner to the hinge
    width_cm: float = 80.0
    height_cm: float = 200.0
    swing_radius_cm: Optional[float] = None   # defaults to door width


@dataclass
class Obstacle:
    """Rectangular thing already in the room (bed, radiator, shelf...)."""
    name: str
    x_cm: float
    y_cm: float
    length_cm: float
    width_cm: float

    @property
    def polygon(self) -> Polygon:
        return box(self.x_cm, self.y_cm, self.x_cm + self.length_cm, self.y_cm + self.width_cm)


@dataclass
class Room:
    length_cm: float
    width_cm: float
    door: Door = field(default_factory=Door)
    ceiling_height_cm: float = 250.0
    min_walkway_clearance_cm: float = 60.0
    tolerance_margin_cm: float = 2.0
    obstacles: List[Obstacle] = field(default_factory=list)

    def __post_init__(self):
        if self.length_cm <= 0 or self.width_cm <= 0:
            raise ValueError("Room dimensions must be positive.")
        if self.door.wall not in SIDES:
            raise ValueError(f"door.wall must be one of {SIDES}.")
        wall_len = self.length_cm if self.door.wall in ("-y", "+y") else self.width_cm
        if self.door.offset_cm < 0 or self.door.offset_cm + self.door.width_cm > wall_len:
            raise ValueError("Door does not fit on its wall.")


@dataclass
class FurnitureItem:
    name: str
    length_cm: float
    width_cm: float
    height_cm: float
    drawer_depth_cm: float = 0.0
    front_faces: str = "+y"          # side drawers/doors open toward (at rotation 0)



# Helpers

def _wall_frame(wall: str, length: float, width: float):
    """(start point, unit vector along wall, inward unit normal) for a wall."""
    return {
        "-y": ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        "+y": ((0.0, width), (1.0, 0.0), (0.0, -1.0)),
        "-x": ((0.0, 0.0), (0.0, 1.0), (1.0, 0.0)),
        "+x": ((length, 0.0), (0.0, 1.0), (-1.0, 0.0)),
    }[wall]


def _parts(geom) -> List[Polygon]:
    if geom.is_empty:
        return []
    parts = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    return [p for p in parts if p.geom_type == "Polygon" and p.area > EPS]


def _coords(poly) -> List[Tuple[float, float]]:
    if poly is None or poly.is_empty:
        return []
    return [(round(x, 2), round(y, 2)) for x, y in poly.exterior.coords]



# Engine

class SimulationEngine:
    def __init__(self, room: Room):
        self.room = room
        L, W = room.length_cm, room.width_cm
        self.room_poly = box(0, 0, L, W)
        self._room_eps = self.room_poly.buffer(EPS, join_style=2)
        self._obstacle_polys = [o.polygon for o in room.obstacles]

        d = room.door
        (sx, sy), (ux, uy), (nx, ny) = _wall_frame(d.wall, L, W)
        self._normal = (nx, ny)
        p0 = (sx + ux * d.offset_cm, sy + uy * d.offset_cm)
        self._door_mid = (p0[0] + ux * d.width_cm / 2, p0[1] + uy * d.width_cm / 2)
        r = d.swing_radius_cm or d.width_cm
        quadrant = Polygon([
            p0,
            (p0[0] + ux * r, p0[1] + uy * r),
            (p0[0] + ux * r + nx * r, p0[1] + uy * r + ny * r),
            (p0[0] + nx * r, p0[1] + ny * r),
        ])
        self.swing_zone = Point(p0).buffer(r, 64).intersection(quadrant).intersection(self.room_poly)
        self._base_cache: Dict[float, Tuple[bool, int]] = {}

    # validation 
    def _validate(self, item: FurnitureItem, x: float, y: float, rotation: int):
        if min(item.length_cm, item.width_cm, item.height_cm) <= 0:
            raise ValueError("Item dimensions must be positive.")
        if item.drawer_depth_cm < 0:
            raise ValueError("drawer_depth_cm cannot be negative.")
        if x < 0 or y < 0:
            raise ValueError("Position cannot be negative.")
        if item.front_faces not in SIDES:
            raise ValueError(f"front_faces must be one of {SIDES}.")
        if rotation not in (0, 90):
            raise ValueError("rotation_deg must be 0 or 90.")

    # doorway
    def _doorway_ok(self, item: FurnitureItem, margin: float) -> bool:
        """Item may be tilted: its two smallest dimensions must fit door width x height."""
        a, b, _ = sorted([item.length_cm, item.width_cm, item.height_cm])
        w = self.room.door.width_cm - margin
        h = self.room.door.height_cm - margin
        return (a <= w and b <= h) or (b <= w and a <= h)

    # walkway 
    def _reach(self, footprint: Optional[Polygon], clearance: float) -> Tuple[bool, int]:
        """
        Erode the free floor by clearance/2 (a person `clearance` wide).
        Returns (entrance_is_walkable, number_of_isolated_pockets).
        """
        blockers = list(self._obstacle_polys)
        if footprint is not None:
            blockers.append(footprint)
        free = self.room_poly.difference(unary_union(blockers)) if blockers else self.room_poly
        comps = _parts(free.buffer(-clearance / 2, join_style=2))

        nx, ny = self._normal
        entry = Point(self._door_mid[0] + nx * (clearance / 2 + 1),
                      self._door_mid[1] + ny * (clearance / 2 + 1))
        entry_idx = next((i for i, c in enumerate(comps) if c.distance(entry) <= 2.0), None)
        if entry_idx is None:
            return False, 0
        min_area = clearance ** 2
        pockets = sum(1 for i, c in enumerate(comps) if i != entry_idx and c.area >= min_area)
        return True, pockets

    def _baseline(self, clearance: float) -> Tuple[bool, int]:
        if clearance not in self._base_cache:
            self._base_cache[clearance] = self._reach(None, clearance)
        return self._base_cache[clearance]

    #  drawer geometry
    @staticmethod
    def _drawer_zone(fp: Polygon, front: str, depth: float) -> Polygon:
        x0, y0, x1, y1 = fp.bounds
        return {
            "+y": box(x0, y1, x1, y1 + depth),
            "-y": box(x0, y0 - depth, x1, y0),
            "+x": box(x1, y0, x1 + depth, y1),
            "-x": box(x0 - depth, y0, x0, y1),
        }[front]

    def _clash(self, a: Polygon, b: Polygon) -> Optional[str]:
        """'overlap', 'tight' (gap smaller than tolerance) or None."""
        if a.intersection(b).area > EPS:
            return "overlap"
        dist = a.distance(b)
        if EPS < dist < self.room.tolerance_margin_cm:
            return "tight"
        return None

    # core check 
    def _evaluate(self, item: FurnitureItem, x: float, y: float, rotation: int) -> Dict[str, Any]:
        self._validate(item, x, y, rotation)
        room, tol = self.room, self.room.tolerance_margin_cm
        L, W = room.length_cm, room.width_cm

        length, width = (item.length_cm, item.width_cm) if rotation == 0 else (item.width_cm, item.length_cm)
        front = item.front_faces if rotation == 0 else _ROTATE_CW[item.front_faces]
        fp = box(x, y, x + length, y + width)
        gaps = {"-x": x, "+x": L - (x + length), "-y": y, "+y": W - (y + width)}

        checks: List[Dict[str, str]] = []

        def add(code: str, severity: str, message: str):
            checks.append({"code": code, "severity": severity, "message": message})

        # 1. Boundary 
        in_room = self._room_eps.covers(fp)
        if not in_room:
            for side, gap in gaps.items():
                if gap < -EPS:
                    add("out_of_bounds", "fail", f"Exceeds the room on the {side} side by {abs(gap):.1f} cm.")
        else:
            spare = min(L - length, W - width)
            if spare < tol:
                add("tight_fit", "fragile",
                    f"Only {spare:.1f} cm spare across the room: within the +/-{tol} cm measurement margin.")

        # 2. Ceiling 
        if item.height_cm > room.ceiling_height_cm + EPS:
            add("ceiling", "fail",
                f"Item is {item.height_cm - room.ceiling_height_cm:.1f} cm taller than the ceiling.")
        elif room.ceiling_height_cm - item.height_cm < tol:
            add("ceiling_tight", "fragile", f"Ceiling clearance is within +/-{tol} cm.")

        # 3. Doorway 
        if not self._doorway_ok(item, 0):
            add("doorway", "fail", "Item cannot pass through the doorway, even when tilted.")
        elif not self._doorway_ok(item, tol):
            add("doorway_tight", "fragile", f"Doorway fit is within +/-{tol} cm: it may not pass.")

        # 4. Door swing
        clash = self._clash(fp, self.swing_zone)
        if clash == "overlap":
            add("door_swing_blocked", "fail", "Item sits inside the door swing area.")
        elif clash == "tight":
            add("door_swing_tight", "fragile", "Item is within tolerance of the door swing area.")

        # 5. Drawers
        drawer_zone = None
        if item.drawer_depth_cm > 0:
            d = item.drawer_depth_cm
            drawer_zone = self._drawer_zone(fp, front, d)
            front_gap = gaps[front]
            if front_gap < d - EPS:
                add("drawer_blocked", "fail",
                    f"Drawers need {d:.1f} cm in front ({front} side); only {max(front_gap, 0):.1f} cm available.")
            elif front_gap - d < tol:
                add("drawer_tight", "fragile",
                    f"Drawers fit with only {front_gap - d:.1f} cm to spare (within +/-{tol} cm).")
            for ob, poly in zip(room.obstacles, self._obstacle_polys):
                if drawer_zone.intersection(poly).area > EPS:
                    add("drawer_blocked", "fail", f"Drawers would hit '{ob.name}'.")
            if drawer_zone.intersection(self.swing_zone).area > EPS:
                add("drawer_in_swing", "warning", "Drawer zone overlaps the door swing area.")

        # 6. Obstacles 
        for ob, poly in zip(room.obstacles, self._obstacle_polys):
            clash = self._clash(fp, poly)
            if clash == "overlap":
                add("obstacle_overlap", "fail", f"Item overlaps '{ob.name}'.")
            elif clash == "tight":
                add("obstacle_tight", "fragile", f"Item is within +/-{tol} cm of '{ob.name}'.")

        # 7. Walkway (only meaningful if nothing has failed yet)
        if not any(c["severity"] == "fail" for c in checks):
            clearance = room.min_walkway_clearance_cm
            base_ok, base_pockets = self._baseline(clearance)
            if not base_ok:
                add("walkway_skipped", "warning",
                    "Walkway check skipped: the entrance is narrower than the walkway even with an empty room.")
            else:
                ok, pockets = self._reach(fp, clearance)
                if not ok:
                    add("entry_blocked", "fail",
                        f"Item leaves less than {clearance:.0f} cm of walkway at the entrance.")
                else:
                    new = max(0, pockets - base_pockets)
                    if new:
                        add("isolated_area", "warning",
                            f"Item cuts off {new} area(s) of the room: less than {clearance:.0f} cm to get through.")
                    worst = clearance + 2 * tol
                    b2_ok, b2_pockets = self._baseline(worst)
                    if b2_ok:
                        ok2, pockets2 = self._reach(fp, worst)
                        if (not ok2) or max(0, pockets2 - b2_pockets) > new:
                            add("walkway_tight", "fragile",
                                f"Walkway only works if measurements are exact (+/-{tol} cm breaks it).")

        # Status
        sev = {c["severity"] for c in checks}
        if "fail" in sev:
            status = "FAIL"
        elif "fragile" in sev:
            status = "FRAGILE PASS"
        elif "warning" in sev:
            status = "PASS WITH WARNINGS"
        else:
            status = "PASS"

        open_gaps = [g for g in gaps.values() if g > 0.5]
        return {
            "status": status,
            "passed": status != "FAIL",
            "rotation_deg": rotation,
            "failures": [c["message"] for c in checks if c["severity"] == "fail"],
            "warnings": [c["message"] for c in checks if c["severity"] in ("fragile", "warning")],
            "checks": checks,
            "gaps_cm": {k: round(v, 1) for k, v in gaps.items()},
            "min_open_gap_cm": round(min(open_gaps), 1) if open_gaps else 0.0,
            "suggestions": [],
            "evidence": {
                "room": _coords(self.room_poly),
                "footprint": _coords(fp),
                "drawer_zone": _coords(drawer_zone),
                "door_swing_zone": _coords(self.swing_zone),
                "obstacles": {o.name: _coords(p) for o, p in zip(room.obstacles, self._obstacle_polys)},
            },
        }

    # public API
    def evaluate_fit(self, item: FurnitureItem, x_cm: float, y_cm: float,
                     rotation_deg: int = 0, suggest: bool = True) -> Dict[str, Any]:
        result = self._evaluate(item, x_cm, y_cm, rotation_deg)
        if suggest and result["status"] != "PASS":
            result["suggestions"] = self._suggest(item, result, x_cm, y_cm, rotation_deg)
        return result

    def find_placements(self, item: FurnitureItem, step_cm: float = 20.0,
                        limit: int = 3) -> List[Dict[str, Any]]:
        """Grid-search positions and both rotations; best statuses first."""
        if not self._doorway_ok(item, 0):
            return []  # no placement can fix a doorway failure
        rank = {"PASS": 0, "PASS WITH WARNINGS": 1, "FRAGILE PASS": 2}
        found = []
        for rot in (0, 90):
            length, width = (item.length_cm, item.width_cm) if rot == 0 else (item.width_cm, item.length_cm)
            sx, sy = self.room.length_cm - length, self.room.width_cm - width
            if sx < 0 or sy < 0:
                continue
            xs = sorted({round(v * step_cm, 6) for v in range(int(sx // step_cm) + 1)} | {sx})
            ys = sorted({round(v * step_cm, 6) for v in range(int(sy // step_cm) + 1)} | {sy})
            for px in xs:
                for py in ys:
                    r = self._evaluate(item, px, py, rot)
                    if r["status"] in rank:
                        found.append((rank[r["status"]], px, py, rot, r["status"]))
        found.sort(key=lambda t: t[0])
        return [{"x_cm": px, "y_cm": py, "rotation_deg": rot, "status": st}
                for _, px, py, rot, st in found[:limit]]

    def _suggest(self, item, result, x, y, rotation) -> List[str]:
        tips: List[str] = []
        codes = {c["code"] for c in result["checks"]}
        gaps = result["gaps_cm"]

        if "out_of_bounds" in codes:
            for side, opposite in (("+x", "-x"), ("+y", "-y")):
                if gaps[side] < 0:
                    tips.append(f"Move the item {abs(gaps[side]):.1f} cm toward {opposite}, "
                                f"or pick a model {abs(gaps[side]):.1f} cm smaller on that axis.")
        if "drawer_blocked" in codes:
            tips.append("Rotate or reposition the item so its drawers face open floor.")
        if "doorway" in codes:
            tips.append("Choose a flat-pack / disassembled version, or a model that fits the doorway.")
        if "door_swing_blocked" in codes:
            tips.append("Move the item out of the door swing area.")
        if "ceiling" in codes:
            tips.append("Choose a lower model.")
        if "entry_blocked" in codes or "isolated_area" in codes:
            tips.append("Shift the item so at least the minimum walkway stays open around it.")
        if {"tight_fit", "doorway_tight", "drawer_tight", "walkway_tight"} & codes:
            tips.append("Re-measure carefully: this only passes if measurements are exact.")

        # Concrete alternatives from the search (only worth doing on a real fail).
        if result["status"] == "FAIL":
            alts = self.find_placements(item)
            if alts:
                a = alts[0]
                tips.append(f"Valid placement: x={a['x_cm']:.0f}, y={a['y_cm']:.0f}, "
                            f"rotation {a['rotation_deg']} deg ({a['status']}).")
            elif self._doorway_ok(item, 0):
                tips.append("No placement of this item works in this room: try a smaller model.")
        return tips



if __name__ == "__main__":
    room = Room(length_cm=400, width_cm=300,
                door=Door(wall="-y", offset_cm=50, width_cm=80, height_cm=200))
    desk = FurnitureItem("Executive Standing Desk", 160, 80, 75, drawer_depth_cm=40, front_faces="+y")

    engine = SimulationEngine(room)
    res = engine.evaluate_fit(desk, 0, 80)
    print("=== Simulation Result ===")
    print("Status:", res["status"])
    print("Failures:", res["failures"])
    print("Warnings:", res["warnings"])
    print("Suggestions:", res["suggestions"])
