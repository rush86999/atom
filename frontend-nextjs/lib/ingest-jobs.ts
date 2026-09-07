// Shared client helpers for the drive integrations' background ingest jobs.
//
// Every storage integration's ingest endpoints (zoho-workdrive, onedrive,
// gdrive, dropbox, box) start a job server-side and return
// {success, data:{job_id}} immediately — a big file or folder tree takes
// minutes to download + parse + embed, while the Next.js dev proxy aborts
// proxied requests at 30s and synthesizes a 500 ("socket hang up") while the
// backend is still working. The panels poll the job instead of holding one
// request open, and surface the shared recent-jobs list so an ingest
// started before this page load is visible instead of silently reset.

export interface IngestJob {
  job_id: string;
  status: 'running' | 'completed' | 'failed';
  kind?: string;
  integration?: string;
  folder_ids?: string[] | null;
  file_id?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  result?: any;
  error?: string | null;
}

export type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;

const JOB_POLL_INTERVAL_MS = 3000;
const JOB_POLL_CAP_MS = 20 * 60 * 1000; // 20 min — folder trees are slow
const PERSISTENT_MISSING_LIMIT = 3; // consecutive 404s ⇒ the backend restarted

/**
 * POST the ingest endpoint and return the started job id (null when the
 * backend answered with a synchronous, pre-job result — backward compat).
 * Throws on HTTP errors with the server's message.
 */
export async function startIngestJob(
  fetchFn: FetchLike,
  postPath: string,
  body: Record<string, unknown>
): Promise<{ jobId: string | null; started: any }> {
  const response = await fetchFn(postPath, {
    method: 'POST',
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(extractErrorMessage(text, response.status));
  }
  const started = await response.json();
  return { jobId: started?.job_id ?? started?.data?.job_id ?? null, started };
}

/**
 * Poll a job until completed/failed, then resolve with its result (already
 * normalized to {success, error?, ...}). `basePath` is the integration's API
 * base (e.g. "/api/onedrive") — every integration's router mounts the shared
 * status route at {basePath}/ingest/jobs/{job_id}. Persistent 404s mean the
 * in-process registry is gone (backend restarted) — say so instead of
 * timing out.
 */
export async function pollIngestJob(
  fetchFn: FetchLike,
  jobId: string,
  basePath: string,
  label: string
): Promise<any> {
  const deadline = Date.now() + JOB_POLL_CAP_MS;
  let consecutiveMissing = 0;
  for (;;) {
    const statusResp = await fetchFn(`${basePath}/ingest/jobs/${jobId}`);
    if (statusResp.status === 404) {
      consecutiveMissing += 1;
      if (consecutiveMissing >= PERSISTENT_MISSING_LIMIT) {
        throw new Error(
          `Ingestion job was interrupted (the server restarted) — please run the ${label} again.`
        );
      }
    } else if (statusResp.ok) {
      consecutiveMissing = 0;
      const snap = await statusResp.json();
      const job = snap?.data ?? snap;
      if (job?.status === 'completed' || job?.status === 'failed') {
        const result = job.result ?? {};
        if (job.status === 'failed') {
          return {
            ...result,
            success: false,
            error: job.error || result?.error || `${label} failed`
          };
        }
        return result;
      }
    }
    if (Date.now() > deadline) break;
    await new Promise(resolve => setTimeout(resolve, JOB_POLL_INTERVAL_MS));
  }
  throw new Error('Ingestion is still running — check the ingestion status in a few minutes.');
}

/** Convenience: start + poll in one call. `basePath` = integration base
 * (e.g. "/api/gdrive"); `postPath` = the ingest POST endpoint. */
export async function runIngestJob(
  fetchFn: FetchLike,
  postPath: string,
  basePath: string,
  body: Record<string, unknown>,
  label: string
): Promise<any> {
  const { jobId, started } = await startIngestJob(fetchFn, postPath, body);
  if (!jobId) return started; // backward compat: synchronous result
  return pollIngestJob(fetchFn, jobId, basePath, label);
}

/** Recent jobs for one integration (running first) — GET {basePath}/ingest/jobs. */
export async function fetchRecentJobs(fetchFn: FetchLike, basePath: string): Promise<IngestJob[]> {
  try {
    const response = await fetchFn(`${basePath}/ingest/jobs`);
    if (!response.ok) return [];
    const data = await response.json();
    const jobs = data?.data ?? data;
    return Array.isArray(jobs) ? jobs : [];
  } catch {
    return []; // the status strip is best-effort
  }
}

// The backend error envelope is {detail:{error:{message,...}}} (BaseAPIRouter)
// or plain {detail} / {error} — extract something human for toasts.
export function extractErrorMessage(text: string, status: number): string {
  try {
    const parsed = JSON.parse(text);
    return (
      parsed?.detail?.error?.message ||
      parsed?.detail?.message ||
      (typeof parsed?.detail === 'string' ? parsed.detail : undefined) ||
      parsed?.error ||
      `Request failed (${status})`
    );
  } catch {
    return text || `Request failed (${status})`;
  }
}
