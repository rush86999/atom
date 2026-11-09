import type { Session } from 'next-auth';
import type { JWT } from 'next-auth/jwt';

class BackendSessionRejected extends Error {
  constructor() {
    super('BACKEND_SESSION_UNAVAILABLE');
    Object.setPrototypeOf(this, new.target.prototype);
  }
}
// Retain only credential/standard JWT metadata. Unknown cached claims are not authority.
const credentialKeys = ['id', 'sub', 'backendToken', 'iat', 'exp', 'jti'] as const;
function credentialOnly(token: JWT): JWT {
  return Object.fromEntries(credentialKeys.filter(key => token[key] !== undefined).map(key => [key, token[key]]));
}

/** A refusal is known; unavailable authority is unknown and grants nothing. */
async function reauthorizeBackendSession(token: JWT, resolveBackend: () => string): Promise<JWT | null> {
  if (typeof token.id !== 'string' || !token.id || typeof token.backendToken !== 'string' || !token.backendToken ||
      (token.sub !== undefined && token.sub !== token.id)) throw new BackendSessionRejected();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(`${resolveBackend().replace(/\/$/, '')}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token.backendToken}`, Accept: 'application/json' },
      cache: 'no-store', redirect: 'error', signal: controller.signal,
    });
    if (response.status === 401 || response.status === 403) throw new BackendSessionRejected();
    if (!response.ok) return null;
    const current = await response.json();
    if (controller.signal.aborted || !current || typeof current !== 'object' || Array.isArray(current)) return null;
    if ((current.id !== undefined && current.id !== token.id) ||
        (current.status !== undefined && current.status !== 'active')) throw new BackendSessionRejected();
    const scopeValue = (key: string) => Object.prototype.hasOwnProperty.call(current, key) &&
      (current[key] === null || typeof current[key] === 'string');
    if (current.id !== token.id || current.status !== 'active' ||
        (current.success !== undefined && current.success !== true) ||
        typeof current.email !== 'string' || !current.email || typeof current.role !== 'string' || !current.role ||
        !scopeValue('workspace_id') || !scopeValue('tenant_id')) return null;
    const refreshed: JWT = { ...credentialOnly(token), email: current.email, role: current.role,
      workspace_id: current.workspace_id, tenant_id: current.tenant_id,
      name: `${typeof current.first_name === 'string' ? current.first_name : ''} ${typeof current.last_name === 'string' ? current.last_name : ''}`.trim() || current.email };
    return refreshed;
  } catch (error) {
    if (error instanceof BackendSessionRejected) throw error;
    // An outage/invalid response is not proof that the credential was revoked.
    // Never attach a bearer, response body or raw exception to SDK logs.
    return null;
  } finally {
    controller.abort();
    clearTimeout(timer);
  }
}

/** The installed v4 consumer accepts null session bodies without a grant.
 * Verification belongs here, on every session read, not in persisted JWT flags.
 * Unknown results keep only the recoverable credential, never cached authority.
 */
export async function projectCurrentBackendSession(session: Session, token: JWT | undefined, resolveBackend: () => string): Promise<Session | null> {
  if (!session?.user || !token) return null;
  const credentialOnlySnapshot = credentialOnly(token);
  const fresh = await reauthorizeBackendSession(token, resolveBackend);
  for (const key of Object.keys(token)) delete token[key];
  Object.assign(token, fresh || credentialOnlySnapshot);
  if (!fresh) return null;
  // Do not preserve arbitrary fields from a stale cookie or an earlier callback.
  return { expires: session.expires, backendToken: fresh.backendToken as string,
    user: { id: fresh.id as string, email: fresh.email, name: fresh.name,
      role: fresh.role as string, workspace_id: fresh.workspace_id as string | null,
      tenant_id: fresh.tenant_id as string | null } };
}
