import {
  AppShell,
  Badge,
  Box,
  Button,
  Card,
  Group,
  JsonInput,
  NavLink,
  NumberInput,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Route, Routes, useParams, useSearchParams } from "react-router-dom";
import {
  cancelFile,
  deleteFile,
  fetchFile,
  fetchFilePages,
  fetchFiles,
  fetchTask,
  fetchTasks,
  mediaUrl,
  reprocessFile,
  uploadPdf,
} from "./api";
import { useEffect, useRef, useState } from "react";
import { getBlockContentState } from "./blockContent";
import { BlockItem, DetectionBoxItem, PageItem } from "./types";

function useFileEvents(fileId: string | undefined) {
  const qc = useQueryClient();
  useEffect(() => {
    if (!fileId) return;
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://${window.location.host}/api/ws/files/${fileId}`);
    ws.onmessage = () => {
      qc.invalidateQueries({ queryKey: ["file", fileId] });
      qc.invalidateQueries({ queryKey: ["pages", fileId] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
    };
    return () => ws.close();
  }, [fileId, qc]);
}

function FilesPage() {
  const qc = useQueryClient();
  const files = useQuery({ queryKey: ["files"], queryFn: fetchFiles });
  const [uploading, setUploading] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadErrors, setUploadErrors] = useState<string[]>([]);
  const [uploadProgress, setUploadProgress] = useState<{ done: number; total: number } | null>(null);
  const [reprocessingFileId, setReprocessingFileId] = useState<string | null>(null);
  const [cancellingFileId, setCancellingFileId] = useState<string | null>(null);
  const [deletingFileId, setDeletingFileId] = useState<string | null>(null);
  const [reprocessErrorById, setReprocessErrorById] = useState<Record<string, string>>({});
  const [cancelErrorById, setCancelErrorById] = useState<Record<string, string>>({});
  const [deleteErrorById, setDeleteErrorById] = useState<Record<string, string>>({});
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const onUpload = async () => {
    if (selectedFiles.length === 0) return;
    setUploading(true);
    setUploadErrors([]);
    setUploadProgress({ done: 0, total: selectedFiles.length });
    const errors: string[] = [];
    try {
      for (let i = 0; i < selectedFiles.length; i += 1) {
        const file = selectedFiles[i];
        try {
          await uploadPdf(file);
        } catch (err) {
          const message = err instanceof Error ? err.message : "Upload failed";
          errors.push(`${file.name}: ${message}`);
        } finally {
          setUploadProgress({ done: i + 1, total: selectedFiles.length });
        }
      }
      setSelectedFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
      await qc.invalidateQueries({ queryKey: ["files"] });
      await qc.invalidateQueries({ queryKey: ["tasks"] });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Upload failed";
      errors.push(message);
    } finally {
      setUploadErrors(errors);
      setUploadProgress(null);
      setUploading(false);
    }
  };

  const onReprocess = async (fileId: string) => {
    setReprocessingFileId(fileId);
    setReprocessErrorById((prev) => ({ ...prev, [fileId]: "" }));
    try {
      await reprocessFile(fileId);
      await qc.invalidateQueries({ queryKey: ["files"] });
      await qc.invalidateQueries({ queryKey: ["tasks"] });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Reprocess failed";
      setReprocessErrorById((prev) => ({ ...prev, [fileId]: message }));
    } finally {
      setReprocessingFileId(null);
    }
  };

  const onDelete = async (fileId: string) => {
    setDeletingFileId(fileId);
    setDeleteErrorById((prev) => ({ ...prev, [fileId]: "" }));
    try {
      await deleteFile(fileId);
      await qc.invalidateQueries({ queryKey: ["files"] });
      await qc.invalidateQueries({ queryKey: ["tasks"] });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Delete failed";
      setDeleteErrorById((prev) => ({ ...prev, [fileId]: message }));
    } finally {
      setDeletingFileId(null);
    }
  };

  const onCancel = async (fileId: string) => {
    setCancellingFileId(fileId);
    setCancelErrorById((prev) => ({ ...prev, [fileId]: "" }));
    try {
      await cancelFile(fileId);
      await qc.invalidateQueries({ queryKey: ["files"] });
      await qc.invalidateQueries({ queryKey: ["tasks"] });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Cancel failed";
      setCancelErrorById((prev) => ({ ...prev, [fileId]: message }));
    } finally {
      setCancellingFileId(null);
    }
  };

  return (
    <Stack>
      <Group>
        <Title order={2}>Files</Title>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          multiple
          onChange={(e) => {
            const filesList = e.target.files ? Array.from(e.target.files) : [];
            setSelectedFiles(filesList);
            setUploadErrors([]);
          }}
        />
        <Button onClick={onUpload} disabled={selectedFiles.length === 0 || uploading} loading={uploading}>
          Upload
        </Button>
        <Button
          variant="light"
          disabled={selectedFiles.length === 0 || uploading}
          onClick={() => {
            setSelectedFiles([]);
            setUploadErrors([]);
            setUploadProgress(null);
            if (fileInputRef.current) fileInputRef.current.value = "";
          }}
        >
          Clear
        </Button>
      </Group>
      <Group>
        <Text size="sm">
          {selectedFiles.length === 0
            ? "Selected: none"
            : selectedFiles.length === 1
              ? `Selected: ${selectedFiles[0].name} (${Math.ceil(selectedFiles[0].size / 1024)} KB)`
              : `Selected: ${selectedFiles.length} files (${Math.ceil(selectedFiles.reduce((sum, file) => sum + file.size, 0) / 1024)} KB)`}
        </Text>
      </Group>
      {uploadErrors.map((message, index) => (
        <Text size="sm" c="red" key={`${index}-${message}`}>
          {message}
        </Text>
      ))}
      {uploading && (
        <Text size="sm">
          Uploading {uploadProgress?.done ?? 0}/{uploadProgress?.total ?? selectedFiles.length}...
        </Text>
      )}
      <Group>
        <Text size="sm" c="dimmed">
          Upload starts only after pressing the Upload button.
        </Text>
      </Group>
      {files.data?.map((f) => (
        <Card withBorder key={f.id}>
          <Group justify="space-between">
            <Box>
              <Text fw={600}>{f.filename}</Text>
              <Text size="sm">status: {f.status}</Text>
              <Text size="sm">pages: {f.pages_count ?? "-"}</Text>
              <Text size="sm">
                {f.task_status_counts.new} new, {f.task_status_counts.done} done, {f.task_status_counts.failed} failed
              </Text>
              {f.error_summary && <Text c="red">{f.error_summary}</Text>}
              {reprocessErrorById[f.id] && <Text c="red">{reprocessErrorById[f.id]}</Text>}
              {cancelErrorById[f.id] && <Text c="red">{cancelErrorById[f.id]}</Text>}
              {deleteErrorById[f.id] && <Text c="red">{deleteErrorById[f.id]}</Text>}
            </Box>
            <Group>
              <Button
                color="orange"
                variant="light"
                loading={cancellingFileId === f.id}
                disabled={
                  reprocessingFileId !== null ||
                  cancellingFileId !== null ||
                  deletingFileId !== null ||
                  !["new", "validation", "in_progress"].includes(f.status)
                }
                onClick={() => onCancel(f.id)}
              >
                Cancel
              </Button>
              <Button
                variant="light"
                loading={reprocessingFileId === f.id}
                disabled={
                  reprocessingFileId !== null ||
                  cancellingFileId !== null ||
                  deletingFileId !== null ||
                  !["done", "failed", "validation_failed", "cancelled"].includes(f.status)
                }
                onClick={() => onReprocess(f.id)}
              >
                Reprocess
              </Button>
              <Button
                color="red"
                variant="light"
                loading={deletingFileId === f.id}
                disabled={
                  reprocessingFileId !== null ||
                  cancellingFileId !== null ||
                  deletingFileId !== null ||
                  !["done", "failed", "validation_failed", "cancelled"].includes(f.status)
                }
                onClick={() => onDelete(f.id)}
              >
                Delete
              </Button>
              <Button component={Link} to={`/files/${f.id}`}>
                Open
              </Button>
            </Group>
          </Group>
        </Card>
      ))}
    </Stack>
  );
}

function TasksPage() {
  const tasks = useQuery({ queryKey: ["tasks"], queryFn: fetchTasks, refetchInterval: 2000 });
  return (
    <Stack>
      <Title order={2}>Tasks</Title>
      {tasks.data?.map((t) => (
        <Card withBorder key={t.id}>
          <Group justify="space-between">
            <Text>
              {t.type} / {t.status}
            </Text>
            <Button component={Link} to={`/tasks/${t.id}`} variant="light">
              Open
            </Button>
          </Group>
        </Card>
      ))}
    </Stack>
  );
}

function TaskPage() {
  const { taskId = "" } = useParams();
  const task = useQuery({ queryKey: ["task", taskId], queryFn: () => fetchTask(taskId) });
  if (!task.data) return <Text>Loading...</Text>;
  return (
    <Stack>
      <Title order={2}>Task {task.data.id}</Title>
      <Badge>{task.data.status}</Badge>
      <JsonInput label="Input" value={JSON.stringify(task.data.input_payload, null, 2)} autosize minRows={6} readOnly />
      <JsonInput
        label="Output"
        value={JSON.stringify(task.data.output_payload ?? {}, null, 2)}
        autosize
        minRows={6}
        readOnly
      />
      <Text c="red">{task.data.error_message}</Text>
    </Stack>
  );
}

function OverlayPage({
  page,
  hoveredId,
  setHoveredId,
  mode,
}: {
  page: PageItem;
  hoveredId: string | null;
  setHoveredId: (id: string | null) => void;
  mode: "layout" | "detection";
}) {
  const detections = page.detections ?? [];
  return (
    <Box className="page-box">
      <img className="page-image" src={mediaUrl(page.image_path)} alt={`page-${page.page_number}-${mode}`} />
      <svg className="overlay" viewBox={`0 0 ${page.width_px ?? 1} ${page.height_px ?? 1}`}>
        {mode === "layout"
          ? page.blocks.map((b: BlockItem) => (
              <rect
                key={b.id}
                x={b.bbox_px.x}
                y={b.bbox_px.y}
                width={b.bbox_px.width}
                height={b.bbox_px.height}
                fill="none"
                stroke={b.color_key}
                strokeWidth={hoveredId === b.id ? 4 : 2}
                onMouseEnter={() => setHoveredId(b.id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                <title>{JSON.stringify(b.raw_surya, null, 2)}</title>
              </rect>
            ))
          : detections.map((d: DetectionBoxItem) => {
              const points = d.polygon_px?.points ?? [];
              if (points.length >= 3) {
                return (
                  <polygon
                    key={d.id}
                    points={points.map((point) => `${point.x},${point.y}`).join(" ")}
                    fill="none"
                    stroke="#2563eb"
                    strokeWidth={hoveredId === d.id ? 3 : 2}
                    onMouseEnter={() => setHoveredId(d.id)}
                    onMouseLeave={() => setHoveredId(null)}
                  >
                    <title>{JSON.stringify(d.raw_surya, null, 2)}</title>
                  </polygon>
                );
              }
              return (
                <rect
                  key={d.id}
                  x={d.bbox_px.x}
                  y={d.bbox_px.y}
                  width={d.bbox_px.width}
                  height={d.bbox_px.height}
                  fill="none"
                  stroke="#2563eb"
                  strokeWidth={hoveredId === d.id ? 3 : 2}
                  onMouseEnter={() => setHoveredId(d.id)}
                  onMouseLeave={() => setHoveredId(null)}
                >
                  <title>{JSON.stringify(d.raw_surya, null, 2)}</title>
                </rect>
              );
            })}
      </svg>
    </Box>
  );
}

function FilePage() {
  const { fileId = "" } = useParams();
  useFileEvents(fileId);
  const [params, setParams] = useSearchParams();
  const [hoveredBlock, setHoveredBlock] = useState<string | null>(null);
  const [hoveredDetection, setHoveredDetection] = useState<string | null>(null);
  const pageSize = Number(params.get("limit") ?? "10");
  const offset = Number(params.get("offset") ?? "0");
  const file = useQuery({ queryKey: ["file", fileId], queryFn: () => fetchFile(fileId), refetchInterval: 2000 });
  const pages = useQuery({
    queryKey: ["pages", fileId, pageSize, offset],
    queryFn: () => fetchFilePages(fileId, pageSize, offset),
    refetchInterval: 2000,
  });
  return (
    <Stack>
      <Title order={2}>File</Title>
      <Text>
        {file.data?.filename} | {file.data?.status} | {file.data?.progress_done}/{file.data?.progress_total}
      </Text>
      <Group>
        <NumberInput
          label="Page size"
          value={pageSize}
          onChange={(v) => setParams({ limit: String(v || 10), offset: "0" })}
          min={10}
          max={50}
          step={10}
        />
        <Button onClick={() => setParams({ limit: String(pageSize), offset: String(Math.max(0, offset - pageSize)) })}>
          Prev
        </Button>
        <Button onClick={() => setParams({ limit: String(pageSize), offset: String(offset + pageSize) })}>Next</Button>
      </Group>
      {pages.data?.items.map((p: PageItem) => (
        <Card key={p.id} withBorder>
          <Title order={4}>Page {p.page_number}</Title>
          <Box className="file-page-layout">
            <Box className="file-left-column">
              <OverlayPage page={p} hoveredId={hoveredBlock} setHoveredId={setHoveredBlock} mode="layout" />
              <OverlayPage page={p} hoveredId={hoveredDetection} setHoveredId={setHoveredDetection} mode="detection" />
            </Box>
            <Stack className="file-right-column">
              {p.blocks.map((b: BlockItem) => {
                const content = getBlockContentState(b);
                return (
                  <Card
                    key={b.id}
                    withBorder
                    className={hoveredBlock === b.id ? "focused" : ""}
                    style={{ borderColor: b.color_key, borderWidth: 2 }}
                  >
                    <Text fw={600}>{b.type}</Text>
                    {content.kind === "image" ? (
                      <img src={mediaUrl(b.artifact_path)} alt={`block-${b.id}`} style={{ maxWidth: "100%", display: "block" }} />
                    ) : content.kind === "image_pending" ? (
                      <Text size="sm">Image pending</Text>
                    ) : content.kind === "text" ? (
                      <Text size="sm" className="block-text-content">
                        {content.text}
                      </Text>
                    ) : content.kind === "ocr_pending" ? (
                      <Text size="sm">OCR pending</Text>
                    ) : (
                      <Text size="sm">No extracted content</Text>
                    )}
                  </Card>
                );
              })}
            </Stack>
          </Box>
        </Card>
      ))}
    </Stack>
  );
}

export function App() {
  return (
    <AppShell navbar={{ width: 260, breakpoint: "sm" }} padding="md">
      <AppShell.Navbar p="md">
        <NavLink label="Files" component={Link} to="/" />
        <NavLink label="Tasks" component={Link} to="/tasks" />
      </AppShell.Navbar>
      <AppShell.Main>
        <Routes>
          <Route path="/" element={<FilesPage />} />
          <Route path="/tasks" element={<TasksPage />} />
          <Route path="/tasks/:taskId" element={<TaskPage />} />
          <Route path="/files/:fileId" element={<FilePage />} />
        </Routes>
      </AppShell.Main>
    </AppShell>
  );
}
