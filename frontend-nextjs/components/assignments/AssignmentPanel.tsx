"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
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
  AssignmentDetail,
  AssignmentStep,
  AssignmentSummary,
  cancelAssignment,
  correctAssignmentMapping,
  createAssignment,
  getAssignment,
  listAssignments,
  recordAssignmentResponse,
  resolveAssignmentGap,
  resumeAssignment,
} from "@/lib/assignment-api";

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
  const [startDraft, setStartDraft] = useState({
    objective: "",
    sourcePath: "",
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

  useEffect(() => {
    refreshList();
  }, [refreshList]);

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

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const sourceKind = /\.xlsx?$/i.test(startDraft.sourcePath)
        ? "workbook"
        : "document";
      const payload: Parameters<typeof createAssignment>[0] = {
        objective: startDraft.objective,
        agent_id: agentId || undefined,
        sources: startDraft.discover
          ? []
          : [{ kind: sourceKind, path: startDraft.sourcePath }],
        discover: startDraft.discover,
        source_scope: startDraft.discover
          ? { query: startDraft.scopeQuery }
          : undefined,
        deliverables: [{
          kind: startDraft.deliverableKind,
          description: startDraft.objective,
          content: startDraft.content.trim() || undefined,
        }],
      };
      if (startDraft.expression.trim()) {
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
        sourcePath: "",
        deliverableKind: "document",
        content: "",
        recipient: "",
        expression: "",
        correlation: "",
        discover: false,
        scopeQuery: "",
      });
      setSelected(result.run_id);
      await refreshList();
      await refreshDetail(result.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start assignment");
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

      <div className="space-y-1 rounded border bg-slate-50 p-2" data-testid="assignment-start">
        <p className="font-medium">Start durable work</p>
        <textarea
          value={startDraft.objective}
          onChange={(e) =>
            setStartDraft((d) => ({ ...d, objective: e.target.value }))
          }
          placeholder="Objective"
          rows={2}
          className="w-full rounded border px-1.5 py-1"
          aria-label="Assignment objective"
        />
        <label className="flex items-center gap-1 text-[10px]">
          <input
            type="checkbox"
            checked={startDraft.discover}
            onChange={(e) =>
              setStartDraft((d) => ({ ...d, discover: e.target.checked }))
            }
            aria-label="Discover resource from scope"
          />
          Discover an authorized resource from a scope (ordinary employee)
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
          />
        ) : (
          <input
            value={startDraft.sourcePath}
            onChange={(e) =>
              setStartDraft((d) => ({ ...d, sourcePath: e.target.value }))
            }
            placeholder="Authorized source reference (advanced/controlled)"
            className="w-full rounded border px-1.5 py-1"
            aria-label="Authorized source path"
          />
        )}
        {!startDraft.discover ? (
          <textarea
            value={startDraft.content}
            onChange={(e) =>
              setStartDraft((d) => ({ ...d, content: e.target.value }))
            }
            placeholder="Artifact content (optional when a calculation supplies the result)"
            rows={2}
            className="w-full rounded border px-1.5 py-1"
            aria-label="Artifact content"
          />
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
            className="rounded border px-1.5 py-1"
            aria-label="Deliverable kind"
          >
            <option value="document">Document</option>
            <option value="presentation">Presentation</option>
            <option value="email_draft">Email draft</option>
          </select>
          <input
            value={startDraft.expression}
            onChange={(e) =>
              setStartDraft((d) => ({ ...d, expression: e.target.value }))
            }
            placeholder="Calculation expression (optional)"
            className="min-w-0 flex-1 rounded border px-1.5 py-1"
            aria-label="Calculation expression"
          />
        </div>
        <input
          value={startDraft.recipient}
          onChange={(e) =>
            setStartDraft((d) => ({ ...d, recipient: e.target.value }))
          }
          placeholder="Test recipient (optional, controlled transport)"
          className="w-full rounded border px-1.5 py-1"
          aria-label="Test recipient"
        />
        <input
          value={startDraft.correlation}
          onChange={(e) =>
            setStartDraft((d) => ({ ...d, correlation: e.target.value }))
          }
          placeholder="Correlation id (optional external-fact wait)"
          className="w-full rounded border px-1.5 py-1"
          aria-label="Correlation id"
        />
        <Button
          size="sm"
          disabled={
            busy ||
            !startDraft.objective.trim() ||
            (!startDraft.discover && !startDraft.sourcePath.trim()) ||
            (startDraft.discover && !startDraft.scopeQuery.trim())
          }
          onClick={start}
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
                {String(step.waiting.correlation_id)}. Paste only the
                authorized response; it is evidence, not teaching.
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
                    act(
                      () =>
                        recordAssignmentResponse(
                          detail.run_id,
                          String(step.waiting.correlation_id),
                          responseDraft
                        ),
                      detail.run_id
                    )
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
