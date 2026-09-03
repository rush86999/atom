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

import RichTextEditor, { sanitizeEmailHtml } from "../RichTextEditor";

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
