"use client";

/**
 * Rich WYSIWYG text editor (Outlook-style toolbar) used for the email body
 * and the signature editor.
 *
 * Zero dependencies: formatting runs through document.execCommand, which is
 * deprecated but universally supported and the right tradeoff for email
 * composition (a full editor lib is overkill here).
 *
 * The value is an HTML STRING (styled email bodies/signatures are a
 * supported feature). All emitted HTML is sanitized with a dedicated
 * DOMPurify profile: unlike the shared agent-output sanitizer, inline
 * `style` (text color/alignment) and links are allowed, while scripts,
 * handlers, images, and forms stay forbidden.
 *
 * Enter inserts <br> (email-style), matching the line-aware plain-text →
 * HTML conversion in integrations/outlook_service._body_to_html.
 */

import React, { useEffect, useRef } from "react";
import DOMPurify from "dompurify";

const ALLOWED_TAGS = [
  "b", "i", "em", "strong", "u", "s", "br", "hr", "a", "span",
  "div", "p", "font", "ul", "ol", "li",
  // Tables (Outlook-style email tables — quotes, specs, comparisons)
  "table", "thead", "tbody", "tr", "td", "th",
];
const ALLOWED_ATTR = [
  "href", "style", "color", "target", "rel", "title", "size", "face",
  // Table geometry (Outlook composes with border/cellpadding attrs +
  // inline styles; colspan/rowspan for merged header cells)
  "border", "cellpadding", "cellspacing", "width", "align",
  "colspan", "rowspan", "valign",
];

export function sanitizeEmailHtml(dirty: string | undefined | null): string {
  if (!dirty) return "";
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ALLOW_DATA_ATTR: false,
    FORBID_TAGS: ["script", "style", "iframe", "object", "embed", "form", "input", "button", "img"],
    FORBID_ATTR: [
      "onerror", "onload", "onclick", "onmouseover", "onmouseenter",
      "onmouseleave", "onsubmit", "onchange", "oninput", "onfocus", "onblur",
    ],
  });
}

const COLORS: Array<{ label: string; value: string }> = [
  { label: "A", value: "" },        // default text color
  { label: "A", value: "#e8590c" }, // orange
  { label: "A", value: "#9775fa" }, // purple
  { label: "A", value: "#1971c2" }, // blue
  { label: "A", value: "#2f9e44" }, // green
  { label: "A", value: "#e03131" }, // red
  { label: "A", value: "#868e96" }, // gray
];

const FONTS = [
  { label: "Aptos", value: "Aptos, Calibri, Arial, sans-serif" },
  { label: "Calibri", value: "Calibri, Arial, sans-serif" },
  { label: "Arial", value: "Arial, Helvetica, sans-serif" },
  { label: "Georgia", value: "Georgia, serif" },
  { label: "Times New Roman", value: "'Times New Roman', serif" },
  { label: "Courier New", value: "'Courier New', monospace" },
  { label: "Verdana", value: "Verdana, Geneva, sans-serif" },
  { label: "Trebuchet MS", value: "'Trebuchet MS', sans-serif" },
];

export const DEFAULT_EMAIL_FONT = "Aptos, 'Segoe UI', Calibri, Arial, sans-serif";

// Plain text → display HTML, mirroring the send sink's conversion
// (integrations/outlook_service._body_to_html): legacy plain-text bodies
// (newline-separated) MUST be converted for display — newlines are
// invisible in contentEditable HTML, which read as "all formatting lost".
function toDisplayHtml(raw: string): string {
  // Multi-line HTML (agent-drafted tables pretty-print one tag per line)
  // must be re-joined at tag boundaries BEFORE the per-line pass: a lone
  // <table>/<tr>/<td> fragment sanitizes outside a table context and is
  // destroyed (empty <table></table>, hoisted cell text, escaped </tr> —
  // observed live 2026-09-03: a well-formed quote table flattened into a
  // bare line list, then persisted by the composer's save).
  const text = String(raw ?? "").replace(/>\s*\n\s*</g, "><");
  const lines = text.split("\n");
  const tagRe = /<\s*(p|br|div|span|ul|ol|li|h[1-6]|hr|table|thead|tbody|tr|td|th|a|b|i|strong|em|u|font)\b/i;
  if (!lines.some((ln) => tagRe.test(ln))) {
    const escaped = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    return escaped.split("\n").join("<br>");
  }
  // Mixed content (plain draft + styled HTML signature): convert plain
  // lines, keep HTML lines verbatim — same contract as the send sink.
  return lines
    .map((ln) => (tagRe.test(ln) ? sanitizeEmailHtml(ln) : (
      ln.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    )))
    .join("<br>");
}

const SIZE_OPTIONS = [
  { label: "Small", value: "1" },
  { label: "Normal", value: "3" },
  { label: "Large", value: "5" },
  { label: "Huge", value: "7" },
];

