import { describe, expect, it } from "vitest";
import { getBlockContentState } from "./blockContent";
import { BlockItem } from "./types";

function buildBlock(partial: Partial<BlockItem>): BlockItem {
  return {
    id: "block-id",
    type: "Text",
    bbox_px: { x: 0, y: 0, width: 1, height: 1 },
    bbox_norm: { x: 0, y: 0, width: 1, height: 1 },
    color_key: "blue",
    raw_surya: {},
    result: null,
    artifact_path: null,
    ...partial,
  };
}

describe("getBlockContentState", () => {
  it("shows text for list item when OCR result exists", () => {
    const block = buildBlock({ type: "ListItem", result: { text: "Item text" } });
    expect(getBlockContentState(block)).toEqual({ kind: "text", text: "Item text" });
  });

  it("shows text for section header when OCR result exists", () => {
    const block = buildBlock({ type: "SectionHeader", result: { text: "Header text" } });
    expect(getBlockContentState(block)).toEqual({ kind: "text", text: "Header text" });
  });

  it("shows OCR pending for OCR block with empty text", () => {
    const block = buildBlock({ type: "Text", result: { text: "   " } });
    expect(getBlockContentState(block)).toEqual({ kind: "ocr_pending" });
  });

  it("shows image pending for picture block without artifact", () => {
    const block = buildBlock({ type: "Picture" });
    expect(getBlockContentState(block)).toEqual({ kind: "image_pending" });
  });

  it("shows no content for unsupported block without extraction", () => {
    const block = buildBlock({ type: "Table" });
    expect(getBlockContentState(block)).toEqual({ kind: "none" });
  });
});
