"""Measure a room from its photo with OpenCV.

A room photo gives three reliable straight lines: the vertical edge where the two
visible walls meet, and the two wall/floor junctions that run away from it. The
corner spans floor to ceiling, so its pixel length is the ruler everything else
is measured with. Objects standing on the floor are found as dark rectangles in
the floor band and mapped into room metres with a four-point homography of that
band.

The result is a proportion estimate, not a survey. `RoomScan.confidence` says how
much to trust it, and `main.py` keeps the shopper's declared dimensions whenever
the photo cannot be read or the reading looks unreliable.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import cv2
import numpy as np

from byb_common.contracts import Obstacle, RoomScan

logger = logging.getLogger("byb.vision")

MAX_DX_FOR_VERTICAL = math.sin(math.radians(30))  # within 30 degrees of vertical
MIN_COS_HORIZONTAL = math.cos(math.radians(15))  # within 15 degrees of horizontal
MIN_ROOM_M, MAX_ROOM_M = 1.0, 20.0


def _load(path: Path) -> np.ndarray | None:
    """cv2.imread is the only decode step, so an unreadable file simply returns None."""
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    return None if image is None or image.size == 0 else image


def _segments(gray: np.ndarray) -> list[tuple[tuple[float, float, float, float], float]]:
    """Line segments with their pixel length, from Canny edges plus probabilistic Hough."""
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)
    height, width = gray.shape
    raw = cv2.HoughLinesP(
        edges, 1, np.pi / 180.0, threshold=80,
        minLineLength=int(max(40, 0.2 * min(width, height))), maxLineGap=8,
    )
    found: list[tuple[tuple[float, float, float, float], float]] = []
    if raw is None:
        return found
    for line in raw:
        # OpenCV 4 hands back (N, 1, 4), OpenCV 5 (N, 4); flatten to the four endpoints.
        x0, y0, x1, y1 = map(float, np.asarray(line).reshape(-1)[:4])
        length = math.hypot(x1 - x0, y1 - y0)
        if length > 0:
            found.append(((x0, y0, x1, y1), length))
    return found


def _flatness(endpoints: tuple[float, float, float, float]) -> float:
    """|dx| / length: near 1 for horizontal lines, near 0 for vertical ones."""
    x0, y0, x1, y1 = endpoints
    length = math.hypot(x1 - x0, y1 - y0)
    return abs(x1 - x0) / length if length else 0.0


def _corner(segments, width: int, height: int) -> tuple[float | None, float, float]:
    """The wall-to-wall corner as (x ratio, pixel length, length/height coverage)."""
    candidates = [
        (endpoints, length) for endpoints, length in segments
        if _flatness(endpoints) <= MAX_DX_FOR_VERTICAL and length >= 0.35 * height
    ]
    if not candidates:
        return None, 0.0, 0.0
    (x0, _y0, x1, _y1), length = max(candidates, key=lambda pair: pair[1])
    centre = (x0 + x1) / 2
    if not 0.1 * width <= centre <= 0.9 * width:
        # A vertical line glued to an image edge is a door frame, not the room's corner.
        return None, 0.0, 0.0
    return centre / width, length, min(1.0, length / height)


def _junctions(segments, width: int, height: int, corner_x: float) -> tuple[float, float, float] | None:
    """Where each wall meets the floor at the two image edges, as y ratios, plus line strength."""
    left: list[tuple[float, float]] = []
    right: list[tuple[float, float]] = []
    for endpoints, length in segments:
        if _flatness(endpoints) < MIN_COS_HORIZONTAL or length < 0.2 * width:
            continue
        x0, y0, x1, y1 = endpoints
        if min(y0, y1) < 0.35 * height:
            continue  # ceiling and wall-to-wall junctions sit higher in the frame
        (left if (x0 + x1) / 2 < corner_x * width else right).append((max(y0, y1) / height, length / width))
    if not left and not right:
        return None
    strength = max((value for bucket in (left, right) for _y, value in bucket), default=0.0)
    far_left = max((y for y, _v in left), default=None)
    far_right = max((y for y, _v in right), default=None)
    if far_left is None:
        far_left = far_right
    if far_right is None:
        far_right = far_left
    return far_left, far_right, min(1.0, strength)


def _obstacles(
    gray: np.ndarray, junction_y: float, metres_per_pixel: float,
    room_width_m: float, room_depth_m: float, limit: int,
) -> list[Obstacle]:
    """Dark rectangles in the floor band, projected onto the room rectangle."""
    height, width = gray.shape
    y_top = int(junction_y * height) + 1
    if y_top > height - 10:
        return []
    band = gray[y_top:height, :]
    _, mask = cv2.threshold(band, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    band_to_room = cv2.getPerspectiveTransform(
        np.float32([[0.0, y_top], [float(width), y_top], [float(width), float(height)], [0.0, float(height)]]),
        np.float32([[0.0, room_depth_m], [room_width_m, room_depth_m], [room_width_m, 0.0], [0.0, 0.0]]),
    )
    band_area = float(band.shape[0] * band.shape[1])
    found: list[Obstacle] = []
    for index, contour in enumerate(sorted(contours, key=cv2.contourArea, reverse=True)):
        area = cv2.contourArea(contour)
        if not 0.005 * band_area <= area <= 0.35 * band_area:
            continue
        hull_area = cv2.contourArea(cv2.convexHull(contour))
        if not hull_area or area / hull_area < 0.7:
            continue
        approx = cv2.approxPolyDP(contour, 0.04 * cv2.arcLength(contour, True), True)
        if len(approx) < 4:
            continue
        points = approx.reshape(-1, 2).astype(np.float32)
        points[:, 1] += y_top
        projected = cv2.perspectiveTransform(points[None, ...], band_to_room)[0]
        ring = [
            (round(float(min(max(x, 0.0), room_width_m)), 2), round(float(min(max(y, 0.0), room_depth_m)), 2))
            for x, y in projected
        ]
        ring.append(ring[0])
        if len(ring) < 4:
            continue
        _x, _y, _w, box_height = cv2.boundingRect(points)
        found.append(
            Obstacle(
                label=f"object {index + 1} (photo)",
                ring=ring,
                height_m=round(min(2.4, max(0.05, box_height * metres_per_pixel)), 2),
                source="photo",
            )
        )
        if len(found) >= limit:
            break
    return found


def scan_photo(
    path: Path, *, room_width_m: float, room_depth_m: float, room_height_m: float,
    min_confidence: float, max_obstacles: int,
) -> RoomScan:
    """The declared room unless the photo reads well enough to replace it."""
    declared = RoomScan(
        width_m=room_width_m, depth_m=room_depth_m, height_m=room_height_m,
        measured=False, method="declared", confidence=0.0,
    )
    image = _load(path)
    if image is None:
        logger.warning("could not decode %s", path)
        return declared

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    segments = _segments(gray)
    corner_x, corner_px, corner_coverage = _corner(segments, width, height)
    junctions = _junctions(segments, width, height, corner_x if corner_x is not None else 0.5)

    scan = declared
    metres_per_pixel = room_height_m / corner_px if corner_px else 0.0
    if corner_x is not None and metres_per_pixel > 0:
        left_wall_m, right_wall_m = (corner_x * width * metres_per_pixel, (1 - corner_x) * width * metres_per_pixel)
        if junctions is not None:
            confidence = round(min(0.9, 0.35 + 0.3 * corner_coverage + 0.35 * junctions[2]), 2)
        else:
            confidence = round(min(0.6, 0.3 + 0.4 * corner_coverage), 2)
        inside = MIN_ROOM_M <= left_wall_m <= MAX_ROOM_M and MIN_ROOM_M <= right_wall_m <= MAX_ROOM_M
        if confidence >= min_confidence and inside:
            scan = RoomScan(
                width_m=round(left_wall_m, 2), depth_m=round(right_wall_m, 2),
                height_m=room_height_m, measured=True, method="photo", confidence=confidence,
            )
        else:
            scan = declared.model_copy(update={"method": "photo-ignored", "confidence": confidence})

    if junctions is not None:
        obstacles = _obstacles(
            gray, max(junctions[0], junctions[1]), metres_per_pixel or room_height_m / height,
            scan.width_m, scan.depth_m, max_obstacles,
        )
        if obstacles:
            logger.info("photo gave %d floor obstacle(s)", len(obstacles))
            scan = scan.model_copy(update={"obstacles": obstacles})
    return scan
