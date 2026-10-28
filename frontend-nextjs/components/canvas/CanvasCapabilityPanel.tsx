"use client";

/**
 * CanvasCapabilityPanel — the user-facing boundary for a canvas's declared
 * capabilities. It does not decide what is allowed: it renders the server's
 * effective-operation intersection and the structured receipts returned by
 * the adapters (selection rows, deterministic totals, certified assessments,
 * edit readback, export artifact identity).
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, Download, Loader2, Play, Save, ShieldCheck } from "lucide-react";
import { apiClient } from "@/lib/api";

interface CapabilityState {
    manifest: Record<string, any>;
    operations: { effective?: string[]; declared?: string[]; adapter?: string[]; resource?: string[] };
    revision?: number;
    policy_revision?: string;
    dataset?: { columns?: string[]; row_count?: number; source?: Record<string, any> };
}

const DEFAULT_MANIFEST: Record<string, any> = {
    schema_version: 1,
    base_component: "table",
    operations: ["read", "select", "calculate", "assess", "edit", "export", "bind"],
    data_binding: { subject_field: "", measure_field: "", status_field: "" },
    editable_fields: [],
    teaching_binding: { agent_id: "", scope_id: "" },
    decision_options: [],
    task_policy: "",
    outputs: ["xlsx"],
    required_approvals: [],
};

export function CanvasCapabilityPanel({
    canvasId,
    initial,
    onChanged,
}: {
    canvasId: string;
    initial?: CapabilityState | null;
    onChanged?: () => void;
}) {
    const [state, setState] = useState<CapabilityState | null>(initial || null);
    const [open, setOpen] = useState(false);
    const [manifestText, setManifestText] = useState(
        JSON.stringify(initial?.manifest || DEFAULT_MANIFEST, null, 2),
    );
    const [ask, setAsk] = useState("");
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState<string | null>(null);
    const [editRow, setEditRow] = useState("");
    const [editColumn, setEditColumn] = useState("");
    const [editValue, setEditValue] = useState("");
    const fileRef = useRef<HTMLInputElement | null>(null);

    const effective = useMemo(() => new Set(state?.operations?.effective || []), [state]);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const res = await apiClient.get(`/api/canvas/${canvasId}/capability`);
                if (cancelled || res.data?.success === false) return;
                setState(res.data);
                setManifestText(JSON.stringify(res.data.manifest || DEFAULT_MANIFEST, null, 2));
            } catch {
                // Not a capability canvas yet — the Enable action stays available.
            }
        })();
        return () => { cancelled = true; };
    }, [canvasId]);

    const call = useCallback(async (path: string, body?: any, method: "get" | "post" | "put" = "post") => {
        setBusy(path);
        setError(null);
        try {
            const res = method === "get"
                ? await apiClient.get(path)
                : method === "put"
                    ? await apiClient.put(path, body)
                    : await apiClient.post(path, body);
            if (res.data?.success === false) {
                throw new Error(res.data?.error?.message || "Operation refused");
            }
            setResult(res.data);
            if (res.data?.revision != null) {
                setState((prev) => prev ? {
                    ...prev,
                    revision: res.data.revision,
                    ...(res.data.source_version ? {
                        dataset: {
                            ...(prev.dataset || {}),
                            source: { ...(prev.dataset?.source || {}), source_version: res.data.source_version },
                        },
                    } : {}),
                } : prev);
            }
            return res.data;
        } catch (e: any) {
            const msg = e?.response?.data?.error?.message || e?.response?.data?.detail || e?.message || "Operation failed";
            setError(msg);
            return null;
        } finally {
            setBusy(null);
        }
    }, []);

    const refresh = useCallback(async () => {
        const data = await call(`/api/canvas/${canvasId}/capability`, undefined, "get");
        if (data) {
            setState(data);
            setManifestText(JSON.stringify(data.manifest || DEFAULT_MANIFEST, null, 2));
            onChanged?.();
        }
    }, [call, canvasId, onChanged]);

    const saveManifest = async (manifest?: any) => {
        let parsed = manifest;
        if (!parsed) {
            try { parsed = JSON.parse(manifestText); } catch { setError("Manifest is not valid JSON"); return; }
        }
        const data = await call(`/api/canvas/${canvasId}/capability/manifest`, { manifest: parsed }, "put");
        if (data) {
            setManifestText(JSON.stringify(data.manifest, null, 2));
            setState((prev) => ({ ...(prev || {}), manifest: data.manifest, operations: data.operations, revision: data.revision, policy_revision: data.policy_revision }));
            onChanged?.();
        }
    };

    const bindFile = async (file: File) => {
        const form = new FormData();
        form.append("file", file);
        setBusy("bind");
        setError(null);
        try {
            const res = await apiClient.post(`/api/canvas/${canvasId}/capability/bind`, form, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            if (res.data?.success === false) throw new Error(res.data?.error?.message || "Bind refused");
            setResult(res.data);
            await refresh();
        } catch (e: any) {
            setError(e?.response?.data?.error?.message || e?.message || "Bind failed");
        } finally {
            setBusy(null);
        }
    };

    const exportArtifact = async () => {
        const data = await call(`/api/canvas/${canvasId}/capability/export`);
        if (!data?.artifact?.file_path) return;
        try {
            const res = await apiClient.get("/api/v1/office/download", {
                params: { file_path: data.artifact.file_path },
                responseType: "blob",
            });
            const url = URL.createObjectURL(res.data as Blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = data.artifact.file_name || "canvas.xlsx";
            a.click();
            URL.revokeObjectURL(url);
        } catch (e: any) {
            setError(e?.message || "Artifact download failed");
        }
    };

    const hasManifest = !!state?.manifest && Object.keys(state.manifest).length > 0;
    const columns: string[] = state?.dataset?.columns || [];
    const displayed = result?.operation === "select"
        ? result.rows || []
        : [];

    return (
        <div className="border-b bg-muted/20 px-3 py-2" data-testid="canvas-capability-panel">
            <div className="flex items-center gap-2 flex-wrap">
                <button
                    type="button"
                    className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide flex items-center gap-1"
                    onClick={() => setOpen((v) => !v)}
                >
                    {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                    Data operations
                </button>
                {hasManifest ? (
                    <span className="text-[10px] text-emerald-600 dark:text-emerald-400 flex items-center gap-1" data-testid="capability-effective">
                        <ShieldCheck className="h-3 w-3" />
                        effective: {(state?.operations?.effective || []).join(", ") || "none"}
                    </span>
                ) : (
                    <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => saveManifest(DEFAULT_MANIFEST)} data-testid="capability-enable">
                        Enable table operations
                    </Button>
                )}
                {hasManifest && (
                    <span className="text-[10px] text-zinc-400" data-testid="capability-revision">
                        revision {state?.revision ?? 0}
                        {state?.dataset?.row_count ? ` · ${state.dataset.row_count} rows` : ""}
                    </span>
                )}
            </div>

            {open && (
                <div className="mt-2 space-y-2">
                    <div className="grid gap-2 lg:grid-cols-2">
                        <div>
                            <div className="text-[10px] uppercase tracking-wider text-zinc-400 mb-1">Capability manifest</div>
                            <textarea
                                value={manifestText}
                                onChange={(e) => setManifestText(e.target.value)}
                                rows={12}
                                spellCheck={false}
                                data-testid="capability-manifest"
                                className="w-full rounded border border-zinc-200 dark:border-white/10 bg-transparent p-2 font-mono text-[11px]"
                            />
                            <div className="flex gap-2 mt-1">
                                <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => saveManifest()} disabled={busy !== null} data-testid="capability-save-manifest">
                                    {busy?.includes("manifest") ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />} Save manifest
                                </Button>
                                <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => fileRef.current?.click()} disabled={!hasManifest || busy !== null} data-testid="capability-bind">
                                    {busy === "bind" ? <Loader2 className="h-3 w-3 animate-spin" /> : null} Bind CSV/XLSX
                                </Button>
                                <input
                                    ref={fileRef}
                                    type="file"
                                    accept=".csv,.xlsx,.xlsm"
                                    className="hidden"
                                    onChange={(e) => {
                                        const file = e.target.files?.[0];
                                        if (file) void bindFile(file);
                                        e.target.value = "";
                                    }}
                                />
                            </div>
                        </div>
                        <div className="space-y-2">
                            <div className="text-[10px] uppercase tracking-wider text-zinc-400">Ask / operate</div>
                            <textarea
                                value={ask}
                                onChange={(e) => setAsk(e.target.value)}
                                rows={3}
                                placeholder="e.g. sum Amount for Open rows"
                                data-testid="capability-ask"
                                className="w-full rounded border border-zinc-200 dark:border-white/10 bg-transparent p-2 text-xs"
                            />
                            <div className="flex gap-1 flex-wrap">
                                <Button size="sm" variant="outline" className="h-7 text-xs" disabled={!effective.has("select") || busy !== null} onClick={() => call(`/api/canvas/${canvasId}/capability/select`, { ask })} data-testid="capability-select">
                                    Select
                                </Button>
                                <Button size="sm" variant="outline" className="h-7 text-xs" disabled={!effective.has("calculate") || busy !== null} onClick={() => call(`/api/canvas/${canvasId}/capability/calculate`, { ask })} data-testid="capability-calculate">
                                    Calculate
                                </Button>
                                <Button size="sm" variant="outline" className="h-7 text-xs" disabled={!effective.has("assess") || busy !== null} onClick={() => call(`/api/canvas/${canvasId}/capability/assess`, { ask })} data-testid="capability-assess">
                                    Assess
                                </Button>
                                <Button size="sm" variant="outline" className="h-7 text-xs" disabled={!effective.has("export") || busy !== null} onClick={exportArtifact} data-testid="capability-export">
                                    <Download className="h-3 w-3" /> Export XLSX
                                </Button>
                            </div>
                            <div className="flex gap-1 items-end flex-wrap">
                                <label className="text-[10px] text-zinc-400">Row
                                    <input value={editRow} onChange={(e) => setEditRow(e.target.value)} data-testid="capability-edit-row" className="block w-16 rounded border border-zinc-200 dark:border-white/10 bg-transparent px-1 py-0.5 text-xs" />
                                </label>
                                <label className="text-[10px] text-zinc-400">Column
                                    <input value={editColumn} onChange={(e) => setEditColumn(e.target.value)} list="capability-columns" data-testid="capability-edit-column" className="block w-28 rounded border border-zinc-200 dark:border-white/10 bg-transparent px-1 py-0.5 text-xs" />
                                    <datalist id="capability-columns">
                                        {columns.map((c) => <option key={c} value={c} />)}
                                    </datalist>
                                </label>
                                <label className="text-[10px] text-zinc-400">Value
                                    <input value={editValue} onChange={(e) => setEditValue(e.target.value)} data-testid="capability-edit-value" className="block w-24 rounded border border-zinc-200 dark:border-white/10 bg-transparent px-1 py-0.5 text-xs" />
                                </label>
                                <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 text-xs"
                                    disabled={!effective.has("edit") || busy !== null}
                                    data-testid="capability-edit"
                                    onClick={() => call(`/api/canvas/${canvasId}/capability/edit`, {
                                        edits: [{ row: Number(editRow), column: editColumn, value: editValue }],
                                        expected_revision: state?.revision,
                                    })}
                                >
                                    <Play className="h-3 w-3" /> Apply edit
                                </Button>
                            </div>
                        </div>
                    </div>

                    {error && <p role="alert" className="text-[11px] text-red-600" data-testid="capability-error">{error}</p>}

                    {result && (
                        <div className="rounded border border-zinc-200 dark:border-white/10 p-2 text-[11px]" data-testid="capability-result">
                            <div className="flex gap-2 flex-wrap text-zinc-500">
                                <span>operation: {result.operation || "state"}</span>
                                {result.status && <span>status: {result.status}</span>}
                                {result.measure && <span>measure: {result.measure}</span>}
                                {result.source?.source_version && <span>source: {result.source.source_version}</span>}
                                {result.manifest_revision && <span>manifest: {result.manifest_revision}</span>}
                                {result.policy_revision && <span>policy: {result.policy_revision}</span>}
                            </div>
                            {result.total_values && (
                                <div className="mt-1 font-mono" data-testid="capability-total">
                                    {Object.entries(result.total_values).map(([k, v]) => (
                                        <div key={k}>{k === "(unstated)" ? "" : `${k} `}total: {String(v)}</div>
                                    ))}
                                </div>
                            )}
                            {!!result.gaps?.length && <div className="text-amber-600 mt-1">gaps: {result.gaps.length} (no certified total)</div>}
                            {result.certified === false && (
                                <div className="text-red-600 mt-1">failed closed — no certified assessment</div>
                            )}
                            {!!result.assessments?.length && (
                                <table className="mt-1 border-collapse">
                                    <thead><tr><th className="border px-2 py-0.5 text-left">Subject</th><th className="border px-2 py-0.5 text-left">Decision</th><th className="border px-2 py-0.5 text-left">Evidence</th></tr></thead>
                                    <tbody>
                                        {result.assessments.map((a: any, i: number) => (
                                            <tr key={i}>
                                                <td className="border px-2 py-0.5">{a.subject_id}</td>
                                                <td className="border px-2 py-0.5">{a.decision}</td>
                                                <td className="border px-2 py-0.5">{(a.evidence_ids || []).join(", ")}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                            {!!displayed.length && (
                                <table className="mt-1 border-collapse">
                                    <thead><tr><th className="border px-2 py-0.5 text-left">Row</th>{Object.keys(displayed[0]?.cells || {}).map((c) => <th key={c} className="border px-2 py-0.5 text-left">{c}</th>)}</tr></thead>
                                    <tbody>
                                        {displayed.map((r: any) => (
                                            <tr key={r.row}>
                                                <td className="border px-2 py-0.5">{r.row}</td>
                                                {Object.keys(r.cells || {}).map((c) => <td key={c} className="border px-2 py-0.5">{String(r.cells[c] ?? "")}</td>)}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                            {result.edits && (
                                <div className="mt-1">
                                    {result.edits.map((e: any, i: number) => (
                                        <div key={i}>{e.column} row {e.row}: {String(e.before)} → {String(e.readback)} ({e.readback_matches ? "readback matches" : "READBACK MISMATCH"})</div>
                                    ))}
                                </div>
                            )}
                            {result.artifact && (
                                <div className="mt-1 font-mono">artifact: {result.artifact.file_name} · {result.artifact.sha256?.slice(0, 12)}…</div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
