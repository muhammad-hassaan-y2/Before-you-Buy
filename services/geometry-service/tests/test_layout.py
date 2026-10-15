from byb_common.contracts import Obstacle, ProductGeometry, ProductProfile
from byb_geometry.layout import analyse_fit, candidate_rects, door_swing, obstacle_shapes, room_polygon


def profile(width_cm: float, depth_cm: float, height_cm: float = 85, clearance_cm: float = 60) -> ProductProfile:
    return ProductProfile(
        name="Test piece",
        category="sofa",
        geometry=ProductGeometry(width_cm=width_cm, depth_cm=depth_cm, height_cm=height_cm, clearance_cm=clearance_cm),
    )


def test_room_and_swing_geometry():
    room = room_polygon(4.0, 3.0)
    assert room.area == 12.0
    swing = door_swing(room)
    # Quarter circle of radius 0.85 m, hinged at the jamb.
    assert 0.5 < swing.area < 0.58
    assert swing.within(room)


def test_small_product_fits_a_large_room():
    report = analyse_fit(5.0, 4.0, 2.5, profile(150, 80))
    assert report.verdict == "fits"
    assert any(spot.fits for spot in report.placements)
    assert report.coverage_pct > 0
    assert report.room_area_m2 == 20.0


def test_every_placement_is_a_closed_ring():
    report = analyse_fit(5.0, 4.0, 2.5, profile(150, 80))
    for spot in report.placements:
        assert len(spot.ring) == 5
        assert spot.ring[0] == spot.ring[-1]


def test_oversized_product_is_too_large():
    report = analyse_fit(3.0, 2.5, 2.5, profile(400, 200))
    assert report.verdict == "too_large"
    assert report.placements == []
    assert report.conflicts


def test_too_tall_reports_ceiling_conflict():
    report = analyse_fit(4.0, 4.0, 2.0, profile(100, 60, height_cm=240))
    assert "ceiling" in report.conflicts[0]


def test_walkway_rule_blocks_a_snug_room():
    # A 220x95 sofa does land in a 2.5x1.1 room, but never with a 90 cm walkway.
    report = analyse_fit(2.5, 1.1, 2.5, profile(220, 95, clearance_cm=90))
    assert report.verdict in {"tight", "blocked"}
    assert not any(spot.fits for spot in report.placements)


def test_candidate_rects_cover_both_orientations():
    spots = candidate_rects(4.0, 3.0, 1.8, 0.9, 0.05)
    assert len(spots) == 10
    assert any("turned" in label for label, _ in spots)
    assert all(rect.x0 >= 0 and rect.y0 >= 0 for _, rect in spots)


def box_obstacle(x0: float, y0: float, x1: float, y1: float, label="existing sofa") -> Obstacle:
    return Obstacle(label=label, ring=[(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], height_m=0.75, source="photo")


def test_obstacle_takes_floor_out_of_the_usable_area():
    clear = analyse_fit(4.0, 3.0, 2.5, profile(150, 80))
    blocked = analyse_fit(4.0, 3.0, 2.5, profile(150, 80), obstacles=[box_obstacle(0.5, 1.0, 2.0, 2.0)])
    assert blocked.usable_area_m2 == round(clear.usable_area_m2 - 1.5, 2)
    assert blocked.obstacles[0].label == "existing sofa"


def test_placement_on_top_of_an_obstacle_names_it():
    # Covers the centred back-wall candidate (1.25..2.75 x 2.15..2.95) exactly.
    report = analyse_fit(4.0, 3.0, 2.5, profile(150, 80), obstacles=[box_obstacle(1.25, 2.15, 2.75, 2.95)])
    back_wall = next(spot for spot in report.placements if "back wall" in spot.label and "turned" not in spot.label)
    assert not back_wall.fits
    assert any("existing sofa" in conflict for conflict in report.conflicts)
    assert report.verdict in {"fits", "tight"}  # the other candidates are still open floor


def test_a_room_filled_with_furniture_leaves_no_floor():
    report = analyse_fit(3.0, 2.4, 2.5, profile(150, 80), obstacles=[box_obstacle(0.0, 0.0, 3.0, 2.4, label="everything")])
    assert report.verdict == "too_large"
    assert report.placements == []
    assert report.usable_area_m2 == 0.0


def test_degenerate_rings_are_dropped_not_fatal():
    junk = [
        Obstacle(label="dot", ring=[(0.5, 0.5)] * 5),
        Obstacle(label="open", ring=[(0.0, 0.0), (1.0, 0.0)]),
        box_obstacle(0.5, 0.5, 1.5, 1.2, label="sofa"),
    ]
    assert [obstacle.label for obstacle, _ in obstacle_shapes(junk)] == ["sofa"]
    report = analyse_fit(4.0, 3.0, 2.5, profile(150, 80), obstacles=junk)
    assert report.usable_area_m2 < 12.0


def test_placements_carry_what_the_engine_draws():
    report = analyse_fit(4.0, 3.0, 2.5, profile(150, 80))
    back_wall = next(spot for spot in report.placements if spot.label == "centred on the back wall")
    assert (back_wall.centre_x_m, back_wall.centre_y_m) == (2.0, 2.55)
    assert back_wall.rotation_deg == 0.0
    assert back_wall.walkway_m == {"left": 1.25, "right": 1.25, "front": 2.15, "back": 0.05}

    turned = next(spot for spot in report.placements if spot.label == "centred on the back wall (turned)")
    assert turned.rotation_deg == 90.0
    assert turned.footprint_m2 == round(0.8 * 1.5, 2)
