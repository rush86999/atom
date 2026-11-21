import React, { useEffect, useId, useRef, useState } from "react";

export type Revision = {
  version: number;
  created_at: string;
  created_by: string;
  preview: string;
};

type RevisionPanelProps = {
  load: () => Promise<Revision[]>; restore: (version: number) => Promise<number>;
  refreshEditor: () => Promise<void>; canRestore: boolean; epoch: number;
};

const buttonClass = "rounded border px-3 py-1 text-sm disabled:opacity-50";
const dangerClass = "rounded bg-red-700 px-3 py-1 text-sm text-white disabled:opacity-50";
const errorClass = "rounded border border-red-300 bg-red-50 p-2 text-sm text-red-800";
const successClass = "rounded border border-green-300 bg-green-50 p-2 text-sm text-green-800";

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

export default function RevisionPanel({ load, restore, refreshEditor, canRestore, epoch }: RevisionPanelProps) {
  const titleId = useId();
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [request, setRequest] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<number | null>(null);
  const [restoring, setRestoring] = useState<number | null>(null);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const [restoreSuccess, setRestoreSuccess] = useState<string | null>(null);
  const loadRef = useRef(load);
  const restoringRef = useRef(false);
  loadRef.current = load;

  useEffect(() => {
    let stale = false;
    setLoading(true);
    setLoadError(null);
    loadRef.current().then(
      (data) => {
        if (!stale) {
          setRevisions(data);
          setLoading(false);
        }
      },
      (error) => {
        if (!stale) {
          setLoadError(errorText(error));
          setLoading(false);
        }
      },
    );
    return () => {
      stale = true;
    };
  }, [epoch, request]);

  function refreshHistory() {
    setRequest((value) => value + 1);
  }

  async function confirmRestore(version: number) {
    if (restoringRef.current || !canRestore) return;
    restoringRef.current = true;
    setConfirming(null);
    setRestoring(version);
    setRestoreError(null); setRestoreSuccess(null);
    try {
      const newVersion = await restore(version);
      setRestoreSuccess(`Version ${version} restored as version ${newVersion}.`);
      refreshHistory();
      try { await refreshEditor(); }
      catch {
        setRestoreSuccess((message) => `${message ?? "The restore succeeded."} The editor could not be refreshed; the restore is still confirmed.`);
      }
    } catch (error) {
      setRestoreError(`The restore could not be confirmed. History is being refreshed; check it before trying again. ${errorText(error)}`);
      refreshHistory();
    } finally {
      restoringRef.current = false; setRestoring(null);
    }
  }

  const ordered = revisions.slice().sort((a, b) => b.version - a.version);
  const empty = !loading && !loadError && revisions.length === 0;

  return (
    <section aria-labelledby={titleId} aria-busy={loading} className="space-y-4 rounded border border-slate-300 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 id={titleId} className="text-lg font-semibold">Revision history</h2>
          <p className="text-sm text-slate-600">Newest revisions first.</p>
        </div>
        <button type="button" className={buttonClass} onClick={refreshHistory} disabled={loading}>Refresh history</button>
      </div>

      {!canRestore && <p className="text-sm text-slate-600">Restoring is currently unavailable.</p>}
      {loading && (
        <p role="status" className="text-sm">
          {revisions.length > 0 ? "Refreshing history…" : "Loading revisions…"}
        </p>
      )}
      {loadError && <p role="alert" className={errorClass}>Could not load revisions: {loadError}</p>}
      {empty && <p role="status" className="text-sm text-slate-600">No revisions yet.</p>}
      {restoring !== null && <p role="status" className="text-sm">Restoring version {restoring}…</p>}
      {restoreSuccess && <p role="status" className={successClass}>{restoreSuccess}</p>}
      {restoreError && <p role="alert" className={errorClass}>{restoreError}</p>}

      <ol className="space-y-3">
        {ordered.map((revision) => (
          <li key={revision.version} className="rounded border border-slate-200 p-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-medium">Version {revision.version}</p>
              <p className="text-sm text-slate-600">
                By <span className="font-medium">{revision.created_by}</span> ·{" "}
                <time dateTime={revision.created_at}>{new Date(revision.created_at).toLocaleString()}</time>
              </p>
            </div>
            <h3 className="mt-3 text-sm font-medium">Source preview</h3>
            <pre tabIndex={0} aria-label={`Source preview for version ${revision.version}`} className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">
              {revision.preview}
            </pre>
            <div className="mt-2">
              {confirming === revision.version ? (
                <div role="group" aria-label={`Confirm restore of version ${revision.version}`} className="rounded border border-amber-300 bg-amber-50 p-2">
                  <p className="text-sm">Restore version {revision.version}? This replaces the editor content.</p>
                  <div className="mt-2 flex gap-2">
                    <button type="button" className={dangerClass} onClick={() => void confirmRestore(revision.version)} disabled={!canRestore || restoring !== null}>
                      Confirm restore
                    </button>
                    <button type="button" className={buttonClass} onClick={() => setConfirming(null)}>Cancel</button>
                  </div>
                </div>
              ) : (
                <button type="button" className={buttonClass} onClick={() => setConfirming(revision.version)} disabled={!canRestore || restoring !== null}>
                  Restore version {revision.version}
                </button>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
