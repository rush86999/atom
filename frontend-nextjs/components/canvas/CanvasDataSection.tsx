"use client";

import React, { useCallback, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, HardDriveUpload, Folder, ChevronRight } from "lucide-react";
import { uploadCanvasData } from "@/lib/canvas-api";

/**
 * Load data into a canvas's world — step 3 of the canvas journey, gated on
 * the attached hire (step 2). Everything here is DISABLED until a hire is
 * attached, and the backend enforces the same gate (409 NO_AGENT_ON_CANVAS)
 * — the UI state is guidance, never the only guard.
 *
 * Sources: direct file upload (role-tagged ingest) and folder picks from the
 * connected drives (Zoho WorkDrive / Google Drive / OneDrive — the ingest
 * endpoints run as background jobs and are polled to completion).
 */

type DriveId = "zoho" | "gdrive" | "onedrive";

interface DriveFolderEntry {
    id: string;
    name: string;
}

const DRIVES: { id: DriveId; label: string }[] = [
    { id: "zoho", label: "Zoho WorkDrive" },
    { id: "gdrive", label: "Google Drive" },
    { id: "onedrive", label: "OneDrive" },
];

const DRIVE_ROOT_LABEL: Record<DriveId, string> = {
    zoho: "My Workspace",
    gdrive: "My Drive",
    onedrive: "My Files",
};

/** Result line shown after a load (kept terse — the Journey panel has the audit). */
interface LoadNotice {
    kind: "ok" | "error" | "info";
    text: string;
}

