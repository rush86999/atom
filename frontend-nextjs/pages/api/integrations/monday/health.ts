import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  // Round 80: forward the caller's Authorization header to the backend
  const fwdAuth = req.headers.authorization
    ? { Authorization: req.headers.authorization as string }
    : {};

  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { access_token } = req.query;

    if (!access_token) {
      return res.status(400).json({
        error: 'Access token required',
        details: 'Please provide Monday.com access token'
      });
    }

    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
    // Forward health check to backend
    const backendResponse = await fetch(`${backendUrl}/api/monday/status?user_id=test_user`, {
      method: 'GET',
      headers: { ...fwdAuth,
        'Authorization': `Bearer ${access_token}`,
        'Content-Type': 'application/json'
      }
    });

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json();
      return res.status(backendResponse.status).json({
        error: 'Monday.com health check failed',
        details: errorData.detail || 'Unknown error'
      });
    }

    const healthData = await backendResponse.json();

    return res.status(200).json(healthData);

  } catch (error) {
    console.error('Monday.com health check error:', error);

    return res.status(500).json({
      error: 'Monday.com service unavailable',
      details: error instanceof Error ? error.message : 'Unknown error',
      timestamp: new Date().toISOString()
    });
  }
}
