"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
    AlertCircle,
    ArrowDown,
    ArrowUp,
    FileOutput,
    Loader2,
    RotateCcw,
    RotateCw,
    Save,
    Trash2,
    Undo2,
} from "lucide-react";
import {
    attachPdfToEmail,
    applyPageOps,
    archiveToOnedrive,
    extractText,
    fetchPdfBytes,
    flattenForm,
    getFormFields,
    mergePdfUpload,
    redactText,
    sendToDocuSign,
    setFormFields,
    stampSignature,
    transitionLifecycle,
    unwrapPdfState,
    type PdfCanvasState,
    type PdfLifecycleTransition,
    type PdfPageSpec,
} from "@/lib/pdf-canvas-api";
import { CheckCircle2, Eraser, Eye, FileSignature, FileText, RotateCcw as Reopen, Archive, CloudUpload } from "lucide-react";
import { pdfWorkerSrc } from "@/lib/pdf-worker-src";

/**
 * PDF canvas — the "real file" renderer for canvas_type="pdf", following the
 * OfficeFileCanvas pattern: the panel renders from `data` (the audit-trail
 * state) plus the bytes streamed from /api/canvas/pdf/{id}/file, and every
 * mutation commits server-side through pdf-canvas-api (which appends an
 * audited version and broadcasts canvas:update — this component then reloads
 * the new version's bytes).
 *
 * Editing model: pdf.js renders the COMMITTED bytes; the user's pending page
 * map (reorder/delete/rotate) is a local working copy turned into a real,
 * versioned save by the Save button. Absolute rotations + base_hash keep the
 * save idempotent and conflict-safe against co-editing agents.
 */

type PdfjsDoc = { numPages: number; getPage: (n: number) => Promise<any> };

