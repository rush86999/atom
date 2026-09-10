/**
 * OfficeFileCanvas Tests (components/canvas/OfficeFileCanvas.tsx)
 *
 * The co-editing loop: user edits commit to the real file via
 * POST /api/v1/office/sync-update, and structured snapshots (from the save
 * response or WS canvas:update) re-render the editors.
 *
 * Covered:
 * - xlsx grid renders cells; editing a cell commits on blur with
 *   {cell_path, value, is_formula} (formula detection for '=' values)
 * - unchanged cells don't POST
 * - sheet tabs switch the rendered sheet
 * - docx textarea commits edit_type 'document' with full text
 * - pptx slide title/content commit edit_type 'slide'; Add Slide posts
 *   'add_slide'
 * - save-response snapshot is applied (recalced values replace inputs)
 * - agent WS snapshot arriving mid-edit queues behind an "Agent updated"
 *   notice instead of clobbering the user's work
 * - backend errors surface in the status strip
 * - preview mode renders sanitized backend HTML
 */
import React from "react";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import "@testing-library/jest-dom";

import { OfficeFileCanvas, OfficeFileContent } from "../OfficeFileCanvas";

// The component talks through the shared axios client (absolute backend
// baseURL). Mock it directly so tests capture the exact sync payloads.
jest.mock("@/lib/api", () => ({
  apiClient: { post: jest.fn().mockResolvedValue({ data: {} }), get: jest.fn() },
}));

import { apiClient } from "@/lib/api";
const postMock = apiClient.post as jest.Mock;
const getMock = apiClient.get as jest.Mock;

const XLSX_SNAPSHOT: OfficeFileContent = {
  format: "xlsx",
  file_path: "/data/office/book.xlsx",
  active_sheet: "Sheet1",
  sheet_names: ["Sheet1"],
  sheets: [{ name: "Sheet1", rows: [["Item", "Qty"], ["Widget", 4]] }],
  formulas: {},
};

