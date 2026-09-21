// Extract a readable message from a backend error response body.
//
// Backend error bodies vary by handler: FastAPI `detail` may be a string,
// an object, or a validation-error array; other handlers return `error`
// (string or {type, message}) or `message`. Stringify whatever comes back
// so toasts never render "[object Object]" (see PR #616, issue #618).
export function extractApiErrorMessage(
  data: unknown,
  fallback: string,
  status?: number
): string {
  if (data && typeof data === "object") {
    const body = data as Record<string, any>;
    const err = body.error;
    const candidates = [
      body.detail,
      body.message,
      typeof err === "string" ? err : err?.message ?? err?.type,
    ];
    for (const candidate of candidates) {
      if (typeof candidate === "string") {
        if (candidate.trim()) return candidate;
      } else if (candidate != null) {
        return JSON.stringify(candidate);
      }
    }
  }
  return status ? `${fallback} (${status})` : fallback;
}
