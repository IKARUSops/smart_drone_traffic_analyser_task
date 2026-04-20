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
    scene_mode: str = "auto"
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
            "scene_mode": self.scene_mode,
            "progress_percent": self.progress_percent,
            "processed_frames": self.processed_frames,
            "total_frames": self.total_frames,
            "stage": self.stage,
            "fps": self.fps,
            "eta_seconds": self.eta_seconds,
            "result": self.result,
            "error": self.error,
        }
