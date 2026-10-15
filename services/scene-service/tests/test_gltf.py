"""Structural checks on the document scene-service hands to the browser.

These are the glTF 2.0 rules a viewer refuses the file over, so they are worth asserting
before the first three.js build ever loads a model.
"""

import base64
import math

import pytest

from byb_scene.gltf import build_gltf, cube_arrays, ring_bounds, y_quaternion
from byb_scene.spec import best_placement, build_scene

COMPONENT_BYTES = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
TYPE_CHANNELS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
POSITION = 5126
INDICES = 5123


@pytest.fixture
def document(fitted):
    from byb_common.contracts import SimulationFitted

    scene = build_scene(SimulationFitted.model_validate(fitted))
    return build_gltf(scene, best_placement(scene.placements)), scene


def buffer_bytes(doc) -> bytes:
    uri = doc["buffers"][0]["uri"]
    assert uri.startswith("data:application/octet-stream;base64,")
    return base64.b64decode(uri.split(",", 1)[1])


def assert_well_formed(doc) -> None:
    assert doc["asset"]["version"] == "2.0"
    data = buffer_bytes(doc)
    total = doc["buffers"][0]["byteLength"]
    assert len(data) == total

    for view in doc["bufferViews"]:
        assert view["buffer"] == 0
        assert view["byteOffset"] % 4 == 0, "every view must start on a 4-byte boundary"
        assert view["byteOffset"] + view["byteLength"] <= total

    for accessor in doc["accessors"]:
        size = COMPONENT_BYTES[accessor["componentType"]] * TYPE_CHANNELS[accessor["type"]]
        view = doc["bufferViews"][accessor["bufferView"]]
        start = view["byteOffset"] + accessor.get("byteOffset", 0)
        assert start % COMPONENT_BYTES[accessor["componentType"]] == 0
        assert accessor["count"] > 0
        assert start + accessor["count"] * size <= view["byteOffset"] + view["byteLength"]
        if accessor["type"] == "VEC3" and "min" in accessor:
            assert len(accessor["min"]) == len(accessor["max"]) == 3

    for mesh in doc["meshes"]:
        for primitive in mesh["primitives"]:
            assert primitive["material"] < len(doc["materials"])
            assert primitive["indices"] < len(doc["accessors"])
            assert all(index < len(doc["accessors"]) for index in primitive["attributes"].values())

    known_attributes = {"POSITION", "NORMAL", "TEXCOORD_0"}
    for mesh in doc["meshes"]:
        for primitive in mesh["primitives"]:
            assert set(primitive["attributes"]) <= known_attributes
            assert {"POSITION", "NORMAL"} <= set(primitive["attributes"])

    for node in doc["nodes"]:
        if "mesh" in node:
            assert node["mesh"] < len(doc["meshes"])
        if "rotation" in node:
            assert abs(math.sqrt(sum(value * value for value in node["rotation"])) - 1.0) < 1e-4, "quaternions must be unit length"
        if "scale" in node:
            assert all(value > 0 for value in node["scale"])
        for child in node.get("children", []):
            assert child < len(doc["nodes"])

    scene = doc["scenes"][doc["scene"]]
    assert doc["scene"] < len(doc["scenes"])
    assert all(index < len(doc["nodes"]) for index in scene["nodes"])
    for material in doc["materials"]:
        factor = material["pbrMetallicRoughness"]["baseColorFactor"]
        assert len(factor) == 4 and all(0.0 <= channel <= 1.0 for channel in factor)


def test_the_document_a_viewer_would_accept(document):
    assert_well_formed(document[0])


def test_one_cube_is_shared_and_the_buffer_stays_small(document):
    doc = document[0]
    assert doc["buffers"][0]["byteLength"] == 648, "24 positions + 24 normals (float) + 36 indices (uint16)"
    assert len(doc["accessors"]) == 3
    assert len(doc["meshes"]) == len(doc["materials"]) <= 7


def test_the_cube_is_unit_sized_and_centred(document):
    positions, normals, indices = cube_arrays()
    assert len(positions) == len(normals) == 72
    assert len(indices) == 36 and max(indices) < 24
    accessor = document[0]["accessors"][0]
    assert accessor["min"] == [-0.5, -0.5, -0.5]
    assert accessor["max"] == [0.5, 0.5, 0.5]


def test_the_room_shell_and_the_product_are_both_in_the_scene(document):
    doc, scene = document
    names = [node["name"] for node in doc["nodes"]]
    assert {"floor", "back wall", "left wall", "right wall", "radiator"} <= set(names)
    assert "front wall" not in names, "the door wall stays open so the camera can look in"
    product = next(node for node in doc["nodes"] if node["name"].startswith("product:"))
    assert len(product["children"]) == len(scene.parts)


def test_the_walls_are_the_measured_room_not_the_declared_one(document):
    doc, scene = document
    floor = next(node for node in doc["nodes"] if node["name"] == "floor")
    assert floor["scale"][:2] == [scene.room_width_m, 0.05]
    assert floor["scale"][2] == scene.room_depth_m


def test_a_turn_is_carried_as_a_unit_quaternion_on_the_product():
    from byb_common.contracts import ScenePlacement

    spot = ScenePlacement(label="turned", fits=True, position_m=(1.0, 0.0, 1.0), rotation_deg=90.0)
    quaternion = y_quaternion(spot.rotation_deg)
    assert quaternion[0] == 0.0 and quaternion[2] == 0.0
    assert quaternion[1] == pytest.approx(-0.707107, abs=1e-4)
    assert y_quaternion(0.0) == [0.0, 0.0, 0.0, 1.0]


def test_an_obstacle_ring_becomes_a_box_at_its_own_bounds():
    centre_x, centre_z, size_x, size_z = ring_bounds([(0.0, 0.0), (0.9, 0.0), (0.9, 0.2), (0.0, 0.2)])
    assert (centre_x, centre_z) == pytest.approx((0.45, 0.1))
    assert (size_x, size_z) == pytest.approx((0.9, 0.2))


def test_a_room_without_a_product_still_opens(document):
    doc, scene = document
    empty = build_gltf(scene, None)
    assert_well_formed(empty)
    assert not any(node["name"].startswith("product:") for node in empty["nodes"])
    assert len(empty["nodes"]) == len(doc["nodes"]) - len(scene.parts) - 1


def test_an_obstacle_with_no_height_is_drawn_full_height(fitted):
    from byb_common.contracts import SimulationFitted

    message = SimulationFitted.model_validate(fitted)
    scene = build_scene(message)
    scene.walls[0].height_m = 0.0
    doc = build_gltf(scene, None)
    radiator = next(node for node in doc["nodes"] if node["name"] == "radiator")
    assert radiator["scale"][1] == scene.room_height_m
