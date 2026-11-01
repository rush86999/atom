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
import { ChevronDown, ChevronRight, Download, Loader2, Play, Plus, Save, ShieldCheck, Trash2 } from "lucide-react";
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

type GuidedCondition = { field: string; op: string; value: string };
type GuidedRule = { decision: string; when: GuidedCondition[]; basis: string };

const GUIDED_OPS = [
    ["eq", "is"],
    ["ne", "is not"],
    ["gt", "is greater than"],
    ["gte", "is at least"],
    ["lt", "is less than"],
    ["lte", "is at most"],
    ["in", "is one of"],
    ["contains", "contains"],
    ["blank", "is blank"],
    ["not_blank", "is not blank"],
] as const;

function labelsFromText(value: string): string[] {
    const labels = value
        .split(/[\n,]+/)
        .map((item) => item.trim().toUpperCase())
        .filter(Boolean);
    return Array.from(new Set(labels));
}

function guidedStateFromManifest(manifest: Record<string, any> | undefined) {
    const source = manifest || {};
    const binding = source.data_binding || {};
    const decisions = Array.isArray(source.decision_options)
        ? source.decision_options.map((item: any) => String(item).trim().toUpperCase()).filter(Boolean)
        : [];
    const rules: GuidedRule[] = Array.isArray(source.decision_rules)
        ? source.decision_rules.map((rule: any) => ({
            decision: String(rule?.decision || decisions[0] || "REVIEW").toUpperCase(),
            basis: String(rule?.basis || ""),
            when: Array.isArray(rule?.when)
                ? rule.when.map((condition: any) => ({
                    field: String(condition?.field || ""),
                    op: String(condition?.op || "eq").toLowerCase(),
                    value: Array.isArray(condition?.value)
                        ? condition.value.join(", ")
                        : condition?.value == null
                            ? ""
                            : String(condition.value),
                }))
                : [],
        }))
        : [];
    return {
        mode: String(source.assessment_mode || "model").toLowerCase(),
        decisionsText: decisions.length ? decisions.join(", ") : "APPROVE, REVIEW, DENY",
        binding: {
            subject_field: String(binding.subject_field || ""),
            measure_field: String(binding.measure_field || ""),
            status_field: String(binding.status_field || ""),
        },
        rules,
    };
}

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
    const initialGuided = guidedStateFromManifest(initial?.manifest || DEFAULT_MANIFEST);
    const [guidedMode, setGuidedMode] = useState(initialGuided.mode);
    const [guidedDecisions, setGuidedDecisions] = useState(initialGuided.decisionsText);
    const [guidedBinding, setGuidedBinding] = useState(initialGuided.binding);
    const [guidedPolicy, setGuidedPolicy] = useState(String(initial?.manifest?.task_policy || ""));
    const [guidedEditable, setGuidedEditable] = useState<string[]>(
        Array.isArray(initial?.manifest?.editable_fields) ? initial.manifest.editable_fields : [],
    );
    const [guidedRules, setGuidedRules] = useState<GuidedRule[]>(initialGuided.rules);
    const [ask, setAsk] = useState("");
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState<string | null>(null);
    const [editRow, setEditRow] = useState("");
    const [editColumn, setEditColumn] = useState("");
    const [editValue, setEditValue] = useState("");
    const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, string>>({});
    const [decisions, setDecisions] = useState<Record<string, string> | null>(null);
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
                const guided = guidedStateFromManifest(res.data.manifest || DEFAULT_MANIFEST);
                setGuidedMode(guided.mode);
                setGuidedDecisions(guided.decisionsText);
                setGuidedBinding(guided.binding);
                setGuidedPolicy(String(res.data.manifest?.task_policy || ""));
                setGuidedEditable(Array.isArray(res.data.manifest?.editable_fields) ? res.data.manifest.editable_fields : []);
                setGuidedRules(guided.rules);
            } catch {
                // Not a capability canvas yet — the Enable action stays available.
            }
        })();
        return () => { cancelled = true; };
    }, [canvasId]);

    const call = useCallback(async (path: string, body?: any, method: "get" | "post" | "put" = "post") => {
        setBusy(path);
        setError(null);
        setResult(null);
        try {
            const res = method === "get"
                ? await apiClient.get(path)
                : method === "put"
                    ? await apiClient.put(path, body)
                    : await apiClient.post(path, body);
            if (res.data?.success === false) {
                setResult(res.data);
                throw new Error(res.data?.error?.message || "Operation refused");
            }
            setResult(res.data);
            if (String(path).includes("/capability/assess") && !String(path).includes("/clarify")) {
                setClarificationAnswers({});
                setDecisions(null);
            }
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
            setState((prev) => ({ ...(prev || {}), manifest: data.manifest, operations: data.operations || prev?.operations, revision: data.revision, policy_revision: data.policy_revision }));
            const guided = guidedStateFromManifest(data.manifest);
            setGuidedMode(guided.mode);
            setGuidedDecisions(guided.decisionsText);
            setGuidedBinding(guided.binding);
            setGuidedPolicy(String(data.manifest?.task_policy || ""));
            setGuidedEditable(Array.isArray(data.manifest?.editable_fields) ? data.manifest.editable_fields : []);
            setGuidedRules(guided.rules);
            onChanged?.();
        }
        return data;
    };

    const addGuidedRule = () => {
        const labels = labelsFromText(guidedDecisions);
        const decision = labels.find((item) => item !== "REVIEW") || labels[0] || "APPROVE";
        const field = (state?.dataset?.columns || [])[0] || state?.manifest?.data_binding?.subject_field || "";
        setGuidedRules((current) => [...current, {
            decision,
            basis: "",
            when: [{ field, op: "eq", value: "" }],
        }]);
    };

    const updateGuidedRule = (index: number, patch: Partial<GuidedRule>) => {
        setGuidedRules((current) => current.map((rule, i) => i === index ? { ...rule, ...patch } : rule));
    };

    const updateGuidedCondition = (ruleIndex: number, conditionIndex: number, patch: Partial<GuidedCondition>) => {
        setGuidedRules((current) => current.map((rule, i) => {
            if (i !== ruleIndex) return rule;
            return {
                ...rule,
                when: rule.when.map((condition, j) => j === conditionIndex ? { ...condition, ...patch } : condition),
            };
        }));
    };

    const removeGuidedCondition = (ruleIndex: number, conditionIndex: number) => {
        setGuidedRules((current) => current.map((rule, i) => {
            if (i !== ruleIndex) return rule;
            return { ...rule, when: rule.when.filter((_, j) => j !== conditionIndex) };
        }));
    };

    const addGuidedCondition = (ruleIndex: number) => {
        const field = (state?.dataset?.columns || [])[0] || state?.manifest?.data_binding?.subject_field || "";
        setGuidedRules((current) => current.map((rule, i) => i === ruleIndex
            ? { ...rule, when: [...rule.when, { field, op: "eq", value: "" }] }
            : rule));
    };

    const saveGuidedRules = async () => {
        let parsed: Record<string, any>;
        try {
            parsed = JSON.parse(manifestText);
        } catch {
            setError("Manifest is not valid JSON");
            return;
        }
        if (!guidedRules.length) {
            setError("Add at least one decision rule");
            return;
        }
        const decisions = labelsFromText(guidedDecisions);
        if (!decisions.includes("REVIEW")) decisions.push("REVIEW");
        const rules = guidedRules.map((rule, index) => ({
            decision: rule.decision,
            basis: rule.basis.trim() || `Matched guided rule ${index + 1}`,
            when: rule.when.map((condition) => {
                const clean: Record<string, any> = { field: condition.field, op: condition.op };
                if (condition.op !== "blank" && condition.op !== "not_blank") {
                    clean.value = condition.op === "in"
                        ? condition.value.split(",").map((item) => item.trim()).filter(Boolean)
                        : condition.value;
                }
                return clean;
            }),
        }));
        const opLabels = Object.fromEntries(GUIDED_OPS) as Record<string, string>;
        const generatedPolicy = guidedRules.map((rule, index) => {
            const conditions = rule.when.map((condition) => {
                const suffix = condition.op === "blank" || condition.op === "not_blank"
                    ? ""
                    : ` ${condition.value}`;
                return `${condition.field} ${opLabels[condition.op] || condition.op}${suffix}`;
            }).join(" and ");
            return `Rule ${index + 1}: ${rule.decision} when ${conditions}.`;
        }).join(" ");
        const data = await saveManifest({
            ...parsed,
            data_binding: {
                ...(parsed.data_binding || {}),
                subject_field: guidedBinding.subject_field,
                measure_field: guidedBinding.measure_field,
                status_field: guidedBinding.status_field,
            },
            editable_fields: guidedEditable.filter((field) => guidedFields.includes(field)),
            assessment_mode: "deterministic",
            decision_options: decisions,
            decision_rules: rules,
            task_policy: guidedPolicy.trim() || generatedPolicy || "Apply the decision rules; otherwise REVIEW.",
        });
        if (data) {
            setResult({
                operation: "manifest",
                status: "saved",
                manifest_revision: data.manifest_revision,
                policy_revision: data.policy_revision,
            });
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
                params: { file_path: data.artifact.file_path, canvas_id: canvasId },
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

    const approveAssessment = async () => {
        if (!result?.execution_id) return;
        setBusy("assess-approve");
        setError(null);
        try {
            const res = await apiClient.post(
                `/api/canvas/${canvasId}/capability/assess/${encodeURIComponent(result.execution_id)}/approve`,
            );
            if (res.data?.success === false) {
                throw new Error(res.data?.error?.message || "Approval refused");
            }
            setResult((prev: any) => ({
                ...prev,
                authorized: true,
                authorization: res.data.authorization,
            }));
        } catch (e: any) {
            setError(e?.response?.data?.error?.message || e?.message || "Approval failed");
        } finally {
            setBusy(null);
        }
    };

    const submitClarification = async () => {
        if (!result?.execution_id) return;
        const answers = Object.entries(clarificationAnswers)
            .filter(([, answer]) => answer.trim())
            .map(([subject, answer]) => ({ subject, answer: answer.trim() }));
        if (!answers.length) {
            setError("Answer at least one clarification requirement");
            return;
        }
        setBusy("assess-clarify");
        setError(null);
        try {
            const res = await apiClient.post(
                `/api/canvas/${canvasId}/capability/assess/${encodeURIComponent(result.execution_id)}/clarify`,
                { answers },
            );
            if (res.data?.success === false) {
                throw new Error(res.data?.error?.message || "Clarification refused");
            }
            setResult(res.data);
            setClarificationAnswers({});
        } catch (e: any) {
            setError(e?.response?.data?.error?.message || e?.message || "Clarification failed");
        } finally {
            setBusy(null);
        }
    };

    const useDecisions = async () => {
        setBusy("decisions");
        setError(null);
        try {
            const res = await apiClient.get(`/api/canvas/${canvasId}/capability/decisions`);
            if (res.data?.success === false) {
                throw new Error(res.data?.error?.message || "Decisions refused");
            }
            setDecisions(res.data.decisions || {});
        } catch (e: any) {
            setError(e?.response?.data?.error?.message || e?.message || "Decisions failed");
        } finally {
            setBusy(null);
        }
    };

    const hasManifest = !!state?.manifest && Object.keys(state.manifest).length > 0;
    const columns: string[] = useMemo(
        () => state?.dataset?.columns || [],
        [state?.dataset?.columns],
    );
    const guidedFields = useMemo(() => {
        const fields = new Set<string>(columns);
        const binding = state?.manifest?.data_binding || {};
        Object.entries(binding).forEach(([key, value]) => {
            if (value && key.endsWith("_field")) fields.add(String(value));
        });
        return Array.from(fields);
    }, [columns, state?.manifest]);
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
                        <div className="space-y-2">
                            <div className="rounded border border-zinc-200 dark:border-white/10 p-2 space-y-2" data-testid="capability-guided-rules">
                                <div className="flex items-start justify-between gap-2">
                                    <div>
                                        <div className="text-[10px] uppercase tracking-wider text-zinc-400">Decision rules — guided</div>
                                        <p className="text-[10px] text-muted-foreground">
                                            Build the rules without JSON. Rules run top to bottom and the first full match wins;
                                            REVIEW is the fallback when nothing matches or a value is blank.
                                        </p>
                                        <span className="text-[10px] text-muted-foreground" data-testid="capability-guided-mode">
                                            {guidedMode === "deterministic" ? "deterministic rules" : "saving switches assessment to deterministic rules"}
                                        </span>
                                    </div>
                                    <Button size="sm" variant="outline" className="h-7 text-xs shrink-0" onClick={addGuidedRule} disabled={!hasManifest || busy !== null} data-testid="capability-rule-add">
                                        <Plus className="h-3 w-3" /> Add rule
                                    </Button>
                                </div>
                                <label className="block text-[10px] text-zinc-500">
                                    Decision labels (comma-separated; REVIEW is the fallback)
                                    <input
                                        value={guidedDecisions}
                                        onChange={(e) => setGuidedDecisions(e.target.value)}
                                        aria-label="Decision labels"
                                        data-testid="capability-guided-decisions"
                                        className="mt-0.5 w-full rounded border border-zinc-200 dark:border-white/10 bg-transparent px-2 py-1 text-xs"
                                    />
                                </label>
                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-1" data-testid="capability-guided-binding">
                                    {([
                                        ["subject_field", "Row ID / subject", "capability-guided-subject"],
                                        ["measure_field", "Measure / amount", "capability-guided-measure"],
                                        ["status_field", "Status (optional)", "capability-guided-status"],
                                    ] as const).map(([key, label, testId]) => (
                                        <label key={key} className="text-[10px] text-zinc-500">
                                            {label}
                                            <select
                                                value={guidedBinding[key]}
                                                onChange={(e) => setGuidedBinding((current) => ({ ...current, [key]: e.target.value }))}
                                                aria-label={label}
                                                data-testid={testId}
                                                className="mt-0.5 w-full rounded border border-zinc-200 dark:border-white/10 bg-transparent px-1 py-1 text-xs"
                                            >
                                                <option value="">Not set</option>
                                                {guidedFields.map((field) => <option key={field} value={field}>{field}</option>)}
                                                {guidedBinding[key] && !guidedFields.includes(guidedBinding[key]) && (
                                                    <option value={guidedBinding[key]}>{guidedBinding[key]}</option>
                                                )}
                                            </select>
                                        </label>
                                    ))}
                                </div>
                                <label className="block text-[10px] text-zinc-500">
                                    Policy summary (shown to reviewers; generated from the rules if left blank)
                                    <textarea
                                        value={guidedPolicy}
                                        onChange={(e) => setGuidedPolicy(e.target.value)}
                                        rows={2}
                                        aria-label="Policy summary"
                                        data-testid="capability-guided-policy"
                                        className="mt-0.5 w-full rounded border border-zinc-200 dark:border-white/10 bg-transparent px-2 py-1 text-xs"
                                    />
                                </label>
                                {guidedFields.length > 0 && (
                                    <div className="text-[10px] text-zinc-500" data-testid="capability-guided-editable">
                                        Editable fields (optional)
                                        <div className="flex flex-wrap gap-2 mt-0.5">
                                            {guidedFields.map((field) => (
                                                <label key={field} className="flex items-center gap-1">
                                                    <input
                                                        type="checkbox"
                                                        checked={guidedEditable.includes(field)}
                                                        onChange={(e) => setGuidedEditable((current) => e.target.checked
                                                            ? [...current, field]
                                                            : current.filter((item) => item !== field))}
                                                        data-testid={`capability-guided-editable-${field}`}
                                                    />
                                                    {field}
                                                </label>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                {guidedRules.length === 0 ? (
                                    <p className="text-[11px] text-muted-foreground" data-testid="capability-guided-empty">
                                        No rules yet. Bind the data, then add a rule such as “Amount is at least 100 → APPROVE”.
                                    </p>
                                ) : guidedRules.map((rule, ruleIndex) => (
                                    <div key={ruleIndex} className="rounded border border-zinc-200 dark:border-white/10 p-1.5 space-y-1.5" data-testid={`capability-rule-${ruleIndex}`}>
                                        <div className="flex items-center gap-1 flex-wrap">
                                            <span className="text-[10px] text-zinc-400">Rule {ruleIndex + 1}</span>
                                            <select
                                                value={rule.decision}
                                                onChange={(e) => updateGuidedRule(ruleIndex, { decision: e.target.value })}
                                                aria-label={`Rule ${ruleIndex + 1} decision`}
                                                data-testid={`capability-rule-${ruleIndex}-decision`}
                                                className="h-7 rounded border border-zinc-200 dark:border-white/10 bg-transparent px-1 text-xs"
                                            >
                                                {labelsFromText(guidedDecisions).map((decision) => (
                                                    <option key={decision} value={decision}>{decision}</option>
                                                ))}
                                                {!labelsFromText(guidedDecisions).includes(rule.decision) && (
                                                    <option value={rule.decision}>{rule.decision}</option>
                                                )}
                                            </select>
                                            <input
                                                value={rule.basis}
                                                onChange={(e) => updateGuidedRule(ruleIndex, { basis: e.target.value })}
                                                placeholder="Why this rule applies (shown as the basis)"
                                                aria-label={`Rule ${ruleIndex + 1} basis`}
                                                data-testid={`capability-rule-${ruleIndex}-basis`}
                                                className="h-7 min-w-[10rem] flex-1 rounded border border-zinc-200 dark:border-white/10 bg-transparent px-2 text-xs"
                                            />
                                            <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => { if (ruleIndex > 0) { const next = [...guidedRules]; [next[ruleIndex - 1], next[ruleIndex]] = [next[ruleIndex], next[ruleIndex - 1]]; setGuidedRules(next); } }} disabled={ruleIndex === 0} aria-label={`Move rule ${ruleIndex + 1} up`}>↑</Button>
                                            <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => { if (ruleIndex < guidedRules.length - 1) { const next = [...guidedRules]; [next[ruleIndex + 1], next[ruleIndex]] = [next[ruleIndex], next[ruleIndex + 1]]; setGuidedRules(next); } }} disabled={ruleIndex === guidedRules.length - 1} aria-label={`Move rule ${ruleIndex + 1} down`}>↓</Button>
                                            <Button size="sm" variant="ghost" className="h-7 px-2 text-xs text-red-600" onClick={() => setGuidedRules((current) => current.filter((_, i) => i !== ruleIndex))} aria-label={`Remove rule ${ruleIndex + 1}`} data-testid={`capability-rule-${ruleIndex}-remove`}>
                                                <Trash2 className="h-3 w-3" />
                                            </Button>
                                        </div>
                                        {rule.when.map((condition, conditionIndex) => (
                                            <div key={conditionIndex} className="flex items-center gap-1 flex-wrap" data-testid={`capability-rule-${ruleIndex}-condition-${conditionIndex}`}>
                                                <select
                                                    value={condition.field}
                                                    onChange={(e) => updateGuidedCondition(ruleIndex, conditionIndex, { field: e.target.value })}
                                                    aria-label={`Rule ${ruleIndex + 1} condition ${conditionIndex + 1} field`}
                                                    data-testid={`capability-rule-${ruleIndex}-condition-${conditionIndex}-field`}
                                                    className="h-7 rounded border border-zinc-200 dark:border-white/10 bg-transparent px-1 text-xs"
                                                >
                                                    <option value="">Select field</option>
                                                    {guidedFields.map((field) => <option key={field} value={field}>{field}</option>)}
                                                    {condition.field && !guidedFields.includes(condition.field) && (
                                                        <option value={condition.field}>{condition.field}</option>
                                                    )}
                                                </select>
                                                <select
                                                    value={condition.op}
                                                    onChange={(e) => updateGuidedCondition(ruleIndex, conditionIndex, { op: e.target.value })}
                                                    aria-label={`Rule ${ruleIndex + 1} condition ${conditionIndex + 1} operator`}
                                                    data-testid={`capability-rule-${ruleIndex}-condition-${conditionIndex}-op`}
                                                    className="h-7 rounded border border-zinc-200 dark:border-white/10 bg-transparent px-1 text-xs"
                                                >
                                                    {GUIDED_OPS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                                                </select>
                                                {condition.op === "blank" || condition.op === "not_blank" ? (
                                                    <span className="text-[10px] text-zinc-400">no value needed</span>
                                                ) : (
                                                    <input
                                                        value={condition.value}
                                                        onChange={(e) => updateGuidedCondition(ruleIndex, conditionIndex, { value: e.target.value })}
                                                        placeholder={condition.op === "in" ? "comma-separated values" : "value"}
                                                        aria-label={`Rule ${ruleIndex + 1} condition ${conditionIndex + 1} value`}
                                                        data-testid={`capability-rule-${ruleIndex}-condition-${conditionIndex}-value`}
                                                        className="h-7 min-w-[8rem] flex-1 rounded border border-zinc-200 dark:border-white/10 bg-transparent px-2 text-xs"
                                                    />
                                                )}
                                                <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => removeGuidedCondition(ruleIndex, conditionIndex)} aria-label={`Remove rule ${ruleIndex + 1} condition ${conditionIndex + 1}`}>×</Button>
                                            </div>
                                        ))}
                                        <Button size="sm" variant="ghost" className="h-6 px-1 text-[10px]" onClick={() => addGuidedCondition(ruleIndex)} data-testid={`capability-rule-${ruleIndex}-condition-add`}>
                                            <Plus className="h-3 w-3" /> Add condition
                                        </Button>
                                    </div>
                                ))}
                                <Button size="sm" variant="outline" className="h-7 text-xs" onClick={saveGuidedRules} disabled={!hasManifest || busy !== null} data-testid="capability-guided-save">
                                    {busy?.includes("manifest") ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />} Save decision rules
                                </Button>
                            </div>
                            <div className="flex gap-2 items-center flex-wrap">
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
                                <span className="text-[10px] text-zinc-400" data-testid="capability-guided-fields">
                                    {columns.length ? `${columns.length} bound fields available` : "Bind data to choose fields"}
                                </span>
                            </div>
                            <details className="rounded border border-zinc-200 dark:border-white/10 p-1.5" data-testid="capability-advanced-manifest">
                                <summary className="cursor-pointer text-[10px] font-medium text-zinc-500">
                                    Advanced: edit manifest JSON
                                </summary>
                                <textarea
                                    value={manifestText}
                                    onChange={(e) => setManifestText(e.target.value)}
                                    rows={12}
                                    spellCheck={false}
                                    data-testid="capability-manifest"
                                    className="mt-1 w-full rounded border border-zinc-200 dark:border-white/10 bg-transparent p-2 font-mono text-[11px]"
                                />
                                <Button size="sm" variant="outline" className="mt-1 h-7 text-xs" onClick={() => saveManifest()} disabled={busy !== null} data-testid="capability-save-manifest">
                                    {busy?.includes("manifest") ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />} Save manifest
                                </Button>
                            </details>
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
                            {result.operation === "assess" && (
                                <div className="mt-1 space-y-1" data-testid="capability-assessment-state">
                                    <p className={result.authorized === true ? "text-emerald-700" : "text-amber-700"}>
                                        {result.authorized === true
                                            ? "Authorized assessment — decisions may be used."
                                            : result.certified
                                                ? "Draft assessment — not authorized. A human must approve this exact assessment before the decisions can be used."
                                                : "Draft assessment — not certified; no decision may be used."}
                                    </p>
                                    {result.authorized !== true && result.certified && result.execution_id ? (
                                        <Button
                                            size="sm"
                                            className="h-7 text-xs"
                                            disabled={busy !== null}
                                            data-testid="capability-assess-approve"
                                            onClick={approveAssessment}
                                        >
                                            Approve this assessment
                                        </Button>
                                    ) : null}
                                    {result.authorized === true ? (
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            className="h-7 text-xs"
                                            disabled={busy !== null}
                                            data-testid="capability-decisions"
                                            onClick={useDecisions}
                                        >
                                            Use decisions
                                        </Button>
                                    ) : null}
                                    {decisions ? (
                                        <div className="font-mono text-[11px]" data-testid="capability-decisions-result">
                                            {Object.entries(decisions).map(([subject, decision]) => (
                                                <div key={subject}>{subject}: {String(decision)}</div>
                                            ))}
                                        </div>
                                    ) : null}
                                    {result.clarification?.state === "open" ? (
                                        <div className="rounded border border-amber-300 bg-amber-50 p-2" data-testid="capability-clarification">
                                            <p className="font-medium">Clarification required</p>
                                            {(result.clarification.requirements || [])
                                                .filter((item: any) => !item.answer)
                                                .map((item: any) => (
                                                    <label key={`${item.subject}:${item.requirement}`} className="mt-1 block text-[11px]">
                                                        {item.subject}: {item.requirement}
                                                        <input
                                                            value={clarificationAnswers[item.subject] || ""}
                                                            onChange={(e) => setClarificationAnswers((prev) => ({
                                                                ...prev,
                                                                [item.subject]: e.target.value,
                                                            }))}
                                                            className="mt-0.5 w-full rounded border px-1.5 py-0.5"
                                                            aria-label={`Clarification answer ${item.subject}`}
                                                            data-testid={`capability-clarification-${item.subject}`}
                                                        />
                                                    </label>
                                                ))}
                                            <Button
                                                size="sm"
                                                className="mt-1 h-7 text-xs"
                                                disabled={busy !== null}
                                                data-testid="capability-clarification-submit"
                                                onClick={submitClarification}
                                            >
                                                Submit answers and resume
                                            </Button>
                                        </div>
                                    ) : null}
                                </div>
                            )}
                            {!!result.assessments?.length && (
                                <table className="mt-1 border-collapse">
                                    <thead><tr><th className="border px-2 py-0.5 text-left">Subject</th><th className="border px-2 py-0.5 text-left">Decision</th><th className="border px-2 py-0.5 text-left">Evidence</th></tr></thead>
                                    <tbody>
                                        {result.assessments.map((a: any, i: number) => (
                                            <tr key={i}>
                                                <td className="border px-2 py-0.5">{a.subject_id}</td>
                                                <td className="border px-2 py-0.5">{a.decision}</td>
                                                <td className="border px-2 py-0.5">{(a.evidence_refs || []).map((e: any) => e.evidence_id).join(", ")}</td>
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
