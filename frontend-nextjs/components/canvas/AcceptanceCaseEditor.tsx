import React, { useCallback, useEffect, useId, useRef, useState } from "react";

type Rpc = (action: string, args: Record<string, unknown>) => Promise<unknown>;
type Row = { name: string; input: unknown; expected: unknown };
type Outcome = { passed: number; total: number; failed: string[] };
type Failure = { message: string; stale: boolean };

type GradeStatus = "pending" | "running" | "completed" | "failed" | "interrupted";
type GradeResponse = {
  run_id: string;
  submission_id: string;
  status: GradeStatus;
  source_digest: string;
  tests_digest: string;
  report?: unknown;
  error?: string;
};
type PendingGrade = {
  submissionId: string;
  sourceDigest: string;
  testsDigest: string;
  runId?: string;
};

export type Principal = {
  tenantId: string;
  workspaceId: string;
  userId: string;
};

interface AcceptanceCaseEditorProps {
  appId: string;
  rpc: Rpc;
  sourceRevision: string;
  /** Canonical authenticated owner. Without one, grading keeps the sync path. */
  principal?: Principal | null;
}

export const GRADE_PENDING_STORAGE_PREFIX = "atom.canvas.grade.pending.v1";
const POLL_INITIAL_MS = 300;
const POLL_MAX_MS = 3000;
const POLL_MAX_TRANSIENT = 8;
const POLL_MAX_MISSES = 3;
const STATUSES: GradeStatus[] = ["pending", "running", "completed", "failed", "interrupted"];

const row = (value: unknown): Row => {
  const c = (value ?? {}) as { name?: unknown; inputs?: unknown; expect_state?: unknown };
  return { name: typeof c.name === "string" ? c.name : "", input: c.inputs, expected: c.expect_state };
};

const parse = (text: string): unknown => {
  if (!text.trim()) return "";
  try { return JSON.parse(text); } catch { return text; }
};

const show = (value: unknown): string =>
  value === undefined ? "" : typeof value === "string" ? value : JSON.stringify(value) ?? String(value);

const stale = (error: unknown): boolean => {
  const e = error as { code?: unknown; message?: unknown; actionResult?: { error?: unknown } };
  return /stale|conflict|mismatch|changed|409/i.test(`${String(e?.actionResult?.error ?? e?.code ?? "")} ${String(e?.message ?? error)}`);
};

