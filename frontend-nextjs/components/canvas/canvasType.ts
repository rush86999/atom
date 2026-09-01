/**
 * Manual canvas type switching — the frontend half of a two-part override.
 *
 * The chat→canvas classifier (`backend/core/chat_draft_classifier.py`) picks a
 * canvas type structurally and can guess wrong (a document that opens as an
 * email composer, code that lands in a doc editor). The backend half is the
 * `retype=true` flag on PUT /api/canvas/{id}: it appends an audit row with
 * `type_pinned`, and read-time email coercion respects the pin so the manual
 * choice survives every later read/save. This module decides which types a
 * user may switch between, converts the current content into the target
 * type's shape (no content is lost — worst case it lands as markdown text),
 * and persists the retype.
 */

export const CANVAS_TYPE_OPTIONS = [
    { value: "document", label: "Document" },
    { value: "email", label: "Email" },
    { value: "markdown", label: "Markdown" },
    { value: "code", label: "Code" },
    { value: "sheet", label: "Sheet" },
] as const;

export type SwitchableCanvasType = (typeof CANVAS_TYPE_OPTIONS)[number]["value"];

/**
 * ALL canvas apps, in recommended-first order — this drives the at-open
 * picker on "Open latest draft in canvas": the top entries are the apps a
 * chat draft almost always wants (document, email), and the specialized
 * apps follow for when the user disagrees with the classifier. Office apps
 * are intentionally absent: they require a real generated FILE, which the
 * backend's auto path creates only when the draft IS office-shaped.
 */
export const CANVAS_APP_TYPE_OPTIONS = [
    { value: "document", label: "Document" },
    { value: "email", label: "Email" },
    { value: "markdown", label: "Markdown" },
    { value: "code", label: "Code" },
    { value: "sheet", label: "Sheet" },
    { value: "status_panel", label: "Status panel" },
    { value: "form", label: "Form" },
    { value: "line_chart", label: "Line chart" },
    { value: "bar_chart", label: "Bar chart" },
    { value: "pie_chart", label: "Pie chart" },
    { value: "terminal", label: "Terminal" },
    { value: "orchestration", label: "Orchestration" },
    // Office apps DO appear: forcing them generates a REAL file via the
    // backend office engine (openpyxl/python-pptx/python-docx, LibreOffice
    // headless when installed for formula recalc). A draft without the
    // matching shape (table/slides/doc) falls back to a document with a
    // warning instead of a broken office component.
    { value: "office_word", label: "Word (docx)" },
    { value: "office_excel", label: "Excel (xlsx)" },
    { value: "office_pptx", label: "PowerPoint (pptx)" },
] as const;

export type CanvasAppType = (typeof CANVAS_APP_TYPE_OPTIONS)[number]["value"];

export const CANVAS_APP_TYPE_VALUES: readonly string[] =
    CANVAS_APP_TYPE_OPTIONS.map((o) => o.value);

const SWITCHABLE_VALUES = new Set<string>(CANVAS_TYPE_OPTIONS.map((o) => o.value));

// Doc-like legacy canvas_type values ("docs", "generic", "doc") also render
// as text editors — the switcher appears for them too.
const DOC_LIKE = new Set(["docs", "generic", "doc", "terminal"]);

/**
 * Map backend/registry canvas_type names onto the component names the canvas
 * hosts render. Two vocabularies exist: the AI-accessibility registry and the
 * audit trail speak type names ("sheets", "docs", "coding" — see the
 * `type:` values in useCanvasStateRegistration), while CanvasContent's switch
 * handles component names ("sheet", "document", "code"). Without this, a
 * sheet canvas updated by the co-editor renders as a raw-JSON dump and its
 * per-type state seeding (sheet rows, email metadata) is skipped. Charts,
 * forms, office_* and email pass through unchanged.
 */
export function normalizeCanvasComponent(component?: string | null): string {
    const raw = (component || "").trim().toLowerCase();
    if (!raw) return "markdown";
    if (raw === "sheets" || raw === "spreadsheet") return "sheet";
    if (raw === "docs" || raw === "doc") return "document";
    if (raw === "coding") return "code";
    if (raw === "generic") return "markdown";
    return raw;
}

/**
 * Whether the type badge offers a manual switch. Specialized canvases
 * (real office files, charts, forms, snapshots) carry structured payloads
 * that can't be hand-converted to another type.
 */
export function isTypeSwitchable(component?: string | null): boolean {
    if (!component) return false;
    return SWITCHABLE_VALUES.has(component) || DOC_LIKE.has(component);
}

