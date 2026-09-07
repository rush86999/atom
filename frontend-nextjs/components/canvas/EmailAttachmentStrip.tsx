/**
 * EmailAttachmentStrip — attachment chips for the email canvas composer.
 *
 * Rendered by both hosts (chat canvas-host + full-page CanvasPanel). Chips
 * carry the backend's attachment record (docs/canvas/EMAIL_ATTACHMENT_CRUD_PLAN.md
 * §D2): staged uploads download from the server, received ones stream through
 * from the mailbox. "Add to memory" triggers on-demand ingestion; the result
 * arrives on this same component via the WS canvas:update
 * (action="email_attachments") broadcast the backend emits on every mutation.
 */
import React, { useRef, useState } from "react";
import { useRouter } from "next/router";
import { FileText, Paperclip, Plus, Trash2, Download, Brain, Loader2, FileOutput } from "lucide-react";

export interface EmailAttachmentRecord {
    attachment_id: string;
    message_id?: string | null;
    provider?: string;
    filename: string;
    content_type?: string;
    size?: number;
    origin?: "received" | "staged" | "agent_added";
    ingestion?: { status?: string; doc_id?: string | null; ingested_at?: string | null } | null;
    sent_at?: string | null;
    staged_deleted?: boolean;
}

interface EmailAttachmentStripProps {
    canvasId?: string;
    attachments: EmailAttachmentRecord[];
    /** Sent state hides mutating actions (the email has left the draft). */
    readOnly?: boolean;
}

