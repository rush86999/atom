"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Link2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  confirmLearningCandidate,
  createLearningCandidate,
  getLearningCandidate,
  LearningCandidatePayload,
  LearningReview,
  listLearningCandidates,
  promoteLearningCandidate,
  rejectLearningCandidate,
  resolveLearningDependency,
} from "@/lib/conversation-learning-api";

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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [resources, setResources] = useState<Record<string, string>>({});
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
    methodStatus: "explicit",
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
      setError(err?.response?.data?.detail || err?.message || "Could not load the learning review");
    }
  }, [threadId, candidateId]);

  useEffect(() => {
    void load();
  }, [load]);

  const review = payload?.review;
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
      const created = await createLearningCandidate({
        thread_id: threadId,
        agent_id: draft.agentId,
        proposed_lesson: draft.lesson,
        applies_to: draft.appliesTo
          .split(",").map((item) => item.trim()).filter(Boolean),
        method: {
          intended_outcome: draft.outcome || draft.lesson,
          operation: draft.operation,
          inputs,
          output_unit: draft.unit1,
          transformation: draft.operation === "sum"
            ? "sum of the declared input"
            : "declared by the reviewer",
        },
        method_status: draft.methodStatus,
      });
      setPayload(created);
      setNotice("Candidate drafted. Resolve the remaining questions before confirmation.");
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Could not draft the candidate");
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
      setError(err?.response?.data?.detail || err?.message || "Could not resolve the question");
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
      setError(err?.response?.data?.detail || err?.message || "Could not confirm the review");
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
      setError(err?.response?.data?.detail || err?.message || "Could not promote the lesson");
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
      setError(err?.response?.data?.detail || err?.message || "Could not reject the proposal");
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
            <input
              className="mt-1 w-full rounded border p-1"
              data-testid="learning-agent-input"
              value={draft.agentId}
              onChange={(event) => setDraft({ ...draft, agentId: event.target.value })}
              placeholder="agent id"
            />
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
          <Button data-testid="learning-draft-button" disabled={busy || !draft.agentId || !draft.lesson} onClick={create}>
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
          </div>
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
