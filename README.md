# Smart Drone Traffic Analyzer

End-to-end traffic analysis system with:
- FastAPI + OpenCV + YOLOv10 backend
- Next.js frontend with line-selection workflow
- Annotated output video with live IDs and bounding boxes
- CSV/XLSX report export

## Finalized Product Decisions

- Device mode: auto-select GPU if available, otherwise CPU
- Detection model: YOLOv10
- Vehicle scope: includes bicycle and other vehicle classes from configured YOLO IDs
- Counting directions: North, South, East, West
- Line/region definition: user selects 4 points on frame 20 to define a convex counting region
- Export format: user chooses CSV or XLSX at download time
- Artifact retention target: 24 hours

## Architecture

### Backend (FastAPI)

The backend is asynchronous and task-based.

Workflow:
1. Upload video
2. Extract frame 20 for line-selection UI
3. Accept four OpenCV-format points for a convex region
4. Start tracking/counting job in background
5. Poll status until completion
6. Return annotated video and downloadable reports

Core modules:
- `backend/app/main.py` API endpoints
- `backend/app/services/video_io.py` upload persistence and frame extraction
- `backend/app/services/processor.py` YOLOv10 tracking + counting pipeline
- `backend/app/services/counter.py` crossing logic, direction logic, global-motion compensation
- `backend/app/services/reporting.py` CSV/XLSX report generation
- `backend/app/store.py` in-memory task state

### Frontend (Next.js App Router)

UI states:
1. Upload view
2. Region picker view (frame 20)
3. Processing view with 2-second polling
4. Result dashboard with video playback and report download

Core files:
- `frontend/app/page.tsx` full UI flow and API integration
- `frontend/components/LinePicker.tsx` four-point region picker canvas
- `frontend/types/api.ts` API contracts

## Counting Methodology

### Trigger rule

- Compute signed distance of tracked point against monitored region edges
- A crossing is registered when the sign changes between consecutive observations for monitored edges
- One unique count per track ID and monitored edge to prevent duplicate edge events

### Tracking point mode

- `top_down`: centroid
- `angled`: bottom-center of bounding box
- `auto`: heuristic chooses mode per detection geometry

### Direction logic (N/S/E/W)

- Direction is inferred from track displacement around crossing
- A global-motion estimate is computed from background optical flow
- Object displacement is corrected by subtracting estimated camera motion so directions remain stable in moving-camera clips

## API Contract

Base URL: `http://localhost:8000`

1. `POST /api/v1/tasks/upload`
- Multipart upload field: `video`
- Returns: `task_id`, frame preview URL, status `awaiting_line`

2. `GET /api/v1/tasks/{task_id}/frame`
- Returns frame 20 image for region placement

3. `POST /api/v1/tasks/{task_id}/line`
- Body:
	- `line_points`: `[[x1,y1],[x2,y2]]` in OpenCV pixel coordinates
	- `image_width`, `image_height`
	- `scene_mode`: `auto | top_down | angled`
- Starts processing

4. `POST /api/v2/tasks/{task_id}/region`
- Body:
	- `box_points`: `[[x1,y1],[x2,y2],[x3,y3],[x4,y4]]` in OpenCV pixel coordinates (convex ordered quad)
	- `image_width`, `image_height`
	- `scene_mode`: `auto | top_down | angled`
	- `region_orientation`: `horizontal | vertical`
- Starts processing

5. `GET /api/v1/tasks/{task_id}/status`
- Returns task progress, FPS, ETA, stage and failure details

6. `GET /api/v1/tasks/{task_id}/result`
- Returns total unique count, class counts, directional counts, confidence summary, performance metrics

7. `GET /api/v1/tasks/{task_id}/video`
- Returns annotated output MP4

8. `GET /api/v1/tasks/{task_id}/report?format=csv|xlsx`
- Returns user-selected report format

9. `POST /api/v1/tasks/{task_id}/cancel`
- Requests graceful cancellation of an in-flight task

## Report Columns

- `event_id`
- `timestamp_seconds`
- `frame_index`
- `track_id`
- `vehicle_class`
- `crossing_direction`
- `crossing_point_x`
- `crossing_point_y`
- `edge_crossed`
- `box_region_id`
- `confidence`
- `device_used`
- `processing_fps`

## Local Setup

## 1) Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Start API:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 2) Frontend

```bash
cd frontend
npm install
```

Create `.env.local` in `frontend/`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

Start frontend:

```bash
npm run dev
```

Open:
- `http://127.0.0.1:3000`

## 3) Typical run

1. Upload video
2. Pick four ordered points on frame 20 to define the region
3. Confirm region
4. Wait for processing completion
5. Watch processed video and download CSV/XLSX

## Engineering Assumptions

- Input videos are road/drone traffic scenes where vehicles are detectable by YOLOv10
- Frontend polling (2s) is sufficient for progress visibility without WebSockets
- In-memory task store is acceptable for prototype scope
- Production hardening (persistent DB, queue workers, auth, retention daemon) is intentionally out of MVP scope

## Recommended Production Upgrades

- Persist tasks in PostgreSQL
- Queue processing in Celery/RQ
- Add authentication and job ownership
- Add periodic cleanup for 24-hour retention policy
- Add stronger stabilization and per-scene calibration profiles