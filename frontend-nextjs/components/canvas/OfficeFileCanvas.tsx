"use client";

/**
 * OfficeFileCanvas — editable canvas for real .xlsx / .docx / .pptx files.
 *
 * Co-editing model (#39): user edits commit to the file on disk via
 * POST /api/v1/office/sync-update, and the backend responds with (and
 * broadcasts) a fresh STRUCTURED content snapshot that this component
 * re-renders from — so user edits and agent edits converge on the same
 * file state.
 *
 * Incoming WS snapshots (agent edits, or echoes of the user's own commits)
 * are applied immediately UNLESS the user is mid-edit in a field, in which
 * case they're queued and an "agent updated this file" notice is shown.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Check, Globe, Loader2, Plus } from "lucide-react";
import { sanitizeHtml } from "@/lib/sanitize";
import { apiClient } from "@/lib/api";

export interface OfficeSheet {
    name: string;
    rows: any[][];
}

export interface OfficeSlide {
    slide_number: number;
    title: string;
    content: string;
}

export interface OfficeFileContent {
    format?: "xlsx" | "docx" | "pptx" | string;
    file_path?: string;
    office_file?: string; // key used by persisted Canvas rows
    html?: string;
    // xlsx
    active_sheet?: string;
    sheet_names?: string[];
    sheets?: OfficeSheet[];
    formulas?: Record<string, Record<string, string>>;
    // docx
    text?: string;
    paragraphs?: { index: number; text: string; style: string }[];
    // pptx
    slides?: OfficeSlide[];
}

interface OfficeFileCanvasProps {
    canvasId?: string;
    data: OfficeFileContent;
    /** Show the backend HTML render instead of the editable UI. */
    showPreview?: boolean;
    onDirtyChange?: (dirty: boolean) => void;
}

const colLetter = (idx: number): string => {
    let s = "";
    let n = idx;
    while (n >= 0) {
        s = String.fromCharCode(65 + (n % 26)) + s;
        n = Math.floor(n / 26) - 1;
    }
    return s;
};

