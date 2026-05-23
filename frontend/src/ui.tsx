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
import { Link, Route, Routes, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { deleteFile, fetchFile, fetchFilePages, fetchFiles, fetchTask, fetchTasks, mediaUrl, reprocessFile, uploadPdf } from "./api";
import { useEffect, useState } from "react";
import { getBlockContentState } from "./blockContent";
import { BlockItem, PageItem } from "./types";

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
  const navigate = useNavigate();
  const files = useQuery({ queryKey: ["files"], queryFn: fetchFiles });
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [reprocessingFileId, setReprocessingFileId] = useState<string | null>(null);
  const [deletingFileId, setDeletingFileId] = useState<string | null>(null);
  const [reprocessErrorById, setReprocessErrorById] = useState<Record<string, string>>({});
  const [deleteErrorById, setDeleteErrorById] = useState<Record<string, string>>({});

  const onUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setUploadError(null);
    try {
      const created = await uploadPdf(selectedFile);
      setSelectedFile(null);
      await qc.invalidateQueries({ queryKey: ["files"] });
      navigate(`/files/${created.id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Upload failed";
      setUploadError(message);
    } finally {
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

  return (
    <Stack>
      <Group>
        <Title order={2}>Files</Title>
        <input
          type="file"
          accept=".pdf"
          onChange={(e) => {
            const file = e.target.files?.[0] ?? null;
            setSelectedFile(file);
            setUploadError(null);
          }}
        />
        <Button onClick={onUpload} disabled={!selectedFile || uploading} loading={uploading}>
          Upload
        </Button>
        <Button
          variant="light"
          disabled={!selectedFile || uploading}
          onClick={() => {
            setSelectedFile(null);
            setUploadError(null);
          }}
        >
          Clear
        </Button>
      </Group>
      <Group>
        <Text size="sm">
          Selected: {selectedFile ? `${selectedFile.name} (${Math.ceil(selectedFile.size / 1024)} KB)` : "none"}
        </Text>
      </Group>
      {uploadError && (
        <Text size="sm" c="red">
          {uploadError}
        </Text>
      )}
      {uploading && <Text size="sm">Uploading...</Text>}
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
              <Text size="sm">
                status: {f.status} | progress: {f.progress_done}/{f.progress_total} | pages: {f.pages_count ?? "-"}
              </Text>
              {f.error_summary && <Text c="red">{f.error_summary}</Text>}
              {reprocessErrorById[f.id] && <Text c="red">{reprocessErrorById[f.id]}</Text>}
              {deleteErrorById[f.id] && <Text c="red">{deleteErrorById[f.id]}</Text>}
            </Box>
            <Group>
              <Button
                variant="light"
                loading={reprocessingFileId === f.id}
                disabled={
                  reprocessingFileId !== null ||
                  deletingFileId !== null ||
                  !["done", "failed", "validation_failed"].includes(f.status)
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
                  deletingFileId !== null ||
                  !["done", "failed", "validation_failed"].includes(f.status)
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

function FilePage() {
  const { fileId = "" } = useParams();
  useFileEvents(fileId);
  const [params, setParams] = useSearchParams();
  const [hoveredBlock, setHoveredBlock] = useState<string | null>(null);
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
            <Box className="file-left-column page-box">
              <img className="page-image" src={mediaUrl(p.image_path)} alt={`page-${p.page_number}`} />
              <svg className="overlay" viewBox={`0 0 ${p.width_px ?? 1} ${p.height_px ?? 1}`}>
                {p.blocks.map((b: BlockItem) => (
                  <rect
                    key={b.id}
                    x={b.bbox_px.x}
                    y={b.bbox_px.y}
                    width={b.bbox_px.width}
                    height={b.bbox_px.height}
                    fill="none"
                    stroke={b.color_key}
                    strokeWidth={hoveredBlock === b.id ? 4 : 2}
                    onMouseEnter={() => setHoveredBlock(b.id)}
                    onMouseLeave={() => setHoveredBlock(null)}
                  />
                ))}
              </svg>
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
