"""A glTF 2.0 writer for the scene spec.

Only one piece of geometry exists in the buffer: a unit cube. Every box in the room - floor
slab, wall, obstacle, sofa cushion - is that cube on a node with a scale, which keeps the
document a few hundred bytes and means a viewer cannot disagree with the browser engine about
where the furniture is.

Coordinates follow the contract: product-local centimetres (x width, y depth, z up) become
scene metres (x width, y up, z depth), and a placement's turn is applied as -rotation_deg
about the scene y axis, so a parent node's rotation carries its part offsets with it.
"""

from __future__ import annotations

import base64
import math
import struct
from typing import Any

from byb_common.contracts import ScenePlacement, SceneSpec

PALETTE: dict[str, tuple[float, float, float, float]] = {
    "floor": (0.80, 0.74, 0.66, 1.0),
    "wall": (0.90, 0.89, 0.87, 1.0),
    "obstacle": (0.44, 0.46, 0.50, 1.0),
    "upholstery": (0.40, 0.50, 0.62, 1.0),
    "timber": (0.55, 0.38, 0.24, 1.0),
    "leg": (0.25, 0.24, 0.23, 1.0),
    "linen": (0.93, 0.93, 0.90, 1.0),
}
ROUGHNESS = 0.85

# Six faces: four outward-wound corners plus the normal they all share.
FACES = [
    ((0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5), (0.5, -0.5, 0.5), (1.0, 0.0, 0.0)),
    ((-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5), (-0.5, 0.5, -0.5), (-0.5, -0.5, -0.5), (-1.0, 0.0, 0.0)),
    ((-0.5, 0.5, -0.5), (-0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (0.5, 0.5, -0.5), (0.0, 1.0, 0.0)),
    ((-0.5, -0.5, -0.5), (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, -0.5, -0.5), (0.0, -1.0, 0.0)),
    ((-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (0.5, -0.5, 0.5), (0.0, 0.0, 1.0)),
    ((0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5), (-0.5, -0.5, -0.5), (0.0, 0.0, -1.0)),
]


def cube_arrays() -> tuple[list[float], list[float], list[int]]:
    positions: list[float] = []
    normals: list[float] = []
    indices: list[int] = []
    for face, corners in enumerate(FACES):
        base = face * 4
        for corner in corners[:4]:
            positions.extend(corner)
            normals.extend(corners[4])
        indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])
    return positions, normals, indices


