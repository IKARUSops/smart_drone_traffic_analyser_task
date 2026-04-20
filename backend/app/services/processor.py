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
from app.services.counter import (
    classify_direction,
    estimate_global_motion,
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
    if task is None or task.line_points is None:
        return

    p1 = (int(task.line_points[0][0]), int(task.line_points[0][1]))
    p2 = (int(task.line_points[1][0]), int(task.line_points[1][1]))

    store.update(task_id, status="processing", stage="tracking vehicles")

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
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        writer = cv2.VideoWriter(
            str(output_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (width, height),
        )
        if not writer.isOpened():
            store.update(task_id, status="failed", stage="error", error="Unable to create output video")
            return

        start_time = perf_counter()
        previous_points: dict[int, tuple[float, float]] = {}
        previous_signed_distances: dict[int, float] = {}
        counted_track_ids: set[int] = set()

        per_class_count: dict[str, int] = defaultdict(int)
        per_direction_count: dict[str, int] = defaultdict(int)
        confidence_accumulator: dict[str, list[float]] = defaultdict(list)
        report_rows: list[dict[str, object]] = []

        prev_gray: np.ndarray | None = None

        frame_index = 0
        event_index = 0

        while True:
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

                        if track_id in previous_points and track_id not in counted_track_ids:
                            prev_point = previous_points[track_id]
                            prev_signed = previous_signed_distances[track_id]

                            crossed_line = prev_signed * signed_distance < 0
                            displacement = np.hypot(point[0] - prev_point[0], point[1] - prev_point[1])

                            if crossed_line and displacement > 2.0:
                                corrected_dx = (point[0] - prev_point[0]) - global_dx
                                corrected_dy = (point[1] - prev_point[1]) - global_dy
                                direction = classify_direction(corrected_dx, corrected_dy)

                                counted_track_ids.add(track_id)
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
                                        "line_point_x": int(point[0]),
                                        "line_point_y": int(point[1]),
                                        "confidence": round(confidence, 4),
                                        "device_used": device,
                                        "processing_fps": 0.0,
                                    }
                                )

                        previous_points[track_id] = point
                        previous_signed_distances[track_id] = signed_distance

            cv2.line(frame, p1, p2, (0, 255, 0), 3)
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

        for row in report_rows:
            row["processing_fps"] = round(processing_fps, 2)

        average_confidence_by_class = {
            key: round(sum(values) / len(values), 4) if values else 0.0
            for key, values in confidence_accumulator.items()
        }

        result = {
            "task_id": task_id,
            "status": "completed",
            "total_unique_vehicles": int(sum(per_class_count.values())),
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
    except Exception as exc:
        logger.exception("Task %s failed during processing", task_id)
        store.update(task_id, status="failed", stage="error", error="Processing failed")
    finally:
        if cap is not None:
            cap.release()
        if writer is not None:
            writer.release()
