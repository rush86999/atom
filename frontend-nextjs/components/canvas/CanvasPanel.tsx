"use client";

import React, { useEffect, useState, useRef, useMemo, useCallback } from "react";
import { X, Code, Camera, Globe, Play, Layers, Save, History, Check, Loader2, FileText, Table2, Presentation } from "lucide-react";
import { marked } from "marked";
import { renderMarkdownSafe } from "@/lib/sanitize";
import Editor from "@monaco-editor/react";
import { useCanvasStateRegistration } from "@/hooks/useCanvasStateRegistration";
import { useCanvasAutosave } from "@/hooks/useCanvasAutosave";
import { saveCanvasAudit } from "@/lib/canvasAuditSave";
import { onCanvasRefresh } from "@/lib/canvasSync";
import { CANVAS } from "@/src/lib/testIds";
import { LineChartCanvas } from "@/components/canvas/LineChart";
import { BarChartCanvas } from "@/components/canvas/BarChart";
import { PieChartCanvas } from "@/components/canvas/PieChart";
import { InteractiveForm } from "@/components/canvas/InteractiveForm";
import { OfficeFileCanvas } from "@/components/canvas/OfficeFileCanvas";
import { EmailRecipientField } from "@/components/canvas/EmailRecipientField";
import { CanvasTypeBadge } from "@/components/canvas/CanvasTypeBadge";
import { persistCanvasTypeSwitch, switchCanvasType, normalizeCanvasComponent, type SwitchableCanvasType } from "@/components/canvas/canvasType";
import SignatureEditor from "@/components/canvas/SignatureEditor";
import RichTextEditor from "@/components/canvas/RichTextEditor";

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
}