export function PdfFileCanvas({
    canvasId,
    data,
}: {
    canvasId?: string;
    data: any;
}) {
    const serverState = useMemo<PdfCanvasState | null>(() => unwrapPdfState(data), [data]);
    const [doc, setDoc] = useState<PdfjsDoc | null>(null);
    const [pageMap, setPageMap] = useState<PdfPageSpec[]>([]);
    const [history, setHistory] = useState<PdfPageSpec[][]>([]);
    const [bytesHash, setBytesHash] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<{ text: string; href?: string } | null>(null);
    const [saving, setSaving] = useState(false);
    const [attaching, setAttaching] = useState(false);
    const [transitioning, setTransitioning] = useState(false);
    const [flattenOnAttach, setFlattenOnAttach] = useState(false);
    const [mode, setMode] = useState<"pages" | "text" | "form">("pages");
    const [textPages, setTextPages] = useState<{ page: number; text: string }[] | null>(null);
    const [textOcr, setTextOcr] = useState(false);
    const [formFieldsState, setFormFieldsState] = useState<Record<string, string>>({});
    const [formLoaded, setFormLoaded] = useState(false);
    const [signPanel, setSignPanel] = useState(false);
    const [signLines, setSignLines] = useState("");
    const [signLabel, setSignLabel] = useState(`Signed ${new Date().toISOString().slice(0, 10)} via ATOM`);
    const [redactPanel, setRedactPanel] = useState(false);
    const [redactTargets, setRedactTargets] = useState("");
    const [dsPanel, setDsPanel] = useState(false);
    const [dsEmail, setDsEmail] = useState("");
    const [dsName, setDsName] = useState("");
    const [busyOp, setBusyOp] = useState<string | null>(null);
    const mergeInputRef = useRef<HTMLInputElement>(null);
    const renderTokenRef = useRef(0);

    const dirty = useMemo(
        () =>
            pageMap.length > 0 &&
            (pageMap.length !== (serverState?.file.page_count ?? 0) ||
                pageMap.some((p, i) => p.src_index !== i || p.rotation !== 0)),
        [pageMap, serverState]
    );

    // Load (or reload after a committed version) the bytes and rebase the
    // working page map onto them.
    const loadBytes = useCallback(
        async (hash: string) => {
            if (!canvasId) return;
            setLoading(true);
            setError(null);
            try {
                const blob = await fetchPdfBytes(canvasId, hash);
                const pdfjs = await import("pdfjs-dist");
                // Isolated in lib/pdf-worker-src (webpack asset); if worker
                // setup fails, pdf.js degrades to a main-thread fake worker.
                try {
                    pdfjs.GlobalWorkerOptions.workerSrc = pdfWorkerSrc();
                } catch {
                    /* fake-worker fallback still renders */
                }
                const buf = await blob.arrayBuffer();
                const loaded = await pdfjs.getDocument({ data: buf }).promise;
                renderTokenRef.current += 1;
                setDoc(loaded);
                setBytesHash(hash);
                setPageMap(Array.from({ length: loaded.numPages }, (_, i) => ({ src_index: i, rotation: 0 })));
                setHistory([]);
            } catch (e: any) {
                setError(describeError(e, "Could not load the PDF file"));
            } finally {
                setLoading(false);
            }
        },
        [canvasId]
    );

    useEffect(() => {
        const hash = serverState?.file?.hash;
        if (canvasId && hash && hash !== bytesHash && !dirty) {
            void loadBytes(hash);
        }
        if (!canvasId || !hash) setLoading(false);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [canvasId, serverState?.file?.hash]);

    // ── pending page-map ops (local until Save) ─────────────────────────
    const mutate = (fn: (prev: PdfPageSpec[]) => PdfPageSpec[]) => {
        setPageMap((prev) => {
            setHistory((h) => [...h.slice(-19), prev]);
            return fn(prev);
        });
    };

    const rotatePage = (i: number, delta: number) =>
        mutate((prev) => prev.map((p, j) => (j === i ? { ...p, rotation: (p.rotation + delta + 360) % 360 } : p)));
    const deletePage = (i: number) =>
        mutate((prev) => (prev.length <= 1 ? prev : prev.filter((_, j) => j !== i)));
    const movePage = (i: number, dir: -1 | 1) =>
        mutate((prev) => {
            const j = i + dir;
            if (j < 0 || j >= prev.length) return prev;
            const next = [...prev];
            [next[i], next[j]] = [next[j], next[i]];
            return next;
        });
    const undo = () =>
        setHistory((h) => {
            if (!h.length) return h;
            setPageMap(h[h.length - 1]);
            return h.slice(0, -1);
        });

    const save = async () => {
        if (!canvasId || !serverState || !dirty) return;
        setSaving(true);
        setError(null);
        try {
            const res = await applyPageOps(canvasId, pageMap, serverState.file.hash);
            // The WS canvas:update also refreshes `data`; load immediately so
            // the viewer never shows stale bytes between frames.
            await loadBytes(res.state.file.hash);
            setNotice({ text: `Saved — version ${res.state.file.hash.slice(0, 8)} committed` });
        } catch (e: any) {
            setError(describeError(e, "Save failed"));
        } finally {
            setSaving(false);
        }
    };

    const mergeFile = async (file: File) => {
        if (!canvasId) return;
        setSaving(true);
        setError(null);
        try {
            const res = await mergePdfUpload(canvasId, file);
            await loadBytes(res.state.file.hash);
            setNotice({ text: `Merged ${file.name} — ${res.state.file.page_count} pages total` });
        } catch (e: any) {
            setError(describeError(e, "Merge failed"));
        } finally {
            setSaving(false);
        }
    };

    const attach = async () => {
        if (!canvasId || !serverState) return;
        setAttaching(true);
        setError(null);
        try {
            const res = await attachPdfToEmail(canvasId, flattenOnAttach);
            setNotice({
                text: (res.flattened ? "Attached a flattened copy — " : "Attached — ")
                    + (res.created_email_canvas ? `new email draft (${res.filename})` : "existing email draft"),
                href: `/canvas/${res.email_canvas_id}`,
            });
        } catch (e: any) {
            setError(describeError(e, "Attach to email failed"));
        } finally {
            setAttaching(false);
        }
    };

    // Human lifecycle moves (the state machine lives server-side; agent
    // callers go through the maturity-gated tools and propose instead).
    const runLifecycle = async (t: PdfLifecycleTransition, label: string) => {
        if (!canvasId) return;
        setTransitioning(true);
        setError(null);
        try {
            await transitionLifecycle(canvasId, t);
            setNotice({ text: label });
            // The server broadcasts canvas:update — `data` (and the chip)
            // refresh from that frame; no byte reload needed (hash unchanged).
        } catch (e: any) {
            setError(describeError(e, "Lifecycle update failed"));
        } finally {
            setTransitioning(false);
        }
    };

    // ── P3/P4 panels ────────────────────────────────────────────────────
    const openTextPane = async (ocr = false) => {
        if (!canvasId) return;
        setTextOcr(ocr);
        setBusyOp("text");
        setError(null);
        try {
            const res = await extractText(canvasId, ocr);
            setTextPages(res.pages || []);
        } catch (e: any) {
            setError(describeError(e, "Text extraction failed"));
        } finally {
            setBusyOp(null);
        }
    };

    const openFormPane = async () => {
        if (!canvasId) return;
        setBusyOp("form");
        setError(null);
        try {
            const res = await getFormFields(canvasId);
            const vals: Record<string, string> = {};
            for (const [name, f] of Object.entries(res.fields || {})) vals[name] = f.value || "";
            setFormFieldsState(vals);
            setFormLoaded(true);
        } catch (e: any) {
            setError(describeError(e, "Could not read form fields"));
        } finally {
            setBusyOp(null);
        }
    };

    const saveForm = async () => {
        if (!canvasId || !serverState) return;
        setSaving(true);
        setError(null);
        try {
            const res = await setFormFields(canvasId, formFieldsState || {}, serverState.file.hash);
            await loadBytes(res.state.file.hash);
            setNotice({ text: "Form values saved as a new version" });
        } catch (e: any) {
            setError(describeError(e, "Form fill failed"));
        } finally {
            setSaving(false);
        }
    };

    const doFlatten = async () => {
        if (!canvasId) return;
        setSaving(true);
        setError(null);
        try {
            const res = await flattenForm(canvasId);
            await loadBytes(res.state.file.hash);
            setNotice({ text: "Flattened — form values are now part of the page content" });
        } catch (e: any) {
            setError(describeError(e, "Flatten failed"));
        } finally {
            setSaving(false);
        }
    };

    const doRedact = async () => {
        if (!canvasId || !serverState) return;
        const targets = redactTargets.split("\n").map((s) => s.trim()).filter(Boolean);
        if (!targets.length) return;
        setSaving(true);
        setError(null);
        try {
            // locate the pages client-side: the backend refuses items whose
            // text is absent from the named page
            const ext = await extractText(canvasId);
            const items: { page: number; text: string }[] = [];
            const missing: string[] = [];
            for (const t of targets) {
                const pages = (ext.pages || []).filter((p) => p.text.includes(t)).map((p) => p.page);
                if (!pages.length) missing.push(t);
                else pages.forEach((p) => items.push({ page: p, text: t }));
            }
            if (missing.length) {
                setError(`Not found in the document: ${missing.join(", ")}`);
                return;
            }
            const res = await redactText(canvasId, items);
            await loadBytes(res.state.file.hash);
            setNotice({ text: `Redacted ${items.length} occurrence(s) — content removed and verified` });
        } catch (e: any) {
            setError(describeError(e, "Redaction failed"));
        } finally {
            setSaving(false);
        }
    };

    const doSign = async () => {
        if (!canvasId) return;
        const lines = signLines.split("\n").map((s) => s.trim()).filter(Boolean);
        if (!lines.length) {
            setError("Enter a signature first");
            return;
        }
        setSaving(true);
        setError(null);
        try {
            const res = await stampSignature(canvasId, lines, signLabel);
            await loadBytes(res.state.file.hash);
            setNotice({ text: "Signature stamped as a new version" });
            setSignPanel(false);
        } catch (e: any) {
            setError(describeError(e, "Signing failed"));
        } finally {
            setSaving(false);
        }
    };

    const doArchive = async () => {
        if (!canvasId) return;
        setBusyOp("archive");
        setError(null);
        try {
            const res = await archiveToOnedrive(canvasId);
            setNotice({ text: `Archived to OneDrive (${res.filename || serverState?.file.filename})` });
        } catch (e: any) {
            setError(describeError(e, "Archive failed"));
        } finally {
            setBusyOp(null);
        }
    };

    const doDocuSign = async () => {
        if (!canvasId || !dsEmail.trim()) {
            setError("Signer email is required");
            return;
        }
        setSaving(true);
        setError(null);
        try {
            const res = await sendToDocuSign(canvasId, dsEmail.trim(), dsName.trim() || dsEmail.trim());
            setNotice({ text: `DocuSign envelope ${res.envelope_id.slice(0, 8)} sent to ${dsEmail.trim()}` });
            setDsPanel(false);
        } catch (e: any) {
            setError(describeError(e, "DocuSign send failed"));
        } finally {
            setSaving(false);
        }
    };

    // Render every page in the working map at fit-to-container width.
    useEffect(() => {
        if (!doc) return;
        const token = renderTokenRef.current;
        let cancelled = false;
        (async () => {
            for (let i = 0; i < pageMap.length; i++) {
                const canvasEl = document.querySelector(
                    `canvas[data-pdf-page-slot="${canvasId}:${i}"]`
                ) as HTMLCanvasElement | null;
                if (!canvasEl || cancelled) continue;
                try {
                    const page = await doc.getPage(pageMap[i].src_index + 1);
                    const base = page.getViewport({ scale: 1 });
                    const containerWidth = canvasEl.parentElement?.clientWidth || 640;
                    const scale = Math.max(0.2, Math.min(2, (containerWidth - 8) / base.width));
                    const viewport = page.getViewport({ scale, rotation: pageMap[i].rotation });
                    canvasEl.width = Math.floor(viewport.width);
                    canvasEl.height = Math.floor(viewport.height);
                    const ctx = canvasEl.getContext("2d");
                    if (!ctx) continue;
                    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
                    await page.render({ canvasContext: ctx, viewport }).promise;
                } catch {
                    /* one bad page must not kill the rest */
                }
                if (renderTokenRef.current !== token) return;
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [doc, pageMap, canvasId]);

    if (!canvasId || !serverState) {
        return (
            <div className="p-4 text-sm text-zinc-500" data-testid="canvas-pdf-missing">
                This PDF canvas has no file state.
            </div>
        );
    }

    const lifecycle = serverState.lifecycle?.state || "drafting";
    const mutable = lifecycle === "drafting" || lifecycle === "in_review";

    return (
        <div className="flex flex-col h-full bg-zinc-50 dark:bg-black/30" data-testid="canvas-pdf-root">
            {/* toolbar */}
            <div className="flex flex-wrap items-center gap-2 px-3 py-2 border-b bg-white dark:bg-slate-900/50 text-xs">
                <span className="font-mono text-[10px] text-zinc-500 truncate max-w-[220px]" title={serverState.file.filename}>
                    {serverState.file.filename}
                </span>
                <span
                    className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-white/10 text-zinc-500 uppercase"
                    data-testid="canvas-pdf-lifecycle"
                >
                    {lifecycle}
                </span>
                {!mutable && (
                    <span className="text-[10px] text-amber-600 dark:text-amber-400" title="Approved documents are immutable — reopen to edit">
                        🔒
                    </span>
                )}
                <span className="text-[10px] text-zinc-400">
                    {pageMap.length || serverState.file.page_count} pages
                </span>
                {/* lifecycle moves (human authority; agent approvals propose) */}
                {lifecycle === "drafting" && (
                    <button
                        onClick={() => runLifecycle("submit_review", "Submitted for review")}
                        disabled={transitioning}
                        className="flex items-center gap-1 px-2 py-1 rounded border hover:bg-zinc-100 dark:hover:bg-white/10 disabled:opacity-40"
                        data-testid="canvas-pdf-submit-review"
                    >
                        <Eye className="h-3 w-3" /> Submit for review
                    </button>
                )}
                {(lifecycle === "drafting" || lifecycle === "in_review") && (
                    <button
                        onClick={() => runLifecycle("approve", "Approved — content is now immutable")}
                        disabled={transitioning}
                        className="flex items-center gap-1 px-2 py-1 rounded border border-emerald-500 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 disabled:opacity-40"
                        data-testid="canvas-pdf-approve"
                    >
                        <CheckCircle2 className="h-3 w-3" /> Approve
                    </button>
                )}
                {lifecycle === "approved" && (
                    <button
                        onClick={() => runLifecycle("reopen", "Reopened for editing")}
                        disabled={transitioning}
                        className="flex items-center gap-1 px-2 py-1 rounded border hover:bg-zinc-100 dark:hover:bg-white/10 disabled:opacity-40"
                        data-testid="canvas-pdf-reopen"
                    >
                        <Reopen className="h-3 w-3" /> Reopen
                    </button>
                )}
                {lifecycle !== "archived" && (
                    <button
                        onClick={() => runLifecycle("archive", "Archived")}
                        disabled={transitioning}
                        className="flex items-center gap-1 px-2 py-1 rounded border hover:bg-zinc-100 dark:hover:bg-white/10 disabled:opacity-40"
                        data-testid="canvas-pdf-archive"
                    >
                        <Archive className="h-3 w-3" /> Archive
                    </button>
                )}
                <span className="flex-1" />
                {dirty && (
                    <button
                        onClick={undo}
                        disabled={!history.length}
                        className="flex items-center gap-1 px-2 py-1 rounded border hover:bg-zinc-100 dark:hover:bg-white/10 disabled:opacity-40"
                        data-testid="canvas-pdf-undo"
                    >
                        <Undo2 className="h-3 w-3" /> Undo
                    </button>
                )}
                <button
                    onClick={() => mergeInputRef.current?.click()}
                    disabled={saving || attaching || !mutable}
                    className="flex items-center gap-1 px-2 py-1 rounded border hover:bg-zinc-100 dark:hover:bg-white/10 disabled:opacity-40"
                    data-testid="canvas-pdf-merge"
                >
                    Merge…
                </button>
                <input
                    ref={mergeInputRef}
                    type="file"
                    accept="application/pdf"
                    className="hidden"
                    onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) void mergeFile(f);
                        e.target.value = "";
                    }}
                />
                <label
                    className="flex items-center gap-1 text-[10px] text-zinc-500 cursor-pointer select-none"
                    title="Stage a frozen copy: form values burned in, no interactive layer — the canvas keeps its editable version"
                >
                    <input
                        type="checkbox"
                        checked={flattenOnAttach}
                        onChange={(e) => setFlattenOnAttach(e.target.checked)}
                        data-testid="canvas-pdf-flatten-toggle"
                    />
                    Flatten form
                </label>
                <button
                    onClick={attach}
                    disabled={saving || attaching}
                    className="flex items-center gap-1 px-2 py-1 rounded border border-emerald-500 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 disabled:opacity-40"
                    data-testid="canvas-pdf-attach"
                >
                    {attaching ? <Loader2 className="h-3 w-3 animate-spin" /> : <FileOutput className="h-3 w-3" />}
                    Attach to email
                </button>
                <button
                    onClick={save}
                    disabled={!dirty || saving || !mutable}
                    className="flex items-center gap-1 px-2.5 py-1 rounded bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-40"
                    data-testid="canvas-pdf-save"
                >
                    {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
                    Save
                </button>
                {/* view tabs */}
                <div className="flex rounded border overflow-hidden" data-testid="canvas-pdf-modes">
                    {(["pages", "text", "form"] as const).map((m) => (
                        <button
                            key={m}
                            onClick={() => { setMode(m); if (m === "text") void openTextPane(textOcr); if (m === "form") void openFormPane(); }}
                            className={`px-2 py-1 text-[10px] capitalize ${mode === m
                                ? "bg-indigo-600 text-white"
                                : "hover:bg-zinc-100 dark:hover:bg-white/10"}`}
                            data-testid={`canvas-pdf-mode-${m}`}
                        >
                            {m}
                        </button>
                    ))}
                </div>
                {/* maturity-gated actions (agents propose these same ops) */}
                {mutable && (
                    <button
                        onClick={() => { setSignPanel(!signPanel); setRedactPanel(false); setDsPanel(false); }}
                        className="flex items-center gap-1 px-2 py-1 rounded border hover:bg-zinc-100 dark:hover:bg-white/10"
                        data-testid="canvas-pdf-sign-open"
                    >
                        <FileSignature className="h-3 w-3" /> Sign
                    </button>
                )}
                {mutable && (
                    <button
                        onClick={() => { setRedactPanel(!redactPanel); setSignPanel(false); setDsPanel(false); }}
                        className="flex items-center gap-1 px-2 py-1 rounded border hover:bg-zinc-100 dark:hover:bg-white/10"
                        data-testid="canvas-pdf-redact-open"
                    >
                        <Eraser className="h-3 w-3" /> Redact
                    </button>
                )}
                <button
                    onClick={() => void doArchive()}
                    disabled={busyOp === "archive"}
                    className="flex items-center gap-1 px-2 py-1 rounded border hover:bg-zinc-100 dark:hover:bg-white/10 disabled:opacity-40"
                    data-testid="canvas-pdf-archive-open"
                >
                    <CloudUpload className="h-3 w-3" /> Archive
                </button>
                <button
                    onClick={() => { setDsPanel(!dsPanel); setSignPanel(false); setRedactPanel(false); }}
                    className="flex items-center gap-1 px-2 py-1 rounded border hover:bg-zinc-100 dark:hover:bg-white/10"
                    data-testid="canvas-pdf-docusign-open"
                >
                    DocuSign…
                </button>
            </div>

            {loading && (
                <div className="flex items-center gap-2 p-4 text-sm text-zinc-500" data-testid="canvas-pdf-loading">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading PDF…
                </div>
            )}
            {error && (
                <div className="flex items-start gap-2 m-3 p-2 rounded bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300 text-xs" data-testid="canvas-pdf-error">
                    <AlertCircle className="h-4 w-4 shrink-0" /> {error}
                </div>
            )}
            {notice && !error && (
                <div className="m-3 p-2 rounded bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300 text-xs" data-testid="canvas-pdf-notice">
                    {notice.href ? (
                        <a href={notice.href} className="underline">
                            {notice.text} — open the email draft
                        </a>
                    ) : (
                        notice.text
                    )}
                </div>
            )}

            {/* sign / redact / docusign inline panels */}
            {signPanel && (
                <div className="mx-3 mt-2 p-2 rounded border bg-white dark:bg-slate-900/60 text-xs space-y-2" data-testid="canvas-pdf-sign-panel">
                    <textarea
                        value={signLines}
                        onChange={(e) => setSignLines(e.target.value)}
                        placeholder="Signature lines (one per line)"
                        className="w-full border rounded p-1.5 bg-transparent"
                        rows={2}
                        data-testid="canvas-pdf-sign-lines"
                    />
                    <input
                        value={signLabel}
                        onChange={(e) => setSignLabel(e.target.value)}
                        placeholder="Attribution (date / name)"
                        className="w-full border rounded p-1.5 bg-transparent"
                        data-testid="canvas-pdf-sign-label"
                    />
                    <button
                        onClick={doSign}
                        disabled={saving}
                        className="px-2.5 py-1 rounded bg-indigo-600 text-white disabled:opacity-40"
                        data-testid="canvas-pdf-sign-apply"
                    >
                        Stamp signature
                    </button>
                </div>
            )}
            {redactPanel && (
                <div className="mx-3 mt-2 p-2 rounded border bg-white dark:bg-slate-900/60 text-xs space-y-2" data-testid="canvas-pdf-redact-panel">
                    <p className="text-zinc-500">One target per line — each is permanently removed from every page that contains it, then verified.</p>
                    <textarea
                        value={redactTargets}
                        onChange={(e) => setRedactTargets(e.target.value)}
                        placeholder={"SSN: 123-45-6789\nConfidential — draft"}
                        className="w-full border rounded p-1.5 bg-transparent font-mono"
                        rows={3}
                        data-testid="canvas-pdf-redact-input"
                    />
                    <button
                        onClick={doRedact}
                        disabled={saving}
                        className="px-2.5 py-1 rounded bg-red-600 text-white disabled:opacity-40"
                        data-testid="canvas-pdf-redact-apply"
                    >
                        Redact permanently
                    </button>
                </div>
            )}
            {dsPanel && (
                <div className="mx-3 mt-2 p-2 rounded border bg-white dark:bg-slate-900/60 text-xs space-y-2" data-testid="canvas-pdf-docusign-panel">
                    <input
                        value={dsEmail}
                        onChange={(e) => setDsEmail(e.target.value)}
                        placeholder="Signer email"
                        className="w-full border rounded p-1.5 bg-transparent"
                        data-testid="canvas-pdf-docusign-email"
                    />
                    <input
                        value={dsName}
                        onChange={(e) => setDsName(e.target.value)}
                        placeholder="Signer name"
                        className="w-full border rounded p-1.5 bg-transparent"
                        data-testid="canvas-pdf-docusign-name"
                    />
                    <button
                        onClick={doDocuSign}
                        disabled={saving}
                        className="px-2.5 py-1 rounded bg-indigo-600 text-white disabled:opacity-40"
                        data-testid="canvas-pdf-docusign-apply"
                    >
                        Send for signature
                    </button>
                </div>
            )}

            {/* text / form panes (pages render below in the default mode) */}
            {mode === "text" && (
                <div className="px-3 pb-2 text-xs" data-testid="canvas-pdf-text-pane">
                    <label className="flex items-center gap-1 mb-2 text-[10px] text-zinc-500">
                        <input
                            type="checkbox"
                            checked={textOcr}
                            onChange={(e) => void openTextPane(e.target.checked)}
                            data-testid="canvas-pdf-ocr-toggle"
                        />
                        OCR scanned pages (Docling)
                    </label>
                    {(textPages || []).map((p) => (
                        <div key={p.page} className="mb-2 p-2 rounded border bg-white dark:bg-white/5">
                            <div className="text-[9px] text-zinc-400 mb-1">Page {p.page + 1}</div>
                            <pre className="whitespace-pre-wrap text-[11px] text-zinc-700 dark:text-zinc-300">{p.text || "(no text layer — try OCR)"}</pre>
                        </div>
                    ))}
                </div>
            )}
            {mode === "form" && (
                <div className="px-3 pb-2 text-xs" data-testid="canvas-pdf-form-pane">
                    {formLoaded && Object.keys(formFieldsState).length ? (
                        <>
                            {Object.entries(formFieldsState).map(([name, value]) => (
                                <label key={name} className="flex items-center gap-2 mb-2">
                                    <span className="w-40 shrink-0 font-mono text-[10px] text-zinc-500 truncate" title={name}>{name}</span>
                                    <input
                                        value={value}
                                        onChange={(e) => setFormFieldsState({ ...formFieldsState, [name]: e.target.value })}
                                        className="flex-1 border rounded px-2 py-1 bg-transparent"
                                        data-testid={`canvas-pdf-field-${name}`}
                                    />
                                </label>
                            ))}
                            <div className="flex gap-2">
                                <button
                                    onClick={saveForm}
                                    disabled={saving}
                                    className="px-2.5 py-1 rounded bg-indigo-600 text-white disabled:opacity-40"
                                    data-testid="canvas-pdf-form-save"
                                >
                                    Fill fields
                                </button>
                                <button
                                    onClick={doFlatten}
                                    disabled={saving}
                                    className="px-2.5 py-1 rounded border disabled:opacity-40"
                                    data-testid="canvas-pdf-form-flatten"
                                    title="Burn values into the page and remove the interactive form"
                                >
                                    Flatten form
                                </button>
                            </div>
                        </>
                    ) : (
                        <p className="text-zinc-500">{busyOp === "form" ? "Reading fields…" : "This PDF has no fillable form fields."}</p>
                    )}
                </div>
            )}

            {/* pages */}
            <div className={`flex-1 overflow-y-auto custom-scrollbar px-3 pb-4 ${mode === "pages" ? "" : "hidden"}`}>
                {pageMap.map((spec, i) => (
                    <div key={`${spec.src_index}:${i}`} className="mb-4" data-testid={`canvas-pdf-page-${i}`}>
                        <div className="flex items-center gap-1 mb-1 text-[10px] text-zinc-400">
                            <span>Page {i + 1}{spec.rotation ? ` · ${spec.rotation}°` : ""}</span>
                            <span className="flex-1" />
                            <button onClick={() => rotatePage(i, -90)} title="Rotate left" disabled={!mutable}
                                data-testid={`canvas-pdf-rotate-left-${i}`}
                                className="p-1 rounded hover:bg-zinc-200 dark:hover:bg-white/10 disabled:opacity-30">
                                <RotateCcw className="h-3 w-3" />
                            </button>
                            <button onClick={() => rotatePage(i, 90)} title="Rotate right" disabled={!mutable}
                                data-testid={`canvas-pdf-rotate-right-${i}`}
                                className="p-1 rounded hover:bg-zinc-200 dark:hover:bg-white/10 disabled:opacity-30">
                                <RotateCw className="h-3 w-3" />
                            </button>
                            <button onClick={() => movePage(i, -1)} title="Move up" disabled={!mutable}
                                data-testid={`canvas-pdf-move-up-${i}`}
                                className="p-1 rounded hover:bg-zinc-200 dark:hover:bg-white/10 disabled:opacity-30">
                                <ArrowUp className="h-3 w-3" />
                            </button>
                            <button onClick={() => movePage(i, 1)} title="Move down" disabled={!mutable}
                                data-testid={`canvas-pdf-move-down-${i}`}
                                className="p-1 rounded hover:bg-zinc-200 dark:hover:bg-white/10 disabled:opacity-30">
                                <ArrowDown className="h-3 w-3" />
                            </button>
                            <button onClick={() => deletePage(i)} title="Delete page" disabled={!mutable}
                                data-testid={`canvas-pdf-delete-${i}`}
                                className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-950/40 text-red-500 disabled:opacity-30">
                                <Trash2 className="h-3 w-3" />
                            </button>
                        </div>
                        <div className="rounded border bg-white shadow-sm dark:border-white/10 overflow-hidden">
                            <canvas data-pdf-page-slot={`${canvasId}:${i}`} className="block w-full" />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

function describeError(e: any, fallback: string): string {
    const detail =
        e?.response?.data?.error?.message ||
        e?.response?.data?.detail ||
        e?.response?.data?.message ||
        e?.message;
    return detail ? `${fallback}: ${detail}` : fallback;
}