export interface CanvasTypeSource {
    component: string;
    /** Raw canvas payload (WS present / audit-trail read). */
    data: any;
    /** Current editable text — composer body for email, editor content otherwise. */
    text: string;
    email?: { to?: string; cc?: string; subject?: string };
    sheet?: any[][];
    title?: string;
}

export interface CanvasTypeConversion {
    component: SwitchableCanvasType;
    /** Payload for the target renderer (matches what present/update carry). */
    data: any;
    /** Plain-text body of the converted canvas. */
    text: string;
    email: { to: string; cc: string; subject: string };
    sheet: any[][];
    /** Body for PUT /api/canvas/{id} — the shape read_canvas stores/returns. */
    payload: any;
}

// ── markdown table ⇄ rows (same shape the backend's draft classifier uses) ──

const TABLE_SEPARATOR = /^\s*\|?[\s:-]*-{3,}[\s:|-]*\|[\s:|-]*$/;

function rowsToMarkdown(rows: any[][]): string {
    if (!rows.length) return "";
    const line = (cells: any[]) => `| ${cells.map((c) => String(c ?? "")).join(" | ")} |`;
    const [head, ...body] = rows;
    const separator = `| ${head.map(() => "---").join(" | ")} |`;
    return [line(head), separator, ...body.map(line)].join("\n");
}

function markdownToRows(text: string): any[][] | null {
    const lines = (text || "").split(/\r?\n/);
    for (let i = 0; i < lines.length - 1; i++) {
        if (lines[i].includes("|") && TABLE_SEPARATOR.test(lines[i + 1])) {
            const parse = (line: string) =>
                line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
            const rows = [parse(lines[i])];
            for (const follow of lines.slice(i + 2)) {
                if (!follow.includes("|") || !follow.trim()) break;
                rows.push(parse(follow));
            }
            if (rows.length >= 2) return rows;
        }
    }
    return null;
}

/** Best-effort plain text of the current canvas, whatever shape it holds. */
function extractText(src: CanvasTypeSource): string {
    if (src.component === "email") return src.text || "";
    const data = src.data;
    if (typeof data === "string") return data;
    if (Array.isArray(data)) return rowsToMarkdown(data);
    if (typeof data?.content === "string") return data.content;
    if (typeof data?.body === "string") return data.body;
    if (data == null) return src.text || "";
    return JSON.stringify(data, null, 2);
}

/**
 * Convert the current canvas into `target`. Text is preserved verbatim
 * across the text-like types; sheets convert to/from markdown tables; the
 * email composer's To/Cc/Subject ride along when the source is an email.
 */
export function switchCanvasType(target: SwitchableCanvasType, src: CanvasTypeSource): CanvasTypeConversion {
    const text = extractText(src);
    const email = {
        to: src.email?.to || "",
        cc: src.email?.cc || "",
        subject: src.email?.subject || "",
    };
    const sheet = Array.isArray(src.sheet) && src.sheet.length ? src.sheet : [];

    switch (target) {
        case "email": {
            const data = { to: email.to, cc: email.cc, subject: email.subject || src.title || "", body: text };
            return { component: target, data, text, email: { ...email, subject: data.subject }, sheet, payload: data };
        }
        case "sheet": {
            const rows = sheet.length ? sheet : (markdownToRows(text) || text.split(/\r?\n/).filter((l) => l.trim()).slice(0, 50).map((l) => [l]));
            const data = rows.length ? rows : [[""]];
            return { component: target, data, text: rowsToMarkdown(data), email, sheet: data, payload: data };
        }
        case "code":
        case "markdown":
            return { component: target, data: text, text, email, sheet, payload: text };
        case "document":
        default: {
            // Coming from the email composer, the subject is real content —
            // keep it as the document's heading instead of dropping it.
            const docText = src.component === "email" && email.subject && !text.startsWith("#")
                ? `# ${email.subject}\n\n${text}`
                : text;
            return { component: "document", data: docText, text: docText, email, sheet, payload: docText };
        }
    }
}

/** Persist a manual retype (best-effort — the canvas stays usable offline). */
export async function persistCanvasTypeSwitch(
    canvasId: string,
    conversion: CanvasTypeConversion,
    title?: string,
): Promise<void> {
    const { apiClient } = await import("@/lib/api");
    const params = new URLSearchParams({ canvas_type: conversion.component, retype: "true" });
    if (title) params.set("title", title);
    await apiClient.put(`/api/canvas/${canvasId}?${params.toString()}`, conversion.payload);
}
