import { NextApiRequest, NextApiResponse } from 'next';

// Proxy /api/integrations/gmail/events -> backend /api/gmail/events,
// forwarding the caller's Authorization header (same pattern as status.ts).
// Backend failures are forwarded with the real status code — the page can
// then tell "no events" apart from "request failed".
export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const fwdAuth = req.headers.authorization
    ? { Authorization: req.headers.authorization as string }
    : {};

  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
    const response = await fetch(`${backendUrl}/api/gmail/events`, {
      method: 'GET',
      headers: { ...fwdAuth, 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      let detail: string | null = null;
      try {
        const body = await response.json();
        detail = body?.detail || null;
      } catch {
        // non-JSON error body — fall through to the generic message
      }
      return res.status(response.status || 502).json({
        events: [],
        total: 0,
        error: detail || `backend ${response.status}`,
      });
    }

    const data = await response.json();
    return res.status(200).json({
      events: data.events || [],
      total: data.total || 0,
      error: data.error || undefined,
    });
  } catch (error) {
    console.error('Gmail events proxy error:', error);
    // Backend unreachable — 502 so the caller never mistakes this for an
    // empty calendar.
    return res.status(502).json({ events: [], total: 0, error: 'Failed to reach backend' });
  }
}
