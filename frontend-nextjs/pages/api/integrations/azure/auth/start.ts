import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  // Round 80: forward the caller's Authorization header to the backend
  const fwdAuth = req.headers.authorization
    ? { Authorization: req.headers.authorization as string }
    : {};

  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

  try {
    // Start OAuth flow
    const response = await fetch(`${backendUrl}/api/auth/azure/start`, {
      method: 'POST',
      headers: { ...fwdAuth,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: 'current',
        redirect_uri: `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/integrations/azure/auth/callback`,
      }),
    });

    if (response.ok) {
      const data = await response.json();
      // Redirect to Azure authorization URL
      if (data.authorization_url) {
        res.redirect(data.authorization_url);
      } else {
        res.status(500).json({
          error: 'Failed to get Azure authorization URL',
          message: 'No authorization URL returned from backend',
        });
      }
    } else {
      res.status(500).json({
        error: 'Backend Azure service error',
        message: 'Failed to contact Azure authentication service',
      });
    }
  } catch (error) {
    console.error('Azure OAuth start error:', error);
    return res.status(500).json({
      error: 'Failed to start Azure OAuth flow',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}