import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Redirect to backend OAuth authorization endpoint (Standard Google OAuth)
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

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