describe("OfficeFileCanvas", () => {
  beforeEach(() => {
    postMock.mockReset();
    postMock.mockResolvedValue({ data: {} });
    getMock.mockReset();
  });

  const xlsxData = (over: Partial<OfficeFileContent> = {}): OfficeFileContent => ({
    ...XLSX_SNAPSHOT,
    ...over,
  });

  const lastBody = () => postMock.mock.calls[postMock.mock.calls.length - 1][1];

  it("renders grid cells from the structured snapshot", () => {
    render(<OfficeFileCanvas data={xlsxData()} />);
    expect(screen.getByDisplayValue("Widget")).toBeInTheDocument();
    expect(screen.getByDisplayValue("4")).toBeInTheDocument();
    expect(screen.getByText("Synced to file")).toBeInTheDocument();
  });

  it("commits an edited cell on blur with its cell_path", async () => {
    render(<OfficeFileCanvas canvasId="c-1" data={xlsxData()} />);

    const qty = screen.getByDisplayValue("4");
    fireEvent.change(qty, { target: { value: "9" } });
    fireEvent.blur(qty);

    await waitFor(() => expect(postMock).toHaveBeenCalledTimes(1));
    expect(postMock.mock.calls[0][0]).toBe("/api/v1/office/sync-update");
    expect(lastBody()).toMatchObject({
      canvas_id: "c-1",
      file_path: "/data/office/book.xlsx",
      edit_type: "cell",
      data: { cell_path: "/Sheet1/B2", value: "9", is_formula: false },
    });
  });

  it("flags '=' input as a formula", async () => {
    render(<OfficeFileCanvas data={xlsxData()} />);

    const qty = screen.getByDisplayValue("4");
    fireEvent.change(qty, { target: { value: "=SUM(B1:B2)" } });
    fireEvent.blur(qty);

    await waitFor(() => expect(postMock).toHaveBeenCalledTimes(1));
    expect(lastBody().data.is_formula).toBe(true);
    expect(lastBody().data.value).toBe("=SUM(B1:B2)");
  });

  it("does not POST when a blurred cell is unchanged", async () => {
    render(<OfficeFileCanvas data={xlsxData()} />);

    const widget = screen.getByDisplayValue("Widget");
    fireEvent.focus(widget);
    fireEvent.blur(widget);

    expect(postMock).not.toHaveBeenCalled();
    expect(screen.getByText("Synced to file")).toBeInTheDocument();
  });

  describe("formulas", () => {
    const formulaData = () =>
      xlsxData({
        sheets: [{ name: "Sheet1", rows: [["Item", "Qty"], ["a", 1], ["b", 2], ["total", 3]] }],
        formulas: { Sheet1: { B4: "=SUM(B2:B3)" } },
      });

    it("shows the selected cell's formula in the formula bar", () => {
      render(<OfficeFileCanvas data={formulaData()} />);
      const bar = screen.getByLabelText("Formula bar");
      const gridCell = (text: string) =>
        within(screen.getByRole("table")).getByDisplayValue(text);

      // Formula cell: bar shows the '=...' source, not the computed value.
      fireEvent.focus(gridCell("3"));
      expect(bar).toHaveDisplayValue("=SUM(B2:B3)");

      // Plain cell: bar falls back to the cell value.
      fireEvent.focus(gridCell("a"));
      expect(bar).toHaveDisplayValue("a");
    });

    it("shows the formula in the cell on focus and restores the value on blur", () => {
      render(<OfficeFileCanvas data={formulaData()} />);

      const cell = screen.getByDisplayValue("3");
      fireEvent.focus(cell);
      expect(cell).toHaveDisplayValue("=SUM(B2:B3)");

      fireEvent.blur(cell);
      expect(cell).toHaveDisplayValue("3");
      // A formula shown on focus + untouched blur is NOT a user edit.
      expect(postMock).not.toHaveBeenCalled();
    });

    it("commits when the user edits the formula text", async () => {
      render(<OfficeFileCanvas data={formulaData()} />);

      const cell = screen.getByDisplayValue("3");
      fireEvent.focus(cell);
      expect(cell).toHaveDisplayValue("=SUM(B2:B3)");
      fireEvent.change(cell, { target: { value: "=SUM(B2:B3)*2" } });
      fireEvent.blur(cell);

      await waitFor(() => expect(postMock).toHaveBeenCalledTimes(1));
      expect(lastBody().data).toMatchObject({
        cell_path: "/Sheet1/B4",
        value: "=SUM(B2:B3)*2",
        is_formula: true,
      });
    });

    it("flags a new '=' entry as a formula even when the cell shows a computed value", async () => {
      render(<OfficeFileCanvas data={formulaData()} />);

      const total = screen.getByDisplayValue("3");
      fireEvent.change(total, { target: { value: "=B2+B3" } });
      fireEvent.blur(total);

      await waitFor(() => expect(postMock).toHaveBeenCalledTimes(1));
      expect(lastBody().data.is_formula).toBe(true);
    });
  });

  describe("hydration (REST reload with no structured snapshot)", () => {
    it("fetches every sheet plus the formulas map for the formula bar", async () => {
      getMock.mockImplementation((_url: string, params: { params: { cell_path: string } }) => {
        if (params.params.cell_path === "A1:Z500") {
          return Promise.resolve({
            data: {
              success: true,
              sheet_name: "Sheet1",
              sheet_names: ["Sheet1", "Summary"],
              cells: [[{ cell_ref: "A1", value: "Widget", cell_type: "text" }]],
            },
          });
        }
        if (params.params.cell_path === "/Summary/A1:Z500") {
          return Promise.resolve({
            data: {
              success: true,
              sheet_name: "Summary",
              cells: [[{ cell_ref: "A1", value: 42, cell_type: "text" }]],
              formulas: { A1: "=SUM(Sheet1!A1)" },
            },
          });
        }
        return Promise.resolve({ data: { success: true, sheet_name: "?", cells: [] } });
      });

      render(<OfficeFileCanvas data={{ format: "xlsx", file_path: "/data/office/book.xlsx" }} />);

      // Active sheet hydrated from the response…
      expect(await screen.findByDisplayValue("Widget")).toBeInTheDocument();
      // …the second sheet's rows are hydrated too (tabs functional)…
      fireEvent.click(screen.getByRole("button", { name: "Summary" }));
      const summaryCell = await within(screen.getByRole("table")).findByDisplayValue("42");
      // …and the formula bar shows the hydrated formula on selection.
      fireEvent.focus(summaryCell);
      expect(screen.getByLabelText("Formula bar")).toHaveDisplayValue("=SUM(Sheet1!A1)");

      expect(getMock).toHaveBeenCalledWith("/api/v1/office/excel", {
        params: { file_path: "/data/office/book.xlsx", cell_path: "A1:Z500" },
      });
    });
  });

  it("switches sheets via tabs", () => {
    render(
      <OfficeFileCanvas
        data={xlsxData({
          sheet_names: ["Sheet1", "Summary"],
          sheets: [
            { name: "Sheet1", rows: [["a", "b"]] },
            { name: "Summary", rows: [["total", "42"]] },
          ],
        })}
      />
    );

    expect(screen.getByDisplayValue("a")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Summary" }));
    expect(screen.getByDisplayValue("total")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("a")).not.toBeInTheDocument();
  });

  it("applies the recalced snapshot returned by the save response", async () => {
    postMock.mockResolvedValue({
      data: {
        success: true,
        content: {
          format: "xlsx",
          active_sheet: "Sheet1",
          sheet_names: ["Sheet1"],
          sheets: [{ name: "Sheet1", rows: [["Item", "Qty"], ["Widget", 90]] }],
          formulas: {},
        },
      },
    });

    render(<OfficeFileCanvas data={xlsxData()} />);
    const qty = screen.getByDisplayValue("4");
    fireEvent.change(qty, { target: { value: "90" } });
    fireEvent.blur(qty);

    // Recalced value arrives via the response snapshot.
    await waitFor(() => expect(screen.getByDisplayValue("90")).toBeInTheDocument());
  });

    it("queues an agent snapshot while the user is mid-edit", () => {
      const { rerender } = render(<OfficeFileCanvas data={xlsxData()} />);
      const gridCell = (text: string) =>
        within(screen.getByRole("table")).getByDisplayValue(text);

      // User focuses a cell (mid-edit), then an agent edit broadcast arrives.
      fireEvent.focus(gridCell("4"));
      rerender(
        <OfficeFileCanvas
          data={xlsxData({
            sheets: [{ name: "Sheet1", rows: [["Item", "Qty"], ["Widget", "AGENT"]] }],
          })}
        />
      );

      // User's view is NOT clobbered; a notice appears instead.
      expect(gridCell("4")).toBeInTheDocument();
      const notice = screen.getByRole("button", { name: /agent updated this file/i });
      expect(notice).toBeInTheDocument();

      // Clicking loads the agent's version once the user is ready.
      fireEvent.click(notice);
      expect(gridCell("AGENT")).toBeInTheDocument();
    });

  describe("docx", () => {
    it("commits the document text as one edit", async () => {
      render(
        <OfficeFileCanvas
          canvasId="c-doc"
          data={{ format: "docx", file_path: "/data/office/r.docx", text: "Para one." }}
        />
      );

      const area = screen.getByDisplayValue("Para one.");
      fireEvent.change(area, { target: { value: "Para one.\nPara two." } });
      fireEvent.blur(area);

      await waitFor(() => expect(postMock).toHaveBeenCalledTimes(1));
      expect(lastBody()).toMatchObject({
        canvas_id: "c-doc",
        edit_type: "document",
        data: { content: "Para one.\nPara two." },
      });
    });
  });

  describe("pptx", () => {
    const pptxData = (): OfficeFileContent => ({
      format: "pptx",
      file_path: "/data/office/deck.pptx",
      slides: [{ slide_number: 1, title: "Intro", content: "Body text" }],
    });

    it("commits slide title edits", async () => {
      render(<OfficeFileCanvas data={pptxData()} />);

      const title = screen.getByDisplayValue("Intro");
      fireEvent.change(title, { target: { value: "Agenda" } });
      fireEvent.blur(title);

      await waitFor(() => expect(postMock).toHaveBeenCalledTimes(1));
      expect(lastBody().edit_type).toBe("slide");
      expect(lastBody().data).toMatchObject({
        slide_number: 1,
        title: "Agenda",
        content: "Body text",
      });
    });

    it("adds a slide via the Add Slide button", async () => {
      render(<OfficeFileCanvas data={pptxData()} />);

      fireEvent.click(screen.getByRole("button", { name: /add slide/i }));

      await waitFor(() => expect(postMock).toHaveBeenCalledTimes(1));
      expect(lastBody().edit_type).toBe("add_slide");
      expect(lastBody().data.title).toBe("New Slide");
    });
  });

  it("surfaces backend errors in the status strip", async () => {
    postMock.mockRejectedValue({
      response: { data: { detail: "cell_path required" } },
      message: "Request failed",
    });

    render(<OfficeFileCanvas data={xlsxData()} />);
    const qty = screen.getByDisplayValue("4");
    fireEvent.change(qty, { target: { value: "9" } });
    fireEvent.blur(qty);

    expect(await screen.findByText(/cell_path required/i)).toBeInTheDocument();
    // The user's typed value stays put so nothing is silently lost.
    expect(screen.getByDisplayValue("9")).toBeInTheDocument();
  });

  it("preview mode renders sanitized backend HTML", () => {
    render(<OfficeFileCanvas data={xlsxData({ html: "<b>Rich preview</b>" })} showPreview />);
    expect(screen.getByText("Rich preview")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("Widget")).not.toBeInTheDocument();
  });

  it("shows an error when no file is bound", async () => {
    render(<OfficeFileCanvas data={{ format: "docx", text: "x", office_file: "" }} />);

    const area = screen.getByDisplayValue("x");
    fireEvent.change(area, { target: { value: "y" } });
    fireEvent.blur(area);

    expect(await screen.findByText(/no file bound/i)).toBeInTheDocument();
    expect(postMock).not.toHaveBeenCalled();
  });
});
