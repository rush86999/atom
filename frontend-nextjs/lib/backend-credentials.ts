/** The existing backend is the sole credential and current-user authority. */
class BackendChallenge extends Error {
  constructor(code: string) {
    super(code);
    // Preserve the branded challenge under the project's ES5 transpilation.
    Object.setPrototypeOf(this, new.target.prototype);
  }
}
type Credentials = { email?: string; password?: string; totp_code?: string } | undefined;

export function createBackendCredentialsAuthorize(resolveBackend: () => string) {
  return async (credentials: Credentials) => {
    if (!credentials?.email || !credentials.password) return null;
    const controller = new AbortController();
    // One deadline covers dispatch, parsing and identity readback. Never retry
    // credentials under an alternate database, tenant hint or provider.
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const backend = resolveBackend().replace(/\/$/, '');
      const login = await fetch(`${backend}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ username: credentials.email, password: credentials.password, totp_code: credentials.totp_code }),
        signal: controller.signal,
      });
      const data = await login.json();
      if (controller.signal.aborted) return null;
      if (login.ok && data?.two_factor_required === true) throw new BackendChallenge('2FA_REQUIRED');
      if (login.status === 401 && data?.detail === 'Invalid 2FA code') throw new BackendChallenge('INVALID_2FA_CODE');
      if (!login.ok || typeof data?.access_token !== 'string' || !data.access_token) return null;
      const me = await fetch(`${backend}/api/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}`, Accept: 'application/json' },
        cache: 'no-store', signal: controller.signal,
      });
      if (!me.ok) return null;
      const identity = await me.json();
      if (controller.signal.aborted) return null;
      if (!identity || typeof identity.id !== 'string' || !identity.id ||
          typeof identity.email !== 'string' || !identity.email || identity.status !== 'active') return null;
      return {
        id: identity.id, email: identity.email,
        name: `${identity.first_name || ''} ${identity.last_name || ''}`.trim() || identity.email,
        role: identity.role, workspace_id: identity.workspace_id,
        tenant_id: identity.tenant_id,
        // Keep both existing callback contracts; neither is a new credential.
        token: data.access_token, access_token: data.access_token,
      };
    } catch (error) {
      if (error instanceof BackendChallenge) throw error;
      // Response/error bodies may contain credentials or SQL material.
      console.warn('Backend sign-in identity unavailable', { code: 'backend_identity_unavailable' });
      return null;
    } finally {
      clearTimeout(timer);
    }
  };
}
