/**
 * Office canvas AI-accessibility tests — CanvasPanel + CanvasHost must expose
 * the office co-editing state via window.atom.canvas.getState() so agents can
 * read back what the user sees (grid cells / document text / slide outline).
 */
import React from "react";
import { render } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock("@monaco-editor/react", () => ({
  __esModule: true,
  default: ({ value, onChange }: any) => (
    <textarea data-testid="canvas-editor" value={value} onChange={(e) => onChange?.(e.target.value)} />
  ),
}));

import { CanvasPanel } from "@/components/canvas/CanvasPanel";

const OFFICE_XLSX = {
  type: "canvas:present",
  data: {
    action: "present",
    component: "office_excel",
    canvas_id: "off-1",
    title: "book.xlsx",
    data: {
      format: "xlsx",
      file_path: "/data/office/book.xlsx",
      active_sheet: "Sheet1",
      sheets: [{ name: "Sheet1", rows: [["Item", "Qty"], ["Widget", 4]] }],
      formulas: {},
    },
  },
};

describe("office canvas a11y registration", () => {
  let rerenderFn: any;

  beforeEach(() => {
    delete (window as any).atom;
    const { rerender } = render(<CanvasPanel lastMessage={null} />);
    rerenderFn = rerender;
  });

  it("registers sheets state with grid cells and file path for office_excel", () => {
    rerenderFn(<CanvasPanel lastMessage={OFFICE_XLSX} />);

    const state = (window as any).atom.canvas.getState("off-1");
    expect(state).not.toBeNull();
    expect(state.type).toBe("sheets");
    expect(state.sheetName).toBe("Sheet1");
    expect(state.filePath).toBe("/data/office/book.xlsx");
    expect(state.cells).toEqual([
      ["Item", "Qty"],
      ["Widget", 4],
    ]);
  });

  it("registers docs state with text body for office_word", () => {
    rerenderFn(
      <CanvasPanel
        lastMessage={{
          type: "canvas:present",
          data: {
            action: "present",
            component: "office_word",
            canvas_id: "off-2",
            title: "r.docx",
            data: { format: "docx", file_path: "/data/office/r.docx", text: "Para one." },
          },
        }}
      />
    );

    const state = (window as any).atom.canvas.getState("off-2");
    expect(state.type).toBe("docs");
    expect(state.format).toBe("docx");
    expect(state.sections[0].body).toBe("Para one.");
    expect(state.filePath).toBe("/data/office/r.docx");
  });

  it("registers slide outline for office_pptx", () => {
    rerenderFn(
      <CanvasPanel
        lastMessage={{
          type: "canvas:present",
          data: {
            action: "present",
            component: "office_pptx",
            canvas_id: "off-3",
            title: "deck.pptx",
            data: {
              format: "pptx",
              file_path: "/data/office/deck.pptx",
              slides: [{ slide_number: 1, title: "Intro", content: "Body" }],
            },
          },
        }}
      />
    );

    const state = (window as any).atom.canvas.getState("off-3");
    expect(state.component).toBe("office_pptx");
    expect(state.slides).toHaveLength(1);
    expect(state.slides[0].title).toBe("Intro");
    expect(state.filePath).toBe("/data/office/deck.pptx");
  });
});
