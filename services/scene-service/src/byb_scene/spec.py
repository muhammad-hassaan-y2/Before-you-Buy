"""Builds the SceneSpec a browser engine needs out of the message geometry-service published.

Everything is already in metres or centimetres by the time it arrives here, so this module
is placement maths rather than measurement: it decides where the cameras stand, which part
boxes describe the product, and which placement the glTF should show.
"""

from __future__ import annotations

from byb_common.contracts import FitPlacement, ProductProfile, RoomScan, SceneCamera, ScenePlacement, SceneSpec, SimulationFitted
from byb_common.parts import build_parts

EYE_HEIGHT_M = 1.62


class SceneInputError(ValueError):
    """The message is missing something scene-service cannot invent."""


def best_placement(fit_placements: list[FitPlacement]) -> FitPlacement | None:
    """The spot the viewport opens on: the roomiest walkway that still fits."""
    fitting = [spot for spot in fit_placements if spot.fits]
    if not fitting:
        return fit_placements[0] if fit_placements else None
    return max(fitting, key=lambda spot: min(spot.walkway_m.values() or [0.0]))


def cameras_for(scan: RoomScan) -> list[SceneCamera]:
    """Three fixed viewpoints. The overview sits outside the walls so the room reads as a box."""
    width, depth, height = scan.width_m, scan.depth_m, scan.height_m
    centre = (round(width / 2, 2), round(depth / 2, 2))
    return [
        SceneCamera(
            label="overview",
            position_m=(round(width * 1.45, 2), round(height * 1.5, 2), round(-depth * 0.65, 2)),
            target_m=(centre[0], 0.45, centre[1]),
            fov_deg=45.0,
        ),
        SceneCamera(
            label="top-down",
            position_m=(centre[0], round(max(width, depth) * 1.45 + 1.0, 2), round(centre[1] + 0.01, 2)),
            target_m=(centre[0], 0.0, centre[1]),
            fov_deg=50.0,
        ),
        SceneCamera(
            label="first-person",
            position_m=(centre[0], EYE_HEIGHT_M, 0.3),
            target_m=(centre[0], 1.15, depth),
            fov_deg=62.0,
        ),
    ]


def build_scene(fitted: SimulationFitted, *, max_parts: int = 40) -> SceneSpec:
    if fitted.profile is None or fitted.fit is None or fitted.scan is None:
        raise SceneInputError("scene-service needs a profile, a scan and a fit report")

    profile: ProductProfile = fitted.profile
    scan = fitted.scan
    geometry = profile.geometry
    parts = (profile.parts or build_parts(profile.category, geometry.width_cm, geometry.depth_cm, geometry.height_cm))[:max_parts]

    return SceneSpec(
        room_width_m=scan.width_m,
        room_depth_m=scan.depth_m,
        room_height_m=scan.height_m,
        walls=list(fitted.fit.obstacles),
        door_swing_m=fitted.fit.door_swing_m,
        product_name=profile.name,
        product_category=profile.category,
        parts=parts,
        geometry=geometry,
        clearance_m=round(geometry.clearance_cm / 100, 3),
        placements=[
            ScenePlacement(
                label=spot.label,
                fits=spot.fits,
                position_m=(spot.centre_x_m, 0.0, spot.centre_y_m),
                rotation_deg=spot.rotation_deg,
                walkway_m=spot.walkway_m,
            )
            for spot in fitted.fit.placements
        ],
        cameras=cameras_for(scan),
        verdict=fitted.fit.verdict,
        coverage_pct=fitted.fit.coverage_pct,
    )
