from pathlib import Path
import importlib
import sys
import types

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.models import TaskRecord
from app.schemas.api import BoxSelectionRequest
from app.store import store


def make_test_client() -> TestClient:
    sys.modules.pop("app.main", None)

    processor_stub = types.ModuleType("app.services.processor")
    processor_stub.process_task = lambda _task_id: None
    sys.modules["app.services.processor"] = processor_stub

    video_io_stub = types.ModuleType("app.services.video_io")
    video_io_stub.extract_frame = lambda *_args, **_kwargs: 20
    video_io_stub.save_upload_file = lambda *_args, **_kwargs: None
    sys.modules["app.services.video_io"] = video_io_stub

    main_module = importlib.import_module("app.main")
    return TestClient(main_module.app)


@pytest.fixture(autouse=True)
def clear_store() -> None:
    for task in store.list_all():
        store.delete(task.task_id)
    yield
    for task in store.list_all():
        store.delete(task.task_id)


def make_task(task_id: str, token: str, status: str = "processing") -> TaskRecord:
    root = Path(__file__).resolve().parents[1]
    return TaskRecord(
        task_id=task_id,
        access_token=token,
        status=status,
        input_video_path=str(root / "data" / "uploads" / f"{task_id}.mp4"),
        frame_preview_path=str(root / "data" / "frames" / f"{task_id}.jpg"),
        output_video_path=str(root / "data" / "outputs" / f"{task_id}.mp4"),
        csv_report_path=str(root / "data" / "reports" / f"{task_id}.csv"),
        xlsx_report_path=str(root / "data" / "reports" / f"{task_id}.xlsx"),
        stage="tracking vehicles",
    )


def test_box_selection_request_accepts_convex_quad() -> None:
    payload = BoxSelectionRequest(
        box_points=[[10, 10], [100, 10], [100, 60], [10, 60]],
        image_width=1920,
        image_height=1080,
        scene_mode="auto",
        region_orientation="horizontal",
    )

    assert payload.box_points == [[10, 10], [100, 10], [100, 60], [10, 60]]


def test_box_selection_request_rejects_non_convex_quad() -> None:
    with pytest.raises(ValidationError):
        BoxSelectionRequest(
            box_points=[[10, 10], [100, 10], [30, 30], [10, 60]],
            image_width=1920,
            image_height=1080,
            scene_mode="auto",
            region_orientation="horizontal",
        )


def test_cancel_endpoint_sets_cancellation_flag() -> None:
    task = make_task(task_id="task-1", token="token-1", status="processing")
    store.create(task)
    client = make_test_client()

    response = client.post("/api/v1/tasks/task-1/cancel", headers={"X-Task-Token": "token-1"})

    assert response.status_code == 202
    assert response.json()["status"] == "cancellation_requested"

    status_response = client.get("/api/v1/tasks/task-1/status", headers={"X-Task-Token": "token-1"})
    assert status_response.status_code == 200
    assert status_response.json()["cancellation_requested"] is True


def test_cancel_endpoint_rejects_not_started_task() -> None:
    task = make_task(task_id="task-2", token="token-2", status="awaiting_line")
    store.create(task)
    client = make_test_client()

    response = client.post("/api/v1/tasks/task-2/cancel", headers={"X-Task-Token": "token-2"})

    assert response.status_code == 409
    assert "has not started" in response.json()["detail"]