export function CanvasDataSection({
    canvasId,
    hireAttached,
}: {
    canvasId: string;
    hireAttached: boolean;
}) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [uploading, setUploading] = useState(false);
    const [notice, setNotice] = useState<LoadNotice | null>(null);

    // Drive picker state
    const [drive, setDrive] = useState<DriveId | null>(null);
    const [folders, setFolders] = useState<DriveFolderEntry[]>([]);
    const [path, setPath] = useState<DriveFolderEntry[]>([]); // breadcrumb stack
    const [loadingFolders, setLoadingFolders] = useState(false);
    const [selected, setSelected] = useState<Record<string, DriveFolderEntry>>({});
    const [startingJob, setStartingJob] = useState(false);
    const [jobStatus, setJobStatus] = useState<string | null>(null);

    const gatedHint = "Attach an agent to load data.";

    // ── direct upload ───────────────────────────────────────────────────
    const handleUpload = useCallback(async (file: File) => {
        setUploading(true);
        setNotice(null);
        try {
            const res = await uploadCanvasData(canvasId, file);
            const ing = res?.ingestion;
            if (ing?.status === "ingested") {
                setNotice({ kind: "ok", text: `Loaded “${file.name}” — ${res.role ? `${res.role} hire` : "agent"} can recall it.` });
            } else if (ing?.status === "skipped" && (ing?.reason || ing?.status) === "unchanged") {
                setNotice({ kind: "ok", text: `“${file.name}” is already in memory — content unchanged since the last ingest.` });
            } else {
                setNotice({ kind: "info", text: `“${file.name}” was not ingested (${ing?.reason || ing?.status || "unsupported"}).` });
            }
        } catch (e: any) {
            const body = e?.response?.data;
            const msg = body?.error?.message || body?.detail?.message || body?.detail || e?.message;
            setNotice({ kind: "error", text: msg || "Upload failed." });
        } finally {
            setUploading(false);
        }
    }, [canvasId]);

    // ── drive pickers ───────────────────────────────────────────────────

    const listFolders = useCallback(async (d: DriveId, parentId: string | null): Promise<DriveFolderEntry[]> => {
        if (d === "zoho") {
            const { apiClient } = await import("@/lib/api");
            const res = await apiClient.post("/api/zoho-workdrive/files/list", {
                parent_id: parentId || "root",
                recursive: false,
            });
            const rows = res.data?.data || [];
            return rows.filter((r: any) => r.type === "folder").map((r: any) => ({ id: r.id, name: r.name }));
        }
        if (d === "gdrive") {
            const { apiClient } = await import("@/lib/api");
            const res = await apiClient.get("/api/gdrive/list-files", { params: { folder_id: parentId || undefined } });
            if (res.data?.error) throw new Error(res.data.error === "not_connected" ? "Google Drive isn't connected — connect it from Integrations." : res.data.error);
            return (res.data?.files || [])
                .filter((f: any) => f.isFolder)
                .map((f: any) => ({ id: f.id, name: f.name }));
        }
        // onedrive
        const { apiClient } = await import("@/lib/api");
        const res = await apiClient.get("/api/onedrive/list-files", { params: { folder_id: parentId || undefined } });
        if (res.data?.error) throw new Error(res.data.error === "not_connected" ? "OneDrive isn't connected — connect it from Integrations." : res.data.error);
        return (res.data?.files || [])
            .filter((f: any) => f.is_folder)
            .map((f: any) => ({ id: f.id, name: f.name }));
    }, []);

    const openDrive = useCallback(async (d: DriveId) => {
        setDrive(d);
        setSelected({});
        setPath([]);
        setNotice(null);
        setLoadingFolders(true);
        try {
            setFolders(await listFolders(d, null));
        } catch (e: any) {
            setNotice({ kind: "error", text: e?.message || "Couldn't list the drive." });
            setDrive(null);
        } finally {
            setLoadingFolders(false);
        }
    }, [listFolders]);

    const navigateInto = useCallback(async (folder: DriveFolderEntry) => {
        if (!drive) return;
        setLoadingFolders(true);
        try {
            setFolders(await listFolders(drive, folder.id));
            setPath(p => [...p, folder]);
        } catch (e: any) {
            setNotice({ kind: "error", text: e?.message || "Couldn't open the folder." });
        } finally {
            setLoadingFolders(false);
        }
    }, [drive, listFolders]);

    const navigateTo = useCallback(async (depth: number) => {
        if (!drive) return;
        setLoadingFolders(true);
        try {
            const parent = depth > 0 ? path[depth - 1] : null;
            setFolders(await listFolders(drive, parent?.id ?? null));
            setPath(p => p.slice(0, depth));
            setSelected({});
        } catch (e: any) {
            setNotice({ kind: "error", text: e?.message || "Couldn't open the folder." });
        } finally {
            setLoadingFolders(false);
        }
    }, [drive, path, listFolders]);

    const pollJob = useCallback(async (d: DriveId, jobId: string, folderCount: number) => {
        const { apiClient } = await import("@/lib/api");
        const base = d === "zoho" ? "/api/zoho-workdrive" : d === "gdrive" ? "/api/gdrive" : "/api/onedrive";
        for (let attempt = 0; attempt < 120; attempt++) {
            await new Promise(r => setTimeout(r, 3000));
            try {
                const res = await apiClient.get(`${base}/ingest/jobs/${jobId}`);
                const job = res.data?.data || {};
                if (job.status === "completed") {
                    const tally = job.result?.files_ingested ?? job.result?.files_ingested ?? job.result?.ingested;
                    setNotice({ kind: "ok", text: `Loaded ${tally ?? "?"} file${tally === 1 ? "" : "s"} from ${folderCount} folder${folderCount === 1 ? "" : "s"} into this canvas's world.` });
                    setJobStatus(null);
                    return;
                }
                if (job.status === "failed") {
                    setNotice({ kind: "error", text: "The drive load failed — check Integrations for the job's error." });
                    setJobStatus(null);
                    return;
                }
                setJobStatus(job.status || "running");
            } catch {
                // transient poll errors: keep waiting
            }
        }
        setJobStatus(null);
        setNotice({ kind: "info", text: "The load is still running in the background — check Integrations for progress." });
    }, []);

    const loadSelectedFolders = useCallback(async () => {
        if (!drive) return;
        const folderIds = Object.keys(selected);
        const foldersPayload = Object.values(selected);
        setStartingJob(true);
        setNotice(null);
        try {
            const { apiClient } = await import("@/lib/api");
            let jobId: string | undefined;
            if (drive === "zoho") {
                const res = await apiClient.post("/api/zoho-workdrive/ingest-folder", {
                    folder_ids: folderIds,
                    canvas_id: canvasId,
                });
                jobId = res.data?.job_id;
            } else if (drive === "gdrive") {
                const res = await apiClient.post("/api/gdrive/ingest-folders", {
                    folders: foldersPayload.map(f => ({ id: f.id, name: f.name })),
                    canvas_id: canvasId,
                });
                jobId = res.data?.job_id;
            } else {
                const res = await apiClient.post("/api/onedrive/ingest-folders", {
                    folders: foldersPayload.map(f => ({ id: f.id, name: f.name })),
                    canvas_id: canvasId,
                });
                jobId = res.data?.job_id;
            }
            if (!jobId) {
                // started_payload always carries job_id; if it's missing the
                // request was rejected upstream (or coalesced into a job the
                // poller can't see) — say so instead of polling nothing.
                setNotice({ kind: "error", text: "The drive didn't start a load job." });
            } else {
                setNotice({ kind: "info", text: "Load started — working in the background…" });
                void pollJob(drive, jobId, folderIds.length);
            }
        } catch (e: any) {
            const body = e?.response?.data;
            const msg = body?.error?.message || body?.detail?.message || body?.detail || e?.message;
            setNotice({ kind: "error", text: msg || "Couldn't start the load." });
        } finally {
            setStartingJob(false);
        }
    }, [drive, selected, canvasId, pollJob]);

    const selectedCount = Object.keys(selected).length;
    return (
        <div className="border-b bg-muted/20 px-3 py-2" data-testid="canvas-data-section">
            <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Load data</span>

                <input
                    ref={fileInputRef}
                    type="file"
                    className="hidden"
                    onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) void handleUpload(f);
                        e.target.value = "";
                    }}
                />
                <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs"
                    disabled={!hireAttached || uploading}
                    title={hireAttached ? "Upload a file into this canvas's world" : gatedHint}
                    onClick={() => fileInputRef.current?.click()}
                    data-testid="canvas-upload-data-button"
                >
                    {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <HardDriveUpload className="h-3.5 w-3.5" />}
                    Upload file
                </Button>

                {!hireAttached && (
                    <span className="text-[11px] text-muted-foreground" data-testid="data-gated-hint">
                        {gatedHint}
                    </span>
                )}

                {hireAttached && DRIVES.map(d => (
                    <Button
                        key={d.id}
                        variant={drive === d.id ? "default" : "ghost"}
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => (drive === d.id ? setDrive(null) : void openDrive(d.id))}
                        data-testid={`drive-tab-${d.id}`}
                    >
                        <Folder className="h-3.5 w-3.5 mr-1" />
                        {d.label}
                    </Button>
                ))}
            </div>

            {notice && (
                <p
                    role="status"
                    className={`mt-1.5 text-[11px] rounded px-2 py-1 ${
                        notice.kind === "error"
                            ? "text-red-600 bg-red-50 dark:bg-red-900/20"
                            : notice.kind === "ok"
                                ? "text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20"
                                : "text-muted-foreground bg-muted"
                    }`}
                    data-testid="canvas-data-notice"
                >
                    {notice.text}
                </p>
            )}

            {hireAttached && drive && (
                <div className="mt-2 text-xs" data-testid={`drive-picker-${drive}`}>
                    {/* Breadcrumb */}
                    <div className="flex items-center gap-1 flex-wrap mb-1.5">
                        <button className="hover:underline" onClick={() => void navigateTo(0)}>
                            {DRIVE_ROOT_LABEL[drive]}
                        </button>
                        {path.map((p, i) => (
                            <span key={p.id} className="flex items-center gap-1">
                                <ChevronRight className="h-3 w-3 text-muted-foreground" />
                                <button className="hover:underline" onClick={() => void navigateTo(i + 1)}>{p.name}</button>
                            </span>
                        ))}
                    </div>

                    {loadingFolders ? (
                        <p className="text-muted-foreground flex items-center gap-1.5 py-2">
                            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Listing folders…
                        </p>
                    ) : folders.length === 0 ? (
                        <p className="text-muted-foreground py-2">No subfolders here — select this level's folders from a parent.</p>
                    ) : (
                        <ul className="grid grid-cols-2 gap-1">
                            {folders.map(f => {
                                const isSelected = Boolean(selected[f.id]);
                                return (
                                    <li key={f.id} className="flex items-center gap-1 border rounded px-2 py-1">
                                        <button
                                            className="flex items-center gap-1.5 min-w-0 flex-1 hover:underline"
                                            onClick={() => void navigateInto(f)}
                                            title={`Open ${f.name}`}
                                        >
                                            <Folder className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                                            <span className="truncate">{f.name}</span>
                                        </button>
                                        <button
                                            className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded border ${isSelected ? "bg-primary text-primary-foreground border-primary" : "hover:bg-accent"}`}
                                            onClick={() => setSelected(s => {
                                                const next = { ...s };
                                                if (next[f.id]) delete next[f.id];
                                                else next[f.id] = f;
                                                return next;
                                            })}
                                            data-testid={`select-folder-${f.id}`}
                                        >
                                            {isSelected ? "Selected" : "Select"}
                                        </button>
                                    </li>
                                );
                            })}
                        </ul>
                    )}

                    <div className="mt-2 flex items-center gap-2">
                        <Button
                            size="sm"
                            className="h-7 text-xs"
                            disabled={selectedCount === 0 || startingJob}
                            onClick={() => void loadSelectedFolders()}
                            data-testid="load-selected-folders"
                        >
                            {startingJob ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <HardDriveUpload className="h-3.5 w-3.5 mr-1" />}
                            Load {selectedCount || ""} folder{selectedCount === 1 ? "" : "s"}
                        </Button>
                        {jobStatus && <span className="text-[11px] text-muted-foreground">Job {jobStatus}…</span>}
                    </div>
                </div>
            )}
        </div>
    );
}
