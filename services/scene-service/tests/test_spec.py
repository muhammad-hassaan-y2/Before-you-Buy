import pytest

from byb_scene.spec import SceneInputError, best_placement, build_scene, cameras_for


@pytest.fixture
def scene_message(fitted):
    from byb_common.contracts import SimulationFitted

    return SimulationFitted.model_validate(fitted)


def test_the_scene_is_the_room_geometry_actually_measured(scene_message):
    scene = build_scene(scene_message)
    assert (scene.room_width_m, scene.room_depth_m, scene.room_height_m) == (4.0, 3.0, 2.5)
    assert scene.door_swing_m == 0.85
    assert scene.clearance_m == 0.9
    assert scene.verdict == "fits"
    assert scene.product_name == "Ektorp 3-seat sofa"


def test_a_sofa_arrives_as_more_than_one_box(scene_message):
    scene = build_scene(scene_message)
    assert [part.label for part in scene.parts] == ["plinth", "seat cushion", "backrest", "left arm", "right arm"]
    assert all(min(part.size_cm) > 0 for part in scene.parts)


def test_part_budget_is_capped(scene_message):
    assert len(build_scene(scene_message, max_parts=2).parts) == 2


def test_placements_keep_the_transforms_the_engine_needs(scene_message):
    scene = build_scene(scene_message)
    assert len(scene.placements) == 3
    first = scene.placements[0]
    assert first.position_m == (2.0, 0.0, 2.55)
    assert first.rotation_deg == 0.0
    assert first.walkway_m["front"] == 2.1
    assert [spot.fits for spot in scene.placements] == [True, True, False]


def test_obstacles_are_carried_into_the_scene_volume(scene_message):
    scene = build_scene(scene_message)
    assert [wall.label for wall in scene.walls] == ["radiator"]


def test_cameras_are_the_three_viewports_the_ui_offers(scene_message):
    scene = build_scene(scene_message)
    assert [camera.label for camera in scene.cameras] == ["overview", "top-down", "first-person"]
    assert [camera.position_m[1] for camera in scene.cameras][2] == pytest.approx(1.62)
    overview = scene.cameras[0]
    assert overview.position_m[2] < 0, "the overview has to sit outside the door wall to see in"
    assert all(len(camera.target_m) == 3 for camera in scene.cameras)


def test_top_down_camera_moves_with_the_room():
    from byb_common.contracts import RoomScan

    small = cameras_for(RoomScan(width_m=2.0, depth_m=2.0, height_m=2.4))
    large = cameras_for(RoomScan(width_m=8.0, depth_m=8.0, height_m=2.4))
    assert large[1].position_m[1] > small[1].position_m[1]


def test_the_default_spot_is_the_one_with_the_widest_walkway(scene_message):
    scene = build_scene(scene_message)
    assert best_placement(scene.placements).label == "centred on the back wall"


def test_a_blocked_room_still_has_a_spot_to_show(scene_message):
    scene = build_scene(scene_message)
    blocked = [spot for spot in scene.placements if not spot.fits]
    assert best_placement(blocked) is blocked[0]
    assert best_placement([]) is None


@pytest.mark.parametrize("missing", ["profile", "scan", "fit"])
def test_a_partial_message_is_refused_not_invented(fitted, missing):
    from byb_common.contracts import SimulationFitted

    message = SimulationFitted.model_validate(fitted | {missing: None})
    with pytest.raises(SceneInputError):
        build_scene(message)
