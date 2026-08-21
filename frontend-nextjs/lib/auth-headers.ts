/**
 * Auth headers for same-origin integration calls.
 *
 * Round 80: the Next.js proxy handlers under pages/api/integrations/* forward
 * the caller's Authorization header to the backend, and backend data/write
 * endpoints require it (rounds 80/80c). Components stored the JWT in
 * localStorage but never sent it on these calls, so every gated call
 * returned 401 once the proxies started reaching the live backend.
 */
export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return (
    window.localStorage.getItem("auth_token") ||
    window.localStorage.getItem("token")
  );
}

export function authHeaders(
  base: Record<string, string> = {}
): Record<string, string> {
  const headers: Record<string, string> = { ...base };
  const token = getAuthToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}
