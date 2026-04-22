from dataclasses import dataclass
from typing import Literal, Optional

import cv2
import numpy as np


Direction = Literal["North", "South", "East", "West"]
RegionOrientation = Literal["horizontal", "vertical"]


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


def compute_box_edges(
    box_points: list[list[int]],
) -> dict[str, tuple[tuple[int, int], tuple[int, int]]]:
    tl = (int(box_points[0][0]), int(box_points[0][1]))
    tr = (int(box_points[1][0]), int(box_points[1][1]))
    br = (int(box_points[2][0]), int(box_points[2][1]))
    bl = (int(box_points[3][0]), int(box_points[3][1]))

    return {
        "top": (tl, tr),
        "right": (tr, br),
        "bottom": (bl, br),
        "left": (tl, bl),
    }


def point_to_box_edge_crossing(
    prev_pt: tuple[float, float],
    curr_pt: tuple[float, float],
    edges: dict[str, tuple[tuple[int, int], tuple[int, int]]],
    orientation: RegionOrientation,
) -> Optional[str]:
    monitored_edges = ("top", "bottom") if orientation == "horizontal" else ("left", "right")
    crossed_candidates: list[tuple[str, float]] = []

    movement = float(np.hypot(curr_pt[0] - prev_pt[0], curr_pt[1] - prev_pt[1]))
    if movement <= 2.0:
        return None

    for edge_name in monitored_edges:
        edge = edges.get(edge_name)
        if edge is None:
            continue
        p1, p2 = edge
        prev_d = signed_distance_to_line(prev_pt, p1, p2)
        curr_d = signed_distance_to_line(curr_pt, p1, p2)

        crossed = prev_d * curr_d < 0
        if crossed:
            crossed_candidates.append((edge_name, abs(curr_d)))

    if not crossed_candidates:
        return None

    crossed_candidates.sort(key=lambda item: item[1])
    return crossed_candidates[0][0]


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

    # OpenCV LK points are often shaped as (N, 1, 2); normalize to (N, 2).
    prev_xy = np.asarray(good_prev, dtype=np.float32).reshape(-1, 2)
    next_xy = np.asarray(good_next, dtype=np.float32).reshape(-1, 2)
    if prev_xy.shape[0] < 10 or next_xy.shape[0] < 10:
        return 0.0, 0.0

    deltas = next_xy - prev_xy
    dx = float(np.median(deltas[:, 0]))
    dy = float(np.median(deltas[:, 1]))
    return dx, dy


def classify_direction(
    dx: float,
    dy: float,
    edge_crossed: Optional[str] = None,
    orientation: Optional[RegionOrientation] = None,
) -> Direction:
    if edge_crossed is not None and orientation is not None:
        if orientation == "horizontal":
            if abs(dy) >= 0.2:
                return "South" if dy >= 0 else "North"
            return "East" if dx >= 0 else "West"

        if abs(dx) >= 0.2:
            return "East" if dx >= 0 else "West"
        return "South" if dy >= 0 else "North"

    if abs(dx) >= abs(dy):
        return "East" if dx >= 0 else "West"
    return "South" if dy >= 0 else "North"
