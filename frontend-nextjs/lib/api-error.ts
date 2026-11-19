// Extract a readable message from a backend error response body.
//
// Backend error bodies vary by handler: FastAPI `detail` may be a string,
// an object, or a validation-error array; other handlers return `error`
// (string or {type, message}) or `message`. Prefer readable strings,
// including structured `detail.message`, and stringify other values so
// toasts never render "[object Object]" (see PR #616, issue #618).
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
      } else if (Array.isArray(candidate) && candidate.length && candidate.every(
        item => item && typeof item === "object" && typeof item.msg === "string"
      )) {
        // FastAPI validation entries also carry raw `input` and `ctx`. A
        // password form must display the message, never that submitted value.
        return candidate.map(item => item.msg).join("; ");
      } else if (
        candidate != null
        && typeof candidate === "object"
        && !Array.isArray(candidate)
        && typeof (candidate as Record<string, unknown>).message === "string"
        && (candidate as { message: string }).message.trim()
      ) {
        // Structured handler details may carry {message, blockers}; show the
        // readable message instead of stringifying the whole object.
        return (candidate as { message: string }).message;
      } else if (candidate != null) {
        return JSON.stringify(candidate);
      }
    }
  }
  return status ? `${fallback} (${status})` : fallback;
}
