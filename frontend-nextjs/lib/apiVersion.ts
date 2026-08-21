/**
 * API compatibility pin (berd gap #2).
 *
 * The build records the backend API version it was built against
 * (NEXT_PUBLIC_API_VERSION, default 1). At startup we ask the backend for
 * its version; a mismatch warns loudly instead of failing subtly later.
 */

export const EXPECTED_API_VERSION = Number(process.env.NEXT_PUBLIC_API_VERSION || 1);

let checked = false;

export async function checkApiVersion(): Promise<{ ok: boolean; server?: number; message?: string }> {
  if (checked || typeof window === "undefined") return { ok: true };
  checked = true;
  try {
    const base = process.env.NEXT_PUBLIC_API_URL || "";
    const res = await fetch(`${base}/api/meta/version`);
    if (!res.ok) return { ok: false, message: `version endpoint ${res.status}` };
    const data = await res.json();
    const server: number = data.api_version;
    if (server !== EXPECTED_API_VERSION) {
      const message =
        `Backend API version ${server} ≠ build expectation ${EXPECTED_API_VERSION}. ` +
        `The UI may misbehave; rebuild the frontend against the current backend.`;
      console.warn(`[api-version] ${message}`);
      return { ok: false, server, message };
    }
    return { ok: true, server };
  } catch (e) {
    // Version check is best-effort — never block the app on it.
    return { ok: true, message: `unreachable (${String(e)})` };
  }
}
