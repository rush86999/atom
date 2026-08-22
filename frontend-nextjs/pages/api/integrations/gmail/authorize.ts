import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  // Round 80: forward the caller's Authorization header to the backend
  const fwdAuth = req.headers.authorization
    ? { Authorization: req.headers.authorization as string }
    : {};

  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Redirect to backend OAuth authorization endpoint (Standard Google OAuth)
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

    // Redirect to the standard Google OAuth initiation endpoint
    // The backend will handle the redirect to Google
    res.redirect(`${backendUrl}/api/auth/google/initiate`);
  } catch (error) {
    console.error('Gmail authorize error:', error);
    return res.status(500).json({
      error: 'Failed to initiate Gmail OAuth flow',
      service: 'gmail',
      timestamp: new Date().toISOString(),
    });
  }
}