const outcome = (raw: unknown): Outcome => {
  const data = (raw ?? {}) as {
    results?: Array<{ name?: unknown; passed?: unknown; case?: { name?: unknown } }>;
    passed?: unknown;
    total?: unknown;
  };
  const results = Array.isArray(data.results) ? data.results : [];
  const passed = results.filter((r) => r.passed === true).length;
  return {
    passed: typeof data.passed === "number" ? data.passed : passed,
    total: typeof data.total === "number" ? data.total : results.length,
    failed: results.filter((r) => r.passed !== true).map((r, i) =>
      typeof r.name === "string" ? r.name : typeof r.case?.name === "string" ? r.case.name : `Case ${i + 1}`),
  };
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === "object" && !Array.isArray(value);

const text = (value: unknown): string =>
  typeof value === "string" && value.trim() ? value.trim() : "";

function parseGrade(raw: unknown): GradeResponse | null {
  if (!isRecord(raw)) return null;
  const status = raw.status;
  if (typeof status !== "string" || !STATUSES.includes(status as GradeStatus)) return null;
  const submission_id = text(raw.submission_id);
  const source_digest = text(raw.source_digest);
  const tests_digest = text(raw.tests_digest);
  if (!submission_id || !source_digest || !tests_digest) return null;
  return {
    run_id: text(raw.run_id),
    submission_id,
    status: status as GradeStatus,
    source_digest,
    tests_digest,
    report: raw.report,
    error: text(raw.error) || undefined,
  };
}

function parsePending(raw: unknown): PendingGrade | null {
  if (!isRecord(raw)) return null;
  const submissionId = text(raw.submission_id);
  const sourceDigest = text(raw.source_digest);
  const testsDigest = text(raw.tests_digest);
  const runId = text(raw.run_id);
  if (!submissionId || !sourceDigest || !testsDigest) return null;
  return { submissionId, sourceDigest, testsDigest, ...(runId ? { runId } : {}) };
}

function newSubmissionId(): string {
  const cryptoObj = (globalThis as {
    crypto?: {
      randomUUID?: () => string;
      getRandomValues?: (bytes: Uint8Array) => Uint8Array;
    };
  }).crypto;
  try {
    if (cryptoObj && typeof cryptoObj.randomUUID === "function") return cryptoObj.randomUUID();
    if (cryptoObj && typeof cryptoObj.getRandomValues === "function") {
      const bytes = new Uint8Array(16);
      cryptoObj.getRandomValues(bytes);
      bytes[6] = (bytes[6] & 0x0f) | 0x40;
      bytes[8] = (bytes[8] & 0x3f) | 0x80;
      const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
      return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    }
  } catch { /* fall through to the non-crypto fallback */ }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

function sessionStorageSafe(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.sessionStorage : null;
  } catch {
    return null;
  }
}

function canonicalScope(principal?: Principal | null): string | null {
  if (!principal) return null;
  const tenant = text(principal.tenantId);
  const workspace = text(principal.workspaceId);
  const user = text(principal.userId);
  if (!tenant || !workspace || !user) return null;
  return `tenant:${encodeURIComponent(tenant)}:workspace:${encodeURIComponent(workspace)}:user:${encodeURIComponent(user)}`;
}

function storageKeyFor(scope: string | null, appId: string): string | null {
  return scope ? `${GRADE_PENDING_STORAGE_PREFIX}:${scope}:app:${encodeURIComponent(appId)}` : null;
}

function gradeStaleMessage(error: unknown): string | null {
  const e = error as { actionResult?: { error?: unknown }; message?: unknown };
  const detail = `${String(e?.actionResult?.error ?? "")} ${String(e?.message ?? error)}`;
  if (/mini_app_logic_changed/.test(detail)) {
    return "Saved logic changed during grading. Reload the saved logic and run the tests again.";
  }
  return stale(error)
    ? "Tests changed on the server. Reload the snapshot; your draft will be kept."
    : null;
}

function definitiveFailure(error: unknown): boolean {
  const e = error as {
    status?: number;
    response?: { status?: number };
    actionResult?: { success?: unknown; error?: unknown };
  };
  if (e?.actionResult && e.actionResult.success === false) return true;
  const status = e?.status ?? e?.response?.status;
  return typeof status === "number" && status >= 400 && status < 500 && status !== 408 && status !== 429;
}

function failureMessage(error: unknown, fallback: string): string {
  const result = (error as { actionResult?: { success?: unknown; error?: unknown } })?.actionResult;
  if (result?.success === false && typeof result.error === "string" && result.error.trim()) {
    return result.error.trim();
  }
  return fallback;
}

export default function AcceptanceCaseEditor({
  appId,
  rpc,
  sourceRevision,
  principal,
}: AcceptanceCaseEditorProps) {
  const titleId = useId();
  const [snapshot, setSnapshot] = useState<unknown[]>([]);
  const [digest, setDigest] = useState<string | null>(null);
  const [savedSource, setSavedSource] = useState<string | null>(null);
  const [draft, setDraft] = useState({ name: "", inputKey: "", input: "", expectedKey: "", expected: "" });
  const [busy, setBusy] = useState<"load" | "save" | "run" | null>(null);
  const [watching, setWatching] = useState(false);
  const [gradeStatus, setGradeStatus] = useState<GradeStatus | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [result, setResult] = useState<(Outcome & { sourceSha256: string; testsSha256: string }) | null>(null);
  const rpcRef = useRef(rpc); rpcRef.current = rpc;
  const currentSource = useRef(sourceRevision); currentSource.current = sourceRevision;
  const digestRef = useRef(digest); digestRef.current = digest;
  const savedSourceRef = useRef(savedSource); savedSourceRef.current = savedSource;
  const appIdRef = useRef(appId); appIdRef.current = appId;

  const storageKey = storageKeyFor(canonicalScope(principal), appId);
  const storageKeyRef = useRef(storageKey); storageKeyRef.current = storageKey;

  const generation = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelSleep = useRef<(() => void) | null>(null);
  const pendingRef = useRef<PendingGrade | null>(null);
  const runLock = useRef(false);

  const stopSleep = useCallback(() => {
    cancelSleep.current?.();
  }, []);

  const sleep = useCallback((ms: number): Promise<void> => new Promise((resolve) => {
    let settled = false;
    let cancel: () => void = () => {};
    const finish = () => {
      if (settled) return;
      settled = true;
      if (timer.current === id) timer.current = null;
      if (cancelSleep.current === cancel) cancelSleep.current = null;
      resolve();
    };
    const id = setTimeout(finish, ms);
    timer.current = id;
    cancel = () => {
      if (timer.current === id) clearTimeout(id);
      finish();
    };
    cancelSleep.current = cancel;
  }), []);

  const persistPending = useCallback((pending: PendingGrade) => {
    pendingRef.current = pending;
    const key = storageKeyRef.current;
    const storage = sessionStorageSafe();
    if (!key || !storage) return;
    try {
      storage.setItem(key, JSON.stringify({
        submission_id: pending.submissionId,
        source_digest: pending.sourceDigest,
        tests_digest: pending.testsDigest,
        ...(pending.runId ? { run_id: pending.runId } : {}),
      }));
    } catch { /* session storage may be unavailable/disabled */ }
  }, []);

  const clearPending = useCallback(() => {
    pendingRef.current = null;
    const key = storageKeyRef.current;
    const storage = sessionStorageSafe();
    if (!key || !storage) return;
    try { storage.removeItem(key); } catch { /* ignore */ }
  }, []);

  const readPending = useCallback((): PendingGrade | null => {
    const key = storageKeyRef.current;
    const storage = sessionStorageSafe();
    if (!key || !storage) return null;
    try {
      const stored = storage.getItem(key);
      if (!stored) return null;
      const pending = parsePending(JSON.parse(stored));
      if (!pending) {
        storage.removeItem(key);
        return null;
      }
      return pending;
    } catch {
      try { storage.removeItem(key); } catch { /* ignore */ }
      return null;
    }
  }, []);

  const loadSnapshot = useCallback(async (gen: number): Promise<{ digest: string; sourceDigest: string | null } | null> => {
    setBusy("load"); setFailure(null); setResult(null); setGradeStatus(null);
    try {
      const raw = await rpcRef.current("mini_app_status", { app_id: appId, include_acceptance_cases: true });
      if (gen !== generation.current) return null;
      const status = (raw as {
        status?: { acceptance?: { cases?: unknown; tests_sha256?: unknown }; logic?: { source_sha256?: unknown } };
      }).status;
      const acc = status?.acceptance;
      if (typeof acc?.tests_sha256 !== "string" || !acc.tests_sha256 || !Array.isArray(acc.cases)) {
        throw new Error("invalid snapshot");
      }
      const sourceDigest = typeof status?.logic?.source_sha256 === "string" && status.logic.source_sha256
        ? status.logic.source_sha256
        : null;
      setSnapshot(acc.cases);
      digestRef.current = acc.tests_sha256;
      savedSourceRef.current = sourceDigest;
      setDigest(acc.tests_sha256);
      setSavedSource(sourceDigest);
      return { digest: acc.tests_sha256, sourceDigest };
    } catch {
      if (gen === generation.current) setFailure({ message: "Could not load the test snapshot.", stale: false });
      return null;
    } finally {
      if (gen === generation.current) setBusy(null);
    }
  }, [appId]);

  const watchGrade = useCallback(async (
    initial: PendingGrade,
    gen: number,
    sourceAtStart: string,
    dispatchFirst: boolean
  ): Promise<void> => {
    const pending = { ...initial };
    const alive = () => gen === generation.current;
    let needStart = dispatchFirst;
    let delay = POLL_INITIAL_MS;
    let transientErrors = 0;
    let misses = 0;

    const settle = (message: string | null, staleFailure = false) => {
      if (!alive()) return;
      if (message !== null) {
        setResult(null);
        setFailure({ message, stale: staleFailure });
      }
      setBusy(null); setWatching(false); setGradeStatus(null);
      clearPending();
    };

    const unavailable = () => {
      if (!alive()) return;
      setBusy(null); setWatching(false); setGradeStatus(null);
      setFailure({
        message: "Grading status is temporarily unavailable. Your submission is saved; run again or reload to resume it.",
        stale: false,
      });
    };

    const abortForError = (error: unknown): boolean => {
      const message = gradeStaleMessage(error);
      if (message !== null) {
        settle(message, message.includes("Reload the snapshot"));
        return true;
      }
      if (definitiveFailure(error)) {
        settle(failureMessage(error, "Could not start grading."));
        return true;
      }
      return false;
    };

    const handle = (response: GradeResponse): boolean => {
      if (!alive() || response.submission_id !== pending.submissionId) return false;
      if (response.run_id && response.run_id !== pending.runId) {
        pending.runId = response.run_id;
        persistPending(pending);
      }
      if (response.status === "pending" || response.status === "running") {
        setGradeStatus(response.status);
        return false;
      }
      if (response.status === "completed") {
        const older =
          response.source_digest !== pending.sourceDigest ||
          response.tests_digest !== pending.testsDigest ||
          pending.testsDigest !== digestRef.current ||
          (savedSourceRef.current !== null && pending.sourceDigest !== savedSourceRef.current) ||
          sourceAtStart !== currentSource.current;
        if (older) {
          settle("A grade report for an older saved revision is available, but it is stale and is not the current result.");
        } else {
          setResult({ ...outcome(response.report), sourceSha256: pending.sourceDigest, testsSha256: pending.testsDigest });
          setFailure(null);
          settle(null);
        }
        return true;
      }
      settle(response.status === "failed"
        ? (response.error ?? "Grading failed.")
        : "Grading was interrupted. Run the saved tests again.");
      return true;
    };

    while (alive()) {
      if (needStart) {
        needStart = false;
        try {
          const raw = await rpcRef.current("mini_app_start_grade", {
            app_id: appIdRef.current,
            submission_id: pending.submissionId,
            expected_source_digest: pending.sourceDigest,
            expected_tests_digest: pending.testsDigest,
          });
          if (!alive()) return;
          const response = parseGrade(raw);
          if (response) {
            transientErrors = 0;
            if (response.submission_id === pending.submissionId && handle(response)) return;
          } else {
            transientErrors += 1;
          }
        } catch (error) {
          if (!alive()) return;
          if (abortForError(error)) return;
          // A lost acknowledgment is observed by the same submission id below.
          transientErrors += 1;
        }
        if (transientErrors >= POLL_MAX_TRANSIENT) { unavailable(); return; }
      }

      if (!alive()) return;
      let raw: unknown;
      try {
        raw = await rpcRef.current("mini_app_grade_status", {
          app_id: appIdRef.current,
          submission_id: pending.submissionId,
        });
      } catch (error) {
        if (!alive()) return;
        // Status is read-only: retry transient/unknown failures without ever
        // starting a second submission.
        const message = gradeStaleMessage(error);
        if (message !== null) { settle(message); return; }
        transientErrors += 1;
        if (transientErrors >= POLL_MAX_TRANSIENT) { unavailable(); return; }
        await sleep(delay);
        delay = Math.min(POLL_MAX_MS, delay * 2);
        continue;
      }
      if (!alive()) return;

      if (raw === null) {
        misses += 1;
        if (misses > POLL_MAX_MISSES) { unavailable(); return; }
        if (
          pending.testsDigest !== digestRef.current ||
          (savedSourceRef.current !== null && pending.sourceDigest !== savedSourceRef.current)
        ) {
          settle("A pending grade belongs to an older saved revision; its report is stale and is not the current result.");
          return;
        }
        // Exact miss: resubmit the identical UUID and pins.
        persistPending(pending);
        needStart = true;
        continue;
      }

      const response = parseGrade(raw);
      if (!response || response.submission_id !== pending.submissionId) {
        transientErrors += 1;
        if (transientErrors >= POLL_MAX_TRANSIENT) { unavailable(); return; }
        await sleep(delay);
        delay = Math.min(POLL_MAX_MS, delay * 2);
        continue;
      }

      transientErrors = 0;
      if (handle(response)) return;
      await sleep(delay);
      delay = POLL_INITIAL_MS;
    }
  }, [clearPending, persistPending, sleep]);

  // The pending record is scoped by principal + app. Changing either starts a
  // fresh lifetime, stops the old poll, and never adopts the old owner's work.
  useEffect(() => {
    const gen = ++generation.current;
    stopSleep();
    pendingRef.current = null;
    digestRef.current = null;
    savedSourceRef.current = null;
    setSnapshot([]); setDigest(null); setSavedSource(null);
    setDraft({ name: "", inputKey: "", input: "", expectedKey: "", expected: "" });
    setBusy(null); setWatching(false); setGradeStatus(null);
    setFailure(null); setResult(null);

    const boot = async () => {
      const loaded = await loadSnapshot(gen);
      if (!loaded || gen !== generation.current) return;
      const pending = readPending();
      if (!pending || gen !== generation.current) return;
      pendingRef.current = pending;
      setBusy("run"); setWatching(true); setGradeStatus("pending");
      await watchGrade(pending, gen, currentSource.current, false);
    };
    void boot();

    return () => {
      if (gen === generation.current) generation.current += 1;
      stopSleep();
    };
  }, [appId, storageKey, loadSnapshot, readPending, stopSleep, watchGrade]);

  useEffect(() => { setResult(null); }, [sourceRevision]);

  const load = async () => {
    if (busy || watching) return;
    await loadSnapshot(generation.current);
  };

  const edit = (field: keyof typeof draft, value: string) => {
    setDraft((current) => ({ ...current, [field]: value })); setResult(null);
  };

  const fail = (error: unknown, message: string) => {
    const s = stale(error);
    setFailure({ message: s ? "Tests changed on the server. Reload the snapshot; your draft will be kept." : message, stale: s });
  };

  const save = async () => {
    if (busy || watching) return;
    const name = draft.name.trim();
    if (!name) return setFailure({ message: "Enter a case name.", stale: false });
    if (!draft.expectedKey.trim()) return setFailure({ message: "Enter an expected state field.", stale: false });
    if (!digest) return setFailure({ message: "Reload before saving.", stale: true });
    if (snapshot.some((item) => row(item).name.toLowerCase() === name.toLowerCase()))
      return setFailure({ message: "That case name already exists in the snapshot.", stale: false });
    setBusy("save"); setFailure(null); setResult(null);
    const tests = [...snapshot, {
      name,
      inputs: draft.inputKey.trim() ? { [draft.inputKey.trim()]: parse(draft.input) } : {},
      expect_state: { [draft.expectedKey.trim()]: parse(draft.expected) },
    }];
    try {
      const raw = await rpcRef.current("mini_app_set_tests", {
        app_id: appId, tests, expected_tests_sha256: digest,
      });
      const data = raw as {
        success?: unknown; ok?: unknown; error?: unknown; tests_sha256?: unknown;
        acceptance?: { tests_sha256?: unknown };
        status?: { acceptance?: { tests_sha256?: unknown } };
      };
      const next = data.acceptance?.tests_sha256 ?? data.status?.acceptance?.tests_sha256 ?? data.tests_sha256;
      const ok = data.success === true || data.ok === true;
      if (!ok || typeof next !== "string" || !next) {
        throw new Error(typeof data.error === "string" ? data.error : "save failed");
      }
      setSnapshot(tests); setDigest(next); setDraft({ name: "", inputKey: "", input: "", expectedKey: "", expected: "" });
      digestRef.current = next;
    } catch (error) { fail(error, "Could not save the tests. Your draft was kept."); }
    finally { setBusy(null); }
  };

  const runSynchronously = async () => {
    if (!digest || !snapshot.length) return;
    const revisionAtRun = sourceRevision;
    const gen = generation.current;
    setBusy("run"); setFailure(null); setResult(null);
    try {
      const { status } = await rpcRef.current("mini_app_status", {
        app_id: appId, include_acceptance_cases: true,
      }) as { status?: { logic?: { source_sha256?: string }; acceptance?: { tests_sha256?: string } } };
      if (gen !== generation.current) return;
      if (status?.acceptance?.tests_sha256 !== digest) throw new Error("stale");
      const sourceDigest = status?.logic?.source_sha256;
      if (!sourceDigest) throw new Error("missing saved source");
      const raw = await rpcRef.current("mini_app_run_tests", {
        app_id: appId, expected_tests_sha256: digest, expected_source_sha256: sourceDigest,
      });
      if (gen !== generation.current) return;
      const data = raw as { success?: unknown; error?: unknown; source_sha256?: unknown; tests_sha256?: unknown };
      if (data.success !== true) throw new Error(typeof data.error === "string" ? data.error : "run failed");
      if (data.source_sha256 !== sourceDigest || data.tests_sha256 !== digest) {
        throw new Error("The grading result could not be verified.");
      }
      if (currentSource.current === revisionAtRun) {
        setResult({ ...outcome(raw), sourceSha256: sourceDigest, testsSha256: digest });
      }
    } catch (error) {
      if (gen !== generation.current) return;
      const rpcError = error as { actionResult?: { error?: unknown }; message?: unknown };
      if ((rpcError?.actionResult?.error ?? rpcError?.message) === "mini_app_logic_changed") {
        setFailure({ message: "Saved logic changed during grading. Reload the saved logic and run the tests again.", stale: false });
      } else {
        fail(error, "Could not run the tests.");
      }
    } finally { if (gen === generation.current) setBusy(null); }
  };

  const run = async () => {
    if (busy || watching || runLock.current) return;
    runLock.current = true;
    try {
      // Without an authenticated owner there is no canonical storage scope, so
      // keep the established synchronous path unchanged.
      if (!storageKey) {
        await runSynchronously();
        return;
      }

      // A persisted/in-memory submission is resumed, never replaced by a new
      // UUID. This covers transient status failures and reloads.
      const resume = pendingRef.current ?? readPending();
      if (resume) {
        const gen = generation.current;
        pendingRef.current = resume;
        setBusy("run"); setFailure(null); setResult(null); setWatching(true); setGradeStatus("pending");
        await watchGrade(resume, gen, currentSource.current, false);
        return;
      }

      if (!digest || !snapshot.length) return;
      const gen = generation.current;
      setBusy("run"); setFailure(null); setResult(null); setGradeStatus(null); setWatching(true);
      try {
        const { status } = await rpcRef.current("mini_app_status", {
          app_id: appId, include_acceptance_cases: true,
        }) as { status?: { logic?: { source_sha256?: string }; acceptance?: { tests_sha256?: string } } };
        if (gen !== generation.current) return;
        if (status?.acceptance?.tests_sha256 !== digest) throw new Error("stale");
        const sourceDigest = status?.logic?.source_sha256;
        if (!sourceDigest) throw new Error("missing saved source");
        setSavedSource(sourceDigest);
        savedSourceRef.current = sourceDigest;

        const pending: PendingGrade = {
          submissionId: newSubmissionId(),
          sourceDigest,
          testsDigest: digest,
        };
        // Persist before dispatch. Only the UUID, pins, and (once known) run id.
        persistPending(pending);
        await watchGrade(pending, gen, currentSource.current, true);
      } catch (error) {
        if (gen !== generation.current) return;
        setWatching(false); setGradeStatus(null); setBusy(null);
        const message = gradeStaleMessage(error);
        if (message !== null) {
          clearPending();
          setFailure({ message, stale: message.includes("Reload the snapshot") });
        } else {
          fail(error, "Could not run the tests.");
        }
      }
    } finally {
      runLock.current = false;
    }
  };

  const cancel = () => {
    if (!watching) return;
    generation.current += 1;
    stopSleep();
    clearPending();
    setWatching(false); setGradeStatus(null); setBusy(null); setResult(null);
  };

  return (
    <section aria-labelledby={titleId} aria-busy={busy !== null}>
      <h2 id={titleId}>Acceptance tests</h2>
      <p>Save logic before running tests.</p>
      <p>
        <button type="button" onClick={() => void load()} disabled={busy !== null}>Reload snapshot</button>{" "}
        <button type="button" onClick={() => void run()} disabled={busy !== null || !digest || !snapshot.length}>Run saved tests</button>{" "}
        {watching && <button type="button" onClick={cancel} disabled={busy === null}>Cancel grading</button>}
      </p>
      {busy === "load" && <p role="status">Loading snapshot…</p>}
      {busy === "run" && (
        <p role="status">{gradeStatus === "running" ? "Grading saved logic…" : "Waiting for grading…"}</p>
      )}
      {failure && (
        <div role="alert">
          <p>{failure.message}</p>
          {failure.stale && <button type="button" onClick={() => void load()} disabled={busy !== null}>Reload snapshot</button>}
        </div>
      )}
      <table>
        <caption>Server snapshot: {snapshot.length} case(s)</caption>
        <thead>
          <tr><th scope="col">Name</th><th scope="col">Input</th><th scope="col">Expected</th></tr>
        </thead>
        <tbody>
          {snapshot.map((item, index) => {
            const r = row(item);
            return (
              <tr key={index}>
                <th scope="row">{r.name || `Case ${index + 1}`}</th>
                <td><code>{show(r.input)}</code></td>
                <td><code>{show(r.expected)}</code></td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row"><input aria-label="New case name" disabled={busy !== null} placeholder="Name" value={draft.name} onChange={(e) => edit("name", e.target.value)} /></th>
            <td><input aria-label="Input field" disabled={busy !== null} placeholder="Field name" value={draft.inputKey} onChange={(e) => edit("inputKey", e.target.value)} /><input aria-label="New case input" disabled={busy !== null} placeholder="Input or JSON" value={draft.input} onChange={(e) => edit("input", e.target.value)} /></td>
            <td><input aria-label="Expected state field" disabled={busy !== null} placeholder="Field name" value={draft.expectedKey} onChange={(e) => edit("expectedKey", e.target.value)} /><input aria-label="New case expected" disabled={busy !== null} placeholder="Expected or JSON" value={draft.expected} onChange={(e) => edit("expected", e.target.value)} /></td>
          </tr>
        </tfoot>
      </table>
      <button type="button" onClick={() => void save()} disabled={busy !== null || !digest}>Add case</button>
      {result && (
        <div role="status" aria-live="polite">
          <p>{result.passed}/{result.total} passed for saved logic.</p>
          <details>
            <summary>Graded source and tests</summary>
            <p>Source <code>{result.sourceSha256}</code></p>
            <p>Tests <code>{result.testsSha256}</code></p>
          </details>
          {result.failed.length > 0 && (
            <ul aria-label="Failed cases">{result.failed.map((name) => <li key={name}>{name}</li>)}</ul>
          )}
        </div>
      )}
    </section>
  );
}
