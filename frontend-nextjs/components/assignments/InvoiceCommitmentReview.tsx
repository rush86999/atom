"use client";

import React, {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import {
  invoiceCommitmentClient,
  invoiceCommitmentErrorMessage,
  isInvoiceCommitmentConflict,
  type InvoiceCommitmentClient,
  type InvoiceCommitmentRead,
  type InvoiceCommitmentRevision,
  type InvoiceCommitmentVerdict,
  type InvoiceCommitmentWrite,
} from "@/lib/invoice-commitment-api";

const VERDICT_CONFIRMED: InvoiceCommitmentVerdict = "confirmed";
const VERDICT_NO_COMMITMENT: InvoiceCommitmentVerdict = "no_commitment";
const VERDICT_UNCLEAR: InvoiceCommitmentVerdict = "unclear";

function stepStrings(step: unknown): string[] {
  if (!step || typeof step !== "object") return [];
  const value = step as Record<string, unknown>;
  const result: string[] = [];
  const push = (item: unknown) => {
    if (typeof item === "string" && item.trim()) result.push(item);
  };

  [
    "step_id",
    "title",
    "description",
    "label",
    "name",
    "operation",
    "operation_name",
    "operation_kind",
    "kind",
    "type",
    "action",
    "template",
  ].forEach((key) => {
    const item = value[key];
    if (item && typeof item === "object") {
      Object.values(item as Record<string, unknown>).forEach(push);
    } else {
      push(item);
    }
  });

  const waiting = value.waiting;
  if (waiting && typeof waiting === "object") {
    Object.values(waiting as Record<string, unknown>).forEach(push);
  }
  return result;
}

/**
 * The commitment review belongs only on an applied invoice reply wait.
 * The normalised text handles `invoice.wait_for_reply`, `invoice_wait_for_reply`
 * and a human title such as "Invoice wait for reply".
 */
export function isAppliedInvoiceReplyStep(step: unknown): boolean {
  if (!step || typeof step !== "object") return false;
  if ((step as Record<string, unknown>).status !== "applied") return false;
  const text = stepStrings(step)
    .join(" ")
    .toLowerCase()
    .replace(/[\s./\\:_-]+/g, "_");
  if (!text.includes("invoice")) return false;
  return (
    text.includes("wait_for_reply") ||
    text.includes("await_reply") ||
    text.includes("waiting_for_reply") ||
    text.includes("reply_wait")
  );
}

export function invoiceCommitmentReplyId(
  step: unknown,
  operation?: unknown,
): string | undefined {
  const candidates: unknown[] = [];
  const collect = (value: unknown) => {
    if (!value || typeof value !== "object") return;
    const record = value as Record<string, unknown>;
    [
      "expected_reply_id",
      "reply_message_id",
      "reply_id",
      "message_id",
    ].forEach((key) => candidates.push(record[key]));
    ["waiting", "source", "result", "reply"].forEach((key) => {
      const nested = record[key];
      if (nested && typeof nested === "object") {
        const nestedRecord = nested as Record<string, unknown>;
        [
          "expected_reply_id",
          "reply_message_id",
          "reply_id",
          "message_id",
        ].forEach((nestedKey) => candidates.push(nestedRecord[nestedKey]));
      }
    });
  };
  collect(step);
  collect(operation);

  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
  }
  return undefined;
}

function verdictLabel(value: unknown): string {
  const text = String(value ?? "").trim();
  if (text === VERDICT_CONFIRMED) return "Confirmed";
  if (text === VERDICT_NO_COMMITMENT) return "No commitment";
  if (text === VERDICT_UNCLEAR) return "Unclear";
  return text || "Not set";
}

function dateValue(value: unknown): string {
  if (typeof value !== "string") return "";
  const text = value.trim();
  if (!text) return "";
  return /^\d{4}-\d{2}-\d{2}/.test(text) ? text.slice(0, 10) : text;
}

function isIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return (
    !Number.isNaN(parsed.getTime()) &&
    parsed.toISOString().slice(0, 10) === value
  );
}

function revisionHistory(
  record: InvoiceCommitmentRead | null,
): InvoiceCommitmentRevision[] {
  if (!record) return [];
  if (Array.isArray(record.history) && record.history.length) {
    return record.history;
  }
  return record.current ? [record.current] : [];
}

