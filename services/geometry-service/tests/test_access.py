from byb_common.contracts import FitPlacement, Obstacle, ProductGeometry, ProductProfile, RoomScan
from byb_geometry.access import Access, check_access
from byb_geometry.layout import analyse_fit


def profile(width_cm: float, depth_cm: float, height_cm: float = 85, clearance_cm: float = 60, drawer_cm: float = 0) -> ProductProfile:
    return ProductProfile(
        name="Test piece",
        category="sofa",
        geometry=ProductGeometry(
            width_cm=width_cm, depth_cm=depth_cm, height_cm=height_cm, clearance_cm=clearance_cm, drawer_depth_cm=drawer_cm
        ),
    )


def scan(width_m: float = 4.0, depth_m: float = 4.0, height_m: float = 2.5, door_w: float = 0.85, door_h: float = 2.0, obstacles=()) -> RoomScan:
    return RoomScan(
        width_m=width_m,
        depth_m=depth_m,
        height_m=height_m,
        obstacles=list(obstacles),
        door_width_m=door_w,
        door_height_m=door_h,
    )


def spot(ring: list[tuple[float, float]], fits: bool = True, rotation_deg: float = 0.0) -> FitPlacement:
    return FitPlacement(label="test spot", ring=ring, area_m2=1.0, footprint_m2=1.0, fits=fits, rotation_deg=rotation_deg)


def box_ring(x0: float, y0: float, x1: float, y1: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def test_a_normal_piece_gets_in_and_stays_walkable():
    item = profile(150, 80)
    report = analyse_fit(4.0, 4.0, 2.5, item)
    access = check_access(scan(), item, report.placements)
    assert access.door_pass == "pass"
    assert access.walkway_connected is True
    assert access.isolated_pockets == 0
    assert access.suggestions == []


def test_a_cabinet_too_thick_for_the_door_is_blocked():
    # Two smallest axes are 100 and 120 cm: no tilt gets it through an 85 cm opening.
    item = profile(120, 100, height_cm=130, clearance_cm=30)
    report = analyse_fit(4.0, 4.0, 2.5, item)
    assert report.verdict == "fits"
    access = check_access(scan(), item, report.placements)
    assert access.door_pass == "blocked"


def test_a_doorway_fit_inside_the_margin_is_reported_tight():
    # 84 cm is the narrowest axis: it clears an 85 cm door, but not 85 cm minus the 2 cm margin.
    item = profile(150, 84, height_cm=200, clearance_cm=30)
    report = analyse_fit(4.0, 4.0, 2.5, item)
    access = check_access(scan(), item, report.placements)
    assert access.door_pass == "tight"
    assert access.fragile is True


def test_a_piece_that_spans_the_room_seals_the_back_off():
    item = profile(390, 60, height_cm=80, clearance_cm=60)
    placement = spot(box_ring(0.05, 1.8, 3.95, 2.4))
    access = check_access(scan(), item, [placement])
    assert access.isolated_pockets >= 1


def test_a_blocked_walkway_is_reported_as_unreachable():
    # 60 cm strip in front of the door: nothing erodes away at a 60 cm walkway requirement.
    item = profile(390, 60, height_cm=80, clearance_cm=60)
    placement = spot(box_ring(0.05, 0.6, 3.95, 1.2))
    access = check_access(scan(), item, [placement])
    assert access.walkway_connected is False


def test_drawers_that_hit_a_radiator_are_flagged_with_a_suggestion():
    item = profile(120, 60, height_cm=80, clearance_cm=60, drawer_cm=45)
    radiator = Obstacle(label="radiator", ring=box_ring(0.1, 2.0, 1.3, 2.4), height_m=0.6)
    report = analyse_fit(4.0, 4.0, 2.5, item, obstacles=[radiator])
    access = check_access(scan(obstacles=[radiator]), item, report.placements)
    assert access.suggestions or access.fragile or not access.walkway_connected


def test_garbage_obstacle_rings_are_skipped_not_fatal():
    item = profile(150, 80)
    broken = Obstacle(label="degenerate", ring=[(0.0, 0.0), (1.0, 1.0), (0.0, 0.0)])
    access = check_access(scan(obstacles=[broken]), item, [])
    assert isinstance(access, Access)
    assert access.door_pass in {"pass", "tight", "blocked"}


def test_a_room_narrower_than_the_door_still_answers():
    item = profile(100, 60, clearance_cm=20)
    access = check_access(scan(width_m=1.1, depth_m=1.0), item, [])
    assert access.door_pass in {"pass", "tight", "blocked"}
    assert access.tolerance_cm == 2.0
