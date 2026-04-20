import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
FRAME_DIR = DATA_DIR / "frames"
OUTPUT_DIR = DATA_DIR / "outputs"
REPORT_DIR = DATA_DIR / "reports"

YOLO_MODEL = "yolov10m.pt"
FRAME_INDEX_FOR_LINE_PICKER = 20
VEHICLE_CLASS_IDS = [1, 2, 3, 5, 7]
TASK_RETENTION_HOURS = 24
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(3 * 1024 * 1024 * 1024)))
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
ALLOWED_CONTENT_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
}
ALLOWED_CORS_ORIGINS = os.getenv("ALLOWED_CORS_ORIGINS", "http://localhost:3000").split(",")
ADMIN_CLEANUP_TOKEN = os.getenv("ADMIN_CLEANUP_TOKEN", "")
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "2"))

for directory in [UPLOAD_DIR, FRAME_DIR, OUTPUT_DIR, REPORT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)
