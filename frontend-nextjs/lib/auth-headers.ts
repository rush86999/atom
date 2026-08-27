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

/**
 * Clear an invalid session and bounce to /login. Raw fetch() calls bypass
 * the axios 401 interceptor in lib/api.ts (which does exactly this), so
 * fetch-based callers must invoke this themselves when the backend rejects
 * their token (401/403). No-op on auth pages to avoid a redirect loop.
 *
 * Returns true when a redirect was started so callers can bail out of
 * in-flight handlers.
 */
export function handleSessionExpired(): boolean {
  if (typeof window === "undefined") return false;
  const path = window.location.pathname;
  if (path.startsWith("/login") || path.startsWith("/auth/")) {
    return false;
  }
  window.localStorage.removeItem("auth_token");
  window.localStorage.removeItem("token");
  window.location.href = `/login?callbackUrl=${encodeURIComponent(window.location.href)}`;
  return true;
}
