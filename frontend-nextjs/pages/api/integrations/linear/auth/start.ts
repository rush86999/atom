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
    const response = await fetch(`${backendUrl}/api/integrations/linear/auth/start`, {
      method: 'GET',
      headers: { ...fwdAuth,
        'Content-Type': 'application/json',
      },
    });

    if (response.ok) {
      const data = await response.json();
      // Redirect to Linear authorization URL
      if (data.auth_url) {
        res.redirect(data.auth_url);
      } else {
        res.status(500).json({
          error: 'Failed to get Linear authorization URL',
          message: 'No authorization URL returned from backend',
        });
      }
    } else {
      res.status(500).json({
        error: 'Backend Linear service error',
        message: 'Failed to contact Linear authentication service',
      });
    }
  } catch (error) {
    console.error('Linear OAuth start error:', error);
    return res.status(500).json({
      error: 'Failed to start Linear OAuth flow',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}