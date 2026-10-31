"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Link2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  applyLearningCandidate,
  confirmLearningCandidate,
  createLearningCandidate,
  getLearningCandidate,
  LearningCandidatePayload,
  LearningEmployee,
  LearningReview,
  listLearningCandidates,
  listLearningEmployees,
  promoteLearningCandidate,
  rejectLearningCandidate,
  resolveLearningDependency,
} from "@/lib/conversation-learning-api";

function errorText(err: any, fallback: string): string {
  const payload = err?.response?.data
    || err?.technical?.response?.data
    || err?.technical?.response;
  const detail = payload?.detail ?? payload;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail === "object") {
    if (detail.error === "teaching_context_required"
        || detail.reason === "teaching_context_required") {
      const missing = detail.applicability?.missing || [];
      return `Missing required context: ${missing.join(", ") || "unknown"}`;
    }
    if (detail.error === "teaching_context_mismatch"
        || detail.reason === "teaching_context_mismatch") {
      const conflicts = detail.applicability?.conflicts || [];
      const text = conflicts.map((item: any) =>
        `${item.key}: ${item.required} vs ${item.actual}`).join("; ");
      return `Teaching does not apply to this context${text ? ` (${text})` : ""}.`;
    }
    return String(detail.message || detail.error || detail.reason
      || JSON.stringify(detail));
  }
  return String(err?.message || fallback);
}

const STATUS_STYLES: Record<string, string> = {
  review_ready: "bg-emerald-100 text-emerald-800",
  confirmed: "bg-sky-100 text-sky-800",
  promoted: "bg-emerald-100 text-emerald-800",
  needs_clarification: "bg-amber-100 text-amber-800",
  rejected: "bg-rose-100 text-rose-800",
  invalidated: "bg-rose-100 text-rose-800",
};

function statusBadge(status: string) {
  return (
    <Badge className={STATUS_STYLES[status] || "bg-slate-100 text-slate-700"}>
      {status.replace(/_/g, " ")}
    </Badge>
  );
}

function methodSummary(review: LearningReview): string {
  const method = review.method_and_assumptions.method || {};
  const inputs = (method.inputs || [])
    .map((item: any) => `${item.concept} (${item.unit || "unit not stated"})`)
    .join(", ");
  return [
    method.operation || "operation not stated",
    inputs ? `inputs: ${inputs}` : "",
    method.transformation || "",
  ].filter(Boolean).join(" · ");
}

function dependencyAnswer(
  dep: LearningReview["unresolved_questions"][number],
  draft: string,
): Record<string, unknown> {
  if (dep.kind === "unit") return { unit: draft };
  if (dep.kind === "mapping") return { column: draft };
  if (dep.kind === "method" || dep.kind === "method_reference") {
    return { value: draft };
  }
  if (dep.kind === "applicability") return { value: draft };
  return { value: draft };
}

