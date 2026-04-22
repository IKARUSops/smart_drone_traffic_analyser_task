import importlib
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.models import TaskRecord
from app.store import store


@pytest.fixture(autouse=True)
def clear_store() -> None:
    for task in store.list_all():
        store.delete(task.task_id)
    yield
    for task in store.list_all():
        store.delete(task.task_id)


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


def make_task(task_id: str, token: str, status: str = "awaiting_line") -> TaskRecord:
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
        stage="awaiting line selection",
    )


def region_payload() -> dict[str, object]:
    return {
        "box_points": [[10, 10], [100, 10], [100, 60], [10, 60]],
        "image_width": 1920,
        "image_height": 1080,
        "scene_mode": "auto",
        "region_orientation": "horizontal",
    }


def test_region_endpoint_accepts_valid_request() -> None:
    store.create(make_task(task_id="region-ok", token="token-ok"))
    client = make_test_client()

    response = client.post(
        "/api/v2/tasks/region-ok/region",
        headers={"X-Task-Token": "token-ok"},
        json=region_payload(),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "queued"

    updated_task = store.get("region-ok")
    assert updated_task is not None
    assert updated_task.region_box == region_payload()["box_points"]
    assert updated_task.region_orientation == "horizontal"


def test_region_endpoint_rejects_out_of_bounds_points() -> None:
    store.create(make_task(task_id="region-oob", token="token-oob"))
    client = make_test_client()

    payload = region_payload()
    payload["box_points"] = [[10, 10], [2000, 10], [100, 60], [10, 60]]

    response = client.post(
        "/api/v2/tasks/region-oob/region",
        headers={"X-Task-Token": "token-oob"},
        json=payload,
    )

    assert response.status_code == 400
    assert "within image bounds" in response.json()["detail"]


def test_region_endpoint_rejects_invalid_status() -> None:
    store.create(make_task(task_id="region-done", token="token-done", status="completed"))
    client = make_test_client()

    response = client.post(
        "/api/v2/tasks/region-done/region",
        headers={"X-Task-Token": "token-done"},
        json=region_payload(),
    )

    assert response.status_code == 409


def test_region_endpoint_rejects_when_queue_capacity_reached() -> None:
    store.create(make_task(task_id="active-1", token="token-a1", status="queued"))
    store.create(make_task(task_id="active-2", token="token-a2", status="processing"))
    store.create(make_task(task_id="region-full", token="token-full", status="awaiting_line"))
    client = make_test_client()

    response = client.post(
        "/api/v2/tasks/region-full/region",
        headers={"X-Task-Token": "token-full"},
        json=region_payload(),
    )

    assert response.status_code == 429
    assert "queue is full" in response.json()["detail"].lower()