export function OfficeFileCanvas({ canvasId, data, showPreview, onDirtyChange }: OfficeFileCanvasProps) {
    const filePath = data.file_path || data.office_file || "";
    const format = data.format || filePath.split(".").pop() || "";

    const [content, setContent] = useState<OfficeFileContent>(data);
    // Queued snapshot that arrived while the user was mid-edit.
    const [pending, setPending] = useState<OfficeFileContent | null>(null);
    const [agentNotice, setAgentNotice] = useState(false);
    const [savingKeys, setSavingKeys] = useState<Set<string>>(new Set());
    const [error, setError] = useState<string | null>(null);
    // Key of the field currently focused / locally edited but uncommitted.
    const focusedRef = useRef<string | null>(null);

    // Docx full-text editor state (commits as one `document` edit on blur/save).
    const [docText, setDocText] = useState<string>(data.text ?? "");
    const [docDirty, setDocDirty] = useState(false);

    // Active sheet for xlsx.
    const [activeSheet, setActiveSheet] = useState<string>(data.active_sheet || data.sheets?.[0]?.name || "");

    const dirty = docDirty;

    useEffect(() => {
        onDirtyChange?.(dirty);
    }, [dirty, onDirtyChange]);

    // Hydrate the structured snapshot when it's missing (e.g. the canvas
    // page loaded audit-style content with only html + file_path) by reading
    // the file through the office read endpoints.
    useEffect(() => {
        if (!filePath) return;
        const missing =
            format === "xlsx" ? !content.sheets?.length
            : format === "docx" ? content.text == null
            : format === "pptx" ? !content.slides?.length
            : false;
        if (!missing) return;

        let cancelled = false;
        (async () => {
            try {
                if (format === "xlsx") {
                    const res = await apiClient.get("/api/v1/office/excel", {
                        // No leading slash: "A1:Z500" reads the ACTIVE sheet —
                        // "/A1:Z500" would parse as a sheet named "A1:Z500".
                        params: { file_path: filePath, cell_path: "A1:Z500" },
                    });
                    const cells = res.data?.cells;
                    const name = res.data?.sheet_name || "Sheet1";
                    if (!cancelled && Array.isArray(cells)) {
                        // Trim the requested range to the used rectangle —
                        // otherwise the grid renders hundreds of empty rows.
                        const rows = cells.map((r: any[]) =>
                            (r || []).map((c: any) => (c?.value == null ? "" : c.value))
                        );
                        // Trim only TRAILING empty rows/cols — blank separator
                        // rows inside the data must survive (1:1 row mapping).
                        let lastUsed = -1;
                        let lastCol = -1;
                        rows.forEach((r: any[], i: number) => {
                            r.forEach((v: any, j: number) => { if (v !== "") { lastUsed = Math.max(lastUsed, i); lastCol = Math.max(lastCol, j); } });
                        });
                        const used = rows.slice(0, lastUsed + 1);
                        const colCount = lastCol + 1;
                        const trimmed = used.map((r: any[]) => Array.from({ length: colCount }, (_, i) => r[i] ?? ""));
                        setContent((prev) => ({
                            ...prev,
                            sheets: [{ name, rows: trimmed }],
                            active_sheet: name,
                        }));
                    }
                } else if (format === "docx") {
                    const res = await apiClient.get("/api/v1/office/word", {
                        params: { file_path: filePath },
                    });
                    const paras = res.data?.paragraphs || [];
                    if (!cancelled) {
                        // Rebuild the 1:1 line↔paragraph mapping the docx
                        // editor commits, using each paragraph's index.
                        const lines: string[] = [];
                        for (const p of paras) {
                            while (lines.length < p.index) lines.push("");
                            lines[p.index] = p.text;
                        }
                        setContent((prev) => ({ ...prev, text: lines.join("\n") }));
                        setDocText(lines.join("\n"));
                    }
                } else if (format === "pptx") {
                    const res = await apiClient.get("/api/v1/office/pptx", {
                        params: { file_path: filePath },
                    });
                    const rawSlides = res.data?.slides || [];
                    if (!cancelled) {
                        const slides = rawSlides.map((s: any, i: number) => {
                            const shapes = s.shapes || [];
                            const titleShape = shapes.find((sh: any) => /title/i.test(sh.name || "")) || shapes[0];
                            const body = shapes
                                .filter((sh: any) => sh !== titleShape && sh.type === "text")
                                .map((sh: any) => sh.text)
                                .join("\n");
                            return { slide_number: i + 1, title: titleShape?.text || "", content: body };
                        });
                        setContent((prev) => ({ ...prev, slides }));
                    }
                }
            } catch {
                // Hydration is best-effort — the html preview may still render.
            }
        })();
        return () => { cancelled = true; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [format, filePath]);

    // Apply incoming snapshots (new `data` prop from WS / present), unless the
    // user has uncommitted work in a field — then queue + notify instead.
    const applySnapshot = useCallback((snap: OfficeFileContent) => {
        setContent(snap);
        setDocText(snap.text ?? "");
        setDocDirty(false);
        if (snap.active_sheet) setActiveSheet(snap.active_sheet);
        else if (!snap.active_sheet && snap.sheets?.[0]) setActiveSheet((prev) => prev || snap.sheets![0].name);
    }, []);

    useEffect(() => {
        const midEdit = focusedRef.current !== null || docDirty;
        if (midEdit) {
            setPending(data);
            setAgentNotice(true);
        } else {
            applySnapshot(data);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [data]);

    const releaseFocus = () => {
        focusedRef.current = null;
        // Apply a queued agent snapshot once the user is out of edit mode.
        if (pending && !docDirty) {
            applySnapshot(pending);
            setPending(null);
            setAgentNotice(false);
        }
    };

    const commitEdit = useCallback(
        async (key: string, editType: string, editData: Record<string, unknown>) => {
            if (!filePath) {
                setError("No file bound to this canvas");
                return;
            }
            setError(null);
            setSavingKeys((prev) => new Set(prev).add(key));
            try {
                const res = await apiClient.post("/api/v1/office/sync-update", {
                    canvas_id: canvasId,
                    file_path: filePath,
                    user_id: "canvas_user", // server attributes from the auth token
                    edit_type: editType,
                    data: editData,
                });
                // The response carries a fresh structured snapshot — apply it
                // directly so the UI reflects the file (recalced formulas etc.).
                const snap = res.data?.content;
                if (snap?.format) {
                    applySnapshot({ ...snap, file_path: filePath, html: snap.html || content.html });
                    setPending(null);
                    setAgentNotice(false);
                }
            } catch (e: any) {
                setError(e?.response?.data?.detail || e?.message || "Failed to save edit");
            } finally {
                setSavingKeys((prev) => {
                    const next = new Set(prev);
                    next.delete(key);
                    return next;
                });
            }
        },
        [canvasId, filePath, content.html, applySnapshot]
    );

    const isSaving = (key: string) => savingKeys.has(key);

    // ─── Preview mode: sanitized backend HTML render ───
    if (showPreview && content.html) {
        return (
            <div className="p-6 overflow-auto h-full custom-scrollbar bg-white text-zinc-900">
                <div className="office-preview max-w-3xl mx-auto" dangerouslySetInnerHTML={{ __html: sanitizeHtml(content.html) }} />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full overflow-hidden bg-white dark:bg-[#020617]">
            {/* Status strip: save-in-flight / errors / agent-update notice */}
            <div className="flex items-center gap-3 px-3 py-1.5 border-b border-zinc-100 dark:border-white/5 bg-zinc-50/50 dark:bg-white/[0.02] shrink-0">
                <span className="text-[10px] text-zinc-400 font-mono truncate flex-1">{filePath}</span>
                {savingKeys.size > 0 && (
                    <span className="text-[10px] text-indigo-500 flex items-center gap-1">
                        <Loader2 className="h-3 w-3 animate-spin" /> Saving…
                    </span>
                )}
                {agentNotice && (
                    <button
                        onClick={() => {
                            if (pending) applySnapshot(pending);
                            setPending(null);
                            setAgentNotice(false);
                        }}
                        className="text-[10px] px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-900/50 hover:bg-amber-100 transition-colors"
                    >
                        Agent updated this file — click to load
                    </button>
                )}
                {!error && savingKeys.size === 0 && !agentNotice && (
                    <span className="text-[10px] text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-medium">
                        <Check className="h-3 w-3" /> Synced to file
                    </span>
                )}
                {error && (
                    <span className="text-[10px] text-red-500 truncate max-w-[50%]" title={error}>
                        {error}
                    </span>
                )}
            </div>

            <div className="flex-1 overflow-auto custom-scrollbar">
                {format === "xlsx" && (
                    <ExcelEditor
                        content={content}
                        activeSheet={activeSheet}
                        setActiveSheet={setActiveSheet}
                        filePath={filePath}
                        commitEdit={commitEdit}
                        isSaving={isSaving}
                        onFocusKey={(k) => (focusedRef.current = k)}
                        onBlur={releaseFocus}
                    />
                )}
                {format === "docx" && (
                    <DocxEditor
                        text={docText}
                        setText={(t) => {
                            setDocText(t);
                            setDocDirty(true);
                        }}
                        commit={() => {
                            if (docDirty) commitEdit("docx:all", "document", { content: docText });
                        }}
                        onFocusKey={() => (focusedRef.current = "docx:all")}
                        onBlur={releaseFocus}
                    />
                )}
                {format === "pptx" && (
                    <PptxEditor
                        slides={content.slides || []}
                        commitEdit={commitEdit}
                        isSaving={isSaving}
                        onFocusKey={(k) => (focusedRef.current = k)}
                        onBlur={releaseFocus}
                    />
                )}
                {!["xlsx", "docx", "pptx"].includes(format) && (
                    <div className="p-6 text-sm text-zinc-500">Unsupported office format: {format}</div>
                )}
            </div>
        </div>
    );
}

// ────────────────────────────────────────────────────────────────────────
// Excel: editable grid backed by the real workbook
// ────────────────────────────────────────────────────────────────────────

function ExcelEditor({
    content,
    activeSheet,
    setActiveSheet,
    filePath,
    commitEdit,
    isSaving,
    onFocusKey,
    onBlur,
}: {
    content: OfficeFileContent;
    activeSheet: string;
    setActiveSheet: (s: string) => void;
    filePath: string;
    commitEdit: (key: string, editType: string, data: Record<string, unknown>) => Promise<void>;
    isSaving: (key: string) => boolean;
    onFocusKey: (k: string) => void;
    onBlur: () => void;
}) {
    const sheet = useMemo(
        () => content.sheets?.find((s) => s.name === activeSheet) || content.sheets?.[0],
        [content.sheets, activeSheet]
    );
    const rows = sheet?.rows || [];
    // Pad ragged rows so the grid is rectangular.
    const colCount = rows.reduce((m, r) => Math.max(m, r?.length || 0), 0);
    const padded = rows.map((r) => Array.from({ length: colCount }, (_, i) => r?.[i] ?? ""));

    const commitCell = (rowIdx: number, colIdx: number, raw: string) => {
        const original = padded[rowIdx]?.[colIdx];
        const originalStr = original == null ? "" : String(original);
        if (raw === originalStr) return;
        const cellPath = `/${sheet?.name}/${colLetter(colIdx)}${rowIdx + 1}`;
        commitEdit(`cell:${cellPath}`, "cell", {
            cell_path: cellPath,
            value: raw,
            is_formula: raw.startsWith("="),
        });
    };

    const addRow = async () => {
        if (!sheet) return;
        try {
            await apiClient.post(
                `/api/v1/office/excel/insert-rows?file_path=${encodeURIComponent(filePath)}&sheet_name=${encodeURIComponent(sheet.name)}&row=${rows.length + 1}&count=1`
            );
            // insert-rows doesn't return a snapshot — re-present the file so a
            // fresh structured snapshot is broadcast back to this canvas.
            await apiClient.post("/api/v1/office/present", { file_path: filePath, user_id: "canvas_user" });
        } catch {
            // Error surfaces via the next commit; keep the UI responsive.
        }
    };

    return (
        <div className="p-1">
            {/* Sheet tabs */}
            {(content.sheet_names?.length || 0) > 1 && (
                <div className="flex gap-1 mb-1 border-b border-zinc-100 dark:border-white/5">
                    {content.sheet_names!.map((name) => (
                        <button
                            key={name}
                            onClick={() => setActiveSheet(name)}
                            className={`px-3 py-1 text-[11px] rounded-t transition-colors ${
                                name === activeSheet
                                    ? "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-b-2 border-indigo-500"
                                    : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
                            }`}
                        >
                            {name}
                        </button>
                    ))}
                </div>
            )}

            <table className="w-full border-collapse text-[12px] text-zinc-900 dark:text-zinc-300">
                <thead>
                    <tr>
                        <th className="w-8 border border-zinc-100 dark:border-white/10 bg-zinc-50 dark:bg-white/5 p-1 text-[10px] text-zinc-400 font-mono">#</th>
                        {Array.from({ length: colCount }, (_, i) => (
                            <th key={i} className="border border-zinc-100 dark:border-white/10 bg-zinc-50 dark:bg-white/5 p-1 font-bold uppercase tracking-wider text-[10px] text-zinc-400">
                                {colLetter(i)}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {padded.map((row, rowIdx) => (
                        <tr key={rowIdx}>
                            <td className="border border-zinc-100 dark:border-white/10 bg-zinc-50 dark:bg-white/5 p-1 text-center text-[10px] text-zinc-400 font-mono italic">
                                {rowIdx + 1}
                            </td>
                            {row.map((cell, colIdx) => {
                                const cellPath = `/${sheet?.name}/${colLetter(colIdx)}${rowIdx + 1}`;
                                const isFormulaCell =
                                    typeof cell === "string" && cell.startsWith("=") &&
                                    content.formulas?.[sheet?.name || ""]?.[`${colLetter(colIdx)}${rowIdx + 1}`];
                                return (
                                    <td
                                        key={colIdx}
                                        className={`border border-zinc-100 dark:border-white/10 p-1 min-w-[80px] hover:bg-zinc-50 dark:hover:bg-black/5 focus-within:bg-indigo-500/10 focus-within:border-indigo-500/50 transition-colors ${
                                            isFormulaCell ? "bg-emerald-500/5" : ""
                                        }`}
                                        title={isFormulaCell ? "Formula cell" : undefined}
                                    >
                                        <input
                                            type="text"
                                            defaultValue={cell == null ? "" : String(cell)}
                                            key={`${cellPath}:${String(cell)}`}
                                            onFocus={() => onFocusKey(cellPath)}
                                            onBlur={(e) => {
                                                commitCell(rowIdx, colIdx, e.target.value);
                                                onBlur();
                                            }}
                                            className="w-full bg-transparent border-none p-0 focus:ring-0 outline-none"
                                        />
                                        {isSaving(`cell:${cellPath}`) && (
                                            <Loader2 className="inline h-2.5 w-2.5 animate-spin text-indigo-400 ml-1" />
                                        )}
                                    </td>
                                );
                            })}
                        </tr>
                    ))}
                    <tr>
                        <td colSpan={colCount + 1} className="p-1 border border-zinc-100 dark:border-white/5 text-center">
                            <button
                                onClick={addRow}
                                className="text-[10px] text-zinc-400 hover:text-indigo-600 uppercase font-bold tracking-widest transition-colors py-1 w-full flex items-center justify-center gap-1"
                            >
                                <Plus className="h-3 w-3" /> Add Row
                            </button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    );
}

// ────────────────────────────────────────────────────────────────────────
// Word: paragraph-preserving text editor
// ────────────────────────────────────────────────────────────────────────

function DocxEditor({
    text,
    setText,
    commit,
    onFocusKey,
    onBlur,
}: {
    text: string;
    setText: (t: string) => void;
    commit: () => void;
    onFocusKey: () => void;
    onBlur: () => void;
}) {
    return (
        <div className="h-full flex flex-col">
            <div className="px-4 pt-2 text-[10px] text-zinc-400">
                One line = one paragraph. Styles, tables and images in the document are preserved on save.
            </div>
            <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                onFocus={onFocusKey}
                onBlur={() => {
                    commit();
                    onBlur();
                }}
                spellCheck={false}
                className="flex-1 m-3 p-4 rounded-lg border border-zinc-100 dark:border-white/10 bg-transparent text-sm text-zinc-900 dark:text-zinc-200 font-mono leading-relaxed resize-none focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
            />
        </div>
    );
}

// ────────────────────────────────────────────────────────────────────────
// PowerPoint: slide cards with editable title/content
// ────────────────────────────────────────────────────────────────────────

function PptxEditor({
    slides,
    commitEdit,
    isSaving,
    onFocusKey,
    onBlur,
}: {
    slides: OfficeSlide[];
    commitEdit: (key: string, editType: string, data: Record<string, unknown>) => Promise<void>;
    isSaving: (key: string) => boolean;
    onFocusKey: (k: string) => void;
    onBlur: () => void;
}) {
    const commitSlide = (slide: OfficeSlide, field: "title" | "content", raw: string) => {
        if (raw === (slide[field] || "")) return;
        commitEdit(`slide:${slide.slide_number}`, "slide", {
            slide_number: slide.slide_number,
            title: field === "title" ? raw : slide.title,
            content: field === "content" ? raw : slide.content,
        });
    };

    return (
        <div className="p-4 space-y-4">
            {slides.map((slide) => (
                <div
                    key={slide.slide_number}
                    className="rounded-xl border border-zinc-200 dark:border-white/10 bg-zinc-50/50 dark:bg-white/[0.02] p-4 shadow-sm"
                >
                    <div className="flex items-center gap-2 mb-3">
                        <span className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider">Slide {slide.slide_number}</span>
                        {isSaving(`slide:${slide.slide_number}`) && <Loader2 className="h-3 w-3 animate-spin text-indigo-400" />}
                    </div>
                    <input
                        type="text"
                        defaultValue={slide.title}
                        key={`t:${slide.slide_number}:${slide.title}`}
                        onFocus={() => onFocusKey(`slide:${slide.slide_number}`)}
                        onBlur={(e) => {
                            commitSlide(slide, "title", e.target.value);
                            onBlur();
                        }}
                        placeholder="Slide title"
                        className="w-full mb-2 bg-transparent border-b border-zinc-200 dark:border-white/10 focus:border-indigo-500/50 text-sm font-semibold text-zinc-900 dark:text-zinc-100 p-1 focus:outline-none"
                    />
                    <textarea
                        defaultValue={slide.content}
                        key={`c:${slide.slide_number}:${slide.content}`}
                        onFocus={() => onFocusKey(`slide:${slide.slide_number}`)}
                        onBlur={(e) => {
                            commitSlide(slide, "content", e.target.value);
                            onBlur();
                        }}
                        placeholder="Slide content"
                        rows={4}
                        className="w-full bg-transparent border border-zinc-100 dark:border-white/10 rounded-lg p-2 text-[13px] text-zinc-700 dark:text-zinc-300 focus:outline-none focus:ring-1 focus:ring-indigo-500/50 resize-y"
                    />
                </div>
            ))}
            <button
                onClick={() => commitEdit(`slide:add`, "add_slide", { title: "New Slide", content: "" })}
                className="w-full py-2 text-[10px] text-zinc-400 hover:text-indigo-600 uppercase font-bold tracking-widest transition-colors border border-dashed border-zinc-200 dark:border-white/10 rounded-lg flex items-center justify-center gap-1"
            >
                <Plus className="h-3 w-3" /> Add Slide
            </button>
        </div>
    );
}
