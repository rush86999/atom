/**
 * SignatureEditor tests — the rich (WYSIWYG) signature editor.
 *
 * Styled signatures are saved as sanitized HTML: bold/italic/underline,
 * links, text colors, horizontal rules. Scripts/handlers/images are
 * stripped on every emit, so a pasted payload can never ride into
 * outgoing mail as markup.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SignatureEditor, { sanitizeSignatureHtml } from "../SignatureEditor";

describe("sanitizeSignatureHtml", () => {
  it("keeps formatting, links, colors, and rules", () => {
    const html =
      '<strong><em>Rish M.</em></strong><a href="https://www.brennan.ca">site</a>' +
      '<span style="color:#e8590c">How am I doing?</span><hr>';
    expect(sanitizeSignatureHtml(html)).toBe(html);
  });

  it("strips scripts, handlers, images, and forms", () => {
    const dirty =
      '<b onclick="steal()">hi</b><script>evil()</script>' +
      '<img src="x" onerror="evil()"><form action="phish"><input></form><iframe></iframe>';
    const clean = sanitizeSignatureHtml(dirty);
    expect(clean).toContain("<b>hi</b>");
    expect(clean).not.toContain("script");
    expect(clean).not.toContain("onerror");
    expect(clean).not.toContain("onclick");
    expect(clean).not.toContain("<img");
    expect(clean).not.toContain("<form");
    expect(clean).not.toContain("iframe");
  });

  it("keeps font tags with size, face, and color (per-user styles)", () => {
    const html = '<font size="4" face="Georgia" color="#e8590c">styled</font>';
    expect(sanitizeSignatureHtml(html)).toBe(html);
  });

  it("blocks javascript: link URLs", () => {
    const clean = sanitizeSignatureHtml('<a href="javascript:evil()">x</a>');
    expect(clean).not.toContain("javascript:");
  });

  it("returns empty for empty input", () => {
    expect(sanitizeSignatureHtml("")).toBe("");
    expect(sanitizeSignatureHtml(null)).toBe("");
  });
});

describe("SignatureEditor", () => {
  let execMock: jest.Mock;

  beforeEach(() => {
    // jsdom does not implement execCommand at all — install a mock the
    // toolbar actions can be asserted against.
    execMock = jest.fn(() => true);
    (document as any).execCommand = execMock;
  });

  afterEach(() => {
    delete (document as any).execCommand;
  });

  it("renders the current signature HTML into the editable surface", () => {
    render(<SignatureEditor value="<b>Old sig</b>" onChange={() => {}} />);
    const editor = screen.getByTestId("canvas-signature-editor");
    expect(editor.innerHTML).toContain("<b>Old sig</b>");
    expect(editor.getAttribute("contenteditable")).toBe("true");
  });

  it("emits sanitized HTML when the user types", () => {
    const onChange = jest.fn();
    render(<SignatureEditor value="" onChange={onChange} />);
    const editor = screen.getByTestId("canvas-signature-editor");
    fireEvent.input(editor, {
      target: { innerHTML: "Regards,<br><b>Rish M.</b>" },
    });
    expect(onChange).toHaveBeenCalled();
    const emitted = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(emitted).toContain("Regards,<br><b>Rish M.</b>");
  });

  it("toolbar bold/italic/underline run execCommand with the right commands", () => {
    render(<SignatureEditor value="sig" onChange={() => {}} />);
    fireEvent.click(screen.getByLabelText("Bold"));
    fireEvent.click(screen.getByLabelText("Italic"));
    fireEvent.click(screen.getByLabelText("Underline"));
    const calls = execMock.mock.calls.map((c) => c[0]);
    expect(calls).toEqual(expect.arrayContaining(["bold", "italic", "underline"]));
  });

  it("link button prompts for a URL and inserts it", () => {
    const promptSpy = jest.spyOn(window, "prompt").mockReturnValue("https://www.brennan.ca");
    render(<SignatureEditor value="sig" onChange={() => {}} />);
    fireEvent.click(screen.getByTestId("canvas-signature-link"));
    const calls = execMock.mock.calls.map((c) => c[0]);
    expect(calls).toContain("createLink");
    const linkCall = execMock.mock.calls.find(
      (c) => c[0] === "createLink",
    );
    expect(linkCall[2]).toBe("https://www.brennan.ca");
    promptSpy.mockRestore();
  });

  it("link button without a URL does nothing", () => {
    const promptSpy = jest.spyOn(window, "prompt").mockReturnValue(null);
    render(<SignatureEditor value="sig" onChange={() => {}} />);
    fireEvent.click(screen.getByTestId("canvas-signature-link"));
    const calls = execMock.mock.calls.map((c) => c[0]);
    expect(calls).not.toContain("createLink");
    promptSpy.mockRestore();
  });

  it("color swatches apply foreColor", () => {
    render(<SignatureEditor value="sig" onChange={() => {}} />);
    const orange = screen.getByLabelText("Text color #e8590c");
    fireEvent.click(orange);
    const call = execMock.mock.calls.find(
      (c) => c[0] === "foreColor",
    );
    expect(call[2]).toBe("#e8590c");
  });

  it("font size select applies fontSize", () => {
    render(<SignatureEditor value="sig" onChange={() => {}} />);
    const select = screen.getByLabelText("Font size");
    fireEvent.change(select, { target: { value: "5" } });
    const call = execMock.mock.calls.find((c) => c[0] === "fontSize");
    expect(call[2]).toBe("5");
  });

  it("font family select applies fontName", () => {
    render(<SignatureEditor value="sig" onChange={() => {}} />);
    const select = screen.getByLabelText("Font");
    fireEvent.change(select, { target: { value: "Georgia, serif" } });
    const call = execMock.mock.calls.find((c) => c[0] === "fontName");
    expect(call[2]).toBe("Georgia, serif");
  });

  it("hr button inserts a horizontal rule", () => {
    render(<SignatureEditor value="sig" onChange={() => {}} />);
    fireEvent.click(screen.getByTestId("canvas-signature-hr"));
    const calls = execMock.mock.calls.map((c) => c[0]);
    expect(calls).toContain("insertHorizontalRule");
  });

  it("does not clobber the caret while the editor has focus", () => {
    const onChange = jest.fn();
    render(<SignatureEditor value="<b>sig</b>" onChange={onChange} />);
    const editor = screen.getByTestId("canvas-signature-editor");
    editor.focus();
    const before = editor.innerHTML;
    // a parent re-render with the same value must not rewrite the DOM
    render(<SignatureEditor value="<b>sig</b>" onChange={onChange} />);
    expect(editor.innerHTML).toBe(before);
    editor.focus();
  });
});


describe("SignatureEditor active-format dropdowns", () => {
  let execMock: jest.Mock;
  let queryValue: (cmd: string) => unknown;

  beforeEach(() => {
    execMock = jest.fn(() => true);
    (document as any).execCommand = execMock;
    queryValue = () => undefined;
    (document as any).queryCommandValue = (cmd: string) => queryValue(cmd);
  });

  afterEach(() => {
    delete (document as any).execCommand;
    delete (document as any).queryCommandValue;
  });

  const fireSelectionChange = () =>
    document.dispatchEvent(new Event("selectionchange"));

  it("font size dropdown reflects the size at the caret", async () => {
    render(<SignatureEditor value="sig" onChange={() => {}} />);
    queryValue = (cmd) => (cmd === "fontSize" ? 5 : "");
    fireSelectionChange();
    await waitFor(() =>
      expect((screen.getByLabelText("Font size") as HTMLSelectElement).value).toBe("5"),
    );
  });

  it("font family dropdown reflects the family at the caret", async () => {
    render(<SignatureEditor value="sig" onChange={() => {}} />);
    queryValue = (cmd) =>
      cmd === "fontName" ? "Georgia, serif" : "";
    fireSelectionChange();
    await waitFor(() =>
      expect(
        (screen.getByLabelText("Font") as HTMLSelectElement).value,
      ).toContain("Georgia"),
    );
  });

  it("neutral caret shows the placeholder, not a stale family", async () => {
    render(<SignatureEditor value="sig" onChange={() => {}} />);
    queryValue = (cmd) => (cmd === "fontName" ? "Helvetica Neue" : "");
    fireSelectionChange();
    await waitFor(() =>
      expect((screen.getByLabelText("Font") as HTMLSelectElement).value).toBe(""),
    );
  });

  it("applying a size keeps the dropdown on the applied value", async () => {
    queryValue = () => "";
    render(<SignatureEditor value="sig" onChange={() => {}} />);
    const select = screen.getByLabelText("Font size") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "7" } });
    expect((screen.getByLabelText("Font size") as HTMLSelectElement).value).toBe("7");
  });
});
