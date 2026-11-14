import { NextApiRequest, NextApiResponse } from 'next';
import { getServerSession } from 'next-auth';
import { authOptions } from './[...nextauth]';

/**
 * WA-075 — Active Sessions proxy.
 *
 * The FastAPI backend is the only session authority: it owns the inventory
 * (user_sessions) and the durable revocation ledger (revoked_tokens), and it
 * revalidates every NextAuth session read. This route therefore never falls
 * back to a direct Postgres query and never accepts a client-supplied token:
 * a fallback would be a second authority that reports success while the
 * presented credential keeps working.
 */
const API_BASE_URL =
  process.env.PYTHON_API_SERVICE_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'http://127.0.0.1:8000';
const BACKEND_TIMEOUT_MS = 10_000;

type BackendResult = { status: number; body: any };

async function callBackend(
  path: string,
  backendToken: string,
  method: 'GET' | 'POST' | 'DELETE',
): Promise<BackendResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${backendToken}`,
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
      redirect: 'error',
      signal: controller.signal,
    });
    let body: any = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    return { status: response.status, body };
  } finally {
    clearTimeout(timer);
  }
}

function failure(res: NextApiResponse, status: number, body: any, fallback: string) {
  const message =
    (body && typeof body.message === 'string' && body.message) ||
    (body && typeof body.detail === 'string' && body.detail) ||
    fallback;
  return res.status(status).json({
    ...(body && typeof body === 'object' && !Array.isArray(body) ? body : {}),
    error: message,
    message,
  });
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const session = await getServerSession(req, res, authOptions);
  if (!session?.user?.email) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const backendToken = (session as any).backendToken || (session as any).access_token;
  if (typeof backendToken !== 'string' || !backendToken) {
    // No backend credential means no authority to list or revoke anything.
    return res.status(401).json({
      error: 'Backend session unavailable. Sign in again to manage sessions.',
    });
  }

  // GET: list active sessions (backend computes is_current from the bearer).
  if (req.method === 'GET') {
    try {
      const { status, body } = await callBackend('/api/users/sessions', backendToken, 'GET');
      if (status < 200 || status >= 300) {
        return failure(res, status, body, 'Failed to load sessions');
      }
      return res.status(200).json({ sessions: Array.isArray(body) ? body : [] });
    } catch {
      return res.status(503).json({ error: 'Session service unavailable. Try again.' });
    }
  }

  // DELETE: revoke one session or all recorded sessions except this device.
  if (req.method === 'DELETE') {
    const { sessionId, revokeAll } = (req.body ?? {}) as {
      sessionId?: unknown;
      revokeAll?: unknown;
    };

    if (!revokeAll && (typeof sessionId !== 'string' || !sessionId)) {
      return res.status(400).json({ error: 'Session ID is required' });
    }

    const path = revokeAll
      ? '/api/users/sessions'
      : `/api/users/sessions/${encodeURIComponent(sessionId as string)}`;

    try {
      const { status, body } = await callBackend(path, backendToken, 'DELETE');
      if (status < 200 || status >= 300) {
        // Never report success on 401/403/409/5xx: the device may still be
        // signed in, and the caller must be able to say so.
        return failure(res, status, body, 'The session could not be revoked');
      }
      return res.status(200).json({
        ...(body && typeof body === 'object' ? body : {}),
        message:
          (body && typeof body.message === 'string' && body.message) ||
          (revokeAll ? 'All sessions revoked' : 'Session revoked'),
      });
    } catch {
      return res.status(503).json({
        error: 'Session revocation could not be confirmed. Do not assume the device is signed out.',
      });
    }
  }

  // POST: heartbeat for the presented bearer only; a body token is ignored by
  // the backend, so nothing here trusts client-supplied credential material.
  if (req.method === 'POST') {
    try {
      const { status, body } = await callBackend('/api/users/sessions', backendToken, 'POST');
      if (status < 200 || status >= 300) {
        return failure(res, status, body, 'Session activity could not be recorded');
      }
      return res.status(200).json({
        tracked: body?.tracked === true,
        registered: body?.registered === true,
        is_current: body?.is_current === true,
        message: typeof body?.message === 'string' ? body.message : 'Session activity recorded',
      });
    } catch {
      return res.status(503).json({ error: 'Session service unavailable' });
    }
  }

  return res.status(405).json({ error: 'Method not allowed' });
}
