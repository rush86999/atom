"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Download,
  FileText,
  Pencil,
  Play,
  RefreshCw,
  Send,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  approveAssignmentStep,
  AssignmentAgent,
  AssignmentDetail,
  AssignmentSource,
  AssignmentStep,
  AssignmentSummary,
  cancelAssignment,
  correctAssignmentMapping,
  createAssignment,
  downloadAssignmentDeliverable,
  getAssignment,
  listAssignmentAgents,
  listAssignments,
  listAssignmentSources,
  recordAssignmentResponse,
  resolveAssignmentGap,
  resumeAssignment,
} from "@/lib/assignment-api";

function userFacingError(err: unknown, fallback: string): string {
  const anyErr = err as any;
  const raw = anyErr?.response?.data
    || anyErr?.technical?.response?.data;
  const detail = raw?.detail || raw;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail === "object" && detail.message) {
    const conflicts = Array.isArray(detail.conflicts) ? detail.conflicts : [];
    const conflictText = conflicts.flatMap((item: any) =>
      (item?.conflicts || []).map((pair: any) =>
        `${pair.key}: ${pair.required} vs ${pair.actual}`)
    );
    const clarifications = Array.isArray(detail.clarifications)
      ? detail.clarifications : [];
    const missingText = clarifications.flatMap((item: any) =>
      (item?.missing || []).map((key: string) => `missing ${key}`)
    );
    const extra = [...conflictText, ...missingText];
    return extra.length
      ? `${detail.message} (${extra.join("; ")})`
      : String(detail.message);
  }
  if (anyErr?.message) return String(anyErr.message);
  return fallback;
}

function sourceKey(source: AssignmentSource): string {
  return `${source.dataset_name || ""}::${source.sheet || ""}`;
}

const STATE_STYLES: Record<string, string> = {
  completed: "bg-emerald-100 text-emerald-800",
  running: "bg-indigo-100 text-indigo-800",
  waiting: "bg-amber-100 text-amber-800",
  blocked: "bg-rose-100 text-rose-800",
  partial: "bg-orange-100 text-orange-800",
  failed: "bg-rose-100 text-rose-800",
  cancelled: "bg-slate-200 text-slate-700",
  planned: "bg-slate-100 text-slate-700",
};

function currentStep(detail: AssignmentDetail): AssignmentStep | undefined {
  const steps = detail.assignment.steps;
  return (
    steps.find((s) => s.status === "awaiting_approval") ||
    steps.find((s) => s.status === "waiting") ||
    steps.find((s) => s.status === "running") ||
    steps.find((s) => s.status === "pending")
  );
}

