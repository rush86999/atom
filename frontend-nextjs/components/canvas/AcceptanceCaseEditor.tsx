import React, { useEffect, useId, useRef, useState } from "react";

type Rpc = (action: string, args: Record<string, unknown>) => Promise<unknown>;
type Row = { name: string; input: unknown; expected: unknown };
type Outcome = { passed: number; total: number; failed: string[] };
type Failure = { message: string; stale: boolean };

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

export default function AcceptanceCaseEditor({ appId, rpc, sourceRevision }: { appId: string; rpc: Rpc; sourceRevision: string }) {
  const titleId = useId();
  const [snapshot, setSnapshot] = useState<unknown[]>([]);
  const [digest, setDigest] = useState<string | null>(null);
  const [draft, setDraft] = useState({ name: "", inputKey: "", input: "", expectedKey: "", expected: "" });
  const [busy, setBusy] = useState<"load" | "save" | "run" | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [result, setResult] = useState<Outcome | null>(null);
  const rpcRef = useRef(rpc); rpcRef.current = rpc;
  const currentSource = useRef(sourceRevision); currentSource.current = sourceRevision;

  const load = async () => {
    if (busy) return;
    setBusy("load"); setFailure(null);
    try {
      const raw = await rpcRef.current("mini_app_status", { app_id: appId, include_acceptance_cases: true });
      const acc = (raw as { status?: { acceptance?: { cases?: unknown; tests_sha256?: unknown } } }).status?.acceptance;
      if (typeof acc?.tests_sha256 !== "string" || !acc.tests_sha256 || !Array.isArray(acc.cases)) throw new Error("invalid snapshot");
      setSnapshot(acc.cases); setDigest(acc.tests_sha256); setResult(null);
    } catch { setFailure({ message: "Could not load the test snapshot.", stale: false }); }
    finally { setBusy(null); }
  };

  useEffect(() => { void load(); }, [appId]);

  useEffect(() => { setResult(null); }, [sourceRevision]);

  const edit = (field: keyof typeof draft, value: string) => {
    setDraft((current) => ({ ...current, [field]: value })); setResult(null);
  };

  const fail = (error: unknown, message: string) => {
    const s = stale(error);
    setFailure({ message: s ? "Tests changed on the server. Reload the snapshot; your draft will be kept." : message, stale: s });
  };

  const save = async () => {
    if (busy) return;
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
    } catch (error) { fail(error, "Could not save the tests. Your draft was kept."); }
    finally { setBusy(null); }
  };

  const run = async () => {
    if (busy || !digest || !snapshot.length) return;
    setBusy("run"); setFailure(null); setResult(null);
    try {
      const { status } = await rpcRef.current("mini_app_status", {
        app_id: appId, include_acceptance_cases: true,
      }) as { status?: { logic?: { source_sha256?: string }; acceptance?: { tests_sha256?: string } } };
      if (status?.acceptance?.tests_sha256 !== digest) throw new Error("stale");
      const sourceDigest = status?.logic?.source_sha256;
      if (!sourceDigest) throw new Error("missing saved source");
      const raw = await rpcRef.current("mini_app_run_tests", {
        app_id: appId, expected_tests_sha256: digest, expected_source_sha256: sourceDigest,
      });
      const data = raw as { success?: unknown; error?: unknown };
      if (data.success !== true) throw new Error(typeof data.error === "string" ? data.error : "run failed");
      if (currentSource.current === sourceRevision) setResult(outcome(raw));
    } catch (error) { fail(error, "Could not run the tests."); }
    finally { setBusy(null); }
  };

  return (
    <section aria-labelledby={titleId} aria-busy={busy !== null}>
      <h2 id={titleId}>Acceptance tests</h2>
      <p>Save logic before running tests.</p>
      <p>
        <button type="button" onClick={() => void load()} disabled={busy !== null}>Reload snapshot</button>{" "}
        <button type="button" onClick={() => void run()} disabled={busy !== null || !digest || !snapshot.length}>Run saved tests</button>
      </p>
      {busy === "load" && <p role="status">Loading snapshot…</p>}
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
          <p>{result.passed}/{result.total} passed</p>
          {result.failed.length > 0 && (
            <ul aria-label="Failed cases">{result.failed.map((name) => <li key={name}>{name}</li>)}</ul>
          )}
        </div>
      )}
    </section>
  );
}