export function CanvasPanel({ lastMessage }: CanvasHostProps) {
    const [state, setState] = useState<CanvasState | null>(null);
    const [isSaving, setIsSaving] = useState(false);
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
    const localContentRef = useRef<string>("");
    // The detail page rebuilds its synthetic lastMessage object on every
    // render — without this key, each re-render (e.g. sending a co-editor
    // chat message) re-ran the effect below and reverted unsaved edits.
    const lastPayloadKeyRef = useRef<string>("");
    // Reply auto-fill runs once per distinct canvas payload (guarded so
    // re-renders and user edits never re-trigger the lookup).
    const replyResolveRef = useRef<string>("");
    // Signature (`component|content`) of the most recent successful save.
    // PUT /api/canvas/{id} broadcasts the saved content back to this same
    // user over WS; comparing incoming payloads against this lets the
    // effect skip that echo instead of resetting the editor to the saved
    // snapshot (which would drop any keystrokes typed after the autosave
    // fired). Keyed on component too — a type switch can preserve the text,
    // and that broadcast must still apply.
    const lastSavedSigRef = useRef<string | null>(null);
    const [emailMetadata, setEmailMetadata] = useState({ to: "", cc: "", subject: "" });
    // Email composer body is panel-managed (not read straight from the
    // payload) so signature insertion and edits are one source of truth.
    const [emailBody, setEmailBody] = useState("");
    // Default signature: stored override, else the integration's default.
    const [emailSignature, setEmailSignature] = useState<string | null>(null);
    const [signatureSource, setSignatureSource] = useState<string | null>(null);
    const [signatureOpen, setSignatureOpen] = useState(false);
    const signatureFetchedRef = useRef(false);
    const [sheetData, setSheetData] = useState<any[][]>([]);
    const [showPreview, setShowPreview] = useState(false);

    // A trailing sign-off (agent-typed or integration default) means the
    // body already carries a signature — never double-append.
    const hasSignoff = (body: string, sig: string | null): boolean => {
        if (!body) return false;
        if (sig && body.includes(sig)) return true;
        return /(?:best regards|warm regards|kind regards|regards|sincerely|thank you|thanks|cheers|respectfully)\s*,?\s*(?:\n|<br|<div|$)/im.test(body.slice(-400));
    };

    // A draft's own trailing plain sign-off ("Best regards,\nRish …") —
    // swapped out when the styled signature is inserted, so the email ends
    // with ONE signature instead of two stacked ones.
    const stripTrailingSignoff = (body: string): string => {
        const trimmed = body.replace(/\s+$/, "");
        const lines = trimmed.split("\n");
        const closingRe = /(?:best regards|warm regards|kind regards|regards|sincerely|thank you|thanks|cheers|respectfully)\s*,?\s*$/i;
        // Forwarded-history headers bound the sender's own block — never
        // cut into quoted history below a "From:/Sent:" line or a rule.
        const markerRe = /^\s*-{3,}\s*$|^\s*={3,}\s*$|^\s*(from|sent|to|subject)\s*:\s*\S|^_{5,}\s*original\s+message/i;
        let end = lines.length;
        for (let i = 0; i < lines.length; i++) {
            if (markerRe.test(lines[i])) { end = i; break; }
        }
        for (let i = end - 1; i >= 0; i--) {
            if (closingRe.test(lines[i])) return lines.slice(0, i).join("\n");
        }
        return trimmed;
    };

    const applySignature = (sig: string, replace = false) => {
        setEmailBody((prev) => {
            if (sig && prev.includes(sig)) return prev; // already inserted
            // Auto-apply (mount) stays conservative: only when the draft has
            // no sign-off at all. The explicit "Insert into email" click
            // (replace=true) SWAPS the draft's own trailing plain sign-off
            // for the styled signature — a plain "Best regards, …" ending
            // used to win the hasSignoff guard and made Insert a silent
            // no-op (observed 2026-09-01).
            if (!replace && hasSignoff(prev, sig)) return prev;
            const base = sig ? stripTrailingSignoff(prev) : prev;
            const next = `${base.replace(/\s+$/, "")}\n\n${sig}`;
            localContentRef.current = next;
            return next;
        });
    };

    // Fetch the default signature once per composer mount; when it lands,
    // append it to a body that doesn't already carry a sign-off.
    useEffect(() => {
        if (state?.component !== "email" || signatureFetchedRef.current) return;
        signatureFetchedRef.current = true;
        (async () => {
            try {
                const { apiClient } = await import("@/lib/api");
                const res = await apiClient.get("/api/canvas/email/signature");
                const data = (res as any).data || res || {};
                if (typeof data.signature === "string" && data.signature.trim()) {
                    setEmailSignature(data.signature);
                    setSignatureSource(data.source || null);
                    applySignature(data.signature);
                }
            } catch {
                // No signature configured — nothing to append.
            }
        })();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [state?.component]);


    // Native audit-trail content per type + the WS echo signature the
    // payload effect compares against. Null → this type's content shape is
    // backend-owned (charts, office files, forms) and stays on the legacy
    // artifacts store — the panel must not overwrite a dict it only renders.
    const auditTrailContent = (): { content: any; echo: string } | null => {
        if (!state) return null;
        if (state.component === "email") {
            return {
                content: {
                    to: emailMetadata.to,
                    cc: emailMetadata.cc,
                    subject: emailMetadata.subject,
                    body: localContentRef.current || "",
                },
                echo: localContentRef.current || "",
            };
        }
        if (state.component === "sheet") {
            return { content: sheetData, echo: JSON.stringify(sheetData) };
        }
        // String-body canvases: only when the payload the panel rendered was
        // itself a plain string.
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

        // Canvas-audit persistence for every canvas whose content THIS panel
        // owns end-to-end (email dict, sheet rows, string bodies) — not just
        // email. The audit trail is what /canvas/{id} reads, what the WS
        // broadcast updates, and what the chat co-editor plans against; the
        // legacy artifacts store is invisible to all three, so non-email
        // edits saved there got silently reverted by the next co-edit.
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

        if (state.component === "sheet") {
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
                lastSavedSigRef.current = `${state.component}|${payload.content}`;
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
    // interval) because each save appends a version/audit row server-side.
    // resetAutosave is referenced by the payload effect above through this
    // closure — the callbacks are stable across renders.
    const {
        status: autosaveStatus,
        schedule: scheduleAutosave,
        flush: flushAutosave,
        reset: resetAutosave,
    } = useCanvasAutosave({ save: handleSave });

    // Apply one canvas:update / canvas:present frame — from the WebSocket OR
    // from a local store-sync (lib/canvasSync). One guarded path for both.
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
            } else {
                const content = typeof data === 'string'
                    ? data
                    // Email canvases carry the composer body under data.body;
                    // stringifying the {to, subject, body} object made Send
                    // dispatch JSON instead of the drafted text.
                    : (component === 'email' && typeof data?.body === 'string'
                        ? data.body
                        : ((data?.content as string) || JSON.stringify(data ?? {}, null, 2)));

                const payloadKey = `${canvas_id || id || ""}|${component || ""}|${version ?? ""}|${content}`;
                if (payloadKey === lastPayloadKeyRef.current) return;
                lastPayloadKeyRef.current = payloadKey;

                // Autosave echo-guard: PUT /api/canvas/{id} (the email save
                // path) broadcasts the just-saved content back over WS.
                // Applying that echo verbatim would reset the editor to the
                // saved snapshot and drop any keystrokes typed after the
                // autosave fired — skip it; local state stays authoritative.
                if (lastSavedSigRef.current !== null && `${component || ""}|${content}` === lastSavedSigRef.current) {
                    return;
                }

                // A genuinely new payload supersedes local edits — drop any
                // pending autosave so its timer can't fire afterwards and
                // re-write the superseded content.
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

                if (component === "email") {
                    setEmailBody(content);
                    // Signature may already be loaded (later payloads on the
                    // same mount) — apply immediately to the fresh body.
                    if (emailSignature) applySignature(emailSignature);
                }

                if (component === "email") {
                    // To/Cc/Subject ride in `metadata` on the present flow
                    // and in `data` on update broadcasts / detail-page reads.
                    const to = (typeof data?.to === "string" ? data.to : "") || metadata?.to || "";
                    const cc = (typeof data?.cc === "string" ? data.cc : "") || metadata?.cc || "";
                    const subject = (typeof data?.subject === "string" ? data.subject : "") || metadata?.subject || "";
                    setEmailMetadata({ to, cc, subject });

                    // Reply auto-fill: a Re:/Fw: subject with no recipient
                    // yet resolves the original thread from the mailbox and
                    // prefills To (+Cc). Best-effort, once per payload, and
                    // never overwrites something the user already typed.
                    if (!to.trim() && /^(re|fw|fwd)\s*:/i.test(subject) && replyResolveRef.current !== payloadKey) {
                        replyResolveRef.current = payloadKey;
                        (async () => {
                            try {
                                const { apiClient } = await import("@/lib/api");
                                // The body's greeting is the secondary
                                // signal when the subject was invented.
                                const res = await apiClient.get(
                                    `/api/canvas/email/resolve-reply?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(content.slice(0, 500))}`
                                );
                                const resolved = (res as any).data || res || {};
                                if (resolved?.to) {
                                    setEmailMetadata((prev) => ({
                                        ...prev,
                                        to: prev.to.trim() ? prev.to : String(resolved.to),
                                        cc: prev.cc.trim() ? prev.cc : String(resolved.cc || ""),
                                    }));
                                }
                            } catch {
                                // No mailbox / no thread match — the field
                                // stays free-text with autocomplete.
                            }
                        })();
                    }
                }

                if (component === "sheet") {
                    setSheetData(Array.isArray(data) ? data : (data.rows || [["", "", ""], ["", "", ""]]));
                }

                setHasUnsavedChanges(false);
            }
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [emailSignature, resetAutosave]);

    useEffect(() => {
        if (lastMessage) applyCanvasMessage(lastMessage);
    }, [lastMessage, applyCanvasMessage]);

    // Local store-sync convergence (lib/canvasSync): a chat turn flagged as a
    // canvas edit/action re-broadcasts the audit-trail content here, covering
    // the missed-WS-broadcast case (dead socket / throttled tab). Redundant
    // with the detail page's own loadCanvas refetch by design — the guards
    // dedupe identical payloads.
    useEffect(() => onCanvasRefresh((detail) => applyCanvasMessage(detail.message)), [applyCanvasMessage]);

    // To/Cc accept comma-separated lists (the autocomplete inserts them);
    // the send endpoint takes arrays.
    const splitRecipients = (raw: string): string[] =>
        raw.split(",").map((s) => s.trim()).filter(Boolean);

    const handleSendEmail = async () => {
        // Explicit confirm before dispatch — the send endpoint treats the
        // human click as policy authorization for allow/approve decisions,
        // so it should be a deliberate act, not a single accidental click.
        const to = splitRecipients(emailMetadata.to);
        const cc = splitRecipients(emailMetadata.cc);
        if (to.length === 0) {
            alert("Add at least one recipient in the To field before sending.");
            return;
        }
        if (!window.confirm(`Send email to ${to.join(", ")}${cc.length ? `\nCc: ${cc.join(", ")}` : ""}?`)) return;
        try {
            const { apiClient } = await import("@/lib/api");
            const res = await apiClient.post("/api/canvas/email/send", {
                to,
                cc,
                subject: emailMetadata.subject || "",
                body: localContentRef.current || "",
                canvas_id: state?.id || undefined,
            });
            const data = res?.data || {};
            if (data.success) {
                alert(data.status === "sent" ? "Email sent." : `Email status: ${data.status}`);
            } else {
                const reason = data.error || data.message || "unknown error";
                // Consent gap: the token predates a permission (Mail.Send) —
                // only a reconnect can grant it. Offer the one-click fix
                // instead of a dead end.
                if (data.needs_reconnect || /missing the Mail\.Send permission/i.test(reason)) {
                    if (window.confirm(`${reason}\n\nReconnect Outlook now?`)) {
                        const { getAuthToken } = await import("@/lib/auth-headers");
                        window.location.href = `/api/v1/auth/oauth/microsoft/authorize?token=${encodeURIComponent(getAuthToken() ?? "")}`;
                    }
                } else {
                    alert(`Send blocked: ${reason}`);
                }
            }
        } catch (e: any) {
            alert(`Send failed: ${e?.response?.data?.message || e?.message || "unknown error"}`);
        }
    };

    // Manual retype — the escape hatch when the agent-chat classifier picked
    // the wrong canvas type. Converts the content into the target's shape,
    // swaps the rendered component, and persists a pinned audit row so the
    // choice survives reloads and read-time coercion. Note: lastPayloadKeyRef
    // is deliberately NOT updated — the switch isn't a payload delivery, and
    // the guard must keep absorbing stale re-deliveries of the old payload
    // until the PUT's WS broadcast lands with the new type.
    const handleTypeSwitch = (target: SwitchableCanvasType) => {
        if (!state) return;
        const conversion = switchCanvasType(target, {
            component: state.component,
            data: state.data,
            text: localContentRef.current,
            email: emailMetadata,
            sheet: sheetData,
            title: state.title,
        });

        setState({ ...state, component: conversion.component, data: conversion.data });
        localContentRef.current = conversion.text;
        setEmailBody(conversion.component === "email" ? conversion.text : "");
        setEmailMetadata({ to: conversion.email.to, cc: conversion.email.cc, subject: conversion.email.subject });
        setSheetData(conversion.sheet);
        setSignatureOpen(false);
        setShowPreview(false);
        setHasUnsavedChanges(!state.id);
        // The switch persists itself (or intentionally stays unsaved until
        // an id exists) — a pending autosave would only re-write what
        // persistCanvasTypeSwitch just stored.
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
                    cc: emailMetadata.cc,
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
        <div data-testid={CANVAS.CONTAINER} className="flex flex-col h-full bg-white dark:bg-[#020617] relative animate-in fade-in duration-500 overflow-hidden">
            {/* Header needs z-30: backdrop-blur-sm creates a stacking
                context, so without it the popover menus opened from this bar
                (✎ Sig, type switcher) paint UNDER the content area below,
                which is position:relative and later in DOM order. */}
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
                    {state.component === "email" && (
                        <div className="relative">
                            <button
                                onClick={() => setSignatureOpen(!signatureOpen)}
                                title="Default email signature"
                                data-testid="canvas-signature-button"
                                className="h-8 px-3 rounded border border-zinc-200 dark:border-white/10 hover:bg-zinc-100 dark:hover:bg-white/5 text-zinc-600 dark:text-zinc-300 text-[11px] font-medium transition-colors flex items-center gap-1.5"
                            >
                                ✎ Sig
                            </button>
                            {signatureOpen && (
                                <div className="absolute right-0 top-full mt-1 z-30 w-80 bg-white dark:bg-[#1e293b] border border-zinc-200 dark:border-white/10 rounded-lg shadow-lg p-3 space-y-2">
                                    <p className="text-[10px] text-zinc-500" data-testid="canvas-signature-source">
                                        Default signature — {signatureSource === "stored" ? "custom (overrides the integration default)" : "from your Outlook sent mail"}
                                    </p>
                                    {/* Rich WYSIWYG editor: styled signatures
                                        (bold/italic/links/colors/rules) are a
                                        supported feature — saved as sanitized
                                        HTML and rendered by the mail sink. */}
                                    <SignatureEditor
                                        value={emailSignature ?? ""}
                                        onChange={(html) => { setEmailSignature(html); setSignatureSource("stored"); }}
                                    />
                                    <div className="flex gap-2 justify-end">
                                        <button
                                            onClick={async () => {
                                                try {
                                                    const { apiClient } = await import("@/lib/api");
                                                    await apiClient.put("/api/canvas/email/signature", { signature: emailSignature ?? "" });
                                                    setSignatureOpen(false);
                                                } catch { /* keep the popover open on failure */ }
                                            }}
                                            data-testid="canvas-signature-save"
                                            className="px-2 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white text-[11px]"
                                        >
                                            Save as default
                                        </button>
                                        <button
                                            onClick={() => { if (emailSignature?.trim()) applySignature(emailSignature, true); setSignatureOpen(false); }}
                                            className="px-2 py-1 rounded border border-zinc-200 dark:border-white/10 text-zinc-600 dark:text-zinc-300 text-[11px]"
                                        >
                                            Insert into email
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
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
                        aria-label="Close canvas"
                        data-testid={CANVAS.CLOSE_BUTTON}
                        className="h-8 w-8 flex items-center justify-center rounded-full hover:bg-zinc-200 dark:hover:bg-zinc-800 transition-colors"
                    >
                        <X className="h-4 w-4 text-zinc-500" />
                    </button>
                </div>
            </div>

            <div
                className="flex-1 overflow-hidden relative"
                // Leaving the editor (e.g. to type in the co-editor chat)
                // must not race the 3s autosave window: the backend plans
                // canvas edits against the durable store, so keystrokes
                // still pending autosave would be invisible to it.
                onBlur={() => { if (hasUnsavedChanges) void flushAutosave(); }}
            >
                <CanvasContent
                    component={state.component}
                    data={state.data}
                    canvasId={state.id}
                    canvasTitle={state.title}
                    emailMetadata={emailMetadata}
                    setEmailMetadata={(m) => { setEmailMetadata(m); setHasUnsavedChanges(true); scheduleAutosave(); }}
                    emailBody={emailBody}
                    onEmailBodyChange={(v) => { setEmailBody(v); localContentRef.current = v; setHasUnsavedChanges(true); scheduleAutosave(); }}
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
                    <button className="text-[10px] text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 flex items-center gap-1 transition-colors">
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
    emailBody,
    onEmailBodyChange,
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
    emailBody: string;
    onEmailBodyChange: (v: string) => void;
    sheetData: any[][];
    setSheetData: (d: any[][]) => void;
    showPreview: boolean;
    setShowPreview: (s: boolean) => void;
    onContentChange: (val: string) => void
}) {
    if (data == null && component !== "sheet" && component !== "form") return <div className="text-zinc-500 p-4">No data to display</div>;

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
                        <EmailRecipientField
                            label="To:"
                            value={emailMetadata.to}
                            onChange={(to) => setEmailMetadata({ ...emailMetadata, to })}
                            placeholder="recipient@example.com"
                            testId="canvas-email-to"
                        />
                        <EmailRecipientField
                            label="Cc:"
                            value={emailMetadata.cc}
                            onChange={(cc) => setEmailMetadata({ ...emailMetadata, cc })}
                            placeholder="cc@example.com"
                            testId="canvas-email-cc"
                        />
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
                    {/* WYSIWYG body editor — Outlook-style styling (fonts,
                        sizes, colors, links, lists, alignment) that renders
                        in the outgoing email via the HTML send sink. */}
                    <div className="flex-1 overflow-y-auto">
                        <RichTextEditor
                            value={emailBody}
                            onChange={(html) => onEmailBodyChange(html || "")}
                            testIdPrefix="canvas-email-body"
                            minHeight="320px"
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

