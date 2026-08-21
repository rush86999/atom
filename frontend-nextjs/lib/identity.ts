/**
 * Client identity + API base resolution (multi-user cleanup).
 *
 * The backend stamps the authenticated user (JWT `sub`) onto every chat
 * request server-side — the frontend's `user_id` fields only matter for
 * LIST endpoints (sessions) and realtime subscriptions. These helpers make
 * those use the real authenticated identity instead of the legacy shared
 * "default_user" constant (which merged every employee's sessions into one).
 */

export type CurrentUser = {
  id: string;
  email?: string;
};

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(decodeURIComponent(escape(json)));
  } catch {
    return null;
  }
}

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("auth_token") || localStorage.getItem("token");
}

export function getCurrentUser(): CurrentUser | null {
  if (typeof window === "undefined") return null;
  const token = getAuthToken();
  if (token) {
    const claims = decodeJwtPayload(token);
    if (claims?.sub) {
      return { id: String(claims.sub), email: claims.email ? String(claims.email) : undefined };
    }
  }
  const cached = localStorage.getItem("user_id");
  if (cached && cached !== "default_user") return { id: cached };
  return null;
}

/**
 * The user id for list endpoints / subscriptions. Falls back to "me" —
 * never "default_user" (the shared-identity bug) — when unauthenticated;
 * unauthenticated list calls fail with 401 rather than leaking a merged
 * shared history.
 */
export function getCurrentUserId(): string {
  return getCurrentUser()?.id || "me";
}
