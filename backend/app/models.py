from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class TaskRecord:
    task_id: str
    access_token: str
    status: str
    input_video_path: str
    frame_preview_path: str
    output_video_path: str
    csv_report_path: str
    xlsx_report_path: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    line_points: Optional[list[list[int]]] = None
    region_box: Optional[list[list[int]]] = None
    region_orientation: str = "horizontal"
    scene_mode: str = "auto"
    cancellation_requested: bool = False
    processed_events: list[dict[str, Any]] = field(default_factory=list)
    progress_percent: float = 0.0
    processed_frames: int = 0
    total_frames: int = 0
    stage: str = "uploaded"
    fps: float = 0.0
    eta_seconds: Optional[float] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "access_token": self.access_token,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "line_points": self.line_points,
            "region_box": self.region_box,
            "region_orientation": self.region_orientation,
            "scene_mode": self.scene_mode,
            "cancellation_requested": self.cancellation_requested,
            "processed_events": self.processed_events,
            "progress_percent": self.progress_percent,
            "processed_frames": self.processed_frames,
            "total_frames": self.total_frames,
            "stage": self.stage,
            "fps": self.fps,
            "eta_seconds": self.eta_seconds,
            "result": self.result,
            "error": self.error,
        }
