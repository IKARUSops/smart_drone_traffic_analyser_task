import json
import sqlite3
import zlib
from pathlib import Path
from typing import Any, Optional

from app.core.settings import DATA_DIR
from app.models import TaskRecord


DB_PATH = DATA_DIR / "traffic_analyzer.sqlite3"


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_database() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dashboard_tasks (
                task_id TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                status TEXT NOT NULL,
                stage TEXT,
                created_at TEXT,
                updated_at TEXT,
                scene_mode TEXT,
                region_orientation TEXT,
                progress_percent REAL,
                processed_frames INTEGER,
                total_frames INTEGER,
                fps REAL,
                eta_seconds REAL,
                error TEXT,
                total_unique_vehicles INTEGER,
                processing_time_seconds REAL,
                input_fps REAL,
                processing_fps REAL,
                per_class_count_json TEXT,
                per_direction_count_json TEXT,
                result_blob BLOB,
                compression TEXT,
                input_video_path TEXT,
                frame_preview_path TEXT,
                output_video_path TEXT,
                csv_report_path TEXT,
                xlsx_report_path TEXT
            )
            """
        )
        conn.commit()


def _compress_result(result: Optional[dict[str, Any]]) -> bytes:
    if result is None:
        return b""
    payload = json.dumps(result, separators=(",", ":")).encode("utf-8")
    return zlib.compress(payload, level=6)


def _decompress_result(blob: bytes | None, compression: str | None) -> Optional[dict[str, Any]]:
    if not blob:
        return None
    if compression == "zlib":
        data = zlib.decompress(blob)
    else:
        data = blob
    return json.loads(data.decode("utf-8"))


def upsert_dashboard_task(task: TaskRecord) -> None:
    result = task.result or {}
    per_class = result.get("per_class_count", {})
    per_direction = result.get("per_direction_count", {})

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO dashboard_tasks (
                task_id, access_token, status, stage, created_at, updated_at,
                scene_mode, region_orientation, progress_percent, processed_frames,
                total_frames, fps, eta_seconds, error, total_unique_vehicles,
                processing_time_seconds, input_fps, processing_fps,
                per_class_count_json, per_direction_count_json, result_blob,
                compression, input_video_path, frame_preview_path, output_video_path,
                csv_report_path, xlsx_report_path
            ) VALUES (
                :task_id, :access_token, :status, :stage, :created_at, :updated_at,
                :scene_mode, :region_orientation, :progress_percent, :processed_frames,
                :total_frames, :fps, :eta_seconds, :error, :total_unique_vehicles,
                :processing_time_seconds, :input_fps, :processing_fps,
                :per_class_count_json, :per_direction_count_json, :result_blob,
                :compression, :input_video_path, :frame_preview_path, :output_video_path,
                :csv_report_path, :xlsx_report_path
            )
            ON CONFLICT(task_id) DO UPDATE SET
                access_token=excluded.access_token,
                status=excluded.status,
                stage=excluded.stage,
                updated_at=excluded.updated_at,
                scene_mode=excluded.scene_mode,
                region_orientation=excluded.region_orientation,
                progress_percent=excluded.progress_percent,
                processed_frames=excluded.processed_frames,
                total_frames=excluded.total_frames,
                fps=excluded.fps,
                eta_seconds=excluded.eta_seconds,
                error=excluded.error,
                total_unique_vehicles=excluded.total_unique_vehicles,
                processing_time_seconds=excluded.processing_time_seconds,
                input_fps=excluded.input_fps,
                processing_fps=excluded.processing_fps,
                per_class_count_json=excluded.per_class_count_json,
                per_direction_count_json=excluded.per_direction_count_json,
                result_blob=excluded.result_blob,
                compression=excluded.compression,
                input_video_path=excluded.input_video_path,
                frame_preview_path=excluded.frame_preview_path,
                output_video_path=excluded.output_video_path,
                csv_report_path=excluded.csv_report_path,
                xlsx_report_path=excluded.xlsx_report_path
            """,
            {
                "task_id": task.task_id,
                "access_token": task.access_token,
                "status": task.status,
                "stage": task.stage,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
                "scene_mode": task.scene_mode,
                "region_orientation": task.region_orientation,
                "progress_percent": task.progress_percent,
                "processed_frames": task.processed_frames,
                "total_frames": task.total_frames,
                "fps": task.fps,
                "eta_seconds": task.eta_seconds,
                "error": task.error,
                "total_unique_vehicles": result.get("total_unique_vehicles"),
                "processing_time_seconds": result.get("processing_time_seconds"),
                "input_fps": result.get("input_fps"),
                "processing_fps": result.get("processing_fps"),
                "per_class_count_json": json.dumps(per_class),
                "per_direction_count_json": json.dumps(per_direction),
                "result_blob": _compress_result(task.result),
                "compression": "zlib",
                "input_video_path": task.input_video_path,
                "frame_preview_path": task.frame_preview_path,
                "output_video_path": task.output_video_path,
                "csv_report_path": task.csv_report_path,
                "xlsx_report_path": task.xlsx_report_path,
            },
        )
        conn.commit()


def _row_to_task_dict(row: sqlite3.Row) -> dict[str, Any]:
    per_class = json.loads(row["per_class_count_json"] or "{}")
    per_direction = json.loads(row["per_direction_count_json"] or "{}")
    result = _decompress_result(row["result_blob"], row["compression"])

    return {
        "task_id": row["task_id"],
        "access_token": row["access_token"],
        "status": row["status"],
        "stage": row["stage"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "scene_mode": row["scene_mode"],
        "region_orientation": row["region_orientation"],
        "progress_percent": row["progress_percent"],
        "processed_frames": row["processed_frames"],
        "total_frames": row["total_frames"],
        "fps": row["fps"],
        "eta_seconds": row["eta_seconds"],
        "error": row["error"],
        "total_unique_vehicles": row["total_unique_vehicles"],
        "processing_time_seconds": row["processing_time_seconds"],
        "input_fps": row["input_fps"],
        "processing_fps": row["processing_fps"],
        "per_class_count": per_class,
        "per_direction_count": per_direction,
        "result": result,
        "input_video_path": row["input_video_path"],
        "frame_preview_path": row["frame_preview_path"],
        "output_video_path": row["output_video_path"],
        "csv_report_path": row["csv_report_path"],
        "xlsx_report_path": row["xlsx_report_path"],
        "compression": row["compression"],
    }


def list_dashboard_tasks() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM dashboard_tasks
            ORDER BY updated_at DESC
            """
        ).fetchall()
    return [_row_to_task_dict(row) for row in rows]


def get_dashboard_task(task_id: str) -> Optional[dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM dashboard_tasks
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_task_dict(row)


def delete_dashboard_task(task_id: str) -> bool:
    task = get_dashboard_task(task_id)
    if task is None:
        return False

    for key in ["input_video_path", "frame_preview_path", "output_video_path", "csv_report_path", "xlsx_report_path"]:
        path_value = task.get(key)
        if path_value:
            Path(path_value).unlink(missing_ok=True)

    with _connect() as conn:
        conn.execute("DELETE FROM dashboard_tasks WHERE task_id = ?", (task_id,))
        conn.commit()

    return True
