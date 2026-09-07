/**
 * RichTextEditor table support — the canvas email composer gains
 * Outlook-style tables ("add the ability to add tables like outlook in
 * canvas email"). Covers: sanitizer keeps tables but strips dangerous
 * content inside them; the Table toolbar button emits a real <table> even
 * where execCommand insertHTML is unavailable.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

import RichTextEditor, { applyCellShading, closestTableCell, sanitizeEmailHtml } from "../RichTextEditor";

describe("sanitizeEmailHtml — tables", () => {
  it("keeps a styled table with rows and cells", () => {
    const html =
      '<table style="border-collapse: collapse;" border="1" cellspacing="0">' +
      "<tbody><tr><td style=\"border: 1pt solid rgb(191,191,191); padding: 4pt;\">Hydmech DM10</td>" +
      '<td colspan="1">Linmac WG-350DSAV</td></tr></tbody></table>';
    const clean = sanitizeEmailHtml(html);
    expect(clean).toContain("<table");
    expect(clean).toContain("<tr>");
    expect(clean).toContain("<td");
    expect(clean).toContain("Hydmech DM10");
    expect(clean).toContain("border-collapse");
  });

  it("strips scripts and handlers inside table cells", () => {
    const dirty =
      "<table><tr><td onclick=\"steal()\">ok</td>" +
      "<td><script>alert(1)</script>safe</td></tr></table>";
    const clean = sanitizeEmailHtml(dirty);
    expect(clean).not.toContain("onclick");
    expect(clean).not.toContain("script");
    expect(clean).toContain("safe");
  });
});

describe("RichTextEditor Table button", () => {
  it("renders the Table toolbar button", () => {
    render(<RichTextEditor value="<p>hi</p>" onChange={() => {}} testIdPrefix="canvas-email-body" />);
    expect(screen.getByTestId("canvas-email-body-table-btn")).toBeInTheDocument();
    expect(screen.getByTitle("Table")).toBeInTheDocument();
  });

  it("inserts a table via the prompt spec (execCommand fallback path)", async () => {
    const onChange = jest.fn();
    const promptSpy = jest.spyOn(window, "prompt").mockReturnValue("2,3");
    render(
      <RichTextEditor value="" onChange={onChange} testIdPrefix="canvas-email-body" />
    );

    fireEvent.click(screen.getByTestId("canvas-email-body-table-btn"));

    await waitFor(() => {
      expect(onChange).toHaveBeenCalled();
    });
    const emitted = onChange.mock.calls[onChange.mock.calls.length - 1][0] as string;
    expect(emitted).toContain("<table");
    expect(emitted).toContain("<td");
    // 2 rows × 3 cells
    expect(emitted.match(/<tr>/g)?.length).toBe(2);
    expect(emitted.match(/<td /g)?.length).toBe(6);
    promptSpy.mockRestore();
  });

  it("ignores a cancelled prompt", () => {
    const onChange = jest.fn();
    const promptSpy = jest.spyOn(window, "prompt").mockReturnValue(null);
    render(
      <RichTextEditor value="" onChange={onChange} testIdPrefix="canvas-email-body" />
    );
    fireEvent.click(screen.getByTestId("canvas-email-body-table-btn"));
    expect(onChange).not.toHaveBeenCalled();
    promptSpy.mockRestore();
  });
});

describe("RichTextEditor — multi-line HTML table display", () => {
  it("renders a pretty-printed (one-tag-per-line) table as a real table", () => {
    // Agent-drafted tables arrive with newlines between tags. Per-line
    // sanitizing used to destroy them (empty <table>, hoisted <td> text,
    // visible escaped </tr>) — the 2026-09-03 canvas incident.
    const body = [
      "Hi Jacob,",
      "",
      '<table style="border-collapse: collapse; width: 100%;">',
      "<tr>",
      '<td style="border: 1pt solid #000; padding: 8px;"><strong>Description</strong></td>',
      "<td><strong>Price</strong></td>",
      "</tr>",
      "<tr>",
      "<td>Linmac WG-350DSAV</td>",
      "<td>See Consolidated Price List 2019</td>",
      "</tr>",
      "</table>",
      "",
      "Regards,",
      "Rish M.",
    ].join("\n");
    const { getByTestId } = render(
      <RichTextEditor value={body} onChange={() => {}} testIdPrefix="canvas-email-body" />
    );
    const editor = getByTestId("canvas-email-body-editor");
    expect(editor.querySelector("table")).not.toBeNull();
    expect(editor.querySelectorAll("td").length).toBe(4);
    expect(editor.textContent).toContain("Linmac WG-350DSAV");
    // the destruction signatures of the per-line pass
    expect(editor.innerHTML).not.toContain("&lt;/tr&gt;");
    expect(editor.innerHTML).not.toMatch(/<table[^>]*><\/table>/);
  });

  it("still converts plain-text bodies line-by-line", () => {
    const { getByTestId } = render(
      <RichTextEditor
        value={"Hi Jacob,\n\nPlease quote.\n\nRegards,"}
        onChange={() => {}}
        testIdPrefix="canvas-email-body"
      />
    );
    const editor = getByTestId("canvas-email-body-editor");
    expect(editor.innerHTML).toContain("Hi Jacob,<br>");
    expect(editor.querySelector("table")).toBeNull();
  });
});

describe("cell shading", () => {
  it("applyCellShading sets the background of the cell containing the node", () => {
    document.body.innerHTML =
      '<table><tr><td id="c1"><strong>Description</strong></td><td id="c2">Price</td></tr></table>';
    const strong = document.getElementById("c1")!.querySelector("strong")!;
    // caret inside the <strong> inside the cell — the helper must find the CELL
    expect(applyCellShading(strong, "#1F3864")).toBe(true);
    expect((document.getElementById("c1") as HTMLTableCellElement).style.backgroundColor).toBe("rgb(31, 56, 100)");
    expect((document.getElementById("c2") as HTMLTableCellElement).style.backgroundColor).toBe("");
  });

  it("applyCellShading with 'none' clears the fill", () => {
    document.body.innerHTML = '<table><tr><td id="c1" style="background-color: #DBE5F1">x</td></tr></table>';
    const td = document.getElementById("c1")!;
    expect(applyCellShading(td, "none")).toBe(true);
    expect((td as HTMLTableCellElement).style.backgroundColor).toBe("");
  });

  it("applyCellShading returns false outside a table cell", () => {
    document.body.innerHTML = '<p id="p">plain</p>';
    expect(applyCellShading(document.getElementById("p"), "#DBE5F1")).toBe(false);
    expect(closestTableCell(document.getElementById("p"))).toBeNull();
  });

  it("shading dropdown shades the cell under the caret and emits HTML", () => {
    const onChange = jest.fn();
    const body =
      '<table><tr><td><strong>Description</strong></td><td>Price</td></tr>' +
      "<tr><td>Linmac WG-350DSAV</td><td>See price list</td></tr></table>";
    const { getByTestId } = render(
      <RichTextEditor value={body} onChange={onChange} testIdPrefix="canvas-email-body" />
    );
    const editor = getByTestId("canvas-email-body-editor");
    const headerCell = editor.querySelector("td")!;

    // caret inside the first header cell
    const range = document.createRange();
    range.selectNodeContents(headerCell.querySelector("strong")!);
    const sel = window.getSelection()!;
    sel.removeAllRanges();
    sel.addRange(range);

    fireEvent.change(getByTestId("canvas-email-body-shading"), {
      target: { value: "#1F3864" },
    });

    expect((headerCell as HTMLTableCellElement).style.backgroundColor).toBe("rgb(31, 56, 100)");
    expect(onChange).toHaveBeenCalled();
    const emitted = onChange.mock.calls[onChange.mock.calls.length - 1][0] as string;
    expect(emitted.toLowerCase()).toContain("background-color");
  });
});
