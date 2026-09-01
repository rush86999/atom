"use client";

import React, { useEffect, useState, useRef, useMemo, useCallback } from "react";
import { useRouter } from "next/router";
import { X, Code, Camera, Globe, Play, Layers, Save, History, Check, Loader2, FileText, Table2, Presentation, Maximize2 } from "lucide-react";
import { marked } from "marked";
import { renderMarkdownSafe } from "@/lib/sanitize";
import Editor from "@monaco-editor/react";
import { useCanvasStateRegistration } from "@/hooks/useCanvasStateRegistration";
import { useCanvasAutosave } from "@/hooks/useCanvasAutosave";
import { saveCanvasAudit } from "@/lib/canvasAuditSave";
import { onCanvasRefresh } from "@/lib/canvasSync";
import { isCanvasContentFrame } from "@/lib/canvasFrame";
import { CANVAS } from "@/src/lib/testIds";
import { LineChartCanvas } from "@/components/canvas/LineChart";
import { BarChartCanvas } from "@/components/canvas/BarChart";
import { PieChartCanvas } from "@/components/canvas/PieChart";
import { InteractiveForm } from "@/components/canvas/InteractiveForm";
import { OfficeFileCanvas } from "@/components/canvas/OfficeFileCanvas";
import { CanvasTypeBadge } from "@/components/canvas/CanvasTypeBadge";
import { persistCanvasTypeSwitch, switchCanvasType, normalizeCanvasComponent, type SwitchableCanvasType } from "@/components/canvas/canvasType";
import { CanvasVersionHistory } from "@/components/canvas/CanvasVersionHistory";
import { EmailAttachmentStrip, type EmailAttachmentRecord } from "@/components/canvas/EmailAttachmentStrip";

interface CanvasState {
    id?: string;
    visible: boolean;
    component: "markdown" | "code" | "chart" | "form" | "status_panel" | "eval" | "snapshot" | "browser_view" | "email" | "sheet" | "document" | "office_excel" | "office_word" | "office_pptx" | "custom";
    title?: string;
    data: any;
    version?: number;
}

interface CanvasHostProps {
    lastMessage: any;
    /** Chat session the canvas belongs to — carried into the expanded page
        so its agent chat panel continues the same conversation. */
    sessionId?: string | null;
    /** Notified whenever the host goes from empty → showing a canvas or
        back, so parents can reclaim the host's layout space (the chat
        Artifacts tab gives the list the full height while no canvas is
        open). */
    onVisibilityChange?: (visible: boolean) => void;
}