def ring_bounds(ring: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    """Centre x/z plus size x/z of a flat polygon ring."""
    xs = [point[0] for point in ring]
    zs = [point[1] for point in ring]
    return (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2, max(xs) - min(xs), max(zs) - min(zs)


def y_quaternion(rotation_deg: float) -> list[float]:
    half = math.radians(-rotation_deg) / 2
    return [0.0, round(math.sin(half), 6), 0.0, round(math.cos(half), 6)]


class _Builder:
    """Nodes, meshes and materials. The buffer is packed once, at the end."""

    def __init__(self) -> None:
        self.nodes: list[dict[str, Any]] = []
        self.meshes: list[dict[str, Any]] = []
        self.materials: list[dict[str, Any]] = []
        self._mesh_for: dict[int, int] = {}
        self._material_for: dict[str, int] = {}

    def _index(self, node: dict[str, Any], parent: int | None) -> int:
        self.nodes.append(node)
        index = len(self.nodes) - 1
        if parent is not None:
            self.nodes[parent].setdefault("children", []).append(index)
        return index

    def material(self, tone: str) -> int:
        if tone in self._material_for:
            return self._material_for[tone]
        red, green, blue, alpha = PALETTE.get(tone, PALETTE["timber"])
        self.materials.append(
            {
                "name": tone,
                "doubleSided": True,
                "pbrMetallicRoughness": {
                    "baseColorFactor": [round(red, 4), round(green, 4), round(blue, 4), alpha],
                    "metallicFactor": 0.0,
                    "roughnessFactor": ROUGHNESS,
                },
            }
        )
        index = len(self.materials) - 1
        self._material_for[tone] = index
        return index

    def mesh(self, material_index: int) -> int:
        """The same cube, told apart only by its material."""
        if material_index not in self._mesh_for:
            self.meshes.append(
                {"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}, "indices": 2, "material": material_index}]}
            )
            self._mesh_for[material_index] = len(self.meshes) - 1
        return self._mesh_for[material_index]

    def add_group(self, name: str, centre: tuple[float, float, float], rotation_deg: float = 0.0) -> int:
        node: dict[str, Any] = {"name": name, "translation": [round(value, 4) for value in centre]}
        if rotation_deg:
            node["rotation"] = y_quaternion(rotation_deg)
        return self._index(node, None)

    def add_box(
        self,
        name: str,
        centre: tuple[float, float, float],
        size: tuple[float, float, float],
        tone: str,
        parent: int | None = None,
    ) -> int:
        node = {
            "name": name,
            "translation": [round(value, 4) for value in centre],
            "scale": [round(max(value, 0.0001), 4) for value in size],
            "mesh": self.mesh(self.material(tone)),
        }
        return self._index(node, parent)


def add_room(builder: _Builder, spec: SceneSpec, root: list[int]) -> None:
    width, depth, height = spec.room_width_m, spec.room_depth_m, spec.room_height_m
    root.append(builder.add_box("floor", (width / 2, -0.025, depth / 2), (width, 0.05, depth), "floor"))
    # The front wall is left out on purpose: the door lives there, and the camera looks in.
    root.append(builder.add_box("back wall", (width / 2, height / 2, depth + 0.03), (width + 0.06, height, 0.06), "wall"))
    root.append(builder.add_box("left wall", (-0.03, height / 2, depth / 2), (0.06, height, depth), "wall"))
    root.append(builder.add_box("right wall", (width + 0.03, height / 2, depth / 2), (0.06, height, depth), "wall"))
    for obstacle in spec.walls:
        centre_x, centre_z, size_x, size_z = ring_bounds(obstacle.ring)
        box_height = obstacle.height_m if obstacle.height_m > 0 else height
        root.append(builder.add_box(obstacle.label, (centre_x, box_height / 2, centre_z), (size_x, box_height, size_z), "obstacle"))


def add_product(builder: _Builder, spec: SceneSpec, spot: ScenePlacement, root: list[int]) -> None:
    """One parent node carries the placement's turn, so the part offsets rotate with it."""
    centre_x, centre_y, centre_z = spot.position_m
    parent = builder.add_group(f"product: {spot.label}", (centre_x, centre_y, centre_z), spot.rotation_deg)
    root.append(parent)
    for part in spec.parts:
        offset_x, offset_y, offset_z = (value / 100 for value in part.offset_cm)
        size_x, size_y, size_z = (value / 100 for value in part.size_cm)
        builder.add_box(f"{spot.label} / {part.label}", (offset_x, offset_z, offset_y), (size_x, size_z, size_y), part.tone, parent=parent)


def build_gltf(spec: SceneSpec, spot: ScenePlacement | None) -> dict[str, Any]:
    positions, normals, indices = cube_arrays()
    position_bytes = struct.pack(f"<{len(positions)}f", *positions)
    normal_bytes = struct.pack(f"<{len(normals)}f", *normals)
    index_bytes = struct.pack(f"<{len(indices)}H", *indices)

    builder = _Builder()
    root: list[int] = []
    add_room(builder, spec, root)
    if spot is not None:
        add_product(builder, spec, spot, root)

    axes = [positions[axis::3] for axis in range(3)]
    return {
        "asset": {"version": "2.0", "generator": "Buy You Before scene-service"},
        "scene": 0,
        "scenes": [{"name": "room", "nodes": root}],
        "nodes": builder.nodes,
        "meshes": builder.meshes,
        "materials": builder.materials,
        "buffers": [
            {
                "byteLength": len(position_bytes) + len(normal_bytes) + len(index_bytes),
                "uri": "data:application/octet-stream;base64," + base64.b64encode(position_bytes + normal_bytes + index_bytes).decode("ascii"),
            }
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(position_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": len(position_bytes), "byteLength": len(normal_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": len(position_bytes) + len(normal_bytes), "byteLength": len(index_bytes), "target": 34963},
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": len(positions) // 3,
                "type": "VEC3",
                "min": [min(axis) for axis in axes],
                "max": [max(axis) for axis in axes],
            },
            {"bufferView": 1, "componentType": 5126, "count": len(normals) // 3, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5123, "count": len(indices), "type": "SCALAR"},
        ],
    }
