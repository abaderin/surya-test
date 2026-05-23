import { BlockItem } from "./types";

const OCR_BLOCK_TYPES = new Set([
  "text",
  "sectionheader",
  "listitem",
  "pageheader",
  "equation",
  "caption",
  "footnote",
  "code",
  "form",
]);

export type BlockContentState =
  | { kind: "image" }
  | { kind: "text"; text: string }
  | { kind: "ocr_pending" }
  | { kind: "image_pending" }
  | { kind: "none" };

function extractText(result: Record<string, unknown> | null): string | null {
  if (!result) return null;
  const text = result.text;
  if (typeof text !== "string") return null;
  const trimmed = text.trim();
  return trimmed ? trimmed : null;
}

export function getBlockContentState(block: BlockItem): BlockContentState {
  if (block.artifact_path) return { kind: "image" };

  const text = extractText(block.result);
  if (text) return { kind: "text", text };

  const type = block.type.trim().toLowerCase();
  if (type === "picture") return { kind: "image_pending" };
  if (OCR_BLOCK_TYPES.has(type)) return { kind: "ocr_pending" };
  return { kind: "none" };
}
