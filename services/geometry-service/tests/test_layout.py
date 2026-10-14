from byb_common.contracts import ProductGeometry, ProductProfile
from byb_geometry.layout import analyse_fit, candidate_rects, door_swing, room_polygon


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
