"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, History, Link2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  applyLearningCandidate,
  confirmLearningCandidate,
  createLearningCandidate,
  getLearningCandidate,
  getLearningCandidateHistory,
  LearningCandidateHistory,
  LearningCandidatePayload,
  LearningEmployee,
  LearningReview,
  listLearningCandidates,
  listLearningEmployees,
  promoteLearningCandidate,
  rejectLearningCandidate,
  resolveLearningDependency,
  reviseLearningCandidate,
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

/** Bounded proposal list: never hide a proposal silently behind rows[0]. */
const MAX_CANDIDATE_OPTIONS = 25;
const HISTORY_PAGE_SIZE = 10;

const HISTORY_KIND_LABELS: Record<string, string> = {
  learning_candidate_created: "Proposal created",
  learning_candidate_revised: "Revision saved",
  learning_candidate_dependency_resolved: "Question resolved",
  learning_candidate_confirmed: "Review confirmed",
  learning_candidate_promoted: "Lesson promoted",
  learning_candidate_rejected: "Proposal rejected",
  learning_candidate_invalidated: "Review invalidated",
};

const HISTORY_FIELD_LABELS: Record<string, string> = {
  proposed_lesson: "lesson",
  method_status: "method status",
  applies_to: "applies to",
  context: "context",
  format_spec: "format",
  conditions: "conditions",
  decision_options: "decision options",
  method: "method",
  status: "status",
};

function historyKindLabel(kind: string): string {
  return HISTORY_KIND_LABELS[kind] || kind.replace(/_/g, " ");
}

function changedFieldLabel(field: string): string {
  return HISTORY_FIELD_LABELS[field] || field.replace(/_/g, " ");
}

/** Plain wording for the stored invalidation tokens; no new policy claim. */
function invalidationText(reason: string): string {
  const raw = String(reason || "");
  if (raw === "source_changed") return "the source conversation changed";
  if (raw === "source_missing") {
    return "the source conversation is no longer available";
  }
  if (raw.startsWith("reference_stale:")) {
    return `a referenced resource changed (${raw.split(":").slice(1).join(":")})`;
  }
  if (raw.startsWith("reference_missing:")) {
    return `a referenced resource is no longer available (${raw.split(":").slice(1).join(":")})`;
  }
  if (raw.startsWith("reference_")) {
    return `a referenced resource is unusable (${raw})`;
  }
  return raw || "the recorded evidence changed";
}

function isStaleReference(status: string): boolean {
  const value = String(status || "").toLowerCase();
  if (!value) return false;
  return !["resolved", "not_applicable", "active", "current"].includes(value);
}

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

