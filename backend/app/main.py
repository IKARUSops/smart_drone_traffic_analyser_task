import secrets
import re
from pathlib import Path
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from app.core.settings import (
    ADMIN_CLEANUP_TOKEN,
    ALLOWED_CONTENT_TYPES,
    ALLOWED_CORS_ORIGINS,
    ALLOWED_VIDEO_EXTENSIONS,
    FRAME_DIR,
    FRAME_INDEX_FOR_LINE_PICKER,
    MAX_CONCURRENT_TASKS,
    OUTPUT_DIR,
    REPORT_DIR,
    UPLOAD_DIR,
)
from app.models import TaskRecord
from app.schemas.api import (
    LineSelectionRequest,
    ResultResponse,
    StatusResponse,
    UploadResponse,
)
from app.services.processor import process_task
from app.services.maintenance import cleanup_expired_artifacts
from app.services.video_io import extract_frame, save_upload_file
from app.store import store

app = FastAPI(title="Smart Drone Traffic Analyzer API", version="1.0.0")

RANGE_RE = re.compile(r"bytes=(\d+)-(\d*)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def assert_task_access(task_id: str, token: str | None) -> TaskRecord:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if token != task.access_token:
        raise HTTPException(status_code=401, detail="Invalid task token")
    return task


def stream_video_file(path: Path, range_header: str | None = None):
    if not path.exists():
        raise HTTPException(status_code=404, detail="Processed video not available")

    file_size = path.stat().st_size

    if not range_header:
        return FileResponse(
            path,
            media_type="video/mp4",
            headers={"Accept-Ranges": "bytes", "Cache-Control": "no-store"},
        )

    match = RANGE_RE.fullmatch(range_header.strip())
    if not match:
        raise HTTPException(status_code=416, detail="Invalid Range header")

    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else file_size - 1
    if start < 0 or start >= file_size or end < start:
        raise HTTPException(status_code=416, detail="Requested range not satisfiable")

    end = min(end, file_size - 1)
    chunk_size = end - start + 1

    def iterator():
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = chunk_size
            while remaining > 0:
                data = handle.read(min(1024 * 1024, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    return StreamingResponse(
        iterator(),
        status_code=206,
        media_type="video/mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-store",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(chunk_size),
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/tasks/upload", response_model=UploadResponse)
def upload_video(video: UploadFile = File(...)) -> UploadResponse:
    cleanup_expired_artifacts()

    if not video.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must include a filename")

    extension = Path(video.filename).suffix.lower() or ".mp4"
    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file extension")

    if video.content_type and video.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported content type")

    task_id = str(uuid4())
    access_token = secrets.token_urlsafe(24)

    input_video_path = UPLOAD_DIR / f"{task_id}{extension}"
    frame_preview_path = FRAME_DIR / f"{task_id}.jpg"
    output_video_path = OUTPUT_DIR / f"{task_id}.mp4"
    csv_report_path = REPORT_DIR / f"{task_id}.csv"
    xlsx_report_path = REPORT_DIR / f"{task_id}.xlsx"

    try:
        save_upload_file(video, input_video_path)
        used_frame = extract_frame(input_video_path, frame_preview_path, FRAME_INDEX_FOR_LINE_PICKER)
    except ValueError as exc:
        input_video_path.unlink(missing_ok=True)
        frame_preview_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        input_video_path.unlink(missing_ok=True)
        frame_preview_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Invalid or unreadable video") from exc

    task = TaskRecord(
        task_id=task_id,
        access_token=access_token,
        status="awaiting_line",
        input_video_path=str(input_video_path),
        frame_preview_path=str(frame_preview_path),
        output_video_path=str(output_video_path),
        csv_report_path=str(csv_report_path),
        xlsx_report_path=str(xlsx_report_path),
        stage="awaiting line selection",
    )
    store.create(task)

    return UploadResponse(
        task_id=task_id,
        access_token=access_token,
        status=task.status,
        frame_index=used_frame,
        frame_url=f"/api/v1/tasks/{task_id}/frame",
        next_step="line_selection_required",
    )


@app.get("/api/v1/tasks/{task_id}/frame")
def get_frame_preview(task_id: str, x_task_token: str | None = Header(default=None)) -> FileResponse:
    task = assert_task_access(task_id, x_task_token)

    path = Path(task.frame_preview_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Frame preview not found")

    return FileResponse(path, media_type="image/jpeg", filename=f"{task_id}-frame20.jpg")


@app.post("/api/v1/tasks/{task_id}/line")
def submit_line_selection(
    task_id: str,
    payload: LineSelectionRequest,
    background_tasks: BackgroundTasks,
    x_task_token: str | None = Header(default=None),
) -> dict[str, str]:
    assert_task_access(task_id, x_task_token)

    p1, p2 = payload.line_points
    if p1 == p2:
        raise HTTPException(status_code=400, detail="Two unique points are required")
    for point in (p1, p2):
        if point[0] >= payload.image_width or point[1] >= payload.image_height:
            raise HTTPException(status_code=400, detail="Line points must be within image bounds")

    reserve_state = store.reserve_processing_slot(
        task_id=task_id,
        max_concurrent_tasks=MAX_CONCURRENT_TASKS,
        line_points=payload.line_points,
        scene_mode=payload.scene_mode,
    )
    if reserve_state == "not_found":
        raise HTTPException(status_code=404, detail="Task not found")
    if reserve_state == "invalid_status":
        raise HTTPException(status_code=409, detail="Line cannot be changed in current status")
    if reserve_state == "capacity_reached":
        raise HTTPException(status_code=429, detail="Processing queue is full. Please retry shortly.")

    background_tasks.add_task(process_task, task_id)

    return {"task_id": task_id, "status": "queued", "message": "Line accepted. Processing started."}


@app.get("/api/v1/tasks/{task_id}/status", response_model=StatusResponse)
def get_task_status(task_id: str, x_task_token: str | None = Header(default=None)) -> StatusResponse:
    task = assert_task_access(task_id, x_task_token)

    return StatusResponse(
        task_id=task.task_id,
        status=task.status,
        stage=task.stage,
        progress_percent=task.progress_percent,
        processed_frames=task.processed_frames,
        total_frames=task.total_frames,
        fps=task.fps,
        eta_seconds=task.eta_seconds,
        error=task.error,
    )


@app.get("/api/v1/tasks/{task_id}/result", response_model=ResultResponse)
def get_task_result(task_id: str, x_task_token: str | None = Header(default=None)) -> ResultResponse:
    task = assert_task_access(task_id, x_task_token)
    if task.status != "completed" or task.result is None:
        raise HTTPException(status_code=409, detail="Result is not available yet")

    result = task.result
    return ResultResponse(
        task_id=task.task_id,
        status=task.status,
        total_unique_vehicles=result["total_unique_vehicles"],
        per_class_count=result["per_class_count"],
        per_direction_count=result["per_direction_count"],
        average_confidence_by_class=result["average_confidence_by_class"],
        processing_time_seconds=result["processing_time_seconds"],
        input_fps=result["input_fps"],
        processing_fps=result["processing_fps"],
        video_url=f"/api/v1/tasks/{task_id}/video/stream",
        download_url=f"/api/v1/tasks/{task_id}/video/download",
        available_reports=["csv", "xlsx"],
    )


@app.get("/api/v1/tasks/{task_id}/video/stream")
def get_processed_video_stream(
    task_id: str,
    x_task_token: str | None = Header(default=None),
    task_token: str | None = None,
    range: str | None = Header(default=None, alias="Range"),
):
    task = assert_task_access(task_id, x_task_token or task_token)

    path = Path(task.output_video_path)
    return stream_video_file(path, range)


@app.get("/api/v1/tasks/{task_id}/video/download")
def get_processed_video_download(
    task_id: str,
    x_task_token: str | None = Header(default=None),
    task_token: str | None = None,
) -> FileResponse:
    task = assert_task_access(task_id, x_task_token or task_token)

    path = Path(task.output_video_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Processed video not available")

    return FileResponse(path, media_type="video/mp4", filename=f"{task_id}-processed.mp4")


@app.get("/api/v1/tasks/{task_id}/report")
def download_report(task_id: str, format: str = "csv", x_task_token: str | None = Header(default=None)) -> FileResponse:
    task = assert_task_access(task_id, x_task_token)

    report_format = format.lower()
    if report_format not in {"csv", "xlsx"}:
        raise HTTPException(status_code=400, detail="format must be either csv or xlsx")

    path = Path(task.csv_report_path if report_format == "csv" else task.xlsx_report_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Requested report is not available")

    media_type = "text/csv" if report_format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(path, media_type=media_type, filename=f"{task_id}-report.{report_format}")


@app.post("/api/v1/maintenance/cleanup")
def cleanup_artifacts(x_admin_token: str | None = Header(default=None)) -> dict[str, int]:
    if not ADMIN_CLEANUP_TOKEN:
        raise HTTPException(status_code=403, detail="Cleanup endpoint is disabled")
    if x_admin_token != ADMIN_CLEANUP_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")

    removed_tasks = cleanup_expired_artifacts()
    return {"removed_tasks": removed_tasks}