function testIdPart(value: unknown): string {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function authorityLabel(authority: string): string {
  if (authority === "user_confirmed") return "user-confirmed";
  if (authority === "source_evidence") return "source-established";
  if (authority === "taught") return "taught";
  return authority || "not established";
}

export function AssignmentPanel({
  className = "",
  agentId = null,
}: {
  className?: string;
  agentId?: string | null;
}) {
  const [summaries, setSummaries] = useState<AssignmentSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<AssignmentDetail | null>(null);
  const [gapDrafts, setGapDrafts] = useState<Record<string, string>>({});
  const [correction, setCorrection] = useState<{
    concept: string;
    column: string;
    unit: string;
  } | null>(null);
  const [responseDraft, setResponseDraft] = useState("");
  const [sources, setSources] = useState<AssignmentSource[]>([]);
  const [agents, setAgents] = useState<AssignmentAgent[]>([]);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [selectedSourceKey, setSelectedSourceKey] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [measure, setMeasure] = useState("");
  const [customMeasure, setCustomMeasure] = useState("");
  const [businessContext, setBusinessContext] = useState("");
  const [qualification, setQualification] = useState("");
  const [taskScope, setTaskScope] = useState("");
  const [missingFact, setMissingFact] = useState("");
  const [startDraft, setStartDraft] = useState({
    objective: "",
    deliverableKind: "document",
    content: "",
    recipient: "",
    expression: "",
    correlation: "",
    discover: false,
    scopeQuery: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refreshList = useCallback(async () => {
    try {
      const rows = await listAssignments();
      setSummaries(rows);
      if (!selected && rows.length) setSelected(rows[0].run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load assignments");
    }
  }, [selected]);

  const refreshDetail = useCallback(async (runId: string) => {
    try {
      setDetail(await getAssignment(runId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load assignment");
    }
  }, []);

  const refreshSources = useCallback(async () => {
    setSourcesLoading(true);
    try {
      const rows = await listAssignmentSources();
      setSources(rows);
      setSelectedSourceKey((current) => {
        if (current && rows.some((row) => sourceKey(row) === current)) {
          return current;
        }
        return rows[0] ? sourceKey(rows[0]) : "";
      });
    } catch (err) {
      setError(userFacingError(err, "Could not load the data catalog"));
    } finally {
      setSourcesLoading(false);
    }
  }, []);

  const refreshAgents = useCallback(async () => {
    try {
      const rows = await listAssignmentAgents();
      setAgents(rows);
      setSelectedAgentId((current) => current || rows[0]?.id || "");
    } catch {
      // The assignment still works without an employee binding.
    }
  }, []);

  useEffect(() => {
    refreshList();
    refreshSources();
    refreshAgents();
  }, [refreshList, refreshSources, refreshAgents]);

  useEffect(() => {
    if (selected) refreshDetail(selected);
  }, [selected, refreshDetail]);

  const act = async (fn: () => Promise<unknown>, runId: string) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await fn();
      await refreshDetail(runId);
      await refreshList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  };

  const selectedSource =
    sources.find((source) => sourceKey(source) === selectedSourceKey) || null;

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const source = selectedSource;
      const payload: Parameters<typeof createAssignment>[0] = {
        objective: startDraft.objective,
        agent_id: selectedAgentId || agentId || undefined,
        sources: startDraft.discover || !source
          ? []
          : [{
              kind: source.kind,
              dataset_name: source.dataset_name,
              source: source.source,
              external_id: source.external_id,
              source_version: source.source_version,
              sheet: source.sheet,
            }],
        discover: startDraft.discover,
        source_scope: startDraft.discover
          ? { query: startDraft.scopeQuery }
          : undefined,
        deliverables: [{
          kind: startDraft.deliverableKind,
          description: startDraft.objective,
          content: startDraft.content.trim() || undefined,
        }],
        task_context: {
          ...(businessContext.trim()
            ? { business_category: businessContext.trim() }
            : {}),
          ...(qualification.trim()
            ? { qualification: qualification.trim() }
            : {}),
          ...(taskScope.trim() ? { task_scope: taskScope.trim() } : {}),
        },
      };
      const measureValue = measure === "__custom__"
        ? customMeasure.trim()
        : measure;
      if (measureValue) {
        payload.calculation = {
          aggregate: measureValue === "__count__"
            ? { operation: "count" }
            : { operation: "sum", value_column: measureValue },
        };
      } else if (startDraft.expression.trim()) {
        payload.calculation = {
          expression: startDraft.expression.trim(),
          bindings: {},
        };
      }
      if (startDraft.correlation.trim()) {
        payload.wait = {
          correlation_id: startDraft.correlation.trim(),
          party: "external responder",
          detail: "authorized external reply",
          fact: missingFact.trim() || undefined,
        };
      }
      if (startDraft.recipient.trim()) {
        payload.outbound = {
          to: [startDraft.recipient.trim()],
          subject: startDraft.objective,
        };
      }
      if (process.env.NEXT_PUBLIC_ASSIGNMENT_TRANSPORT) {
        payload.transport = process.env.NEXT_PUBLIC_ASSIGNMENT_TRANSPORT;
      }
      const result = await createAssignment(payload);
      setStartDraft({
        objective: "",
        deliverableKind: "document",
        content: "",
        recipient: "",
        expression: "",
        correlation: "",
        discover: false,
        scopeQuery: "",
      });
      setMeasure("");
      setCustomMeasure("");
      setQualification("");
      setTaskScope("");
      setMissingFact("");
      setSelected(result.run_id);
      await refreshList();
      await refreshDetail(result.run_id);
    } catch (err) {
      setError(userFacingError(err, "Could not start assignment"));
    } finally {
      setBusy(false);
    }
  };

  const downloadArtifact = async (deliverableId: string) => {
    if (!detail) return;
    setBusy(true);
    setError(null);
    try {
      const { blob, filename } = await downloadAssignmentDeliverable(
        detail.run_id,
        deliverableId
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(userFacingError(err, "Could not download the artifact"));
    } finally {
      setBusy(false);
    }
  };

  const step = detail ? currentStep(detail) : undefined;
  const openGaps = detail?.open_gaps ?? [];
  const waitingParty = (step?.waiting?.party as string) || "";
  const uncertain = detail?.assignment.steps.find(
    (s) => s.status === "uncertain"
  );

  return (
    <div className={`space-y-3 text-xs ${className}`} data-testid="assignment-panel">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">Assignments</h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            refreshList();
            if (selected) refreshDetail(selected);
          }}
          aria-label="Refresh assignments"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>

      {error ? (
        <div className="rounded border border-rose-200 bg-rose-50 p-2 text-rose-700">
          {error}
        </div>
      ) : null}
      {notice ? (
        <div
          data-testid="assignment-notice"
          className="rounded border border-amber-200 bg-amber-50 p-2 text-amber-800"
        >
          {notice}
        </div>
      ) : null}

      <div className="space-y-1.5 rounded border bg-slate-50 p-2" data-testid="assignment-start">
        <div className="flex items-center justify-between gap-2">
          <p className="font-medium">Start durable work</p>
          <button
            type="button"
            className="text-[10px] text-indigo-600 underline"
            onClick={refreshSources}
            disabled={sourcesLoading}
          >
            {sourcesLoading ? "Refreshing data…" : "Refresh data"}
          </button>
        </div>
        <textarea
          value={startDraft.objective}
          onChange={(e) =>
            setStartDraft((d) => ({ ...d, objective: e.target.value }))
          }
          placeholder="What should the employee do?"
          rows={2}
          className="w-full rounded border px-1.5 py-1"
          aria-label="Assignment objective"
          data-testid="assignment-objective-input"
        />
        <select
          value={selectedAgentId}
          onChange={(e) => setSelectedAgentId(e.target.value)}
          className="w-full rounded border px-1.5 py-1"
          aria-label="Employee"
          data-testid="assignment-agent-select"
        >
          <option value="">No employee binding</option>
          {agents.map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.name}{agent.category ? ` · ${agent.category}` : ""}
            </option>
          ))}
        </select>
        <select
          value={selectedSourceKey}
          onChange={(e) => {
            setSelectedSourceKey(e.target.value);
            setMeasure("");
          }}
          className="w-full rounded border px-1.5 py-1"
          aria-label="Authorized data source"
          data-testid="assignment-source-select"
          disabled={startDraft.discover || sourcesLoading || !sources.length}
        >
          {!sources.length ? (
            <option value="">
              {sourcesLoading ? "Loading data…" : "No data available yet"}
            </option>
          ) : null}
          {sources.map((source) => (
            <option key={sourceKey(source)} value={sourceKey(source)}>
              {source.file_name || source.dataset_name}
              {source.sheet ? ` / ${source.sheet}` : ""}
              {source.row_count ? ` · ${source.row_count} rows` : ""}
            </option>
          ))}
        </select>
        {!sourcesLoading && !sources.length ? (
          <p className="text-[10px] text-muted-foreground">
            Upload a CSV or workbook in{" "}
            <a className="text-indigo-600 underline" href="/documents">
              Data
            </a>{" "}
            first, or connect a source in{" "}
            <a className="text-indigo-600 underline" href="/integrations">
              Integrations
            </a>
            .
          </p>
        ) : null}
        <div className="flex gap-1">
          <select
            value={startDraft.deliverableKind}
            onChange={(e) =>
              setStartDraft((d) => ({
                ...d,
                deliverableKind: e.target.value,
              }))
            }
            className="min-w-0 flex-1 rounded border px-1.5 py-1"
            aria-label="Deliverable kind"
            data-testid="assignment-deliverable-kind"
          >
            <option value="document">Document</option>
            <option value="presentation">Presentation</option>
            <option value="email_draft">Email draft</option>
          </select>
          <select
            value={measure}
            onChange={(e) => setMeasure(e.target.value)}
            className="min-w-0 flex-1 rounded border px-1.5 py-1"
            aria-label="Calculation"
            data-testid="assignment-measure-select"
          >
            <option value="">No calculation / infer</option>
            <option value="__count__">Count rows</option>
            {(selectedSource?.numeric_columns || []).map((column) => (
              <option key={column} value={column}>
                Sum {column}
              </option>
            ))}
            <option value="__custom__">Other business concept…</option>
          </select>
        </div>
        {measure === "__custom__" ? (
          <input
            value={customMeasure}
            onChange={(e) => setCustomMeasure(e.target.value)}
            placeholder="Name the measure the business uses (for example Price)"
            className="w-full rounded border px-1.5 py-1"
            aria-label="Custom measure concept"
            data-testid="assignment-custom-measure-input"
          />
        ) : null}
        <input
          value={businessContext}
          onChange={(e) => setBusinessContext(e.target.value)}
          placeholder="Business context (optional, for example: sales)"
          className="w-full rounded border px-1.5 py-1"
          aria-label="Business context"
          data-testid="assignment-context-input"
        />
        <div className="grid grid-cols-2 gap-1">
          <input
            value={qualification}
            onChange={(e) => setQualification(e.target.value)}
            placeholder="Required qualification"
            className="w-full rounded border px-1.5 py-1"
            aria-label="Required qualification"
            data-testid="assignment-qualification-input"
          />
          <input
            value={taskScope}
            onChange={(e) => setTaskScope(e.target.value)}
            placeholder="Task scope (exception match)"
            className="w-full rounded border px-1.5 py-1"
            aria-label="Task scope"
            data-testid="assignment-task-scope-input"
          />
        </div>
        <label className="flex items-center gap-1 text-[10px]">
          <input
            type="checkbox"
            checked={startDraft.discover}
            onChange={(e) =>
              setStartDraft((d) => ({ ...d, discover: e.target.checked }))
            }
            aria-label="Discover resource from scope"
            data-testid="assignment-discover-checkbox"
          />
          Let Atom choose from a permitted scope instead of the selected data
        </label>
        {startDraft.discover ? (
          <input
            value={startDraft.scopeQuery}
            onChange={(e) =>
              setStartDraft((d) => ({ ...d, scopeQuery: e.target.value }))
            }
            placeholder="Permitted source scope (for example: price list)"
            className="w-full rounded border px-1.5 py-1"
            aria-label="Permitted source scope"
            data-testid="assignment-scope-input"
          />
        ) : null}
        <details className="rounded border bg-white p-1.5">
          <summary className="cursor-pointer text-[10px] font-medium">
            Advanced (optional)
          </summary>
          <div className="mt-1 space-y-1">
            <textarea
              value={startDraft.content}
              onChange={(e) =>
                setStartDraft((d) => ({ ...d, content: e.target.value }))
              }
              placeholder="Artifact content (optional when results supply it)"
              rows={2}
              className="w-full rounded border px-1.5 py-1"
              aria-label="Artifact content"
            />
            <input
              value={startDraft.expression}
              onChange={(e) =>
                setStartDraft((d) => ({ ...d, expression: e.target.value }))
              }
              placeholder="Formula expression (advanced; ignored when a measure is selected)"
              className="w-full rounded border px-1.5 py-1"
              aria-label="Calculation expression"
            />
            <input
              value={startDraft.recipient}
              onChange={(e) =>
                setStartDraft((d) => ({ ...d, recipient: e.target.value }))
              }
              placeholder="Prepare a send approval for this recipient (optional)"
              className="w-full rounded border px-1.5 py-1"
              aria-label="Send recipient"
              data-testid="assignment-recipient-input"
            />
            <input
              value={startDraft.correlation}
              onChange={(e) =>
                setStartDraft((d) => ({ ...d, correlation: e.target.value }))
              }
              placeholder="Correlation id for an external-fact wait (optional)"
              className="w-full rounded border px-1.5 py-1"
              aria-label="Correlation id"
              data-testid="assignment-correlation-input"
            />
            <input
              value={missingFact}
              onChange={(e) => setMissingFact(e.target.value)}
              placeholder="Missing fact (for example delivery_term)"
              className="w-full rounded border px-1.5 py-1"
              aria-label="Missing fact"
              data-testid="assignment-missing-fact-input"
            />
            <p className="text-[10px] text-muted-foreground">
              Sending stays disabled unless this local build enables the
              controlled transport or a separate live-send authorization is in
              force. Any send step still requires explicit approval.
            </p>
          </div>
        </details>
        <Button
          size="sm"
          disabled={
            busy ||
            !startDraft.objective.trim() ||
            (!startDraft.discover && !selectedSource) ||
            (startDraft.discover && !startDraft.scopeQuery.trim())
          }
          onClick={start}
          data-testid="assignment-start-button"
        >
          <Play className="h-3 w-3" /> Start assignment
        </Button>
      </div>

      {summaries.length === 0 ? (
        <p className="text-muted-foreground">No durable assignments yet.</p>
      ) : (
        <div className="space-y-1">
          {summaries.map((item) => (
            <button
              key={item.run_id}
              type="button"
              data-testid={`assignment-summary-${item.run_id}`}
              onClick={() => setSelected(item.run_id)}
              className={`w-full rounded border px-2 py-1.5 text-left ${
                selected === item.run_id ? "border-indigo-400 bg-indigo-50" : ""
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-medium">
                  {item.assignment.objective || "Untitled assignment"}
                </span>
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                    STATE_STYLES[item.assignment.state] || STATE_STYLES.planned
                  }`}
                >
                  {item.assignment.state}
                </span>
              </div>
              {item.assignment.current_action ? (
                <p className="mt-0.5 truncate text-[10px] text-muted-foreground">
                  Current: {item.assignment.current_action}
                </p>
              ) : null}
            </button>
          ))}
        </div>
      )}

      {detail ? (
        <div className="space-y-3 rounded border p-2" data-testid="assignment-detail">
          <div>
            <div className="flex items-center justify-between gap-2">
              <p className="font-semibold" data-testid="assignment-detail-objective">
                {detail.assignment.objective}
              </p>
              <span
                className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                  STATE_STYLES[detail.assignment.status] || STATE_STYLES.planned
                }`}
              >
                {detail.assignment.status}
              </span>
            </div>
            <p className="text-[10px] text-muted-foreground">
              Plan revision {detail.assignment.plan_revision}
              {detail.assignment.teaching_revision
                ? ` · teaching ${detail.assignment.teaching_revision}`
                : ""}
            </p>
            <p
              className="text-[10px] text-muted-foreground"
              data-testid="teaching-snapshot-note"
            >
              Teaching is snapshotted at start. Later teaching changes apply to
              new work; this assignment keeps its accepted revision until an
              explicit reassessment.
            </p>
          </div>

          {step ? (
            <div className="rounded bg-slate-50 p-2">
              <p className="font-medium">
                {step.status === "awaiting_approval"
                  ? "Awaiting approval"
                  : step.status === "waiting"
                    ? "Waiting"
                    : "Current step"}
                : {step.title}
              </p>
              {waitingParty ? (
                <p className="text-[10px] text-amber-700">
                  Waiting for {waitingParty}
                </p>
              ) : null}
            </div>
          ) : null}

          {step?.status === "waiting" && step.waiting.correlation_id ? (
            <div className="rounded border border-amber-300 bg-amber-50 p-2">
              <p className="font-medium">Correlated response</p>
              <p className="text-[10px]">
                Waiting for {waitingParty || "an external reply"} on{" "}
                {String(step.waiting.correlation_id)}
                {step.waiting.fact
                  ? ` · missing fact: ${String(step.waiting.fact)}`
                  : ""}. Paste only the authorized response; it is evidence,
                not teaching.
              </p>
              <div className="mt-1 flex gap-1">
                <input
                  value={responseDraft}
                  onChange={(e) => setResponseDraft(e.target.value)}
                  placeholder="Authorized response"
                  className="min-w-0 flex-1 rounded border px-1.5 py-1"
                  aria-label="Correlated response"
                />
                <Button
                  size="sm"
                  disabled={busy || !responseDraft.trim()}
                  onClick={() =>
                    act(async () => {
                      const result = await recordAssignmentResponse(
                        detail.run_id,
                        String(step.waiting.correlation_id),
                        responseDraft
                      );
                      if (result?.status === "conflict"
                          || result?.status === "partial") {
                        setNotice(
                          String(result.message || "The reply conflicts with "
                            + "the source and did not complete the wait.")
                        );
                      } else if (result?.status === "unmatched") {
                        setNotice(
                          String(result.message || "The reply did not match "
                            + "an open correlation.")
                        );
                      }
                    }, detail.run_id)
                  }
                >
                  <Send className="h-3 w-3" /> Deliver
                </Button>
              </div>
            </div>
          ) : null}

          <div>
            <p className="mb-1 font-medium">Completed work</p>
            <ul className="space-y-0.5">
              {detail.assignment.steps
                .filter((s) => s.status === "applied")
                .map((s) => (
                  <li key={s.step_id} className="flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                    <span>{s.title}</span>
                  </li>
                ))}
              {detail.assignment.steps.every((s) => s.status !== "applied") ? (
                <li className="text-muted-foreground">Nothing completed yet.</li>
              ) : null}
            </ul>
            {detail.assignment.steps.some(
              (s) => s.status === "applied" && s.result_value
            ) ? (
              <ul className="mt-1 space-y-0.5" data-testid="assignment-results">
                {detail.assignment.steps
                  .filter((s) => s.status === "applied" && s.result_value)
                  .map((s) => (
                    <li
                      key={`${s.step_id}-result`}
                      data-testid={`assignment-result-${s.step_id}`}
                      className="text-xs"
                    >
                      <span className="font-medium">
                        Result: {s.result_value} {s.result_unit || ""}
                      </span>
                      {s.result_measure ? (
                        <span className="text-muted-foreground">
                          {" "}· {s.result_measure}
                        </span>
                      ) : null}
                    </li>
                  ))}
              </ul>
            ) : null}
          </div>

          {detail.assignment.deliverables.length ? (
            <div data-testid="assignment-deliverables">
              <p className="mb-1 font-medium">Artifacts</p>
              <ul className="space-y-0.5">
                {detail.assignment.deliverables.map((d) => (
                  <li key={d.deliverable_id} className="flex items-center gap-1">
                    <FileText className="h-3 w-3" />
                    <span>{d.description || d.kind}</span>
                    <Badge variant="outline" className="text-[9px]">
                      {d.status}
                    </Badge>
                    {d.artifact_path ? (
                      <button
                        type="button"
                        className="ml-auto inline-flex items-center gap-1 text-[10px] text-indigo-600 underline"
                        disabled={busy}
                        onClick={() => downloadArtifact(d.deliverable_id)}
                        data-testid={`assignment-download-${testIdPart(d.deliverable_id)}`}
                      >
                        <Download className="h-3 w-3" /> Download
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {(detail.assignment.mappings || []).length ? (
            <div className="space-y-2" data-testid="assignment-mappings">
              <p className="font-medium">Mappings</p>
              {(detail.assignment.mappings || []).map((mapping) => {
                const mappingId = testIdPart(mapping.concept);
                const editing = correction?.concept === mapping.concept;
                return (
                  <div
                    key={`${mapping.concept}:${mapping.sheet}`}
                    className="rounded border p-2 text-xs"
                    data-testid={`mapping-current-${mappingId}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-0.5">
                        <p className="font-medium">
                          {mapping.concept} → {mapping.column}
                        </p>
                        <p className="text-muted-foreground">
                          Source: {mapping.source || "unknown"} · Sheet:{" "}
                          {mapping.sheet} · Version:{" "}
                          {String(mapping.source_version || "").slice(0, 12)}
                        </p>
                        <p className="text-muted-foreground">
                          Required unit:{" "}
                          {mapping.required_unit || "not specified"} ·
                          Established: {authorityLabel(mapping.unit_authority)}
                          {mapping.source_unit
                            ? ` (${mapping.source_unit})`
                            : ""}
                        </p>
                        <p className="text-muted-foreground">
                          Mapping revision: {mapping.revision} · Teaching
                          revision:{" "}
                          {mapping.teaching_revision ||
                            mapping.lesson_revision ||
                            "—"}
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        data-testid={`mapping-correct-${mappingId}`}
                        disabled={busy || !mapping.correctable}
                        onClick={() => {
                          setCorrection({
                            concept: mapping.concept,
                            column: mapping.column,
                            unit: mapping.source_unit || mapping.unit || "",
                          });
                        }}
                      >
                        <Pencil className="mr-1 h-3 w-3" />
                        Correct mapping
                      </Button>
                    </div>
                    {editing && correction ? (
                      <div
                        className="mt-2 space-y-2 rounded bg-muted/40 p-2"
                        data-testid="mapping-correction-form"
                      >
                        <p className="font-medium">
                          Correct {mapping.concept}
                        </p>
                        <p className="text-muted-foreground">
                          Current: {mapping.column} · revision{" "}
                          {mapping.revision}. The replacement is validated
                          against the current authorized source.
                        </p>
                        <label className="block">
                          Replacement column
                        </label>
                        <select
                          data-testid="mapping-correction-column"
                          className="w-full rounded border px-2 py-1 text-xs"
                          value={correction.column}
                          onChange={(e) =>
                            setCorrection({
                              ...correction,
                              column: e.target.value,
                            })
                          }
                        >
                          <option value="">Select a column</option>
                          {mapping.available_columns.map((column) => (
                            <option key={column} value={column}>
                              {column}
                              {mapping.numeric_columns.includes(column)
                                ? " (numeric)"
                                : ""}
                            </option>
                          ))}
                        </select>
                        {mapping.required_unit && !mapping.source_unit ? (
                          <div>
                            <label className="block">Unit</label>
                            <input
                              data-testid="mapping-correction-unit"
                              className="w-full rounded border px-2 py-1 text-xs"
                              value={correction.unit}
                              onChange={(e) =>
                                setCorrection({
                                  ...correction,
                                  unit: e.target.value,
                                })
                              }
                              placeholder={`Required: ${mapping.required_unit}`}
                            />
                          </div>
                        ) : (
                          <p data-testid="mapping-correction-unit-established">
                            Unit:{" "}
                            {mapping.source_unit ||
                              mapping.unit ||
                              "not established"}{" "}
                            ({authorityLabel(mapping.unit_authority)})
                          </p>
                        )}
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            data-testid="mapping-correction-submit"
                            disabled={
                              busy ||
                              !correction.column ||
                              correction.column === mapping.column ||
                              (Boolean(mapping.required_unit) &&
                                !mapping.source_unit &&
                                !correction.unit.trim())
                            }
                            onClick={() =>
                              act(async () => {
                                await correctAssignmentMapping(
                                  detail.run_id,
                                  {
                                    concept: mapping.concept,
                                    expected_revision: mapping.revision,
                                    column: correction.column,
                                    unit:
                                      mapping.source_unit ||
                                      correction.unit ||
                                      "",
                                    evidence:
                                      "mapping corrected from Assignments panel",
                                    sheet: mapping.sheet,
                                    source_version:
                                      mapping.source_version || undefined,
                                  }
                                );
                                setCorrection(null);
                              }, detail.run_id)
                            }
                          >
                            Apply correction
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            data-testid="mapping-correction-cancel"
                            disabled={busy}
                            onClick={() => setCorrection(null)}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          ) : null}

          {openGaps.length ? (
            <div className="space-y-2" data-testid="assignment-gaps">
              <p className="font-medium">Missing information</p>
              {openGaps.map((gap) => {
                const mapping = gap?.inputs?.mapping;
                const candidates = Array.isArray(mapping?.candidates)
                  ? mapping.candidates
                  : [];
                return (
                <div key={gap.question_id} className="rounded border p-2">
                  <p>{gap.question}</p>
                  <p className="text-[10px] text-muted-foreground">
                    {gap.reason || gap.concept || ""}
                    {gap.next_retrieval
                      ? ` · Next: ${gap.next_retrieval}`
                      : ""}
                    {gap.resolver ? ` · Resolver: ${gap.resolver}` : ""}
                  </p>
                  {mapping && candidates.length ? (
                    <div className="mt-2 space-y-1" data-testid="mapping-candidates">
                      <p className="text-[10px] text-muted-foreground">
                        Concept: {String(mapping.concept || "")} · Sheet:{" "}
                        {String(mapping.sheet || "")} · Version:{" "}
                        {String(mapping.source_version || "")}
                        {mapping.mapping_source?.unit
                          ? ` · Taught unit: ${mapping.mapping_source.unit}`
                          : ""}
                        {mapping.source_unit
                          ? ` · Source unit: ${mapping.source_unit}${
                              mapping.source_unit_column
                                ? ` (${mapping.source_unit_column})`
                                : ""
                            }`
                          : " · Source unit: not established"}
                        {mapping.teaching_revision
                          ? ` · Teaching revision: ${mapping.teaching_revision}`
                          : ""}
                      </p>
                      {mapping.required_unit && !mapping.source_unit ? (
                        <div className="space-y-1">
                          <p
                            data-testid="mapping-unit-unresolved"
                            className="text-[10px] text-amber-700"
                          >
                            Unit is unresolved. Required:{" "}
                            {mapping.required_unit}. Confirm the unit
                            explicitly; no conversion is applied.
                          </p>
                          <input
                            data-testid="mapping-unit-input"
                            value={gapDrafts[`${gap.question_id}:unit`] || ""}
                            onChange={(e) =>
                              setGapDrafts((d) => ({
                                ...d,
                                [`${gap.question_id}:unit`]: e.target.value,
                              }))
                            }
                            placeholder={`Confirm unit (required: ${mapping.required_unit})`}
                            className="w-full rounded border px-2 py-1 text-xs"
                            aria-label="Mapping unit"
                          />
                        </div>
                      ) : null}
                      {candidates.map((candidate: any) => (
                        <button
                          key={candidate.column}
                          type="button"
                          data-testid={`mapping-candidate-${candidate.column}`}
                          className="block w-full rounded border px-2 py-1 text-left text-xs hover:bg-muted"
                          disabled={busy || (Boolean(mapping.required_unit) && !mapping.source_unit && !gapDrafts[`${gap.question_id}:unit`]?.trim())}
                          onClick={() =>
                            act(
                              () =>
                                resolveAssignmentGap(
                                  detail.run_id,
                                  gap.question_id,
                                  JSON.stringify({
                                    request_id: gap.question_id,
                                    assignment_id: detail.assignment?.assignment_id,
                                    column: candidate.column,
                                    unit: mapping.source_unit || gapDrafts[`${gap.question_id}:unit`] || "",
                                    source_version: mapping.source_version || undefined,
                                    teaching_revision: mapping.teaching_revision || undefined,
                                  })
                                ),
                              detail.run_id
                            )
                          }
                        >
                          <span className="font-medium">{candidate.column}</span>
                          <span className="ml-2 text-muted-foreground">
                            {candidate.inferred_type || "value"}
                            {Array.isArray(candidate.sample_values) &&
                            candidate.sample_values.length
                              ? ` · ${candidate.sample_values.join(", ")}`
                              : ""}
                          </span>
                        </button>
                      ))}
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy}
                        data-testid="mapping-reject"
                        onClick={() =>
                          act(async () => {
                            await resolveAssignmentGap(
                              detail.run_id,
                              gap.question_id,
                              JSON.stringify({
                                rejected: true,
                                request_id: gap.question_id,
                                assignment_id: detail.assignment?.assignment_id,
                              })
                            );
                            setNotice(
                              "Candidates rejected. The same request remains open; no mapping was applied."
                            );
                          }, detail.run_id)
                        }
                      >
                        None of these
                      </Button>
                    </div>
                  ) : (
                    <div className="mt-1 flex gap-1">
                      <input
                        value={gapDrafts[gap.question_id] || ""}
                        onChange={(e) =>
                          setGapDrafts((d) => ({
                            ...d,
                            [gap.question_id]: e.target.value,
                          }))
                        }
                        placeholder="Answer"
                        className="min-w-0 flex-1 rounded border px-1.5 py-1"
                        aria-label="Gap answer"
                      />
                      <Button
                        size="sm"
                        aria-label={`Resolve gap: ${gap.question}`}
                        disabled={busy || !gapDrafts[gap.question_id]?.trim()}
                        onClick={() =>
                          act(
                            () =>
                              resolveAssignmentGap(
                                detail.run_id,
                                gap.question_id,
                                gapDrafts[gap.question_id]
                              ),
                            detail.run_id
                          )
                        }
                      >
                        <Send className="h-3 w-3" />
                      </Button>
                    </div>
                  )}
                </div>
                );
              })}
            </div>
          ) : null}

          {step?.status === "awaiting_approval" ? (
            <div className="rounded border border-amber-300 bg-amber-50 p-2">
              <p className="font-medium">Approval required</p>
              <p className="text-[10px]">
                Purpose: {String(step.approval_request.purpose || step.title)}
              </p>
              <p className="break-all text-[10px] text-muted-foreground">
                Payload {String(step.approval_request.payload_sha256 || "").slice(0, 16)}
                {step.approval_request.artifact_revision
                  ? ` · artifact ${String(step.approval_request.artifact_revision)}`
                  : ""}
              </p>
              <Button
                size="sm"
                className="mt-1"
                disabled={busy}
                onClick={() =>
                  act(
                    () =>
                      approveAssignmentStep(detail.run_id, step.step_id),
                    detail.run_id
                  )
                }
              >
                Approve this payload
              </Button>
            </div>
          ) : null}

          {uncertain ? (
            <div className="rounded border border-rose-300 bg-rose-50 p-2">
              <p className="flex items-center gap-1 font-medium text-rose-800">
                <AlertTriangle className="h-3.5 w-3.5" />
                External outcome uncertain
              </p>
              <p className="text-[10px]">
                {String(uncertain.failure?.message || "The provider may have accepted the effect.")}
                {" "}It will not be resent automatically. Reconcile before retrying.
              </p>
            </div>
          ) : null}

          <div className="flex flex-wrap gap-1">
            <Button
              size="sm"
              variant="outline"
              disabled={busy || ["completed", "cancelled", "failed"].includes(
                detail.assignment.status
              )}
              onClick={() => act(() => resumeAssignment(detail.run_id), detail.run_id)}
            >
              <Play className="h-3 w-3" /> Resume
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={busy || detail.assignment.status === "cancelled"}
              onClick={() =>
                act(
                  () => cancelAssignment(detail.run_id, "cancelled from panel"),
                  detail.run_id
                )
              }
            >
              <XCircle className="h-3 w-3" /> Cancel
            </Button>
            {["waiting", "blocked", "partial"].includes(detail.assignment.status) ? (
              <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                <Clock className="h-3 w-3" /> Durable state persisted
              </span>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