function parseObjectInput(raw: string, label: string): Record<string, unknown> {
  if (!raw.trim()) return {};
  const parsed = JSON.parse(raw);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON object`);
  }
  return parsed as Record<string, unknown>;
}

type LearningEditDraft = {
  lesson: string;
  appliesTo: string;
  guidanceOnly: boolean;
  operation: string;
  concept1: string;
  column1: string;
  unit1: string;
  concept2: string;
  column2: string;
  unit2: string;
  formatSpec: string;
  conditions: string;
  decisionOptions: string;
  customer: string;
  qualification: string;
};

function editDraftFromReview(review: LearningReview): LearningEditDraft {
  const method = review.method_and_assumptions.method || {};
  const inputs = Array.isArray(method.inputs) ? method.inputs : [];
  const formatSpec = review.artifact_and_protocol?.format_spec || {};
  const conditions = review.artifact_and_protocol?.conditions || {};
  const decisionOptions = review.artifact_and_protocol?.decision_options || [];
  const context = review.where_it_applies.context || {};
  const second = inputs[1] || {};
  const first = inputs[0] || {};
  return {
    lesson: review.proposed_lesson,
    appliesTo: (review.where_it_applies.applies_to || []).join(", "),
    guidanceOnly: !String(method.operation || "") && !inputs.length,
    operation: String(method.operation || "sum"),
    concept1: String(first.concept || ""),
    column1: String(first.column || ""),
    unit1: String(first.unit || ""),
    concept2: String(second.concept || ""),
    column2: String(second.column || ""),
    unit2: String(second.unit || ""),
    formatSpec: Object.keys(formatSpec).length
      ? JSON.stringify(formatSpec, null, 2) : "",
    conditions: Object.keys(conditions).length
      ? JSON.stringify(conditions, null, 2) : "",
    decisionOptions: decisionOptions.join(", "),
    customer: typeof context.customer === "string" ? context.customer : "",
    qualification:
      typeof context.qualification === "string" ? context.qualification : "",
  };
}

function contextWithDraft(
  context: Record<string, unknown>,
  draft: LearningEditDraft,
): Record<string, unknown> {
  const next = { ...(context || {}) };
  const customer = draft.customer.trim();
  const qualification = draft.qualification.trim();
  if (customer) next.customer = customer;
  else if (typeof next.customer === "string") delete next.customer;
  if (qualification) next.qualification = qualification;
  else if (typeof next.qualification === "string") {
    delete next.qualification;
  }
  return next;
}

function commaList(raw: string): string[] {
  return raw.split(",").map((item) => item.trim()).filter(Boolean);
}

/**
 * Build the correction request from the visible edit form.
 *
 * Only fields the reviewer actually changed are sent. Everything else is
 * omitted so the server keeps the candidate's existing method assumptions,
 * references, dependencies, formatting and context byte-for-byte.
 */
function revisionPayload(
  review: LearningReview,
  initial: LearningEditDraft,
  current: LearningEditDraft,
): Record<string, unknown> | null {
  const payload: Record<string, unknown> = {};
  if (current.lesson !== initial.lesson) {
    payload.proposed_lesson = current.lesson;
  }
  if (commaList(current.appliesTo).join("|")
      !== commaList(initial.appliesTo).join("|")) {
    payload.applies_to = commaList(current.appliesTo);
  }

  const baseContext = review.where_it_applies.context || {};
  const initialContext = contextWithDraft(baseContext, initial);
  const currentContext = contextWithDraft(baseContext, current);
  if (JSON.stringify(currentContext) !== JSON.stringify(initialContext)) {
    payload.context = currentContext;
  }

  const initialFormat = parseObjectInput(initial.formatSpec, "Format spec");
  const currentFormat = parseObjectInput(current.formatSpec, "Format spec");
  if (JSON.stringify(currentFormat) !== JSON.stringify(initialFormat)) {
    payload.format_spec = currentFormat;
  }

  const initialConditions = parseObjectInput(initial.conditions, "Conditions");
  const currentConditions = parseObjectInput(current.conditions, "Conditions");
  if (JSON.stringify(currentConditions) !== JSON.stringify(initialConditions)) {
    payload.conditions = currentConditions;
  }

  const initialDecisions = commaList(initial.decisionOptions);
  const currentDecisions = commaList(current.decisionOptions);
  if (JSON.stringify(currentDecisions) !== JSON.stringify(initialDecisions)) {
    payload.decision_options = currentDecisions;
  }

  const methodChanged = (
    current.guidanceOnly !== initial.guidanceOnly
    || current.operation !== initial.operation
    || current.concept1 !== initial.concept1
    || current.column1 !== initial.column1
    || current.unit1 !== initial.unit1
    || current.concept2 !== initial.concept2
    || current.column2 !== initial.column2
    || current.unit2 !== initial.unit2
  );
  if (methodChanged) {
    if (current.guidanceOnly) {
      payload.method = {};
      payload.method_status = "not_applicable";
    } else {
      if (!current.concept1.trim()) {
        throw new Error(
          "A calculation method needs at least one input concept, or tick "
          + "Guidance only.",
        );
      }
      const inputs: Array<Record<string, unknown>> = [];
      if (current.concept1) {
        inputs.push({
          concept: current.concept1,
          column: current.column1,
          unit: current.unit1,
          unit_required: true,
        });
      }
      if (current.concept2) {
        inputs.push({
          concept: current.concept2,
          column: current.column2,
          unit: current.unit2,
          unit_required: true,
        });
      }
      const baseMethod = review.method_and_assumptions.method || {};
      const operation = current.operation || "sum";
      payload.method = {
        ...baseMethod,
        intended_outcome: String(baseMethod.intended_outcome || current.lesson),
        operation,
        inputs,
        output_unit: String(
          baseMethod.output_unit || current.unit2 || current.unit1),
        transformation: String(
          baseMethod.transformation
          || (operation === "sum"
            ? "sum of the declared input"
            : "declared by the reviewer")),
      };
      payload.method_status =
        review.method_and_assumptions.method_status === "not_applicable"
          ? "explicit"
          : review.method_and_assumptions.method_status;
    }
  }

  return Object.keys(payload).length ? payload : null;
}

export function ConversationLearningReview({
  threadId,
  sourceKind = "email",
  candidateId = null,
  reviewer = "owner",
  className = "",
}: {
  threadId: string;
  sourceKind?: string;
  candidateId?: string | null;
  reviewer?: string;
  className?: string;
}) {
  const [payload, setPayload] = useState<LearningCandidatePayload | null>(null);
  const [candidates, setCandidates] = useState<LearningCandidatePayload[]>([]);
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
  const [editing, setEditing] = useState(false);
  const [editInitial, setEditInitial] = useState<LearningEditDraft | null>(null);
  const [editDraft, setEditDraft] = useState<LearningEditDraft | null>(null);
  const [editReason, setEditReason] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [history, setHistory] = useState<LearningCandidateHistory | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
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
        const single = await getLearningCandidate(
          threadId, candidateId, sourceKind);
        setCandidates([]);
        setPayload(single);
        return;
      }
      const rows = await listLearningCandidates(threadId, sourceKind);
      // Every proposal for the conversation stays selectable; nothing is
      // hidden behind the first row.
      setCandidates(rows);
      setPayload(rows[0] || null);
    } catch (err: any) {
      setError(errorText(err, "Could not load the learning review"));
    }
  }, [threadId, sourceKind, candidateId]);

  const selectCandidate = (nextId: string) => {
    const next = candidates.find(
      (row) => row.review.candidate_id === nextId);
    if (!next) return;
    setPayload(next);
    setEditing(false);
    setEditInitial(null);
    setEditDraft(null);
    setEditReason("");
    setApplyResult(null);
    setHistory(null);
    setHistoryOpen(false);
    setHistoryError(null);
    setNotice(null);
    setError(null);
  };

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

  const candidateOptions = useMemo(() => {
    const selectedId = payload?.review.candidate_id || "";
    const rows = candidates.slice(0, MAX_CANDIDATE_OPTIONS);
    if (selectedId
        && !rows.some((row) => row.review.candidate_id === selectedId)) {
      const selected = candidates.find(
        (row) => row.review.candidate_id === selectedId);
      if (selected) rows.push(selected);
    }
    return rows;
  }, [candidates, payload?.review.candidate_id]);

  const staleReferences = useMemo(
    () => (review?.referenced_data_and_versions || []).filter(
      (ref) => isStaleReference(ref.status)),
    [review],
  );

  const adoptCandidate = useCallback((next: LearningCandidatePayload) => {
    setPayload(next);
    setCandidates((rows) => {
      const index = rows.findIndex(
        (row) => row.review.candidate_id === next.review.candidate_id);
      if (index === -1) return [next, ...rows];
      const copy = [...rows];
      copy[index] = next;
      return copy;
    });
    // The stored ledger changed; drop the cached page so an open drawer
    // reloads once instead of showing a stale revision list.
    setHistory(null);
    setHistoryError(null);
  }, []);

  const loadHistory = useCallback(async (offset: number) => {
    const candidateKey = payload?.review.candidate_id;
    if (!candidateKey) return;
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const page = await getLearningCandidateHistory(
        threadId,
        candidateKey,
        { limit: HISTORY_PAGE_SIZE, offset },
        sourceKind,
      );
      setHistory((current) => {
        if (!offset || !current) return page;
        const seen = new Set(current.events.map((event) => event.event_id));
        const appended = page.events.filter(
          (event) => !seen.has(event.event_id));
        const merged = [...current.events, ...appended];
        return {
          ...page,
          events: merged,
          coverage: {
            ...page.coverage,
            // Coverage describes the rows actually shown, not just this page.
            offset: current.coverage.offset,
            returned: merged.length,
          },
        };
      });
    } catch (err: any) {
      setHistoryError(errorText(err, "Could not load the revision history"));
    } finally {
      setHistoryLoading(false);
    }
  }, [payload?.review.candidate_id, threadId, sourceKind]);

  useEffect(() => {
    // Explicit opening only: the review itself issues no history request.
    if (historyOpen && payload?.review && !history
        && !historyLoading && !historyError) {
      void loadHistory(0);
    }
  }, [historyOpen, payload, history, historyLoading, historyError, loadHistory]);

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
        source_kind: sourceKind,
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
      setCandidates((rows) => [created, ...rows]);
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
          expected_revision: review.revision,
          expected_status: review.status,
        },
        sourceKind,
      );
      setPayload(resolved);
      setCandidates((rows) => rows.map((row) =>
        row.review.candidate_id === resolved.review.candidate_id
          ? resolved : row));
      setHistory(null);
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
        threadId, review.candidate_id, reviewer, review.revision, sourceKind,
        review.status);
      adoptCandidate(confirmed);
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
        review.revision, review.digest, sourceKind, review.status);
      setNotice(`Lesson promoted (${promoted.lesson_id}).`);
      await load();
      setHistory(null);
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
        },
        sourceKind);
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
        threadId, review.candidate_id, reviewer, "Rejected in review",
        sourceKind, review.revision, review.status);
      adoptCandidate(rejected);
      setNotice("Proposal rejected. No lesson was written.");
    } catch (err: any) {
      setError(errorText(err, "Could not reject the proposal"));
    } finally {
      setBusy(false);
    }
  };

  const beginEdit = () => {
    if (!review) return;
    const initial = editDraftFromReview(review);
    setEditInitial(initial);
    setEditDraft({ ...initial });
    setEditReason("");
    setEditing(true);
    setError(null);
    setNotice(null);
  };

  const cancelEdit = () => {
    setEditing(false);
    setEditInitial(null);
    setEditDraft(null);
    setEditReason("");
    setError(null);
    setNotice("Edit cancelled. Nothing was saved.");
  };

  const saveRevision = async () => {
    if (!review || !editInitial || !editDraft) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const body = revisionPayload(review, editInitial, editDraft);
      const reason = editReason.trim();
      if (!body) {
        setNotice(reason
          ? "The reason is optional and did not change the lesson. Change "
            + "the lesson or leave the reason blank; nothing was saved."
          : "No changes to save.");
        return;
      }
      const wasApproved = review.status === "confirmed"
        || review.status === "promoted";
      const revised = await reviseLearningCandidate(
        threadId,
        review.candidate_id,
        {
          ...body,
          // Optional: an empty reason is omitted, never defaulted.
          ...(reason ? { reason } : {}),
          expected_revision: review.revision,
          expected_status: review.status,
        },
        sourceKind,
      );
      adoptCandidate(revised);
      setEditing(false);
      setEditInitial(null);
      setEditDraft(null);
      setEditReason("");
      setNotice(
        `Revision ${revised.review.revision} saved (${revised.review.status.replace(/_/g, " ")}).`
        + (reason ? " The reason was recorded with this revision." : "")
        + (wasApproved
          ? " The previous confirmation was cleared; confirm this revision again before promotion."
          : ""),
      );
    } catch (err: any) {
      setError(errorText(err, "Could not save the revision"));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    setEditing(false);
    setEditInitial(null);
    setEditDraft(null);
    setEditReason("");
    setHistory(null);
    setHistoryOpen(false);
    setHistoryError(null);
  }, [threadId, sourceKind, candidateId]);

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

      {candidates.length > 1 ? (
        <div
          className="flex flex-wrap items-center gap-2 rounded border bg-white p-2"
          data-testid="learning-candidates"
        >
          <label className="flex items-center gap-2">
            Proposal
            <select
              className="rounded border p-1"
              data-testid="learning-candidate-select"
              value={payload?.review.candidate_id || ""}
              onChange={(event) => selectCandidate(event.target.value)}
            >
              {candidateOptions.map((row) => (
                <option
                  key={row.review.candidate_id}
                  value={row.review.candidate_id}
                >
                  {`${row.review.status.replace(/_/g, " ")} · revision `
                    + `${row.review.revision} · `
                    + `${row.review.proposed_lesson.slice(0, 60)}`}
                </option>
              ))}
            </select>
          </label>
          <span className="text-slate-500">
            {candidates.length > MAX_CANDIDATE_OPTIONS
              ? `Showing ${candidateOptions.length} of ${candidates.length} proposals; the selected one is always included.`
              : `${candidates.length} proposals for this conversation.`}
          </span>
        </div>
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

          {review.confirmed_by ? (
            <p className="text-slate-600" data-testid="learning-recorded-reviewer">
              Recorded reviewer: {review.confirmed_by}
              {review.confirmed_revision != null
                ? ` (approved revision ${review.confirmed_revision})` : ""}
            </p>
          ) : null}
          {review.rejected_by || review.rejected_reason ? (
            <p
              className="rounded border border-rose-200 bg-rose-50 p-2 text-rose-700"
              data-testid="learning-rejected-reason"
            >
              Rejected{review.rejected_by ? ` by ${review.rejected_by}` : ""}
              {review.rejected_reason ? `: ${review.rejected_reason}` : ""}
            </p>
          ) : null}
          {review.invalidated_reason ? (
            <p
              className="rounded border border-amber-200 bg-amber-50 p-2 text-amber-800"
              data-testid="learning-invalidated-reason"
            >
              Review invalidated because {invalidationText(review.invalidated_reason)}.
              This proposal is terminal; review the current source before a
              fresh proposal.
            </p>
          ) : null}
          {staleReferences.length ? (
            <p
              className="rounded border border-amber-200 bg-amber-50 p-2 text-amber-800"
              data-testid="learning-evidence-stale"
            >
              Outdated or unresolved evidence:{" "}
              {staleReferences.map((ref, index) => (
                <span key={`${ref.reference}-${index}`}>
                  {index ? "; " : ""}
                  {ref.reference} ({ref.status})
                </span>
              ))}
            </p>
          ) : null}

          {editing && editDraft && editInitial ? (
            <div
              className="space-y-2 rounded border border-sky-200 bg-sky-50 p-3"
              data-testid="learning-edit-form"
            >
              <p className="font-semibold">Correct this lesson</p>
              <p className="text-slate-600">
                Saving keeps this candidate and its source, writes a new
                revision, and clears any earlier confirmation. References,
                dependencies and fields you do not change stay as they are.
              </p>
              <label className="block">
                Proposed lesson
                <textarea
                  className="mt-1 w-full rounded border p-1"
                  data-testid="learning-edit-lesson"
                  value={editDraft.lesson}
                  onChange={(event) => setEditDraft({
                    ...editDraft, lesson: event.target.value,
                  })}
                  rows={2}
                />
              </label>
              <label className="block">
                Reason (optional)
                <input
                  className="mt-1 w-full rounded border p-1"
                  data-testid="learning-edit-reason"
                  value={editReason}
                  onChange={(event) => setEditReason(event.target.value)}
                  placeholder="Why is this correction needed?"
                />
                <span className="mt-1 block text-slate-500">
                  Optional. Left blank, no reason is recorded — nothing is
                  assumed or filled in.
                </span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  data-testid="learning-edit-guidance-only"
                  checked={editDraft.guidanceOnly}
                  onChange={(event) => setEditDraft({
                    ...editDraft, guidanceOnly: event.target.checked,
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
                    data-testid="learning-edit-applies-input"
                    value={editDraft.appliesTo}
                    onChange={(event) => setEditDraft({
                      ...editDraft, appliesTo: event.target.value,
                    })}
                  />
                </label>
                <label>
                  Operation
                  <select
                    className="mt-1 w-full rounded border p-1"
                    data-testid="learning-edit-operation-select"
                    value={editDraft.operation}
                    disabled={editDraft.guidanceOnly}
                    onChange={(event) => setEditDraft({
                      ...editDraft, operation: event.target.value,
                    })}
                  >
                    <option value="sum">sum</option>
                    <option value="count">count</option>
                    <option value="multiply_sum">multiply_sum</option>
                    <option value="percentage">percentage</option>
                    <option value="ratio">ratio</option>
                  </select>
                </label>
              </div>
              {!editDraft.guidanceOnly ? (
                <>
                  <div className="grid grid-cols-3 gap-2">
                    <input className="rounded border p-1" data-testid="learning-edit-concept-1" value={editDraft.concept1} onChange={(e) => setEditDraft({ ...editDraft, concept1: e.target.value })} placeholder="input concept" />
                    <input className="rounded border p-1" data-testid="learning-edit-column-1" value={editDraft.column1} onChange={(e) => setEditDraft({ ...editDraft, column1: e.target.value })} placeholder="column" />
                    <input className="rounded border p-1" data-testid="learning-edit-unit-1" value={editDraft.unit1} onChange={(e) => setEditDraft({ ...editDraft, unit1: e.target.value })} placeholder="unit" />
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <input className="rounded border p-1" data-testid="learning-edit-concept-2" value={editDraft.concept2} onChange={(e) => setEditDraft({ ...editDraft, concept2: e.target.value })} placeholder="second input concept (optional)" />
                    <input className="rounded border p-1" data-testid="learning-edit-column-2" value={editDraft.column2} onChange={(e) => setEditDraft({ ...editDraft, column2: e.target.value })} placeholder="second column" />
                    <input className="rounded border p-1" data-testid="learning-edit-unit-2" value={editDraft.unit2} onChange={(e) => setEditDraft({ ...editDraft, unit2: e.target.value })} placeholder="second unit" />
                  </div>
                </>
              ) : null}
              <div className="grid grid-cols-2 gap-2">
                <textarea
                  className="rounded border p-1"
                  data-testid="learning-edit-format-input"
                  value={editDraft.formatSpec}
                  onChange={(event) => setEditDraft({
                    ...editDraft, formatSpec: event.target.value,
                  })}
                  rows={2}
                  placeholder='format spec JSON, e.g. {"greeting":"Dear colleague,"}'
                />
                <textarea
                  className="rounded border p-1"
                  data-testid="learning-edit-conditions-input"
                  value={editDraft.conditions}
                  onChange={(event) => setEditDraft({
                    ...editDraft, conditions: event.target.value,
                  })}
                  rows={2}
                  placeholder='conditions JSON, e.g. {"recipient":"@example.com"}'
                />
              </div>
              <input
                className="w-full rounded border p-1"
                data-testid="learning-edit-decisions-input"
                value={editDraft.decisionOptions}
                onChange={(event) => setEditDraft({
                  ...editDraft, decisionOptions: event.target.value,
                })}
                placeholder="review decision labels, comma separated (optional)"
              />
              <div className="grid grid-cols-2 gap-2">
                <input className="rounded border p-1" data-testid="learning-edit-customer-input" value={editDraft.customer} onChange={(event) => setEditDraft({ ...editDraft, customer: event.target.value })} placeholder="customer (optional)" />
                <input className="rounded border p-1" data-testid="learning-edit-qualification-input" value={editDraft.qualification} onChange={(event) => setEditDraft({ ...editDraft, qualification: event.target.value })} placeholder="qualification (optional)" />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  data-testid="learning-revise-save"
                  disabled={busy || !editDraft.lesson.trim()}
                  onClick={saveRevision}
                >
                  Save revision
                </Button>
                <Button
                  data-testid="learning-revise-cancel"
                  variant="outline"
                  disabled={busy}
                  onClick={cancelEdit}
                >
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <>
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

          <div className="rounded border p-2" data-testid="learning-history">
            <button
              type="button"
              className="flex w-full items-center justify-between gap-2 text-left font-semibold"
              data-testid="learning-history-toggle"
              aria-expanded={historyOpen}
              onClick={() => setHistoryOpen((open) => !open)}
            >
              <span>Previous revisions and recorded decisions (optional)</span>
              <History className="h-3 w-3" />
            </button>
            {historyOpen ? (
              <div className="mt-2 space-y-2" data-testid="learning-history-panel">
                {historyError ? (
                  <p className="text-rose-700" data-testid="learning-history-error">
                    {historyError}{" "}
                    <Button
                      variant="outline"
                      data-testid="learning-history-retry"
                      disabled={historyLoading}
                      onClick={() => {
                        setHistoryError(null);
                        void loadHistory(0);
                      }}
                    >
                      Retry
                    </Button>
                  </p>
                ) : null}
                {historyLoading && !history ? (
                  <p className="text-slate-500">Loading recorded revisions…</p>
                ) : null}
                {history ? (
                  <>
                    <p className="text-slate-500" data-testid="learning-history-coverage">
                      Showing {history.coverage.returned} of{" "}
                      {history.coverage.total_events} recorded entries.
                      {history.coverage.scan_truncated
                        ? " History may be incomplete: the stored-ledger scan limit was reached."
                        : ""}
                      {history.coverage.out_of_scope_events_excluded
                        ? ` ${history.coverage.out_of_scope_events_excluded} entries outside this workspace were excluded.`
                        : ""}
                    </p>
                    <ol className="space-y-2">
                      {history.events.map((event) => (
                        <li
                          key={event.event_id}
                          className="rounded border bg-slate-50 p-2"
                          data-testid="learning-history-event"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold">
                              {historyKindLabel(event.kind)}
                            </span>
                            {statusBadge(event.status)}
                            <span className="text-slate-500">
                              revision {event.revision}
                            </span>
                            {event.recorded_at ? (
                              <span className="text-slate-500">
                                {event.recorded_at}
                              </span>
                            ) : null}
                          </div>
                          <p>
                            {event.actor
                              ? `${event.actor_role === "reviewer" ? "Reviewer" : "Author"}: ${event.actor}`
                              : "Actor not recorded"}
                          </p>
                          <p>
                            {event.reason_recorded && event.reason
                              ? `Reason: ${event.reason}`
                              : "Reason: not recorded"}
                          </p>
                          {event.changed_fields.length ? (
                            <p className="text-slate-500">
                              Changed:{" "}
                              {event.changed_fields.map(changedFieldLabel).join(", ")}
                            </p>
                          ) : null}
                          {event.before && event.after ? (
                            <div className="mt-1" data-testid="learning-history-diff">
                              <p>Before: {event.before.proposed_lesson || "(empty)"}</p>
                              <p>After: {event.after.proposed_lesson || "(empty)"}</p>
                            </div>
                          ) : null}
                        </li>
                      ))}
                    </ol>
                    <p className="text-slate-500">
                      {history.signatures.present
                        ? "Entries carry the ledger's recorded signature."
                        : "These are the stored ledger rows; they are not signed."}
                    </p>
                    {history.coverage.has_more ? (
                      <Button
                        variant="outline"
                        data-testid="learning-history-more"
                        disabled={historyLoading}
                        onClick={() => void loadHistory(
                          history.coverage.offset + history.coverage.returned)}
                      >
                        {historyLoading ? "Loading…" : "Load older entries"}
                      </Button>
                    ) : null}
                  </>
                ) : null}
              </div>
            ) : null}
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
              data-testid="learning-revise"
              variant="outline"
              disabled={busy || review.status === "rejected"
                || review.status === "invalidated"}
              onClick={beginEdit}
            >
              Edit lesson
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
        </>
      )}
    </section>
  );
}
