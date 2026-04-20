from pathlib import Path

import cv2
from fastapi import UploadFile

from app.core.settings import MAX_UPLOAD_BYTES


def save_upload_file(upload_file: UploadFile, destination: Path) -> int:
    total_bytes = 0
    with destination.open("wb") as buffer:
        while True:
            chunk = upload_file.file.read(1024 * 1024)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > MAX_UPLOAD_BYTES:
                raise ValueError("Uploaded file exceeds configured maximum size")
            buffer.write(chunk)
    return total_bytes


def get_video_metadata(video_path: Path) -> dict[str, float]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError("Unable to open uploaded video")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = (total_frames / fps) if fps > 0 else 0.0
    cap.release()

    return {
        "total_frames": total_frames,
        "fps": fps,
        "width": width,
        "height": height,
        "duration": duration,
    }


def extract_frame(video_path: Path, output_image_path: Path, frame_index: int) -> int:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError("Unable to open uploaded video for frame extraction")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    target_index = min(frame_index, max(total_frames - 1, 0))
    cap.set(cv2.CAP_PROP_POS_FRAMES, target_index)
    success, frame = cap.read()
    cap.release()

    if not success:
        raise RuntimeError("Unable to read target frame for line selection")

    cv2.imwrite(str(output_image_path), frame)
    return target_index
