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
 * fetch() for authenticated backend calls — the general expiry mechanism.
 *
 * Injects the Authorization header and, on 401/403 (expired token, rotated
 * signing key), triggers the shared login redirect instead of letting each
 * caller surface a raw "returned 401" error. The response is still returned
 * so existing `response.ok` checks behave unchanged on other statuses.
 *
 * Every fetch() that sends authHeaders() should use this instead; ~20
 * integration components previously handled expiry zero times.
 */
export async function authFetch(
  input: RequestInfo | URL,
  init: RequestInit = {}
): Promise<Response> {
  const headers = new Headers(init.headers || {});
  const token = getAuthToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(input, { ...init, headers });
  if (response.status === 401 || response.status === 403) {
    handleSessionExpired();
  }
  return response;
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
