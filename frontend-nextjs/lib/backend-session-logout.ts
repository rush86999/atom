/** One bounded notification to the existing backend; never retries a write. */
export async function notifyBackendSignOut(resolveBackend: () => string, backendToken: string): Promise<void> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  try {
    const base = resolveBackend().replace(/\/$/, '');
    const response = await fetch(`${base}/api/auth/logout`, {
      method: 'POST', redirect: 'error',
      headers: { Authorization: `Bearer ${backendToken}`, Accept: 'application/json' },
      signal: controller.signal,
    });
    const result = await response.json();
    if (!response.ok || result?.success !== true || result?.verification?.status !== 'verified') {
      console.warn('Server sign-out could not be confirmed.', { code: 'server_logout_unverified', status: response.status });
    }
  } catch {
    // Never log credential material or prevent local cookie clearing. The
    // event supplies no success receipt to the UI and never retries a write.
    console.warn('Server sign-out could not be confirmed.', { code: 'server_logout_unavailable' });
  } finally {
    clearTimeout(timer);
  }
}

/** The existing backend owns revocation; NextAuth still clears this device. */
export function createBackendSignOutEvent(resolveBackend: () => string) {
  return async (message: { token?: unknown; session?: unknown }): Promise<void> => {
    const token = message.token;
    if (!token || typeof token !== 'object' || Array.isArray(token)) return;
    const backendToken = (token as { backendToken?: unknown }).backendToken;
    if (typeof backendToken !== 'string' || !backendToken) return;
    await notifyBackendSignOut(resolveBackend, backendToken);
  };
}