function replyIdForWrite(
  record: InvoiceCommitmentRead | null,
  stepReplyId?: string,
): string | undefined {
  if (stepReplyId && stepReplyId.trim()) return stepReplyId.trim();
  const current: any = record?.current;
  const candidates = [
    current?.expected_reply_id,
    current?.reply_message_id,
    current?.source?.reply_message_id,
    current?.reply_operation_id,
    current?.source?.reply_operation_id,
    current?.reply_id,
    (record as any)?.expected_reply_id,
    (record as any)?.reply_message_id,
    (record as any)?.reply_operation_id,
    (record as any)?.reply_id,
    (record as any)?.source?.reply_message_id,
  ];
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
  }
  return undefined;
}

interface InvoiceCommitmentReviewProps {
  runId: string;
  stepId: string;
  /**
   * Identity of the applied reply, when the assignment payload exposes it.
   * The server still validates it against the fresh reply source.
   */
  expectedReplyId?: string;
  className?: string;
  /** Injected in tests, or when the caller owns the authenticated client. */
  client?: InvoiceCommitmentClient;
}

export function InvoiceCommitmentReview({
  runId,
  stepId,
  expectedReplyId,
  className = "",
  client = invoiceCommitmentClient,
}: InvoiceCommitmentReviewProps) {
  const headingId = useId();
  const panelId = useId();
  const noticeId = useId();
  const errorId = useId();

  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [record, setRecord] = useState<InvoiceCommitmentRead | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [verdict, setVerdict] =
    useState<InvoiceCommitmentVerdict>(VERDICT_CONFIRMED);
  const [commitmentDate, setCommitmentDate] = useState("");
  const [reason, setReason] = useState("");

  const mountedRef = useRef(true);
  const readSeq = useRef(0);
  const writeSeq = useRef(0);
  const submittingRef = useRef(false);
  const wasOpenRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      readSeq.current += 1;
      writeSeq.current += 1;
    };
  }, []);

  // A new opening starts an explicit, empty review. Fetching happens below,
  // only while the disclosure is open.
  useEffect(() => {
    if (open && !wasOpenRef.current) {
      setVerdict(VERDICT_CONFIRMED);
      setCommitmentDate("");
      setReason("");
      setSaveError(null);
      setNotice(null);
    }
    wasOpenRef.current = open;
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const seq = ++readSeq.current;
    let cancelled = false;

    setLoading(true);
    setLoadError(null);
    setRecord(null);

    client
      .read(runId, stepId)
      .then((next) => {
        if (
          cancelled ||
          !mountedRef.current ||
          seq !== readSeq.current
        ) {
          return;
        }
        setRecord(next);
      })
      .catch((error) => {
        if (
          cancelled ||
          !mountedRef.current ||
          seq !== readSeq.current
        ) {
          return;
        }
        setLoadError(
          invoiceCommitmentErrorMessage(
            error,
            "Could not load the invoice commitment review.",
          ),
        );
      })
      .finally(() => {
        if (
          cancelled ||
          !mountedRef.current ||
          seq !== readSeq.current
        ) {
          return;
        }
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, runId, stepId, client]);

  const history = useMemo(() => revisionHistory(record), [record]);
  const current =
    record?.current || (history.length ? history[history.length - 1] : null);
  const revision =
    typeof record?.revision === "number"
      ? record.revision
      : current?.revision || 0;

  const refreshLatest = useCallback(async (): Promise<boolean> => {
    const seq = ++readSeq.current;
    setLoading(true);
    setLoadError(null);
    try {
      const next = await client.read(runId, stepId);
      if (!mountedRef.current || seq !== readSeq.current) return false;
      setRecord(next);
      return true;
    } catch (error) {
      if (mountedRef.current && seq === readSeq.current) {
        setLoadError(
          invoiceCommitmentErrorMessage(
            error,
            "Could not refresh the invoice commitment review.",
          ),
        );
      }
      return false;
    } finally {
      if (mountedRef.current && seq === readSeq.current) {
        setLoading(false);
      }
    }
  }, [client, runId, stepId]);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submittingRef.current || saving || loading || !record) return;

    const trimmedReason = reason.trim();
    const correction = revision > 0;
    if (verdict === VERDICT_CONFIRMED && !isIsoDate(commitmentDate)) {
      setSaveError("Choose the commitment date in YYYY-MM-DD form.");
      return;
    }
    if (correction && !trimmedReason) {
      setSaveError("Explain the correction before recording it.");
      return;
    }

    const body: InvoiceCommitmentWrite = {
      expected_revision: revision,
      verdict,
      commitment_date:
        verdict === VERDICT_CONFIRMED ? commitmentDate : null,
      reason: correction ? trimmedReason : null,
    };
    const replyId = replyIdForWrite(record, expectedReplyId);
    if (replyId) body.expected_reply_id = replyId;

    submittingRef.current = true;
    const seq = ++writeSeq.current;
    setSaving(true);
    setSaveError(null);
    setNotice(null);

    // Exactly one write per explicit submission. There is no retry loop.
    try {
      const next = await client.write(runId, stepId, body);
      if (!mountedRef.current || seq !== writeSeq.current) return;
      setRecord(next);
      setNotice(`Recorded revision ${next.revision}.`);
      setVerdict(VERDICT_CONFIRMED);
      setCommitmentDate("");
      setReason("");
    } catch (error) {
      if (!mountedRef.current || seq !== writeSeq.current) return;
      if (isInvoiceCommitmentConflict(error)) {
        setNotice(
          "This review changed elsewhere. The latest revision was refreshed; " +
            "review it and submit again.",
        );
        await refreshLatest();
      } else {
        setSaveError(
          invoiceCommitmentErrorMessage(
            error,
            "Could not record the invoice commitment review.",
          ),
        );
      }
    } finally {
      submittingRef.current = false;
      if (mountedRef.current && seq === writeSeq.current) {
        setSaving(false);
      }
    }
  };

  return (
    <section
      className={`rounded border border-slate-300 bg-white p-2 ${className}`}
      aria-labelledby={headingId}
      data-testid="invoice-commitment-review"
    >
      <h4 className="text-xs font-semibold">
        <button
          type="button"
          id={headingId}
          className="flex w-full items-center gap-1 text-left"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((value) => !value)}
          data-testid="invoice-commitment-toggle"
        >
          {open ? (
            <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          Invoice commitment review
        </button>
      </h4>
      <p className="mt-0.5 text-[10px] text-muted-foreground">
        Review only. This does not pay or settle the invoice.
      </p>

      {open ? (
        <div
          id={panelId}
          role="region"
          aria-labelledby={headingId}
          className="mt-2 space-y-2 border-t pt-2"
        >
          {loading ? (
            <p
              className="text-[10px] text-muted-foreground"
              data-testid="invoice-commitment-loading"
            >
              Loading current review and revision history…
            </p>
          ) : null}

          {loadError ? (
            <div
              className="rounded border border-rose-200 bg-rose-50 p-2 text-rose-700"
              role="alert"
              data-testid="invoice-commitment-load-error"
            >
              <p>{loadError}</p>
              <button
                type="button"
                className="mt-1 text-[10px] underline"
                onClick={() => {
                  void refreshLatest();
                }}
              >
                Try loading again
              </button>
            </div>
          ) : null}

          {record ? (
            <>
              <div
                className="rounded bg-slate-50 p-2"
                data-testid="invoice-commitment-current"
              >
                <p className="font-medium">
                  Current: {verdictLabel(current?.verdict)}
                </p>
                <p className="text-[10px] text-slate-700">
                  Commitment date:{" "}
                  <span data-testid="invoice-commitment-current-date">
                    {dateValue(current?.commitment_date) || "—"}
                  </span>
                  {" · "}Revision {revision}
                </p>
                {current?.reason ? (
                  <p className="text-[10px] text-slate-700">
                    Correction reason: {current.reason}
                  </p>
                ) : null}
                {current?.reviewed_at ? (
                  <p className="text-[10px] text-muted-foreground">
                    Reviewed {String(current.reviewed_at)}
                  </p>
                ) : null}
              </div>

              <div data-testid="invoice-commitment-history">
                <p className="font-medium">Revision history</p>
                {history.length ? (
                  <ol className="mt-1 max-h-40 space-y-1 overflow-auto">
                    {history.map((entry) => (
                      <li
                        key={`${entry.revision}:${entry.reviewed_at || ""}`}
                        className="rounded border px-1.5 py-1 text-[10px]"
                        data-testid={`invoice-commitment-history-${entry.revision}`}
                      >
                        <span className="font-medium">
                          Revision {entry.revision} ·{" "}
                          {verdictLabel(entry.verdict)}
                        </span>
                        {dateValue(entry.commitment_date) ? (
                          <span> · {dateValue(entry.commitment_date)}</span>
                        ) : null}
                        {entry.reason ? (
                          <span> · {entry.reason}</span>
                        ) : null}
                        {entry.reviewed_at ? (
                          <span className="text-muted-foreground">
                            {" "}
                            · {String(entry.reviewed_at)}
                          </span>
                        ) : null}
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="text-[10px] text-muted-foreground">
                    No reviewed verdict yet. The first review is revision 1.
                  </p>
                )}
              </div>

              <form className="space-y-2" onSubmit={submit} noValidate>
                <fieldset>
                  <legend className="font-medium">
                    Record a reviewed verdict
                  </legend>
                  <div className="mt-1 flex flex-wrap gap-3">
                    <label className="flex items-center gap-1 text-[11px]">
                      <input
                        type="radio"
                        name={`${panelId}-verdict`}
                        value={VERDICT_CONFIRMED}
                        checked={verdict === VERDICT_CONFIRMED}
                        onChange={() => {
                          setVerdict(VERDICT_CONFIRMED);
                          setSaveError(null);
                        }}
                        data-testid="invoice-commitment-verdict-confirmed"
                      />
                      Confirmed
                    </label>
                    <label className="flex items-center gap-1 text-[11px]">
                      <input
                        type="radio"
                        name={`${panelId}-verdict`}
                        value={VERDICT_NO_COMMITMENT}
                        checked={verdict === VERDICT_NO_COMMITMENT}
                        onChange={() => {
                          setVerdict(VERDICT_NO_COMMITMENT);
                          setSaveError(null);
                        }}
                        data-testid="invoice-commitment-verdict-no-commitment"
                      />
                      No commitment
                    </label>
                    <label className="flex items-center gap-1 text-[11px]">
                      <input
                        type="radio"
                        name={`${panelId}-verdict`}
                        value={VERDICT_UNCLEAR}
                        checked={verdict === VERDICT_UNCLEAR}
                        onChange={() => {
                          setVerdict(VERDICT_UNCLEAR);
                          setSaveError(null);
                        }}
                        data-testid="invoice-commitment-verdict-unclear"
                      />
                      Unclear
                    </label>
                  </div>
                </fieldset>

                {verdict === VERDICT_CONFIRMED ? (
                  <div>
                    <label
                      className="block font-medium"
                      htmlFor={`${panelId}-date`}
                    >
                      Commitment date
                    </label>
                    <input
                      id={`${panelId}-date`}
                      type="date"
                      value={commitmentDate}
                      onChange={(event) => {
                        setCommitmentDate(event.target.value);
                        setSaveError(null);
                      }}
                      className="w-full rounded border px-1.5 py-1"
                      required
                      aria-describedby={errorId}
                      data-testid="invoice-commitment-date"
                    />
                    <p className="text-[10px] text-muted-foreground">
                      Enter the reviewed date explicitly; it is not inferred.
                    </p>
                  </div>
                ) : null}

                {revision > 0 ? (
                  <div>
                    <label
                      className="block font-medium"
                      htmlFor={`${panelId}-reason`}
                    >
                      Reason for correction
                    </label>
                    <textarea
                      id={`${panelId}-reason`}
                      value={reason}
                      onChange={(event) => {
                        setReason(event.target.value);
                        setSaveError(null);
                      }}
                      rows={2}
                      className="w-full rounded border px-1.5 py-1"
                      required
                      aria-describedby={errorId}
                      data-testid="invoice-commitment-reason"
                    />
                    <p className="text-[10px] text-muted-foreground">
                      This revision is a correction. The reason is recorded
                      with it; earlier revisions are unchanged.
                    </p>
                  </div>
                ) : null}

                <div className="flex items-center justify-between gap-2">
                  <p className="text-[10px] text-muted-foreground">
                    Based on revision {revision}
                  </p>
                  <button
                    type="submit"
                    className="rounded bg-slate-900 px-2 py-1 text-[11px] font-medium text-white disabled:opacity-50"
                    disabled={saving || loading}
                    aria-describedby={`${noticeId} ${errorId}`}
                    data-testid="invoice-commitment-submit"
                  >
                    {saving
                      ? "Recording…"
                      : revision > 0
                        ? "Record correction"
                        : "Record review"}
                  </button>
                </div>

                {saveError ? (
                  <p
                    id={errorId}
                    className="rounded border border-rose-200 bg-rose-50 p-1.5 text-rose-700"
                    role="alert"
                    data-testid="invoice-commitment-error"
                  >
                    {saveError}
                  </p>
                ) : (
                  <span id={errorId} className="sr-only">
                    Validation messages for the invoice commitment review.
                  </span>
                )}
                <div
                  id={noticeId}
                  aria-live="polite"
                  data-testid="invoice-commitment-notice"
                >
                  {notice ? (
                    <p className="rounded border border-amber-200 bg-amber-50 p-1.5 text-amber-800">
                      {notice}
                    </p>
                  ) : null}
                </div>
              </form>
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
