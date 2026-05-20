import { FileItem, TaskItem } from "./types";

const API_BASE = "/api";

export async function fetchFiles(): Promise<FileItem[]> {
  const res = await fetch(`${API_BASE}/files`);
  if (!res.ok) throw new Error("failed to fetch files");
  return res.json();
}

export async function fetchFile(fileId: string): Promise<FileItem> {
  const res = await fetch(`${API_BASE}/files/${fileId}`);
  if (!res.ok) throw new Error("failed to fetch file");
  return res.json();
}

export async function fetchFilePages(fileId: string, limit: number, offset: number) {
  const res = await fetch(`${API_BASE}/files/${fileId}/pages?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error("failed to fetch pages");
  return res.json();
}

export async function uploadPdf(file: File): Promise<FileItem> {
  const data = new FormData();
  data.append("upload", file);
  const res = await fetch(`${API_BASE}/files`, { method: "POST", body: data });
  if (!res.ok) throw new Error("failed to upload");
  return res.json();
}

export async function fetchTasks(): Promise<TaskItem[]> {
  const res = await fetch(`${API_BASE}/tasks`);
  if (!res.ok) throw new Error("failed to fetch tasks");
  return res.json();
}

export async function fetchTask(taskId: string): Promise<TaskItem> {
  const res = await fetch(`${API_BASE}/tasks/${taskId}`);
  if (!res.ok) throw new Error("failed to fetch task");
  return res.json();
}

export async function reprocessFile(fileId: string): Promise<FileItem> {
  const res = await fetch(`${API_BASE}/files/${fileId}/reprocess`, { method: "POST" });
  if (!res.ok) throw new Error("failed to reprocess file");
  return res.json();
}

export function mediaUrl(path: string | null): string {
  if (!path) return "";
  return `${API_BASE}/media/${path}`;
}
