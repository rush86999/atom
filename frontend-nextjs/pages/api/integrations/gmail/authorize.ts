import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Redirect to backend OAuth authorization endpoint
    const backendUrl = 'http://localhost:5000/api/auth/gmail/authorize';

    // Get user ID from query parameters or session
    const userId = req.query.userId as string || 'default-user';

    // Add any additional parameters needed
    const authUrl = `${backendUrl}?user_id=${encodeURIComponent(userId)}&redirect_uri=${encodeURIComponent('http://localhost:3000/oauth/gmail/callback')}`;

    // Redirect to backend OAuth flow
    res.redirect(authUrl);
  } catch (error) {
    console.error('Gmail authorize error:', error);
    return res.status(500).json({
      error: 'Failed to initiate Gmail OAuth flow',
      service: 'gmail',
      timestamp: new Date().toISOString(),
    });
  }
}
