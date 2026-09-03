import { NextApiRequest, NextApiResponse } from 'next';

// Proxy /api/integrations/gmail/emails -> backend /api/gmail/emails,
// forwarding the caller's Authorization header (same pattern as status.ts).
export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const fwdAuth = req.headers.authorization
    ? { Authorization: req.headers.authorization as string }
    : {};

  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
    const response = await fetch(`${backendUrl}/api/gmail/emails`, {
      method: 'GET',
      headers: { ...fwdAuth, 'Content-Type': 'application/json' },
    });
    const data = await response.json();
    return res.status(200).json({
      emails: data.emails || [],
      total: data.total || 0,
      error: data.error || (response.ok ? undefined : `backend ${response.status}`),
    });
  } catch (error) {
    console.error('Gmail emails proxy error:', error);
    return res.status(200).json({ emails: [], total: 0, error: 'Failed to load emails' });
  }
}
