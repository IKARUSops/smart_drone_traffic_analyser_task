export type UploadResponse = {
  task_id: string;
  access_token: string;
  status: string;
  frame_index: number;
  frame_url: string;
  next_step: string;
};

export type LineSelectionRequest = {
  line_points: number[][];
  image_width: number;
  image_height: number;
  scene_mode: "auto" | "top_down" | "angled";
};

export type RegionSelectionRequest = {
  box_points: number[][];
  image_width: number;
  image_height: number;
  scene_mode: "auto" | "top_down" | "angled";
  region_orientation: "horizontal" | "vertical";
};

export type StatusResponse = {
  task_id: string;
  status: string;
  stage: string;
  cancellation_requested: boolean;
  progress_percent: number;
  processed_frames: number;
  total_frames: number;
  fps: number;
  eta_seconds: number | null;
  error: string | null;
};

export type ResultResponse = {
  task_id: string;
  status: string;
  total_unique_vehicles: number;
  per_class_count: Record<string, number>;
  per_direction_count: Record<string, number>;
  average_confidence_by_class: Record<string, number>;
  processing_time_seconds: number;
  input_fps: number;
  processing_fps: number;
  video_url: string;
  download_url: string;
  available_reports: string[];
};

export type DashboardTaskSummaryResponse = {
  task_id: string;
  status: string;
  stage: string;
  created_at: string | null;
  updated_at: string | null;
  total_unique_vehicles: number;
  processing_time_seconds: number;
  per_class_count: Record<string, number>;
  per_direction_count: Record<string, number>;
};

export type DashboardTaskDetailResponse = {
  task_id: string;
  status: string;
  stage: string;
  created_at: string | null;
  updated_at: string | null;
  scene_mode: string | null;
  region_orientation: string | null;
  error: string | null;
  per_class_count: Record<string, number>;
  per_direction_count: Record<string, number>;
  result: Record<string, unknown> | null;
  video_stream_url: string;
  video_download_url: string;
  report_csv_url: string;
  report_xlsx_url: string;
};
