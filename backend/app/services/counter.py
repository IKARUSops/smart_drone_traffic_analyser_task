from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np


Direction = Literal["North", "South", "East", "West"]


@dataclass
class TrackState:
    previous_point: tuple[float, float]
    previous_signed_distance: float
    crossed: bool = False


def tracking_point_from_bbox(
    bbox: np.ndarray,
    scene_mode: Literal["auto", "top_down", "angled"] = "auto",
) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox.tolist()
    centroid = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
    bottom_center = ((x1 + x2) / 2.0, y2)

    if scene_mode == "top_down":
        return centroid
    if scene_mode == "angled":
        return bottom_center

    # Auto heuristic: taller boxes usually indicate angled perspective.
    width = max(x2 - x1, 1.0)
    height = max(y2 - y1, 1.0)
    aspect_ratio = height / width
    return bottom_center if aspect_ratio > 1.1 else centroid


def signed_distance_to_line(
    point: tuple[float, float],
    p1: tuple[int, int],
    p2: tuple[int, int],
) -> float:
    px, py = point
    x1, y1 = p1
    x2, y2 = p2
    return float((x2 - x1) * (py - y1) - (y2 - y1) * (px - x1))


def estimate_global_motion(prev_gray: np.ndarray, gray: np.ndarray) -> tuple[float, float]:
    prev_points = cv2.goodFeaturesToTrack(prev_gray, maxCorners=300, qualityLevel=0.01, minDistance=8)
    if prev_points is None or len(prev_points) < 10:
        return 0.0, 0.0

    next_points, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, gray, prev_points, None)
    if next_points is None or status is None:
        return 0.0, 0.0

    good_prev = prev_points[status.flatten() == 1]
    good_next = next_points[status.flatten() == 1]
    if len(good_prev) < 10:
        return 0.0, 0.0

    deltas = good_next - good_prev
    dx = float(np.median(deltas[:, 0]))
    dy = float(np.median(deltas[:, 1]))
    return dx, dy


def classify_direction(dx: float, dy: float) -> Direction:
    if abs(dx) >= abs(dy):
        return "East" if dx >= 0 else "West"
    return "South" if dy >= 0 else "North"
