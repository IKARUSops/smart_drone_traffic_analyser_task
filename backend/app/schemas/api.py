from typing import Any, Literal, Optional

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


class BoxSelectionRequest(BaseModel):
    box_points: list[list[int]] = Field(..., min_length=4, max_length=4)
    image_width: int = Field(..., gt=0)
    image_height: int = Field(..., gt=0)
    scene_mode: Literal["auto", "top_down", "angled"] = "auto"
    region_orientation: Literal["horizontal", "vertical"] = "horizontal"

    @field_validator("box_points")
    @classmethod
    def validate_box_points(cls, value: list[list[int]]) -> list[list[int]]:
        parsed_points: list[tuple[int, int]] = []
        for point in value:
            if len(point) != 2:
                raise ValueError("Each point must have exactly 2 coordinates")
            x, y = point
            if x < 0 or y < 0:
                raise ValueError("Coordinates must be non-negative")
            parsed_points.append((x, y))

        if len(set(parsed_points)) != 4:
            raise ValueError("Exactly 4 unique points are required")

        ordered = [
            parsed_points[0],
            parsed_points[1],
            parsed_points[2],
            parsed_points[3],
        ]
        if not cls._is_convex_quad(ordered):
            raise ValueError("Box points must form a convex quadrilateral in order")

        return [[x, y] for x, y in ordered]

    @staticmethod
    def _is_convex_quad(points: list[tuple[int, int]]) -> bool:
        if len(points) != 4:
            return False

        def cross(o: tuple[int, int], a: tuple[int, int], b: tuple[int, int]) -> int:
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        signs: list[int] = []
        for idx in range(4):
            c = cross(points[idx], points[(idx + 1) % 4], points[(idx + 2) % 4])
            if c == 0:
                return False
            signs.append(1 if c > 0 else -1)

        return all(sign == signs[0] for sign in signs)


class StatusResponse(BaseModel):
    task_id: str
    status: str
    stage: str
    cancellation_requested: bool
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
    download_url: str
    available_reports: list[str]


class DashboardTaskSummaryResponse(BaseModel):
    task_id: str
    status: str
    stage: str
    created_at: Optional[str]
    updated_at: Optional[str]
    total_unique_vehicles: int
    processing_time_seconds: float
    per_class_count: dict[str, int]
    per_direction_count: dict[str, int]


class DashboardTaskDetailResponse(BaseModel):
    task_id: str
    status: str
    stage: str
    created_at: Optional[str]
    updated_at: Optional[str]
    scene_mode: Optional[str]
    region_orientation: Optional[str]
    error: Optional[str]
    per_class_count: dict[str, int]
    per_direction_count: dict[str, int]
    result: Optional[dict[str, Any]]
    video_stream_url: str
    video_download_url: str
    report_csv_url: str
    report_xlsx_url: str