export function ConversationLearningReview({
  threadId,
  candidateId = null,
  reviewer = "owner",
  className = "",
}: {
  threadId: string;
  candidateId?: string | null;
  reviewer?: string;
  className?: string;
}) {
  const [payload, setPayload] = useState<LearningCandidatePayload | null>(null);
  const [employees, setEmployees] = useState<LearningEmployee[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [resources, setResources] = useState<Record<string, string>>({});
  const [applyValues, setApplyValues] = useState<Record<string, string>>({});
  const [applyContext, setApplyContext] = useState({
    customer: "",
    qualification: "",
  });
  const [applyResult, setApplyResult] = useState<string | null>(null);
  const [draft, setDraft] = useState({
    agentId: "",
    lesson: "",
    appliesTo: "pricing",
    outcome: "",
    operation: "sum",
    concept1: "amount",
    column1: "",
    unit1: "USD",
    concept2: "",
    column2: "",
    unit2: "",
    customer: "",
    qualification: "",
    methodStatus: "explicit",
    guidanceOnly: false,
    formatSpec: "",
    conditions: "",
    decisionOptions: "",
  });

  const load = useCallback(async () => {
    setError(null);
    try {
      if (candidateId) {
        setPayload(await getLearningCandidate(threadId, candidateId));
        return;
      }
      const rows = await listLearningCandidates(threadId);
      setPayload(rows[0] || null);
    } catch (err: any) {
      setError(errorText(err, "Could not load the learning review"));
    }
  }, [threadId, candidateId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    let cancelled = false;
    listLearningEmployees()
      .then((rows) => {
        if (cancelled) return;
        setEmployees(rows);
        setDraft((current) => current.agentId || !rows.length
          ? current
          : { ...current, agentId: rows[0].id });
      })
      .catch(() => {
        if (!cancelled) setEmployees([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const review = payload?.review;
  const selectedAgentId = draft.agentId || employees[0]?.id || "";
  const unresolved = review?.unresolved_questions || [];

  const resourceOptions = useMemo(() => {
    const out: Array<{ id: string; label: string }> = [];
    const seen = new Set<string>();
    for (const ref of review?.referenced_data_and_versions || []) {
      for (const item of ref.candidates || []) {
        if (!item.resource_id || seen.has(item.resource_id)) continue;
        seen.add(item.resource_id);
        out.push({
          id: item.resource_id,
          label: `${item.original_file_name || item.dataset_name || item.resource_id}`
            + (item.sheet ? ` / ${item.sheet}` : "")
            + (item.source_version ? ` (${item.source_version.slice(0, 8)})` : ""),
        });
      }
    }
    return out;
  }, [review]);

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      const inputs = [
        {
          concept: draft.concept1,
          column: draft.column1,
          unit: draft.unit1,
          unit_required: true,
        },
        ...(draft.concept2
          ? [{
              concept: draft.concept2,
              column: draft.column2,
              unit: draft.unit2,
              unit_required: true,
            }]
          : []),
      ];
      const parseObject = (raw: string, label: string) => {
        if (!raw.trim()) return {};
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          throw new Error(`${label} must be a JSON object`);
        }
        return parsed;
      };
      const formatSpec = parseObject(draft.formatSpec, "Format spec");
      const conditions = parseObject(draft.conditions, "Conditions");
      const decisionOptions = draft.decisionOptions
        .split(",").map((item) => item.trim()).filter(Boolean);
      const created = await createLearningCandidate({
        thread_id: threadId,
        agent_id: selectedAgentId,
        proposed_lesson: draft.lesson,
        applies_to: draft.appliesTo
          .split(",").map((item) => item.trim()).filter(Boolean),
        context: {
          ...(draft.customer ? { customer: draft.customer } : {}),
          ...(draft.qualification
            ? { qualification: draft.qualification } : {}),
        },
        ...(Object.keys(formatSpec).length
          ? { format_spec: formatSpec } : {}),
        ...(Object.keys(conditions).length
          ? { conditions } : {}),
        ...(decisionOptions.length
          ? { decision_options: decisionOptions } : {}),
        ...(draft.guidanceOnly
          ? { method: {}, method_status: "not_applicable" }
          : {
              method: {
                intended_outcome: draft.outcome || draft.lesson,
                operation: draft.operation,
                inputs,
                output_unit: draft.unit2 || draft.unit1,
                transformation: draft.operation === "sum"
                  ? "sum of the declared input"
                  : "declared by the reviewer",
              },
              method_status: draft.methodStatus,
            }),
      });
      setPayload(created);
      setNotice("Candidate drafted. Resolve the remaining questions before confirmation.");
    } catch (err: any) {
      setError(errorText(err, "Could not draft the candidate"));
    } finally {
      setBusy(false);
    }
  };

  const resolve = async (dep: LearningReview["unresolved_questions"][number]) => {
    if (!review) return;
    setBusy(true);
    setError(null);
    try {
      const resourceId = resources[dep.dependency_id] || "";
      const answer = answers[dep.dependency_id] || "";
      const resolved = await resolveLearningDependency(
        threadId,
        review.candidate_id,
        {
          dependency_id: dep.dependency_id,
          resource_id: resourceId,
          ...dependencyAnswer(dep, answer),
          confirmed_by: reviewer,
        },
      );
      setPayload(resolved);
      setNotice("Answer recorded. The candidate needs review again.");
    } catch (err: any) {
      setError(errorText(err, "Could not resolve the question"));
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    if (!review) return;
    setBusy(true);
    setError(null);
    try {
      const confirmed = await confirmLearningCandidate(
        threadId, review.candidate_id, reviewer, review.revision);
      setPayload(confirmed);
      setNotice("Review confirmed. Promotion will bind this exact revision and digest.");
    } catch (err: any) {
      setError(errorText(err, "Could not confirm the review"));
    } finally {
      setBusy(false);
    }
  };

  const promote = async () => {
    if (!review) return;
    setBusy(true);
    setError(null);
    try {
      const promoted = await promoteLearningCandidate(
        threadId, review.candidate_id, reviewer,
        review.revision, review.digest);
      setNotice(`Lesson promoted (${promoted.lesson_id}).`);
      await load();
    } catch (err: any) {
      setError(errorText(err, "Could not promote the lesson"));
    } finally {
      setBusy(false);
    }
  };

  const apply = async () => {
    if (!review) return;
    setBusy(true);
    setError(null);
    setApplyResult(null);
    try {
      const method = review.method_and_assumptions.method || {};
      const row: Record<string, string> = {};
      for (const input of method.inputs || []) {
        const column = String(input.column || input.concept || "");
        if (column) row[column] = applyValues[input.concept] || "";
      }
      const applied = await applyLearningCandidate(
        threadId, review.candidate_id, [row], {},
        {
          ...(applyContext.customer
            ? { customer: applyContext.customer } : {}),
          ...(applyContext.qualification
            ? { qualification: applyContext.qualification } : {}),
        });
      setApplyResult(
        `${applied.result.value} ${applied.result.unit || ""}`.trim());
    } catch (err: any) {
      setError(errorText(err, "Could not apply the approved method"));
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (!review) return;
    setBusy(true);
    setError(null);
    try {
      const rejected = await rejectLearningCandidate(
        threadId, review.candidate_id, reviewer, "Rejected in review");
      setPayload(rejected);
      setNotice("Proposal rejected. No lesson was written.");
    } catch (err: any) {
      setError(errorText(err, "Could not reject the proposal"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={`space-y-3 text-xs ${className}`} data-testid="conversation-learning-review">
      {error ? (
        <p className="rounded border border-rose-200 bg-rose-50 p-2 text-rose-700" data-testid="learning-error">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="rounded border border-emerald-200 bg-emerald-50 p-2 text-emerald-700" data-testid="learning-notice">
          {notice}
        </p>
      ) : null}

      {!review ? (
        <div className="space-y-2 rounded border bg-slate-50 p-3" data-testid="learning-draft-form">
          <p className="font-semibold">Draft a lesson from this conversation</p>
          <label className="block">
            Employee
            <select
              className="mt-1 w-full rounded border p-1"
              data-testid="learning-employee-select"
              value={selectedAgentId}
              onChange={(event) => setDraft({ ...draft, agentId: event.target.value })}
            >
              <option value="">Select an employee</option>
              {employees.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.name}
                  {employee.status ? ` · ${employee.status}` : ""}
                </option>
              ))}
            </select>
            {!employees.length ? (
              <span className="mt-1 block text-slate-500">
                No authorized employees in this workspace.
              </span>
            ) : null}
          </label>
          <label className="block">
            Proposed lesson
            <textarea
              className="mt-1 w-full rounded border p-1"
              data-testid="learning-lesson-input"
              value={draft.lesson}
              onChange={(event) => setDraft({ ...draft, lesson: event.target.value })}
              rows={2}
            />
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              data-testid="learning-guidance-only"
              checked={draft.guidanceOnly}
              onChange={(event) => setDraft({
                ...draft,
                guidanceOnly: event.target.checked,
                methodStatus: event.target.checked
                  ? "not_applicable" : "explicit",
              })}
            />
            Guidance only (style, protocol, preference or approach — no
            calculation method)
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label>
              Applies to
              <input
                className="mt-1 w-full rounded border p-1"
                data-testid="learning-applies-input"
                value={draft.appliesTo}
                onChange={(event) => setDraft({ ...draft, appliesTo: event.target.value })}
              />
            </label>
            <label>
              Operation
              <select
                className="mt-1 w-full rounded border p-1"
                data-testid="learning-operation-select"
                value={draft.operation}
                onChange={(event) => setDraft({ ...draft, operation: event.target.value })}
              >
                <option value="sum">sum</option>
                <option value="count">count</option>
                <option value="multiply_sum">multiply_sum</option>
                <option value="percentage">percentage</option>
                <option value="ratio">ratio</option>
              </select>
            </label>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <input className="rounded border p-1" data-testid="learning-concept-1" value={draft.concept1} onChange={(e) => setDraft({ ...draft, concept1: e.target.value })} placeholder="input concept" />
            <input className="rounded border p-1" data-testid="learning-column-1" value={draft.column1} onChange={(e) => setDraft({ ...draft, column1: e.target.value })} placeholder="column" />
            <input className="rounded border p-1" data-testid="learning-unit-1" value={draft.unit1} onChange={(e) => setDraft({ ...draft, unit1: e.target.value })} placeholder="unit" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <input className="rounded border p-1" data-testid="learning-format-input" value={draft.formatSpec} onChange={(e) => setDraft({ ...draft, formatSpec: e.target.value })} placeholder='format spec JSON, e.g. {"greeting":"Dear colleague,"}' />
            <input className="rounded border p-1" data-testid="learning-conditions-input" value={draft.conditions} onChange={(e) => setDraft({ ...draft, conditions: e.target.value })} placeholder='conditions JSON, e.g. {"recipient":"@example.com"}' />
          </div>
          <input className="w-full rounded border p-1" data-testid="learning-decisions-input" value={draft.decisionOptions} onChange={(e) => setDraft({ ...draft, decisionOptions: e.target.value })} placeholder="review decision labels, comma separated (optional)" />
          <div className="grid grid-cols-2 gap-2">
            <input className="rounded border p-1" data-testid="learning-customer-input" value={draft.customer} onChange={(e) => setDraft({ ...draft, customer: e.target.value })} placeholder="customer (optional)" />
            <input className="rounded border p-1" data-testid="learning-qualification-input" value={draft.qualification} onChange={(e) => setDraft({ ...draft, qualification: e.target.value })} placeholder="qualification (optional)" />
          </div>
          <div className="grid grid-cols-3 gap-2">
            <input className="rounded border p-1" data-testid="learning-concept-2" value={draft.concept2} onChange={(e) => setDraft({ ...draft, concept2: e.target.value })} placeholder="second input concept (optional)" />
            <input className="rounded border p-1" data-testid="learning-column-2" value={draft.column2} onChange={(e) => setDraft({ ...draft, column2: e.target.value })} placeholder="second column" />
            <input className="rounded border p-1" data-testid="learning-unit-2" value={draft.unit2} onChange={(e) => setDraft({ ...draft, unit2: e.target.value })} placeholder="second unit" />
          </div>
          <Button data-testid="learning-draft-button" disabled={busy || !selectedAgentId || !draft.lesson} onClick={create}>
            Draft candidate
          </Button>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold" data-testid="learning-proposed-lesson">
              {review.proposed_lesson}
            </h3>
            {statusBadge(review.status)}
            <span className="text-slate-500">revision {review.revision}</span>
          </div>

          <div className="grid gap-2 md:grid-cols-2">
            <div className="rounded border p-2" data-testid="learning-applies-to">
              <p className="font-semibold">Where it applies</p>
              <p>{(review.where_it_applies.applies_to || []).join(", ") || "not stated"}</p>
              {Object.keys(review.where_it_applies.context || {}).length ? (
                <pre className="mt-1 whitespace-pre-wrap text-[11px]">
                  {JSON.stringify(review.where_it_applies.context, null, 2)}
                </pre>
              ) : null}
            </div>
            <div className="rounded border p-2" data-testid="learning-method">
              <p className="font-semibold">Method and assumptions</p>
              <p>{methodSummary(review)}</p>
              <p className="text-slate-500">status: {review.method_and_assumptions.method_status}</p>
              {review.artifact_and_protocol?.format_spec
                && Object.keys(review.artifact_and_protocol.format_spec).length ? (
                <pre className="mt-1 whitespace-pre-wrap text-[11px]">
                  {JSON.stringify(review.artifact_and_protocol.format_spec, null, 2)}
                </pre>
              ) : null}
              {review.artifact_and_protocol?.decision_options?.length ? (
                <p className="mt-1">
                  decisions: {review.artifact_and_protocol.decision_options.join(", ")}
                </p>
              ) : null}
              {(review.method_and_assumptions.method.assumptions || []).length ? (
                <ul className="mt-1 list-disc pl-4">
                  {review.method_and_assumptions.method.assumptions.map((item: string, index: number) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          </div>

          <div className="rounded border p-2" data-testid="learning-references">
            <p className="font-semibold">Referenced data and versions</p>
            {review.referenced_data_and_versions.length ? (
              <ul className="mt-1 space-y-1">
                {review.referenced_data_and_versions.map((ref, index) => (
                  <li key={index} className="flex flex-wrap items-center gap-2">
                    <Link2 className="h-3 w-3" />
                    <span>{ref.reference}</span>
                    <Badge>{ref.status}</Badge>
                    {ref.file_name ? <span>{ref.file_name}</span> : null}
                    {ref.sheet ? <span>/ {ref.sheet}</span> : null}
                    {ref.source_version ? (
                      <span className="text-slate-500">v{ref.source_version.slice(0, 8)}</span>
                    ) : null}
                    {ref.candidates.length ? (
                      <span className="text-slate-500">
                        candidates: {ref.candidates.map((item) =>
                          `${item.original_file_name || item.dataset_name || item.resource_id}`
                          + (item.sheet ? ` / ${item.sheet}` : "")
                        ).join(", ")}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-slate-500">No resource references.</p>
            )}
          </div>

          <div className="rounded border p-2" data-testid="learning-exceptions">
            <p className="font-semibold">Exceptions</p>
            {review.exceptions.length ? (
              <ul className="mt-1 list-disc pl-4">
                {review.exceptions.map((item, index) => (
                  <li key={index}>{JSON.stringify(item)}</li>
                ))}
              </ul>
            ) : (
              <p className="text-slate-500">None stated.</p>
            )}
          </div>

          <div className="rounded border p-2" data-testid="learning-unresolved">
            <p className="font-semibold">Unresolved questions</p>
            {unresolved.length ? (
              <ul className="mt-1 space-y-2">
                {unresolved.map((dep) => (
                  <li key={dep.dependency_id} className="space-y-1">
                    <p>{dep.question}</p>
                    <div className="flex flex-wrap items-center gap-1">
                      {resourceOptions.length ? (
                        <select
                          className="rounded border p-1"
                          data-testid={`learning-resource-${dep.dependency_id}`}
                          value={resources[dep.dependency_id] || ""}
                          onChange={(event) => setResources({
                            ...resources,
                            [dep.dependency_id]: event.target.value,
                          })}
                        >
                          <option value="">Select resource</option>
                          {resourceOptions.map((item) => (
                            <option key={item.id} value={item.id}>{item.label}</option>
                          ))}
                        </select>
                      ) : null}
                      <input
                        className="rounded border p-1"
                        data-testid={`learning-answer-${dep.dependency_id}`}
                        value={answers[dep.dependency_id] || ""}
                        onChange={(event) => setAnswers({
                          ...answers,
                          [dep.dependency_id]: event.target.value,
                        })}
                        placeholder="answer / column / unit"
                      />
                      <Button
                        data-testid={`learning-resolve-${dep.dependency_id}`}
                        disabled={busy}
                        onClick={() => resolve(dep)}
                      >
                        Resolve
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-emerald-700">No unresolved questions.</p>
            )}
          </div>

          <div className="rounded border p-2" data-testid="learning-supporting-messages">
            <p className="font-semibold">Supporting messages</p>
            <ul className="mt-1 space-y-1">
              {review.supporting_messages.map((message) => (
                <li key={message.message_id}>
                  {message.message_id}
                  {message.is_authority ? (
                    <Badge className="ml-2 bg-sky-100 text-sky-800">authority</Badge>
                  ) : null}
                </li>
              ))}
            </ul>
            {review.authority.excerpt ? (
              <p className="mt-1 text-slate-500">Authority excerpt: {review.authority.excerpt}</p>
            ) : null}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              data-testid="learning-confirm"
              disabled={busy || !review.review_ready || review.status === "confirmed" || review.status === "promoted"}
              onClick={confirm}
            >
              <CheckCircle2 className="mr-1 h-3 w-3" /> Confirm review
            </Button>
            <Button
              data-testid="learning-promote"
              disabled={busy || review.status !== "confirmed"}
              onClick={promote}
            >
              Promote lesson
            </Button>
            <Button
              data-testid="learning-reject"
              variant="outline"
              disabled={busy || review.status === "promoted"}
              onClick={reject}
            >
              <XCircle className="mr-1 h-3 w-3" /> Reject
            </Button>
            <Button
              data-testid="learning-new-draft"
              variant="outline"
              disabled={busy}
              onClick={() => {
                setPayload(null);
                setNotice("Draft another lesson from this conversation.");
              }}
            >
              Draft another lesson
            </Button>
          </div>
          {review.status === "promoted" ? (
            <div className="rounded border p-2" data-testid="learning-apply">
              <p className="font-semibold">Apply to unfamiliar work</p>
              <p className="text-slate-500">
                The approved method runs on a new row; no source is written.
              </p>
              <div className="mt-1 flex flex-wrap items-center gap-1">
                <input
                  className="w-28 rounded border p-1"
                  data-testid="learning-apply-customer"
                  value={applyContext.customer}
                  onChange={(event) => setApplyContext({
                    ...applyContext, customer: event.target.value,
                  })}
                  placeholder="customer"
                />
                <input
                  className="w-28 rounded border p-1"
                  data-testid="learning-apply-qualification"
                  value={applyContext.qualification}
                  onChange={(event) => setApplyContext({
                    ...applyContext, qualification: event.target.value,
                  })}
                  placeholder="qualification"
                />
                {(review.method_and_assumptions.method.inputs || []).map(
                  (input: any) => (
                    <label key={input.concept} className="text-[11px]">
                      {input.concept}
                      <input
                        className="ml-1 w-20 rounded border p-1"
                        data-testid={`learning-apply-${input.concept}`}
                        value={applyValues[input.concept] || ""}
                        onChange={(event) => setApplyValues({
                          ...applyValues,
                          [input.concept]: event.target.value,
                        })}
                      />
                    </label>
                  ))}
                <Button
                  data-testid="learning-apply-button"
                  disabled={busy}
                  onClick={apply}
                >
                  Run method
                </Button>
              </div>
              {applyResult ? (
                <p className="mt-1 font-semibold" data-testid="learning-apply-result">
                  {applyResult}
                </p>
              ) : null}
            </div>
          ) : null}
          {!review.review_ready ? (
            <p className="flex items-center gap-1 text-amber-700" data-testid="learning-blocked">
              <AlertTriangle className="h-3 w-3" /> Resolve the required questions before promotion.
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}
