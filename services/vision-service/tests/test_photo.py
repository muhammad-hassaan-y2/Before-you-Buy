import cv2
import numpy as np

from byb_vision.photo import scan_photo

DECLARED = {"room_width_m": 4.0, "room_depth_m": 3.0, "room_height_m": 2.4}


def write(tmp_path, frame, name="room.png"):
    path = tmp_path / name
    assert cv2.imwrite(str(path), frame)
    return path


def scan(path, **overrides):
    options = {"min_confidence": 0.45, "max_obstacles": 4} | DECLARED | overrides
    return scan_photo(path, **options)


def test_missing_file_keeps_the_declared_room(tmp_path):
    result = scan(tmp_path / "nope.png")
    assert (result.width_m, result.depth_m, result.height_m) == (4.0, 3.0, 2.4)
    assert (result.measured, result.method, result.confidence) == (False, "declared", 0.0)


def test_blank_photo_has_no_lines_to_measure(tmp_path):
    flat = cv2.cvtColor(np.full((480, 640), 255, np.uint8), cv2.COLOR_GRAY2BGR)
    assert scan(write(tmp_path, flat)).method == "declared"


def test_corner_and_floor_junctions_become_metres(tmp_path, draw_room):
    # 260 px of corner is the 2.4 m ceiling, so 240 px of left wall is ~2.2 m and 399 px of right wall ~3.7 m.
    result = scan(write(tmp_path, draw_room()))
    assert result.measured and result.method == "photo"
    assert 1.9 <= result.width_m <= 2.5
    assert 3.3 <= result.depth_m <= 4.1
    assert result.confidence >= 0.45
    assert result.height_m == 2.4  # the ceiling is never guessed from the frame


def test_confidence_gate_keeps_the_shoppers_numbers(tmp_path, draw_room):
    result = scan(write(tmp_path, draw_room()), min_confidence=0.95)
    assert not result.measured
    assert result.method == "photo-ignored"
    assert (result.width_m, result.depth_m) == (4.0, 3.0)
    assert result.confidence > 0.0


def test_absurd_scale_is_rejected(tmp_path, draw_room):
    # A 5 cm ceiling would put the walls outside the 1..20 m envelope.
    result = scan(write(tmp_path, draw_room()), room_height_m=0.05)
    assert not result.measured
    assert (result.width_m, result.depth_m) == (4.0, 3.0)


def test_dark_floor_rectangle_becomes_an_obstacle(tmp_path, draw_room):
    frame = draw_room()
    cv2.rectangle(frame, (300, 380), (420, 450), (20, 20, 20), -1)
    result = scan(write(tmp_path, frame))
    assert len(result.obstacles) == 1
    obstacle = result.obstacles[0]
    assert obstacle.source == "photo" and obstacle.label.endswith("(photo)")
    assert len(obstacle.ring) >= 4 and obstacle.ring[0] == obstacle.ring[-1]
    assert all(0.0 <= x <= result.width_m for x, _ in obstacle.ring)
    assert all(0.0 <= y <= result.depth_m for _, y in obstacle.ring)
    assert 0.05 <= obstacle.height_m <= 2.4


def test_photo_obstacles_survive_an_ignored_measurement(tmp_path, draw_room):
    frame = draw_room()
    cv2.rectangle(frame, (300, 380), (300, 380), (10, 10, 10), -1)
    cv2.rectangle(frame, (60, 360), (170, 430), (30, 30, 30), -1)
    result = scan(write(tmp_path, frame), min_confidence=0.95)
    assert not result.measured and result.obstacles
