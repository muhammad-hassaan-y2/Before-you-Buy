"""Parametric box breakdowns so the 3D engine draws a recognisable piece of furniture.

Coordinates are product-local centimetres with the origin at the floor under the centre of
the footprint: x runs along the product width, y along its depth and z is up. A box is
therefore described by its centre offset plus its size, which is all three.js needs.
"""

from __future__ import annotations

from byb_common.contracts import ProductPart

UPHOLSTERED = {"sofa", "armchair", "sectional", "ottoman", "headboard", "stool"}
TIMBER = {"bed", "wardrobe", "bookcase", "table", "desk", "sideboard", "cabinet", "tv unit", "shelf"}


def _part(label: str, size: tuple[float, float, float], offset: tuple[float, float, float], tone: str) -> ProductPart:
    return ProductPart(label=label, size_cm=size, offset_cm=offset, tone=tone)


def build_parts(category: str, width_cm: float, depth_cm: float, height_cm: float) -> list[ProductPart]:
    """Split a bounding box into sub-boxes. Falls back to the bare box when unknown."""
    key = (category or "").lower()
    seats = next((word for word in UPHOLSTERED if word in key), None)
    cabinets = next((word for word in TIMBER if word in key), None)

    if seats:
        seat_height = round(min(45.0, height_cm * 0.45), 1)
        back_height = round(height_cm - seat_height, 1)
        arm_width = round(min(18.0, width_cm * 0.12), 1)
        inner_width = round(max(width_cm - 2 * arm_width, 10.0), 1)
        cushion_height = seat_height - 10.0
        cushion_size = (inner_width, round(depth_cm * 0.75, 1), cushion_height)
        cushion_offset = (0, round(depth_cm * 0.08, 1), 10.0 + cushion_height / 2)
        back_size = (inner_width, round(depth_cm * 0.22, 1), back_height)
        back_offset = (0, round(-depth_cm * 0.39, 1), seat_height + back_height / 2)
        arm_height = round(seat_height + 15.0, 1)
        arm_size = (arm_width, depth_cm, arm_height)
        arm_x = round(width_cm / 2 - arm_width / 2, 1)
        arm_z = arm_height / 2
        return [
            _part("plinth", (width_cm, depth_cm, 10.0), (0, 0, 5.0), "leg"),
            _part("seat cushion", cushion_size, cushion_offset, "upholstery"),
            _part("backrest", back_size, back_offset, "upholstery"),
            _part("left arm", arm_size, (-arm_x, 0, arm_z), "upholstery"),
            _part("right arm", arm_size, (arm_x, 0, arm_z), "upholstery"),
        ]

    if cabinets == "bed":
        frame_height = round(min(30.0, height_cm * 0.4), 1)
        mattress = round(height_cm - frame_height, 1)
        headboard = round(height_cm * 0.8, 1)
        return [
            _part("frame", (width_cm, depth_cm, frame_height), (0, 0, frame_height / 2), "timber"),
            _part("mattress", (round(width_cm - 4.0, 1), round(depth_cm - 4.0, 1), mattress), (0, 0, frame_height + mattress / 2), "linen"),
            _part("headboard", (width_cm, 6.0, headboard), (0, round(-depth_cm / 2 + 3.0, 1), headboard / 2), "timber"),
        ]

    if cabinets in {"wardrobe", "bookcase", "sideboard", "cabinet", "tv unit", "shelf"}:
        carcass_depth = round(depth_cm * 0.92, 1)
        carcass_height = round(height_cm - 8.0, 1)
        carcass_y = round(-depth_cm * 0.04, 1)
        parts = [
            _part("carcass", (width_cm, carcass_depth, carcass_height), (0, carcass_y, 4.0 + carcass_height / 2), "timber"),
            _part("plinth", (width_cm, depth_cm, 8.0), (0, 0, 4.0), "leg"),
        ]
        shelves = max(0, int((height_cm - 20.0) // 32.0))
        for index in range(shelves):
            level = round(20.0 + (index + 1) * ((height_cm - 24.0) / (shelves + 1)), 1)
            shelf_size = (round(width_cm - 4.0, 1), round(carcass_depth - 4.0, 1), 2.5)
            parts.append(_part(f"shelf {index + 1}", shelf_size, (0, carcass_y, level), "timber"))
        return parts

    if cabinets in {"table", "desk"}:
        top = round(min(4.0, height_cm * 0.06), 1)
        leg_height = round(height_cm - top, 1)
        inset = round(min(8.0, width_cm * 0.08), 1)
        leg = round(min(7.0, width_cm * 0.05), 1)
        parts = [_part("tabletop", (width_cm, depth_cm, top), (0, 0, round(leg_height + top / 2, 1)), "timber")]
        for x_sign, x_label in ((-1, "left"), (1, "right")):
            for y_sign, y_label in ((-1, "near"), (1, "far")):
                parts.append(
                    _part(
                        f"{x_label}-{y_label} leg",
                        (leg, leg, leg_height),
                        (
                            round(x_sign * (width_cm / 2 - inset - leg / 2), 1),
                            round(y_sign * (depth_cm / 2 - inset - leg / 2), 1),
                            round(leg_height / 2, 1),
                        ),
                        "leg",
                    )
                )
        return parts

    return [_part("item", (width_cm, depth_cm, height_cm), (0, 0, round(height_cm / 2, 1)), "timber")]
