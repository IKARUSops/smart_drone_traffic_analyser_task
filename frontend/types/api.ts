export type UploadResponse = {
  task_id: string;
  access_token: string;
  status: string;
  frame_index: number;
  frame_url: string;
  next_step: string;
};

export type StatusResponse = {
  task_id: string;
  status: string;
  stage: string;
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
  available_reports: string[];
};
