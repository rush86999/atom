/**
 * PDF canvas API — thin wrappers over the /api/canvas/pdf routes.
 *
 * The canvas's durable state rides the standard canvas audit trail
 * (GET /api/canvas/{id} → content = PdfCanvasState); only the file bytes and
 * the lifecycle mutations are PDF-specific here. Auth rides the shared
 * apiClient (Bearer token attached by its interceptor).
 */

export interface PdfCanvasVersion {
    hash: string;
    action: string;
    author: string;
    at: string;
}

export interface PdfCanvasState {
    file: {
        hash: string;
        page_count: number;
        size_bytes: number;
        filename: string;
    };
    versions: PdfCanvasVersion[];
    lifecycle: {
        state: "drafting" | "in_review" | "approved" | "sent" | "archived";
        approved_by?: string | null;
        approved_at?: string | null;
        last_attachment?: {
            email_canvas_id: string;
            attachment_id: string;
            hash: string;
            at: string;
        };
    };
    source: "upload" | "blank";
}

export interface PdfPageSpec {
    src_index: number;
    rotation: number;
}

/** Unwrap the state from whatever shape the canvas read/WS frame delivered. */
export function unwrapPdfState(data: any): PdfCanvasState | null {
    const candidate = data?.file ? data : (data?.content?.file ? data.content : null);
    if (!candidate?.file?.hash) return null;
    return candidate as PdfCanvasState;
}

export async function fetchPdfBytes(canvasId: string, hash?: string): Promise<Blob> {
    const { apiClient } = await import("@/lib/api");
    const params = hash ? `?hash=${encodeURIComponent(hash)}` : "";
    const res = await apiClient.get(`/api/canvas/pdf/${canvasId}/file${params}`, {
        responseType: "blob",
    });
    return res.data as Blob;
}

export async function createBlankPdf(title?: string): Promise<{ canvas_id: string }> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.post("/api/canvas/pdf/create", { title: title || null });
    return res.data;
}

export async function createPdfFromUpload(file: File): Promise<{ canvas_id: string }> {
    const { apiClient } = await import("@/lib/api");
    const form = new FormData();
    form.append("file", file);
    const res = await apiClient.post("/api/canvas/pdf/create/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
    });
    return res.data;
}

export async function applyPageOps(
    canvasId: string,
    pages: PdfPageSpec[],
    baseHash: string,
): Promise<{ state: PdfCanvasState }> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.post(`/api/canvas/pdf/${canvasId}/pages`, {
        pages,
        base_hash: baseHash,
    });
    return res.data;
}

export async function mergePdfUpload(canvasId: string, file: File): Promise<{ state: PdfCanvasState }> {
    const { apiClient } = await import("@/lib/api");
    const form = new FormData();
    form.append("file", file);
    const res = await apiClient.post(`/api/canvas/pdf/${canvasId}/merge/upload`, form, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
    });
    return res.data;
}

export async function mergePdfCanvas(canvasId: string, fromCanvasId: string): Promise<{ state: PdfCanvasState }> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.post(`/api/canvas/pdf/${canvasId}/merge/canvas`, {
        from_canvas_id: fromCanvasId,
    });
    return res.data;
}

export type PdfLifecycleTransition = "submit_review" | "approve" | "reopen" | "archive";

export async function transitionLifecycle(
    canvasId: string,
    transition: PdfLifecycleTransition,
): Promise<{ state: PdfCanvasState }> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.post(`/api/canvas/pdf/${canvasId}/lifecycle/${transition}`, {});
    return res.data;
}

export async function attachPdfToEmail(
    canvasId: string,
    flatten?: boolean,
    emailCanvasId?: string,
): Promise<{ email_canvas_id: string; created_email_canvas: boolean; filename: string; flattened?: boolean }> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.post(`/api/canvas/pdf/${canvasId}/attach-to-email`, {
        flatten: !!flatten,
        email_canvas_id: emailCanvasId || null,
    });
    return res.data;
}

// ── P3/P4 surface ────────────────────────────────────────────────────────

export async function createPdfFromEmailAttachment(
    emailCanvasId: string,
    attachmentId: string,
): Promise<{ canvas_id: string }> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.post("/api/canvas/pdf/create/from-email-attachment", {
        email_canvas_id: emailCanvasId,
        attachment_id: attachmentId,
    });
    return res.data;
}

export async function extractText(
    canvasId: string,
    ocr = false,
): Promise<{ pages: { page: number; text: string }[]; ocr?: boolean; truncated?: boolean }> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.post(`/api/canvas/pdf/${canvasId}/extract-text${ocr ? "?ocr=true" : ""}`);
    return res.data;
}

export async function getFormFields(
    canvasId: string,
): Promise<{ fields: Record<string, { type: string; value: string | null }> }> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.get(`/api/canvas/pdf/${canvasId}/form-fields`);
    return res.data;
}

export async function setFormFields(
    canvasId: string,
    values: Record<string, string>,
    baseHash: string,
): Promise<{ state: PdfCanvasState }> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.post(`/api/canvas/pdf/${canvasId}/form`, {
        values,
        base_hash: baseHash,
    });
    return res.data;
}

export async function flattenForm(canvasId: string): Promise<{ state: PdfCanvasState }> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.post(`/api/canvas/pdf/${canvasId}/flatten`);
    return res.data;
}

export async function redactText(
    canvasId: string,
    items: { page: number; text: string }[],
): Promise<{ state: PdfCanvasState }> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.post(`/api/canvas/pdf/${canvasId}/redact`, { items });
    return res.data;
}

export async function stampSignature(
    canvasId: string,
    signatureLines: string[],
    label: string,
    page = 0,
): Promise<{ state: PdfCanvasState }> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.post(`/api/canvas/pdf/${canvasId}/sign`, {
        signature_lines: signatureLines,
        page,
        label,
    });
    return res.data;
}

export async function archiveToOnedrive(
    canvasId: string,
    folderPath = "",
): Promise<{ file_id?: string; filename?: string }> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.post(`/api/canvas/pdf/${canvasId}/archive/onedrive`, {
        folder_path: folderPath,
    });
    return res.data;
}

export async function sendToDocuSign(
    canvasId: string,
    signerEmail: string,
    signerName: string,
): Promise<{ envelope_id: string; status: string; filename: string }> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.post(`/api/canvas/pdf/${canvasId}/docusign`, {
        signer_email: signerEmail,
        signer_name: signerName,
    });
    return res.data;
}
