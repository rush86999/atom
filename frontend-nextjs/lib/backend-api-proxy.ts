/** Thin server transport: backend remains the only authentication/data authority. */
import type { NextApiRequest, NextApiResponse } from 'next';
import { resolveConfiguredBackend, resolveWebAuthSecret } from './web-auth-config';

export async function forwardBackendApi(
  req: NextApiRequest,
  res: NextApiResponse,
  path: string,
  allowedMethods: readonly string[],
  options: { validateResponse?: (payload: unknown) => boolean; pathParameters?: readonly string[] } = {},
): Promise<void> {
  res.setHeader('Cache-Control', 'private, no-store');
  const method = req.method || 'GET';
  if (!allowedMethods.includes(method)) {
    res.setHeader('Allow', allowedMethods.join(', '));
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }
  // Presence is not authentication: the backend validates the exact credential.
  // Do not substitute another cookie when an explicit Authorization is invalid.
  const explicit = req.headers.authorization;
  let authorization = explicit;
  if (explicit === undefined) {
    const direct = req.cookies?.auth_token;
    if (typeof direct === 'string' && direct) authorization = `Bearer ${direct}`;
    else if (Object.keys(req.cookies || {}).some(key => /^(?:__Secure-)?next-auth\.session-token(?:\.\d+)?$/.test(key))) {
      try {
        // Decode only the cookie container. The backend still authorizes the
        // exact generation; cached role/scope is never trusted by this proxy.
        const { getToken } = await import('next-auth/jwt');
        const token = await getToken({ req, secret: resolveWebAuthSecret() });
        if (typeof token?.backendToken === 'string' && token.backendToken)
          authorization = `Bearer ${token.backendToken}`;
      } catch {
        res.status(503).json({ error: 'Authentication configuration is unavailable', code: 'BACKEND_UNAVAILABLE' });
        return;
      }
    }
  }
  if (typeof authorization !== 'string' || authorization.trim() !== authorization || !/^Bearer [^\s]+$/.test(authorization)) {
    res.status(401).json({ error: 'Authentication required' });
    return;
  }
  let target: URL;
  try {
    const configured = new URL(resolveConfiguredBackend());
    target = new URL(path, configured);
    for (const [key, value] of Object.entries(req.query)) {
      if (options.pathParameters?.includes(key) || value === undefined) continue;
      for (const item of Array.isArray(value) ? value : [value]) target.searchParams.append(key, item);
    }
  } catch {
    res.status(503).json({ error: 'Backend is not configured', code: 'BACKEND_UNAVAILABLE' });
    return;
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(target.toString(), {
      method,
      headers: { Authorization: authorization, 'Content-Type': 'application/json', Accept: 'application/json' },
      ...(method === 'GET' ? {} : { body: req.body === undefined ? undefined : JSON.stringify(req.body) }),
      signal: controller.signal,
      redirect: 'error',
      cache: 'no-store',
    });
    if (controller.signal.aborted) throw new Error('backend deadline');
    if (response.status === 204 && !options.validateResponse) {
      res.status(204).end();
      return;
    }
    let payload: unknown;
    try { payload = await response.json(); }
    catch {
      if (!controller.signal.aborted && response.status >= 400 && response.status < 500) {
        res.status(response.status).json({ error: 'Backend request refused', code: 'BACKEND_REFUSED' });
        return;
      }
      throw new Error('backend response unavailable');
    }
    if (controller.signal.aborted) throw new Error('backend deadline');
    if (response.status >= 200 && response.status < 300 && options.validateResponse && !options.validateResponse(payload)) {
      res.status(502).json({ success: false, error: 'Backend response could not be verified', code: 'INVALID_BACKEND_RESPONSE' });
      return;
    }
    res.status(response.status).json(payload);
  } catch {
    // Never retry a mutation after dispatch: confirmation may have been lost.
    res.status(503).json(method === 'GET'
      ? { error: 'Backend is unavailable', code: 'BACKEND_UNAVAILABLE' }
      : { error: 'The operation could not be confirmed', code: 'EFFECT_UNKNOWN', effect: 'unknown', replay: 'do_not_repeat' });
  } finally {
    controller.abort();
    clearTimeout(timer);
  }
}
