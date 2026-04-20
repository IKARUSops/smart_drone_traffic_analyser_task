from datetime import datetime, timedelta
from pathlib import Path

from app.core.settings import TASK_RETENTION_HOURS
from app.store import store


def cleanup_expired_artifacts() -> int:
    cutoff = datetime.utcnow() - timedelta(hours=TASK_RETENTION_HOURS)
    removed = 0

    for task in store.list_all():
        if task.created_at > cutoff:
            continue

        for file_path in [
            task.input_video_path,
            task.frame_preview_path,
            task.output_video_path,
            task.csv_report_path,
            task.xlsx_report_path,
        ]:
            path = Path(file_path)
            if path.exists():
                path.unlink(missing_ok=True)

        store.delete(task.task_id)
        removed += 1

    return removed
