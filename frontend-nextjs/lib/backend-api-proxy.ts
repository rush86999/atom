/** Thin server transport: backend remains the only authentication/data authority. */
import type { NextApiRequest, NextApiResponse } from 'next';

export async function forwardBackendApi(
  req: NextApiRequest,
  res: NextApiResponse,
  path: string,
  allowedMethods: readonly string[],
): Promise<void> {
  const method = req.method || 'GET';
  if (!allowedMethods.includes(method)) {
    res.setHeader('Allow', allowedMethods.join(', '));
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }
  // Presence is not authentication: the backend validates the exact credential.
  // Do not substitute another cookie when an explicit Authorization is invalid.
  const explicit = req.headers.authorization;
  const cookieToken = req.cookies?.auth_token || req.cookies?.['next-auth.session-token'] || req.cookies?.['__Secure-next-auth.session-token'];
  const authorization = explicit === undefined && typeof cookieToken === 'string'
    ? `Bearer ${cookieToken}` : explicit;
  if (typeof authorization !== 'string' || !/^Bearer [^\s]+$/.test(authorization)) {
    res.status(401).json({ error: 'Authentication required' });
    return;
  }
  const base = process.env.BACKEND_URL || process.env.PYTHON_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  let target: URL;
  try {
    if (!base) throw new Error('missing backend');
    const configured = new URL(base);
    if (!['http:', 'https:'].includes(configured.protocol) || configured.username || configured.password) throw new Error('invalid backend');
    target = new URL(path, configured);
    for (const [key, value] of Object.entries(req.query)) {
      if (key === 'id' || value === undefined) continue;
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
    });
    const payload: unknown = await response.json();
    res.status(response.status).json(payload);
  } catch {
    // Never retry a mutation after dispatch: confirmation may have been lost.
    res.status(503).json(method === 'GET'
      ? { error: 'Backend is unavailable', code: 'BACKEND_UNAVAILABLE' }
      : { error: 'The operation could not be confirmed', code: 'EFFECT_UNKNOWN', effect: 'unknown', replay: 'do_not_repeat' });
  } finally {
    clearTimeout(timer);
  }
}