function mapFontSizeValue(fs: unknown): string {
  const raw = String(fs ?? "").trim();
  const n = parseInt(raw, 10);
  if (!Number.isNaN(n)) {
    if (n <= 2) return "1";
    if (n <= 4) return "3";
    if (n <= 6) return "5";
    return "7";
  }
  const px = parseFloat(raw);
  if (!Number.isNaN(px)) {
    if (px < 13) return "1";
    if (px < 17) return "3";
    if (px < 24) return "5";
    return "7";
  }
  return "";
}

function matchFontFamily(ff: string): string {
  const s = String(ff || "").toLowerCase();
  if (!s) return "";
  for (const f of FONTS) {
    const first = f.value.split(",")[0].replace(/'/g, "").trim().toLowerCase();
    if (first && s.includes(first)) return f.value;
  }
  return "";
}

export default function RichTextEditor({
  value,
  onChange,
  testIdPrefix = "rich-editor",
  minHeight = "72px",
  baseFontFamily = DEFAULT_EMAIL_FONT,
  // Outlook's default body size is 11pt ≈ 15px — the Tailwind text-xs that
  // used to sit on this element pinned it at 12px and clobbered it.
  baseFontSize = "15px",
}: {
  value: string;
  onChange: (html: string) => void;
  testIdPrefix?: string;
  minHeight?: string;
  /** Editing-surface font (WYSIWYG). Outlook applies its default font at
   * render time, so this does NOT need to be embedded in the emitted HTML. */
  baseFontFamily?: string;
  baseFontSize?: string;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  // The HTML we last emitted. When the incoming value equals it, the change
  // is our own echo — re-applying it would fight the browser's DOM
  // serialization (attribute/entity normalization differs from DOMPurify
  // output) and visibly reset the editor mid-typing.
  const lastEmittedRef = useRef<string | null>(null);
  // Active formatting at the caret — the dropdowns reflect it (Outlook-style).
  const [activeFontSize, setActiveFontSize] = React.useState("");
  const [activeFontFamily, setActiveFontFamily] = React.useState("");

  const refreshActiveFormats = React.useCallback(() => {
    try {
      const fs = (document as any).queryCommandValue?.("fontSize");
      setActiveFontSize(mapFontSizeValue(fs));
      const ff = String((document as any).queryCommandValue?.("fontName") || "");
      setActiveFontFamily(matchFontFamily(ff));
    } catch {
      // unsupported — dropdowns stay neutral
    }
  }, []);

  useEffect(() => {
    document.addEventListener("selectionchange", refreshActiveFormats);
    return () => document.removeEventListener("selectionchange", refreshActiveFormats);
  }, [refreshActiveFormats]);

  // Reflect external value changes into the editable surface — never while
  // the user is typing in it (that would reset the caret mid-edit).
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (lastEmittedRef.current !== null && value === lastEmittedRef.current) return;
    if (document.activeElement === el) return;
    const next = toDisplayHtml(value);
    if (el.innerHTML !== next) el.innerHTML = next;
  }, [value]);

  // Enter → <br>, not <div> — email-style line breaks that survive the
  // line-aware plain-text → HTML conversion at the send sink.
  useEffect(() => {
    try {
      document.execCommand("defaultParagraphSeparator", false, "br");
    } catch {
      // jsdom / unsupported — Enter behavior degrades gracefully
    }
  }, []);

  const emit = () => {
    const html = sanitizeEmailHtml(ref.current?.innerHTML || "");
    lastEmittedRef.current = html;
    onChange(html);
  };

  const exec = (command: string, arg?: string) => {
    ref.current?.focus();
    try {
      document.execCommand(command, false, arg);
    } catch {
      // not implemented (e.g. jsdom) — formatting is a no-op there
    }
    emit();
  };

  const addLink = () => {
    const url = window.prompt("Link URL (https://…)", "https://");
    if (!url || url === "https://") return;
    exec("createLink", url);
  };

  const insertTable = () => {
    const spec = window.prompt("Table rows,columns (e.g. 3,3)", "3,3");
    if (!spec) return;
    const parts = spec.split(/[,xX*\s]+/);
    const rows = Math.max(1, Math.min(20, parseInt(parts[0], 10) || 0));
    const cols = Math.max(1, Math.min(20, parseInt(parts[1], 10) || 0));
    if (!rows || !cols) return;
    // Outlook-style bordered table: inline cell borders survive email
    // clients where bare <table border> renders inconsistently.
    const cell =
      '<td style="border: 1pt solid rgb(191, 191, 191); padding: 4pt 6pt;">&nbsp;</td>';
    const row = `<tr>${cell.repeat(cols)}</tr>`;
    const html =
      '<table style="border-collapse: collapse;" border="1" cellspacing="0" cellpadding="0">' +
      `<tbody>${row.repeat(rows)}</tbody></table><br>`;
    ref.current?.focus();
    const before = ref.current?.innerHTML ?? "";
    try {
      document.execCommand("insertHTML", false, html);
    } catch {
      // jsdom / unsupported — the append fallback below still applies
    }
    // insertHTML is unimplemented in some environments (jsdom) or no-ops
    // with no caret selection — detect the no-op and append at the end.
    if (ref.current && ref.current.innerHTML === before) {
      ref.current.innerHTML = before + html;
    }
    emit();
  };

  const toolbarBtn =
    "h-6 min-w-6 px-1.5 rounded border border-zinc-200 dark:border-white/10 " +
    "hover:bg-zinc-100 dark:hover:bg-white/10 text-zinc-700 dark:text-zinc-200 " +
    "text-[11px] leading-none font-medium";
  const selectCls =
    "h-6 rounded border border-zinc-200 dark:border-white/10 bg-transparent " +
    "text-[11px] text-zinc-700 dark:text-zinc-200";

  return (
    <div className="space-y-1.5">
      <div
        className="flex flex-wrap items-center gap-0.5 border border-zinc-200 dark:border-white/10 rounded p-1"
        data-testid={`${testIdPrefix}-toolbar`}
      >
        <button type="button" title="Bold" aria-label="Bold" className={toolbarBtn} onClick={() => exec("bold")}>
          <strong>B</strong>
        </button>
        <button type="button" title="Italic" aria-label="Italic" className={`${toolbarBtn} italic`} onClick={() => exec("italic")}>
          I
        </button>
        <button type="button" title="Underline" aria-label="Underline" className={`${toolbarBtn} underline`} onClick={() => exec("underline")}>
          U
        </button>
        <select
          title="Font size"
          aria-label="Font size"
          data-testid={`${testIdPrefix}-font-size`}
          value={activeFontSize}
          className={selectCls}
          onChange={(e) => {
            const v = e.target.value;
            if (v) {
              exec("fontSize", v);
              setActiveFontSize(v);
            }
          }}
        >
          <option value="">Size</option>
          {SIZE_OPTIONS.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
        <select
          title="Font"
          aria-label="Font"
          data-testid={`${testIdPrefix}-font-family`}
          value={activeFontFamily}
          className={`${selectCls} max-w-28`}
          onChange={(e) => {
            const v = e.target.value;
            if (v) {
              exec("fontName", v);
              setActiveFontFamily(v);
            }
          }}
        >
          <option value="">Font</option>
          {FONTS.map((f) => (
            <option key={f.label} value={f.value}>{f.label}</option>
          ))}
        </select>
        {COLORS.map((c, i) => (
          <button
            key={`${c.value}-${i}`}
            type="button"
            title={c.value ? `Text color ${c.value}` : "Default color"}
            aria-label={c.value ? `Text color ${c.value}` : "Default color"}
            className={`${toolbarBtn} font-bold`}
            style={{ color: c.value || undefined }}
            onClick={() => exec("foreColor", c.value || "inherit")}
          >
            A
          </button>
        ))}
        <button
          type="button"
          title="Insert link"
          aria-label="Insert link"
          data-testid={`${testIdPrefix}-link`}
          className={toolbarBtn}
          onClick={addLink}
        >
          🔗
        </button>
        <button
          type="button"
          title="Table"
          aria-label="Insert table"
          data-testid={`${testIdPrefix}-table-btn`}
          className={toolbarBtn}
          onClick={insertTable}
        >
          ▦
        </button>
        <button type="button" title="Bulleted list" aria-label="Bulleted list" className={toolbarBtn} onClick={() => exec("insertUnorderedList")}>
          •≡
        </button>
        <button type="button" title="Numbered list" aria-label="Numbered list" className={toolbarBtn} onClick={() => exec("insertOrderedList")}>
          1≡
        </button>
        <button type="button" title="Align left" aria-label="Align left" className={toolbarBtn} onClick={() => exec("justifyLeft")}>
          ⇤
        </button>
        <button type="button" title="Align center" aria-label="Align center" className={toolbarBtn} onClick={() => exec("justifyCenter")}>
          ↔
        </button>
        <button type="button" title="Align right" aria-label="Align right" className={toolbarBtn} onClick={() => exec("justifyRight")}>
          ⇥
        </button>
        <button
          type="button"
          title="Horizontal rule"
          aria-label="Horizontal rule"
          data-testid={`${testIdPrefix}-hr`}
          className={`${toolbarBtn} w-6`}
          onClick={() => exec("insertHorizontalRule")}
        >
          ─
        </button>
        <button
          type="button"
          title="Clear formatting"
          aria-label="Clear formatting"
          className={`${toolbarBtn} ml-auto`}
          onClick={() => exec("removeFormat")}
        >
          Clear
        </button>
      </div>
      <div
        ref={ref}
        contentEditable
        suppressContentEditableWarning
        role="textbox"
        aria-multiline="true"
        aria-label="Rich text"
        data-testid={`${testIdPrefix}-editor`}
        onInput={emit}
        onBlur={emit}
        style={{ minHeight, fontFamily: baseFontFamily, fontSize: baseFontSize }}
        className="w-full overflow-y-auto bg-transparent border border-zinc-200 dark:border-white/10 rounded p-2 text-zinc-900 dark:text-zinc-100 focus:ring-0 outline-none [&_a]:underline [&_a]:text-indigo-500 dark:[&_a]:text-indigo-300"
      />
    </div>
  );
}