function formatSize(bytes?: number): string {
    if (!bytes && bytes !== 0) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function EmailAttachmentStrip({ canvasId, attachments, readOnly = false }: EmailAttachmentStripProps) {
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const router = useRouter();
    const [uploading, setUploading] = useState(false);
    const [ingesting, setIngesting] = useState<string | null>(null);
    const [openingCanvas, setOpeningCanvas] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    if (!attachments.length && readOnly) return null;

    const isPdf = (att: EmailAttachmentRecord) =>
        (att.content_type || "").includes("pdf") ||
        (att.filename || "").toLowerCase().endsWith(".pdf");

    // Inbound loop closure: turn a PDF attachment into an editable PDF canvas
    // (received attachments stream through from the mailbox server-side).
    const openAsPdfCanvas = async (att: EmailAttachmentRecord) => {
        if (!canvasId) return;
        setOpeningCanvas(att.attachment_id);
        setError(null);
        try {
            const { createPdfFromEmailAttachment } = await import("@/lib/pdf-canvas-api");
            const res = await createPdfFromEmailAttachment(canvasId, att.attachment_id);
            if (res?.canvas_id) router.push(`/canvas/${res.canvas_id}`);
        } catch (e: any) {
            setError(e?.response?.data?.error?.message || e?.message || "Could not open as PDF canvas");
            setOpeningCanvas(null);
        }
    };

    const upload = async (files: FileList | null) => {
        if (!files?.length || !canvasId) return;
        setUploading(true);
        setError(null);
        try {
            const { apiClient } = await import("@/lib/api");
            const form = new FormData();
            Array.from(files).forEach((f) => form.append("files", f));
            await apiClient.post(`/api/canvas/email/${canvasId}/attachments`, form, {
                headers: { "Content-Type": "multipart/form-data" },
                retry: false,
            });
            // The backend broadcasts canvas:update (action=email_attachments);
            // the WS frame updates the chip list. No local merge needed.
        } catch (e: any) {
            setError(e?.response?.data?.message || e?.message || "Upload failed");
        } finally {
            setUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = "";
        }
    };

    const remove = async (attachmentId: string) => {
        if (!canvasId) return;
        try {
            const { apiClient } = await import("@/lib/api");
            await apiClient.delete(`/api/canvas/email/${canvasId}/attachments/${attachmentId}`, { retry: false });
        } catch (e: any) {
            setError(e?.response?.data?.message || e?.message || "Remove failed");
        }
    };

    const download = async (att: EmailAttachmentRecord) => {
        if (!canvasId) return;
        try {
            const { apiClient } = await import("@/lib/api");
            const res = await apiClient.get(
                `/api/canvas/email/${canvasId}/attachments/${att.attachment_id}/download`,
                { responseType: "blob" },
            );
            const url = URL.createObjectURL(res.data as Blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = att.filename || "attachment";
            a.click();
            URL.revokeObjectURL(url);
        } catch (e: any) {
            setError(e?.response?.data?.message || e?.message || "Download failed");
        }
    };

    const ingest = async (attachmentId: string) => {
        if (!canvasId) return;
        setIngesting(attachmentId);
        setError(null);
        try {
            const { apiClient } = await import("@/lib/api");
            await apiClient.post(
                `/api/canvas/email/${canvasId}/attachments/${attachmentId}/ingest`,
                {},
                { retry: false },
            );
        } catch (e: any) {
            setError(e?.response?.data?.message || e?.message || "Add to memory failed");
        } finally {
            setIngesting(null);
        }
    };

    return (
        <div className="px-4 py-2 border-b border-zinc-100 dark:border-white/5" data-testid="email-attachment-strip">
            <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider flex items-center gap-1">
                    <Paperclip className="h-3 w-3" /> Attachments
                </span>
                {attachments.map((att) => {
                    const indexed = att.ingestion?.status === "indexed";
                    return (
                        <div
                            key={att.attachment_id}
                            className="group flex items-center gap-1.5 pl-2 pr-1 py-1 rounded-full bg-zinc-100 dark:bg-white/5 border border-zinc-200 dark:border-white/10 text-[11px] text-zinc-700 dark:text-zinc-300"
                        >
                            <FileText className="h-3 w-3 text-zinc-400" />
                            <span className="max-w-[160px] truncate font-medium" title={att.filename}>
                                {att.filename}
                            </span>
                            {formatSize(att.size) && <span className="text-zinc-400">{formatSize(att.size)}</span>}
                            {att.origin === "received" && (
                                <span className="text-[9px] uppercase tracking-wide text-sky-500">mail</span>
                            )}
                            {indexed && (
                                <span title="Indexed in memory">
                                    <Brain className="h-3 w-3 text-emerald-500" />
                                </span>
                            )}
                            <button
                                onClick={() => download(att)}
                                title="Download"
                                className="p-0.5 rounded-full hover:bg-zinc-200 dark:hover:bg-white/10 text-zinc-500"
                            >
                                <Download className="h-3 w-3" />
                            </button>
                            {isPdf(att) && (
                                <button
                                    onClick={() => openAsPdfCanvas(att)}
                                    title="Open as PDF canvas"
                                    disabled={openingCanvas === att.attachment_id}
                                    data-testid={`attachment-open-pdf-${att.attachment_id}`}
                                    className="p-0.5 rounded-full hover:bg-zinc-200 dark:hover:bg-white/10 text-sky-500 disabled:opacity-50"
                                >
                                    {openingCanvas === att.attachment_id ? (
                                        <Loader2 className="h-3 w-3 animate-spin" />
                                    ) : (
                                        <FileOutput className="h-3 w-3" />
                                    )}
                                </button>
                            )}
                            {!readOnly && (
                                <button
                                    onClick={() => ingest(att.attachment_id)}
                                    title={indexed ? "Re-index in memory" : "Add to memory"}
                                    disabled={ingesting === att.attachment_id}
                                    className="p-0.5 rounded-full hover:bg-zinc-200 dark:hover:bg-white/10 text-zinc-500 disabled:opacity-50"
                                >
                                    {ingesting === att.attachment_id ? (
                                        <Loader2 className="h-3 w-3 animate-spin" />
                                    ) : (
                                        <Brain className="h-3 w-3" />
                                    )}
                                </button>
                            )}
                            {!readOnly && (
                                <button
                                    onClick={() => remove(att.attachment_id)}
                                    title={att.provider === "local" ? "Remove file" : "Detach from draft"}
                                    className="p-0.5 rounded-full hover:bg-red-100 dark:hover:bg-red-500/10 text-zinc-500 hover:text-red-500"
                                >
                                    <Trash2 className="h-3 w-3" />
                                </button>
                            )}
                        </div>
                    );
                })}
                {!readOnly && canvasId && (
                    <>
                        <input
                            ref={fileInputRef}
                            type="file"
                            multiple
                            className="hidden"
                            onChange={(e) => upload(e.target.files)}
                            data-testid="email-attachment-input"
                        />
                        <button
                            onClick={() => fileInputRef.current?.click()}
                            disabled={uploading}
                            title="Attach files"
                            className="flex items-center gap-1 px-2 py-1 rounded-full border border-dashed border-zinc-300 dark:border-white/20 text-[11px] text-zinc-500 hover:border-indigo-400 hover:text-indigo-500 transition-colors disabled:opacity-50"
                        >
                            {uploading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
                            Attach
                        </button>
                    </>
                )}
            </div>
            {error && <p className="mt-1 text-[11px] text-red-500">{error}</p>}
        </div>
    );
}
