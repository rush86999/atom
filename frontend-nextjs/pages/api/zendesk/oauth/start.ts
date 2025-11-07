import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  try {
    const response = await fetch(`${backendUrl}/api/zendesk/auth/start`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (response.ok) {
      const data = await response.json();
      // Redirect to Zendesk authorization URL
      if (data.auth_url) {
        res.redirect(data.auth_url);
      } else {
        res.status(500).json({
          error: 'Failed to get Zendesk authorization URL',
          message: 'No authorization URL returned from backend',
        });
      }
    } else {
      res.status(500).json({
        error: 'Backend Zendesk service error',
        message: 'Failed to contact Zendesk authentication service',
      });
    }
  } catch (error) {
    console.error('Zendesk OAuth start error:', error);
    return res.status(500).json({
      error: 'Failed to start Zendesk OAuth flow',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}