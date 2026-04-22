from collections import defaultdict
from datetime import datetime
import logging
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from app.core.settings import VEHICLE_CLASS_IDS, YOLO_MODEL
from app.services.database import upsert_dashboard_task
from app.services.counter import (
    classify_direction,
    compute_box_edges,
    estimate_global_motion,
    point_to_box_edge_crossing,
    signed_distance_to_line,
    tracking_point_from_bbox,
)
from app.services.reporting import write_csv_report, write_xlsx_report
from app.store import store


CLASS_NAME_MAP = {
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

_model: YOLO | None = None
logger = logging.getLogger(__name__)


def persist_task_snapshot(task_id: str) -> None:
    task = store.get(task_id)
    if task is not None:
        upsert_dashboard_task(task)


def draw_box_outline(frame: np.ndarray, points: list[list[int]], color: tuple[int, int, int] = (0, 255, 0), thickness: int = 3) -> None:
    polygon = np.array(points, dtype=np.int32).reshape((-1, 1, 2))
    cv2.polylines(frame, [polygon], isClosed=True, color=color, thickness=thickness)


def draw_compass_overlay(frame: np.ndarray) -> None:
    height, width = frame.shape[:2]
    color = (80, 220, 255)
    text_color = (240, 240, 240)

    top_center = (width // 2, 36)
    right_center = (width - 36, height // 2)
    left_center = (36, height // 2)
    bottom_center = (width // 2, height - 36)

    cv2.arrowedLine(frame, (top_center[0], top_center[1] + 18), (top_center[0], top_center[1] - 12), color, 2, tipLength=0.35)
    cv2.putText(frame, "North", (top_center[0] - 30, top_center[1] + 38), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)

    cv2.arrowedLine(frame, (right_center[0] - 18, right_center[1]), (right_center[0] + 12, right_center[1]), color, 2, tipLength=0.35)
    cv2.putText(frame, "East", (right_center[0] - 22, right_center[1] - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)

    cv2.arrowedLine(frame, (left_center[0] + 18, left_center[1]), (left_center[0] - 12, left_center[1]), color, 2, tipLength=0.35)
    cv2.putText(frame, "West", (left_center[0] - 20, left_center[1] - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)

    cv2.arrowedLine(frame, (bottom_center[0], bottom_center[1] - 18), (bottom_center[0], bottom_center[1] + 12), color, 2, tipLength=0.35)
    cv2.putText(frame, "South", (bottom_center[0] - 30, bottom_center[1] - 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)


def draw_vehicle_counter_panel(frame: np.ndarray, per_class_count: dict[str, int]) -> None:
    panel_x, panel_y = 12, 84
    panel_width, panel_height = 220, 190

    overlay = frame.copy()
    cv2.rectangle(overlay, (panel_x, panel_y), (panel_x + panel_width, panel_y + panel_height), (24, 24, 24), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    cv2.rectangle(frame, (panel_x, panel_y), (panel_x + panel_width, panel_y + panel_height), (80, 220, 255), 2)

    cv2.putText(frame, "Vehicle Counters", (panel_x + 10, panel_y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 2)

    classes = ["bicycle", "car", "motorcycle", "bus", "truck"]
    for idx, vehicle_class in enumerate(classes):
        count = per_class_count.get(vehicle_class, 0)
        y = panel_y + 54 + idx * 26
        cv2.putText(frame, f"{vehicle_class.title():<10} {count}", (panel_x + 10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 2)


def render_edge_counters(
    frame: np.ndarray,
    per_direction_count: dict[str, int],
    orientation: str,
) -> None:
    summary = (
        f"N:{per_direction_count.get('North', 0)} "
        f"S:{per_direction_count.get('South', 0)} "
        f"E:{per_direction_count.get('East', 0)} "
        f"W:{per_direction_count.get('West', 0)}"
    )
    cv2.putText(frame, summary, (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.putText(frame, f"Region: {orientation}", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)


def classify_entry_direction(edge_crossed: str | None, dx: float, dy: float, orientation: str) -> str:
    if edge_crossed == "top":
        return "South"
    if edge_crossed == "bottom":
        return "North"
    if edge_crossed == "left":
        return "East"
    if edge_crossed == "right":
        return "West"
    return classify_direction(dx, dy, orientation=orientation)


def open_video_writer(output_path: Path, fps: float, frame_size: tuple[int, int]) -> cv2.VideoWriter:
    codec_candidates = ["avc1", "H264", "mp4v"]

    for codec in codec_candidates:
        writer = cv2.VideoWriter(
            str(output_path),
            cv2.VideoWriter_fourcc(*codec),
            fps,
            frame_size,
        )
        if writer.isOpened():
            logger.info("Opened video writer for %s with codec %s", output_path.name, codec)
            return writer

    raise RuntimeError("Unable to create output video writer with a supported codec")


def get_model() -> YOLO:
    global _model
    if _model is None:
        _model = YOLO(YOLO_MODEL)
    return _model


def resolve_device() -> tuple[str, bool]:
    if torch.cuda.is_available():
        return "cuda:0", True
    return "cpu", False


def process_task(task_id: str) -> None:
    task = store.get(task_id)
    if task is None or (task.line_points is None and task.region_box is None):
        return

    use_region_mode = task.region_box is not None
    p1 = (0, 0)
    p2 = (0, 0)
    edges: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {}

    if use_region_mode and task.region_box is not None:
        edges = compute_box_edges(task.region_box)
    elif task.line_points is not None:
        p1 = (int(task.line_points[0][0]), int(task.line_points[0][1]))
        p2 = (int(task.line_points[1][0]), int(task.line_points[1][1]))
    else:
        return

    store.update(task_id, status="processing", stage="tracking vehicles")
    persist_task_snapshot(task_id)

    cap: cv2.VideoCapture | None = None
    writer: cv2.VideoWriter | None = None

    try:
        model = get_model()
        device, half = resolve_device()

        input_path = Path(task.input_video_path)
        output_path = Path(task.output_video_path)
        csv_path = Path(task.csv_report_path)
        xlsx_path = Path(task.xlsx_report_path)

        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            store.update(task_id, status="failed", stage="error", error="Unable to open video")
            persist_task_snapshot(task_id)
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        try:
            writer = open_video_writer(output_path, fps, (width, height))
        except RuntimeError:
            store.update(task_id, status="failed", stage="error", error="Unable to create output video")
            persist_task_snapshot(task_id)
            return

        start_time = perf_counter()
        previous_points: dict[int, tuple[float, float]] = {}
        previous_inside_region: dict[int, bool] = {}
        previous_signed_distances: dict[int, float] = {}
        counted_track_ids: set[int] = set()
        unique_counted_track_ids: set[int] = set()

        per_class_count: dict[str, int] = defaultdict(int)
        per_direction_count: dict[str, int] = defaultdict(int)
        confidence_accumulator: dict[str, list[float]] = defaultdict(list)
        report_rows: list[dict[str, object]] = []

        prev_gray: np.ndarray | None = None

        frame_index = 0
        event_index = 0

        while True:
            runtime_task = store.get(task_id)
            if runtime_task is not None and runtime_task.cancellation_requested:
                store.update(
                    task_id,
                    status="cancelled",
                    stage="cancelled",
                    error=None,
                )
                persist_task_snapshot(task_id)
                return

            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            global_dx, global_dy = (0.0, 0.0)
            if prev_gray is not None:
                global_dx, global_dy = estimate_global_motion(prev_gray, gray)
            prev_gray = gray

            results = model.track(
                frame,
                persist=True,
                classes=VEHICLE_CLASS_IDS,
                device=device,
                half=half,
                verbose=False,
                imgsz=640,
            )

            if results:
                boxes = results[0].boxes
                if boxes is not None and boxes.id is not None:
                    ids = boxes.id.int().cpu().tolist()
                    xyxy = boxes.xyxy.cpu().numpy()
                    classes = boxes.cls.int().cpu().tolist()
                    confidences = boxes.conf.cpu().tolist()

                    for i, track_id in enumerate(ids):
                        cls_id = classes[i]
                        class_name = CLASS_NAME_MAP.get(cls_id, f"class_{cls_id}")
                        confidence = float(confidences[i])
                        bbox = xyxy[i]

                        point = tracking_point_from_bbox(bbox, task.scene_mode)
                        signed_distance = signed_distance_to_line(point, p1, p2)

                        x1, y1, x2, y2 = [int(v) for v in bbox.tolist()]
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 180, 255), 2)
                        cv2.putText(
                            frame,
                            f"ID {track_id} {class_name}",
                            (x1, max(24, y1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (255, 255, 255),
                            2,
                        )

                        if track_id in previous_points:
                            prev_point = previous_points[track_id]
                            corrected_dx = (point[0] - prev_point[0]) - global_dx
                            corrected_dy = (point[1] - prev_point[1]) - global_dy

                            if use_region_mode and task.region_box is not None:
                                polygon = np.array(task.region_box, dtype=np.int32)
                                prev_inside = previous_inside_region.get(
                                    track_id,
                                    cv2.pointPolygonTest(polygon, (float(prev_point[0]), float(prev_point[1])), False) >= 0,
                                )
                                curr_inside = cv2.pointPolygonTest(polygon, (float(point[0]), float(point[1])), False) >= 0
                                edge_crossed = point_to_box_edge_crossing(
                                    prev_point,
                                    point,
                                    edges,
                                    task.region_orientation,
                                )

                                entered_region = (not prev_inside) and curr_inside
                                if entered_region and track_id not in counted_track_ids:
                                    direction = classify_entry_direction(
                                        edge_crossed=edge_crossed,
                                        dx=corrected_dx,
                                        dy=corrected_dy,
                                        orientation=task.region_orientation,
                                    )

                                    counted_track_ids.add(track_id)
                                    unique_counted_track_ids.add(track_id)
                                    per_class_count[class_name] += 1
                                    per_direction_count[direction] += 1
                                    confidence_accumulator[class_name].append(confidence)

                                    event_index += 1
                                    report_rows.append(
                                        {
                                            "event_id": event_index,
                                            "timestamp_seconds": round(frame_index / fps, 3),
                                            "frame_index": frame_index,
                                            "track_id": track_id,
                                            "vehicle_class": class_name,
                                            "crossing_direction": direction,
                                            "crossing_point_x": int(point[0]),
                                            "crossing_point_y": int(point[1]),
                                            "edge_crossed": edge_crossed or "entry",
                                            "box_region_id": "region-1",
                                            "confidence": round(confidence, 4),
                                            "device_used": device,
                                            "processing_fps": 0.0,
                                        }
                                    )
                                previous_inside_region[track_id] = curr_inside
                            else:
                                prev_signed = previous_signed_distances[track_id]

                                crossed_line = prev_signed * signed_distance < 0
                                displacement = np.hypot(point[0] - prev_point[0], point[1] - prev_point[1])

                                if crossed_line and displacement > 2.0 and track_id not in counted_track_ids:
                                    direction = classify_direction(corrected_dx, corrected_dy)

                                    counted_track_ids.add(track_id)
                                    unique_counted_track_ids.add(track_id)
                                    per_class_count[class_name] += 1
                                    per_direction_count[direction] += 1
                                    confidence_accumulator[class_name].append(confidence)

                                    event_index += 1
                                    report_rows.append(
                                        {
                                            "event_id": event_index,
                                            "timestamp_seconds": round(frame_index / fps, 3),
                                            "frame_index": frame_index,
                                            "track_id": track_id,
                                            "vehicle_class": class_name,
                                            "crossing_direction": direction,
                                            "crossing_point_x": int(point[0]),
                                            "crossing_point_y": int(point[1]),
                                            "edge_crossed": "line",
                                            "box_region_id": "",
                                            "confidence": round(confidence, 4),
                                            "device_used": device,
                                            "processing_fps": 0.0,
                                        }
                                    )

                        previous_points[track_id] = point
                        if not use_region_mode:
                            previous_signed_distances[track_id] = signed_distance

            if use_region_mode and task.region_box is not None:
                draw_box_outline(frame, task.region_box)
                render_edge_counters(frame, per_direction_count, task.region_orientation)
            else:
                cv2.line(frame, p1, p2, (0, 255, 0), 3)

            draw_compass_overlay(frame)
            draw_vehicle_counter_panel(frame, per_class_count)
            writer.write(frame)

            frame_index += 1
            elapsed = max(perf_counter() - start_time, 1e-6)
            current_fps = frame_index / elapsed
            progress_percent = (frame_index / total_frames) * 100 if total_frames > 0 else 0.0
            remaining = (total_frames - frame_index) / current_fps if current_fps > 0 else None

            store.update(
                task_id,
                processed_frames=frame_index,
                total_frames=total_frames,
                progress_percent=round(progress_percent, 2),
                stage="tracking vehicles",
                fps=round(current_fps, 2),
                eta_seconds=round(remaining, 2) if remaining is not None else None,
            )

        total_time = max(perf_counter() - start_time, 1e-6)
        processing_fps = frame_index / total_time

        # Finalize media handles before exposing completed status and video URL.
        if cap is not None:
            cap.release()
            cap = None
        if writer is not None:
            writer.release()
            writer = None

        for row in report_rows:
            row["processing_fps"] = round(processing_fps, 2)

        average_confidence_by_class = {
            key: round(sum(values) / len(values), 4) if values else 0.0
            for key, values in confidence_accumulator.items()
        }

        result = {
            "task_id": task_id,
            "status": "completed",
            "total_unique_vehicles": len(unique_counted_track_ids),
            "per_class_count": dict(per_class_count),
            "per_direction_count": {
                "North": per_direction_count.get("North", 0),
                "South": per_direction_count.get("South", 0),
                "East": per_direction_count.get("East", 0),
                "West": per_direction_count.get("West", 0),
            },
            "average_confidence_by_class": average_confidence_by_class,
            "processing_time_seconds": round(total_time, 3),
            "input_fps": round(fps, 2),
            "processing_fps": round(processing_fps, 2),
            "generated_at": datetime.utcnow().isoformat(),
        }

        write_csv_report(csv_path, report_rows)
        write_xlsx_report(xlsx_path, report_rows)

        store.update(
            task_id,
            status="completed",
            stage="completed",
            progress_percent=100.0,
            result=result,
        )
        persist_task_snapshot(task_id)
    except Exception as exc:
        logger.exception("Task %s failed during processing", task_id)
        store.update(task_id, status="failed", stage="error", error="Processing failed")
        persist_task_snapshot(task_id)
    finally:
        if cap is not None:
            cap.release()
        if writer is not None:
            writer.release()
