import csv
from pathlib import Path

from openpyxl import Workbook


REPORT_COLUMNS = [
    "event_id",
    "timestamp_seconds",
    "frame_index",
    "track_id",
    "vehicle_class",
    "crossing_direction",
    "line_point_x",
    "line_point_y",
    "confidence",
    "device_used",
    "processing_fps",
]


def write_csv_report(report_path: Path, rows: list[dict[str, object]]) -> None:
    with report_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_xlsx_report(report_path: Path, rows: list[dict[str, object]]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Vehicle Report"
    worksheet.append(REPORT_COLUMNS)

    for row in rows:
        worksheet.append([row.get(column, "") for column in REPORT_COLUMNS])

    workbook.save(str(report_path))
