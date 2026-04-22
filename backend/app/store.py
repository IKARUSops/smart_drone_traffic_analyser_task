from datetime import datetime
from threading import Lock
from typing import Optional

from app.models import TaskRecord


class TaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = Lock()

    def create(self, task: TaskRecord) -> None:
        with self._lock:
            self._tasks[task.task_id] = task

    def get(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            return self._tasks.get(task_id)

    def update(self, task_id: str, **updates: object) -> Optional[TaskRecord]:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            for key, value in updates.items():
                setattr(task, key, value)
            task.updated_at = datetime.utcnow()
            return task

    def delete(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            return self._tasks.pop(task_id, None)

    def list_all(self) -> list[TaskRecord]:
        with self._lock:
            return list(self._tasks.values())

    def reserve_processing_slot(
        self,
        task_id: str,
        max_concurrent_tasks: int,
        line_points: list[list[int]] | None,
        scene_mode: str,
        region_box: list[list[int]] | None = None,
        region_orientation: str | None = None,
    ) -> Optional[str]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return "not_found"
            if task.status not in {"awaiting_line", "awaiting_region", "failed"}:
                return "invalid_status"

            active_jobs = sum(1 for item in self._tasks.values() if item.status in {"queued", "processing"})
            if active_jobs >= max_concurrent_tasks:
                return "capacity_reached"

            task.line_points = line_points
            task.region_box = region_box
            if region_orientation is not None:
                task.region_orientation = region_orientation
            task.scene_mode = scene_mode
            task.status = "queued"
            task.stage = "queued for processing"
            task.progress_percent = 0.0
            task.error = None
            task.cancellation_requested = False
            task.updated_at = datetime.utcnow()
            return "ok"

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            task.cancellation_requested = True
            task.updated_at = datetime.utcnow()
            return True


store = TaskStore()
