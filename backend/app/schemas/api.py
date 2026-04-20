from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class UploadResponse(BaseModel):
    task_id: str
    access_token: str
    status: str
    frame_index: int
    frame_url: str
    next_step: str


class LineSelectionRequest(BaseModel):
    line_points: list[list[int]] = Field(..., min_length=2, max_length=2)
    image_width: int = Field(..., gt=0)
    image_height: int = Field(..., gt=0)
    scene_mode: Literal["auto", "top_down", "angled"] = "auto"

    @field_validator("line_points")
    @classmethod
    def validate_points(cls, value: list[list[int]]) -> list[list[int]]:
        for point in value:
            if len(point) != 2:
                raise ValueError("Each point must have exactly 2 coordinates")
            if point[0] < 0 or point[1] < 0:
                raise ValueError("Coordinates must be non-negative")
        return value


class StatusResponse(BaseModel):
    task_id: str
    status: str
    stage: str
    progress_percent: float
    processed_frames: int
    total_frames: int
    fps: float
    eta_seconds: Optional[float]
    error: Optional[str]


class ResultResponse(BaseModel):
    task_id: str
    status: str
    total_unique_vehicles: int
    per_class_count: dict[str, int]
    per_direction_count: dict[str, int]
    average_confidence_by_class: dict[str, float]
    processing_time_seconds: float
    input_fps: float
    processing_fps: float
    video_url: str
    available_reports: list[str]