export function CanvasHost({ lastMessage, sessionId, onVisibilityChange }: CanvasHostProps) {
    const router = useRouter();
    const [state, setState] = useState<CanvasState | null>(null);
    const [isSaving, setIsSaving] = useState(false);
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
    const localContentRef = useRef<string>("");
    // Signature (`component|content`) of the most recent successful audit
    // save. PUT /api/canvas/{id} broadcasts the saved content back to this
    // same user over WS; the effect below skips that echo instead of
    // resetting the editor to the saved snapshot (which would drop any
    // keystrokes typed after the autosave fired).
    const lastSavedSigRef = useRef<string | null>(null);
    const [emailMetadata, setEmailMetadata] = useState({ to: "", subject: "" });
    // Email attachments (backend attachment records). Mutations arrive as
    // canvas:update frames with action="email_attachments" (stage/remove/
    // ingest/sent all broadcast the full list).
    const [emailAttachments, setEmailAttachments] = useState<EmailAttachmentRecord[]>([]);
    const [sheetData, setSheetData] = useState<any[][]>([]);
    const [showPreview, setShowPreview] = useState(false);
    // Version-history + restore panel (shared CanvasVersionHistory — every
    // canvas type, both host surfaces). Only meaningful for audit-trail
    // canvases (state.id present).
    const [showHistory, setShowHistory] = useState(false);

    // Native audit-trail content per type + the WS echo signature. Null →
    // this type's content shape is backend-owned (charts, office files,
    // forms) and stays on the legacy artifacts store — the host must not
    // overwrite a dict it only renders.
    const auditTrailContent = (): { content: any; echo: string } | null => {
        if (!state) return null;
        if (state.component === "email") {
            return {
                content: {
                    to: emailMetadata.to,
                    cc: (state.data as any)?.cc || "",
                    subject: emailMetadata.subject,
                    body: localContentRef.current || "",
                },
                echo: localContentRef.current || "",
            };
        }
        if (state.component === "sheet") {
            return { content: sheetData, echo: JSON.stringify(sheetData) };
        }
        if (typeof state.data === "string") {
            return { content: localContentRef.current, echo: localContentRef.current };
        }
        return null;
    };

    // Returns true on success / false on failure — the autosave hook keys
    // its retry + status logic off this result.
    const handleSave = async (): Promise<boolean> => {
        if (!state) return false;
        setIsSaving(true);

        // Canvas-audit persistence for every canvas whose content THIS host
        // owns end-to-end (email dict, sheet rows, string bodies) — the
        // audit trail is what /canvas/{id} reads and what the chat co-editor
        // plans against; the legacy artifacts store is invisible to both,
        // so edits saved there got silently reverted by the next co-edit.
        // A failed audit save (e.g. state.id names a legacy artifact → 404)
        // falls through to the legacy path rather than dropping the edit —
        // except email: the artifacts path loses To/Cc/Subject on refresh.
        if (state.id) {
            const audit = auditTrailContent();
            if (audit !== null) {
                const ok = await saveCanvasAudit(state.id, state.component, state.title, audit.content);
                if (ok) {
                    setHasUnsavedChanges(false);
                    lastSavedSigRef.current = `${state.component}|${audit.echo}`;
                    return true;
                }
                if (state.component === "email") {
                    console.error("Error saving email canvas to the audit trail");
                    setIsSaving(false);
                    return false;
                }
            }
        }

        const payload: any = {
            id: state.id,
            name: state.title || "Untitled Artifact",
            type: state.component,
            content: localContentRef.current,
            session_id: (lastMessage as any)?.sessionId
        };

        if (state.component === "email") {
            payload.metadata = emailMetadata;
        } else if (state.component === "sheet") {
            payload.content = JSON.stringify(sheetData);
        }

        try {
            const endpoint = state.id ? "/api/artifacts/update" : "/api/artifacts";
            const body = JSON.stringify(payload);
            // keepalive lets a beforeunload flush survive navigation; the
            // browser caps keepalive bodies at 64KB, so opt in only below.
            const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body,
                keepalive: body.length < 60000
            });

            if (response.ok) {
                const updated = await response.json();
                setState(prev => prev ? { ...prev, id: updated.id, version: updated.version } : null);
                setHasUnsavedChanges(false);
                return true;
            }
            return false;
        } catch (error) {
            console.error("Error saving artifact:", error);
            return false;
        } finally {
            setIsSaving(false);
        }
    };

    // ─── Auto-save ───
    // Every edit calls scheduleAutosave(); when the user pauses for 3s the
    // same handleSave the manual button uses runs. Idle-debounced (not
    // interval) because each save appends a version row server-side.
    // resetAutosave is referenced by the payload effect above through this
    // closure — the callbacks are stable across renders.
    const {
        status: autosaveStatus,
        schedule: scheduleAutosave,
        flush: flushAutosave,
        reset: resetAutosave,
    } = useCanvasAutosave({ save: handleSave });

    // Apply one canvas:update / canvas:present frame — whether it arrived
    // over the WebSocket or via a local store-sync (lib/canvasSync, the
    // convergence pass for chat turns that co-edited this canvas). One
    // guarded path for both, so a missed WS broadcast converges identically.
    const applyCanvasMessage = useCallback((msg: any) => {
        if (!msg) return;

        // Check for canvas event type
        if (msg.type === "canvas:update" || msg.type === "canvas:present") {
            // Backend broadcasts carry `canvas_id` (tools/canvas_tool.py); the
            // chat flow may carry `id` — accept either so state registration
            // and form submission always know the canvas id.
            const frame = msg.data || msg;
            const { action, data, title, id, canvas_id, version, metadata } = frame;
            // canvas_type names ("sheets"/"docs"/"coding"/"generic") map onto
            // the component names this host renders (normalizeCanvasComponent).
            const component = normalizeCanvasComponent(frame.component);

            if (action === "close") {
                // Closing supersedes local edits — drop any pending autosave
                // so its timer can't write afterwards.
                resetAutosave();
                setState(null);
                setEmailAttachments([]);
            } else if (action === "email_attachments") {
                // Attachment-list broadcast (stage/remove/ingest/sent): data
                // is the attachment list payload, NOT canvas content — never
                // route it through the content path below.
                setEmailAttachments(Array.isArray(data?.attachments) ? data.attachments : []);
            } else {
                // Event/status broadcasts (email_send, mini_app_state, …)
                // declare via `action` that `data` is NOT canvas content.
                // Rendering them as content replaced the user's draft with
                // {status, payload} JSON (observed live 2026-08-31: a failed
                // send made the open email draft vanish from the panel).
                if (!isCanvasContentFrame(frame)) return;
                // BUG FIX: `data` can be undefined for data-less canvas messages
                // (e.g. an empty status panel). Reading `data.content` crashed the
                // effect, which also made CanvasContent's "No data to display"
                // guard unreachable. Use optional chaining instead.
                const content = typeof data === 'string' ? data : (data?.content || JSON.stringify(data, null, 2));

                // Autosave echo-guard: PUT /api/canvas/{id} (the audit save
                // path) broadcasts the just-saved content back over WS.
                // Applying that echo verbatim would reset the editor to the
                // saved snapshot and drop any keystrokes typed after the
                // autosave fired — skip it; local state stays authoritative.
                if (lastSavedSigRef.current !== null && `${component || ""}|${content}` === lastSavedSigRef.current) {
                    return;
                }
                // A new payload supersedes local edits — drop any pending
                // autosave so its timer can't re-write the superseded content.
                resetAutosave();
                localContentRef.current = content;

                setState({
                    id: id || canvas_id,
                    visible: true,
                    component: (component === 'eval' ? 'code' : normalizeCanvasComponent(component)) as CanvasState["component"],
                    title,
                    data,
                    version
                });

                if (component === "email" && metadata) {
                    setEmailMetadata({ to: metadata.to || "", subject: metadata.subject || "" });
                }
                if (component === "email") {
                    // Present/update frames carry the canvas attachment list
                    // in the details payload — seed from it so a reload or
                    // agent-side mutation shows without a dedicated frame.
                    setEmailAttachments(
                        (prev) => (Array.isArray((data as any)?.attachments) ? (data as any).attachments : prev),
                    );
                }

                if (component === "sheet") {
                    setSheetData(Array.isArray(data) ? data : (data.rows || [["", "", ""], ["", "", ""]]));
                }

                setHasUnsavedChanges(false);
            }
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [resetAutosave]);

    useEffect(() => {
        if (lastMessage) applyCanvasMessage(lastMessage);
    }, [lastMessage, applyCanvasMessage]);

    // Visibility is derived state — one effect covers every transition
    // (present/update, close, type switches keep it open).
    const isVisible = !!state?.visible;
    useEffect(() => {
        onVisibilityChange?.(isVisible);
    }, [isVisible, onVisibilityChange]);

    // Local store-sync convergence (lib/canvasSync): a chat turn flagged as a
    // canvas edit/action re-broadcasts the audit-trail content here, covering
    // the missed-WS-broadcast case (dead socket / throttled tab).
    useEffect(() => onCanvasRefresh((detail) => applyCanvasMessage(detail.message)), [applyCanvasMessage]);

    const handleSendEmail = async () => {
        if (!emailMetadata.to.trim()) {
            alert("Add a recipient before sending.");
            return;
        }
        // Explicit confirm before dispatch — the send endpoint treats the
        // human click as policy authorization for allow/approve decisions
        // (same contract as the full-page CanvasPanel composer).
        if (!window.confirm(`Send email to ${emailMetadata.to}?`)) return;
        try {
            const { apiClient } = await import("@/lib/api");
            const res = await apiClient.post("/api/canvas/email/send", {
                to: [emailMetadata.to].filter(Boolean),
                cc: [],
                subject: emailMetadata.subject || "",
                body: localContentRef.current || "",
                canvas_id: state?.id || undefined,
                attachment_ids: emailAttachments.map((a) => a.attachment_id),
            });
            const data = (res as any)?.data || {};
            if (data.success) {
                alert(data.status === "sent" ? "Email sent." : `Email status: ${data.status}`);
            } else {
                alert(`Send blocked: ${data.error || data.message || "unknown error"}`);
            }
        } catch (e: any) {
            alert(`Send failed: ${e?.response?.data?.message || e?.message || "unknown error"}`);
        }
    };

    // Manual retype — the escape hatch when the agent-chat classifier picked
    // the wrong canvas type. Converts the content into the target's shape,
    // swaps the rendered component, and persists a pinned audit row so the
    // choice survives reloads and read-time coercion.
    const handleTypeSwitch = (target: SwitchableCanvasType) => {
        if (!state) return;
        // The chat host's payload effect leaves a JSON blob in
        // localContentRef for UNEDITED email canvases ({to,subject,body} has
        // no content key) — the composer body is authoritative until the
        // first user edit flips hasUnsavedChanges.
        const emailText = hasUnsavedChanges
            ? localContentRef.current
            : ((state.data as any)?.body ?? localContentRef.current);
        const conversion = switchCanvasType(target, {
            component: state.component,
            data: state.data,
            text: state.component === "email" ? emailText : localContentRef.current,
            email: emailMetadata,
            sheet: sheetData,
            title: state.title,
        });

        setState({ ...state, component: conversion.component, data: conversion.data });
        localContentRef.current = conversion.text;
        setEmailMetadata({ to: conversion.email.to, subject: conversion.email.subject });
        setSheetData(conversion.sheet);
        setShowPreview(false);
        setHasUnsavedChanges(!state.id);
        // The switch persists itself — a pending autosave would only
        // re-write what persistCanvasTypeSwitch just stored.
        resetAutosave();

        if (state.id) {
            persistCanvasTypeSwitch(state.id, conversion, state.title).catch((e) => {
                console.error("Failed to persist canvas type change:", e);
                setHasUnsavedChanges(true);
            });
        }
    };

    // ─── AI Accessibility: register canvas state for agent read-back ───
    // Every canvas type exposes its current state via window.atom.canvas.getState()
    // so agents can "see" what's on screen. Uses the reusable registration hook.
    const canvasId = state?.id || `canvas_${state?.component || 'generic'}`;
    const canvasState = useMemo(() => {
        if (!state?.visible) return null;

        switch (state.component) {
            case "sheet":
                return {
                    type: "sheets" as const,
                    cells: sheetData,
                    sheetName: state.title || "Sheet1",
                    activeCell: null as string | null,
                };
            case "email":
                return {
                    type: "email" as const,
                    to: emailMetadata.to,
                    subject: emailMetadata.subject,
                    body: localContentRef.current,
                    draft: hasUnsavedChanges,
                };
            case "document":
                return {
                    type: "docs" as const,
                    title: state.title || "Document",
                    format: "docx" as const,
                    sections: [{ heading: "Content", body: localContentRef.current }],
                };
            case "code":
                return {
                    type: "coding" as const,
                    language: (state.data as any)?.language || "plaintext",
                    code: localContentRef.current,
                    filename: state.title || "untitled",
                };
            case "markdown":
                return {
                    type: "generic" as const,
                    component: "markdown" as const,
                    title: state.title || "Markdown",
                    text: localContentRef.current,
                    html: renderMarkdownSafe(localContentRef.current),
                };
            case "status_panel":
                return {
                    type: "generic" as const,
                    component: "status_panel" as const,
                    title: state.title || "Status",
                    text: localContentRef.current,
                };
            // Office co-editing canvases (#39): agents read back what the user
            // sees — grid cells / document text / slide outline — so they can
            // reason about the file before editing it.
            case "office_excel": {
                const d = state.data as any;
                const sheet = d?.sheets?.find((s: any) => s.name === d?.active_sheet) || d?.sheets?.[0];
                return {
                    type: "sheets" as const,
                    cells: sheet?.rows || [],
                    sheetName: sheet?.name || "Sheet1",
                    activeCell: null as string | null,
                    filePath: d?.file_path,
                };
            }
            case "office_word":
                return {
                    type: "docs" as const,
                    title: state.title || "Document",
                    format: "docx" as const,
                    sections: [{ heading: "Content", body: (state.data as any)?.text || "" }],
                    filePath: (state.data as any)?.file_path,
                };
            case "office_pptx":
                return {
                    type: "generic" as const,
                    component: "office_pptx" as const,
                    title: state.title || "Presentation",
                    slides: (state.data as any)?.slides || [],
                    filePath: (state.data as any)?.file_path,
                };
            default:
                return {
                    type: "generic" as const,
                    component: state.component,
                    title: state.title || "Canvas",
                    data: state.data,
                };
        }
    }, [state, sheetData, emailMetadata, hasUnsavedChanges]);

    useCanvasStateRegistration(canvasId, canvasState as any);

    if (!state || !state.visible) return null;

    return (
        <div
            data-testid={CANVAS.CONTAINER}
            className="flex flex-col h-full bg-white dark:bg-[#020617] relative animate-in fade-in duration-500 overflow-hidden"
            // Leaving the editor must not race the autosave window: the
            // backend plans canvas edits against the durable store, so
            // keystrokes still pending autosave would be invisible to it.
            onBlur={() => { if (hasUnsavedChanges) void flushAutosave(); }}
        >
            {/* Header needs z-30: backdrop-blur-sm creates a stacking
                context, so without it menus opened from this bar (the type
                switcher) paint UNDER the content area below, which is
                position:relative and later in DOM order. */}
            <div className="p-3 border-b flex items-center justify-between bg-zinc-50 dark:bg-slate-900/50 backdrop-blur-sm shrink-0 relative z-30">
                <div className="flex items-center gap-2">
                    <CanvasIcon component={state.component} />
                    <div className="flex flex-col">
                        <h3 className="font-semibold text-sm truncate max-w-[200px] text-zinc-900 dark:text-zinc-100">
                            {state.title || "Agent Artifact"}
                        </h3>
                        <div className="flex items-center gap-2">
                            {state.version && (
                                <span className="text-[10px] text-zinc-500 font-mono">v{state.version}</span>
                            )}
                            <CanvasTypeBadge
                                component={state.component}
                                onSwitch={handleTypeSwitch}
                            />
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {/* Expand into the independent full-page canvas (new tab
                        keeps the chat alive); the canvas page links back. */}
                    {state.id && (
                        <button
                            data-testid="canvas-expand"
                            title="Expand into full page"
                            onClick={() => {
                                const agentId = router.query.agent_id;
                                const params = new URLSearchParams({ from: "chat" });
                                if (agentId) params.set("agent_id", String(agentId));
                                if (sessionId) params.set("session", String(sessionId));
                                window.open(`/canvas/${state.id}?${params.toString()}`, "_blank");
                            }}
                            className="h-8 w-8 flex items-center justify-center rounded-full hover:bg-zinc-200 dark:hover:bg-zinc-800 transition-colors"
                        >
                            <Maximize2 className="h-4 w-4 text-zinc-500" />
                        </button>
                    )}
                    {state.component === "email" && (
                        <button
                            onClick={handleSendEmail}
                            className="h-8 px-3 rounded bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-medium transition-colors flex items-center gap-1.5"
                        >
                            <Play className="h-3 w-3" /> Send
                        </button>
                    )}
                    {(hasUnsavedChanges || state.component === 'sheet') && (
                        <button
                            onClick={() => { void flushAutosave({ force: true }); }}
                            disabled={isSaving || autosaveStatus === "saving"}
                            className="flex items-center gap-1.5 px-2 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-medium transition-colors disabled:opacity-50"
                        >
                            {isSaving || autosaveStatus === "saving" ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
                            Save Changes
                        </button>
                    )}
                    <button
                        onClick={() => setState(null)}
                        data-testid={CANVAS.CLOSE_BUTTON}
                        className="h-8 w-8 flex items-center justify-center rounded-full hover:bg-zinc-200 dark:hover:bg-zinc-800 transition-colors"
                    >
                        <X className="h-4 w-4 text-zinc-500" />
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-hidden relative">
                <CanvasContent
                    component={state.component}
                    data={state.data}
                    canvasId={state.id}
                    canvasTitle={state.title}
                    emailMetadata={emailMetadata}
                    setEmailMetadata={(m) => { setEmailMetadata(m); setHasUnsavedChanges(true); scheduleAutosave(); }}
                    emailAttachments={emailAttachments}
                    sheetData={sheetData}
                    setSheetData={(d) => { setSheetData(d); setHasUnsavedChanges(true); scheduleAutosave(); }}
                    showPreview={showPreview}
                    setShowPreview={setShowPreview}
                    onContentChange={(val) => {
                        localContentRef.current = val;
                        setHasUnsavedChanges(true);
                        scheduleAutosave();
                    }}
                />
            </div>

            <div className="p-2 border-t flex justify-between items-center px-4 bg-zinc-50 dark:bg-slate-900/30">
                <div className="flex gap-4">
                    <button
                        onClick={() => setShowHistory(!showHistory)}
                        disabled={!state.id}
                        title="Version history"
                        className="text-[10px] text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 flex items-center gap-1 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                        <History className="h-3 w-3" /> History
                    </button>
                    {(state.component === "markdown" || state.component === "document" || state.component.startsWith("office_")) && (
                        <button
                            onClick={() => setShowPreview(!showPreview)}
                            className={`text-[10px] flex items-center gap-1 transition-colors ${showPreview ? "text-indigo-600 dark:text-indigo-400" : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"}`}
                        >
                            <Globe className="h-3 w-3" /> {showPreview ? "Edit Mode" : "Preview Mode"}
                        </button>
                    )}
                </div>
                {state.id && (
                    autosaveStatus === "saving" ? (
                        <span data-testid="canvas-autosave-status" className="text-[10px] text-zinc-500 flex items-center gap-1 font-medium">
                            <Loader2 className="h-3 w-3 animate-spin" /> Saving…
                        </span>
                    ) : autosaveStatus === "error" ? (
                        <span
                            data-testid="canvas-autosave-status"
                            className="text-[10px] text-amber-600 dark:text-amber-400 font-medium"
                            title="Auto-save failed. Your edits are kept here — click Save Changes to retry."
                        >
                            ⚠ Auto-save failed
                        </span>
                    ) : autosaveStatus === "pending" ? (
                        <span data-testid="canvas-autosave-status" className="text-[10px] text-zinc-500 flex items-center gap-1 font-medium">
                            Unsaved changes — auto-saving…
                        </span>
                    ) : (
                        <span className="text-[10px] text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-medium">
                            <Check className="h-3 w-3" /> Synced to cloud
                        </span>
                    )
                )}
            </div>

            {/* Version history + restore — shared with /canvas/{id}; a restore
                appends a new version and syncs every host via lib/canvasSync */}
            {showHistory && state.id && (
                <div className="absolute inset-x-3 bottom-12 top-12 z-40 bg-background border border-zinc-200 dark:border-white/10 rounded-lg shadow-lg overflow-y-auto">
                    <div className="p-3 border-b flex justify-between items-center">
                        <h3 className="text-sm font-semibold">Version History</h3>
                        <button
                            onClick={() => setShowHistory(false)}
                            aria-label="Close history"
                            className="h-6 w-6 rounded-full hover:bg-zinc-200 dark:hover:bg-zinc-800 transition-colors"
                        >
                            <X className="h-3.5 w-3.5 mx-auto text-zinc-500" />
                        </button>
                    </div>
                    <CanvasVersionHistory canvasId={state.id} />
                </div>
            )}
        </div>
    );
}

function CanvasIcon({ component }: { component: string }) {
    switch (component) {
        case "code": return <Code className="h-4 w-4 text-blue-500" />;
        case "email": return <Globe className="h-4 w-4 text-emerald-500" />;
        case "sheet": return <Layers className="h-4 w-4 text-amber-500" />;
        case "document": return <FileText className="h-4 w-4 text-indigo-500" />;
        case "snapshot": return <Camera className="h-4 w-4 text-purple-500" />;
        case "browser_view": return <Globe className="h-4 w-4 text-green-500" />;
        case "office_excel": return <Table2 className="h-4 w-4 text-amber-500" />;
        case "office_word": return <FileText className="h-4 w-4 text-blue-500" />;
        case "office_pptx": return <Presentation className="h-4 w-4 text-orange-500" />;
        default: return <Layers className="h-4 w-4 text-indigo-500" />;
    }
}

function resolveChartData(data: any): any[] {
    // Accept: raw array (present flow / DB content), {data: [...]} (WS
    // present message), {content: [...]} (PUT update flow).
    if (Array.isArray(data)) return data;
    if (Array.isArray(data?.content)) return data.content;
    return data?.data || [];
}

function resolveChartTitle(data: any, canvasTitle?: string): string | undefined {
    if (typeof data?.title === "string") return data.title;
    if (typeof data?.content?.title === "string") return data.content.title;
    return canvasTitle || undefined;
}

function CanvasContent({
    component,
    data,
    canvasId,
    canvasTitle,
    emailMetadata,
    setEmailMetadata,
    emailAttachments,
    sheetData,
    setSheetData,
    showPreview,
    setShowPreview,
    onContentChange
}: {
    component: string;
    data: any;
    canvasId?: string;
    canvasTitle?: string;
    emailMetadata: any;
    setEmailMetadata: (m: any) => void;
    emailAttachments: EmailAttachmentRecord[];
    sheetData: any[][];
    setSheetData: (d: any[][]) => void;
    showPreview: boolean;
    setShowPreview: (s: boolean) => void;
    onContentChange: (val: string) => void
}) {
    if (!data && component !== "sheet" && component !== "form") return <div className="text-zinc-500 p-4">No data to display</div>;

    const content = typeof data === 'string' ? data : (data.content || JSON.stringify(data, null, 2));

    switch (component) {
        // Real-file co-editing canvases (.xlsx/.docx/.pptx): edits commit to
        // the file on disk via /api/v1/office/sync-update; agent edits arrive
        // as WS canvas:update snapshots that OfficeFileCanvas re-renders from.
        case "office_excel":
        case "office_word":
        case "office_pptx":
            return <OfficeFileCanvas canvasId={canvasId} data={data} showPreview={showPreview} />;

        case "line_chart":
            return <LineChartCanvas data={resolveChartData(data)} title={resolveChartTitle(data, canvasTitle)} />;
        case "bar_chart":
            return <BarChartCanvas data={resolveChartData(data)} title={resolveChartTitle(data, canvasTitle)} />;
        case "pie_chart":
            return <PieChartCanvas data={resolveChartData(data)} title={resolveChartTitle(data, canvasTitle)} />;

        case "form": {
            // content may arrive unwrapped (WS present), as {content: {...}}
            // (PUT /api/canvas/{id} stores the body under details.content),
            // or as {schema: ...} — accept all three shapes.
            const payload = data?.content && typeof data.content === "object" && !Array.isArray(data.content)
                ? data.content
                : data;
            const schema = payload?.schema || payload?.form_schema || {};
            const fields = Array.isArray(payload?.fields)
                ? payload.fields
                : Array.isArray(schema?.fields)
                    ? schema.fields
                    : [];
            const formTitle = payload?.title || payload?.form_title || canvasTitle;
            return (
                <div className="h-full overflow-auto custom-scrollbar">
                    <div className="p-4">
                        <InteractiveForm
                            fields={fields}
                            canvasId={canvasId}
                            title={formTitle}
                            onSubmit={async (formData) => {
                                try {
                                    const { apiClient } = await import("@/lib/api");
                                    await apiClient.post("/api/canvas/submit", {
                                        canvas_id: canvasId,
                                        form_data: formData,
                                    });
                                } catch (e) {
                                    console.error("Form submission failed:", e);
                                    throw e;
                                }
                            }}
                        />
                    </div>
                </div>
            );
        }

        case "email":
            return (
                <div className="flex flex-col h-full bg-white dark:bg-[#0F172A]">
                    <div className="p-4 border-b border-zinc-100 dark:border-white/5 space-y-3 bg-zinc-50/50 dark:bg-black/20">
                        <div className="flex items-center gap-2">
                            <span className="text-[10px] text-zinc-400 w-12 font-bold uppercase tracking-wider">To:</span>
                            <input
                                type="text"
                                value={emailMetadata.to}
                                onChange={(e) => setEmailMetadata({ ...emailMetadata, to: e.target.value })}
                                className="flex-1 bg-transparent border-none text-zinc-900 dark:text-zinc-200 text-sm focus:ring-0 placeholder:text-zinc-300"
                                placeholder="recipient@example.com"
                            />
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-[10px] text-zinc-400 w-12 font-bold uppercase tracking-wider">Sub:</span>
                            <input
                                type="text"
                                value={emailMetadata.subject}
                                onChange={(e) => setEmailMetadata({ ...emailMetadata, subject: e.target.value })}
                                className="flex-1 bg-transparent border-none text-zinc-900 dark:text-zinc-200 text-sm font-semibold focus:ring-0 placeholder:text-zinc-300"
                                placeholder="Email Subject"
                            />
                        </div>
                    </div>
                    <EmailAttachmentStrip canvasId={canvasId} attachments={emailAttachments} />
                    <div className="flex-1">
                        <Editor
                            height="100%"
                            defaultLanguage="markdown"
                            theme="vs-dark"
                            value={typeof data === "string" ? data : (data.body || data.content || JSON.stringify(data, null, 2))}
                            onChange={(val) => onContentChange(val || "")}
                            options={{
                                minimap: { enabled: false },
                                fontSize: 13,
                                lineNumbers: "off",
                                wordWrap: "on",
                                padding: { top: 20, bottom: 20 }
                            }}
                        />
                    </div>
                </div>
            );

        case "sheet":
            return (
                <div className="h-full overflow-auto bg-white dark:bg-[#020617] p-1 custom-scrollbar">
                    <table className="w-full border-collapse text-[12px] text-zinc-900 dark:text-zinc-300">
                        <thead>
                            <tr>
                                <th className="w-8 border border-zinc-100 dark:border-white/10 bg-zinc-50 dark:bg-white/5 p-1 text-[10px] text-zinc-400 font-mono">#</th>
                                {sheetData[0]?.map((_, i) => (
                                    <th key={i} className="border border-zinc-100 dark:border-white/10 bg-zinc-50 dark:bg-white/5 p-1 font-bold uppercase tracking-wider">
                                        {String.fromCharCode(65 + i)}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {sheetData.map((row, rowIndex) => (
                                <tr key={rowIndex}>
                                    <td className="border border-zinc-100 dark:border-white/10 bg-zinc-50 dark:bg-white/5 p-1 text-center text-[10px] text-zinc-400 font-mono italic">
                                        {rowIndex + 1}
                                    </td>
                                    {row.map((cell, cellIndex) => (
                                        <td
                                            key={cellIndex}
                                            className="border border-zinc-100 dark:border-white/10 p-1 min-w-[80px] hover:bg-zinc-50 dark:hover:bg-black/5 dark:hover:bg-black/5 dark:bg-white/5 focus-within:bg-indigo-500/10 focus-within:border-indigo-500/50 transition-colors"
                                        >
                                            <input
                                                type="text"
                                                value={cell}
                                                onChange={(e) => {
                                                    const newData = [...sheetData];
                                                    newData[rowIndex][cellIndex] = e.target.value;
                                                    setSheetData(newData);
                                                }}
                                                className="w-full bg-transparent border-none p-0 focus:ring-0 outline-none"
                                            />
                                        </td>
                                    ))}
                                </tr>
                            ))}
                            {/* Add Row Button */}
                            <tr>
                                <td
                                    colSpan={sheetData[0]?.length + 1}
                                    className="p-1 border border-zinc-100 dark:border-white/5 text-center"
                                >
                                    <button
                                        onClick={() => setSheetData([...sheetData, Array(sheetData[0]?.length || 3).fill("")])}
                                        className="text-[10px] text-zinc-400 hover:text-indigo-600 uppercase font-bold tracking-widest transition-colors py-1 w-full"
                                    >
                                        + Add New Row
                                    </button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            );

        case "markdown":
        case "document":
        case "code":
            if (showPreview && (component === "markdown" || component === "document")) {
                const htmlContent = renderMarkdownSafe(content);
                return (
                    <div className="p-8 prose dark:prose-invert max-w-none text-sm leading-relaxed overflow-auto h-full custom-scrollbar bg-zinc-50/10 dark:bg-white/[0.02]">
                        <div dangerouslySetInnerHTML={{ __html: htmlContent }} />
                    </div>
                );
            }
            return (
                <Editor
                    height="100%"
                    defaultLanguage={component === "code" ? "javascript" : "markdown"}
                    theme="vs-dark"
                    value={content}
                    onChange={(val) => onContentChange(val || "")}
                    options={{
                        minimap: { enabled: false },
                        scrollBeyondLastLine: false,
                        fontSize: 13,
                        lineNumbers: "on",
                        roundedSelection: false,
                        readOnly: false,
                        cursorStyle: "line",
                        automaticLayout: true
                    }}
                />
            );

        case "snapshot":
            return (
                <div className="space-y-4 p-4 overflow-auto h-full custom-scrollbar">
                    <div className="flex flex-wrap gap-2 mb-4">
                        {data.timestamp && (
                            <span className="px-2 py-1 rounded-md bg-zinc-100 dark:bg-zinc-800 text-[10px] text-zinc-500 border border-zinc-200 dark:border-zinc-700">
                                Captured: {new Date(data.timestamp).toLocaleTimeString()}
                            </span>
                        )}
                        {data.source && (
                            <span className="px-2 py-1 rounded-md bg-blue-50 dark:bg-blue-900/20 text-[10px] text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-900/50">
                                Source: {data.source}
                            </span>
                        )}
                    </div>
                    <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg overflow-hidden bg-white/40 dark:bg-gray-900/40">
                        <div className="p-2 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50 flex justify-between items-center">
                            <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">State Tree</span>
                        </div>
                        <pre className="p-4 text-[11px] overflow-auto max-h-[400px] bg-zinc-50/50 dark:bg-transparent font-mono text-zinc-600 dark:text-zinc-400">
                            {JSON.stringify(data.state || data, null, 2)}
                        </pre>
                    </div>
                </div>
            );

        case "browser_view":
            return (
                <div className="space-y-4 p-4 overflow-auto h-full custom-scrollbar">
                    <div className="flex items-center gap-2 p-2 bg-zinc-100 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700 text-xs">
                        <Globe className="h-3 w-3 text-zinc-500" />
                        <span className="truncate flex-1 text-zinc-500 italic">{data.url || "about:blank"}</span>
                    </div>
                    {data.screenshot ? (
                        <div className="border border-zinc-200 dark:border-zinc-700 rounded-lg overflow-hidden shadow-sm relative group bg-zinc-900">
                            <img
                                src={data.screenshot.startsWith('data:') ? data.screenshot : `data:image/png;base64,${data.screenshot}`}
                                alt="Browser Snapshot"
                                className="w-full h-auto cursor-zoom-in"
                            />
                        </div>
                    ) : (
                        <div className="h-[300px] border border-dashed border-zinc-300 dark:border-zinc-700 rounded-lg flex flex-col items-center justify-center text-zinc-400">
                            <Globe className="h-8 w-8 mb-2 opacity-20" />
                            <p className="text-xs">Connecting to remote browser...</p>
                        </div>
                    )}
                </div>
            );

        default:
            return (
                <div className="p-6 border rounded-xl border-dashed border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900/20 flex flex-col items-center justify-center text-center m-4">
                    <Layers className="h-10 w-10 text-zinc-300 mb-4" />
                    <p className="text-sm font-medium mb-1 dark:text-zinc-200">Custom Component: {component}</p>
                    <p className="text-xs text-zinc-500 mb-4">Rendering raw data payload</p>
                    <pre className="text-[10px] text-left overflow-auto bg-zinc-100 dark:bg-zinc-800 p-4 rounded-lg w-full max-h-[300px] text-zinc-600 dark:text-zinc-300">
                        {JSON.stringify(data, null, 2)}
                    </pre>
                </div>
            );
    }
}

