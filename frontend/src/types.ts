export type FileStatus =
  | "new"
  | "validation"
  | "validation_failed"
  | "in_progress"
  | "cancelling"
  | "cancelled"
  | "failed"
  | "done";

export type TaskStatus = "new" | "in_progress" | "cancelled" | "failed" | "done";

export type FileItem = {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: FileStatus;
  pages_count: number | null;
  progress_done: number;
  progress_total: number;
  cover_path: string | null;
  error_summary: string | null;
  created_at: string;
  updated_at: string;
};

export type BlockItem = {
  id: string;
  type: string;
  bbox_px: { x: number; y: number; width: number; height: number };
  bbox_norm: { x: number; y: number; width: number; height: number };
  color_key: string;
  raw_surya: Record<string, unknown>;
  result: Record<string, unknown> | null;
  artifact_path: string | null;
};

export type DetectionBoxItem = {
  id: string;
  bbox_px: { x: number; y: number; width: number; height: number };
  bbox_norm: { x: number; y: number; width: number; height: number };
  polygon_px: { points: { x: number; y: number }[] } | null;
  confidence: number | null;
  raw_surya: Record<string, unknown>;
  sort_order: number;
};

export type PageItem = {
  id: string;
  page_number: number;
  width_px: number | null;
  height_px: number | null;
  image_path: string | null;
  status: TaskStatus;
  error_message: string | null;
  blocks: BlockItem[];
  detections: DetectionBoxItem[];
};

export type PageListResponse = {
  total: number;
  items: PageItem[];
};

export type TaskItem = {
  id: string;
  file_id: string | null;
  page_id: string | null;
  type: string;
  status: TaskStatus;
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown> | null;
  error_message: string | null;
  attempts: number;
  max_attempts: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};
