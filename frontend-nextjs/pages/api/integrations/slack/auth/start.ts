import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  try {
    // Start OAuth flow
    const response = await fetch(`${backendUrl}/api/slack/oauth/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: 'current',
        redirect_uri: `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/integrations/slack/auth/callback`,
      }),
    });

    if (response.ok) {
      const data = await response.json();
      // Redirect to Slack authorization URL
      if (data.authorization_url) {
        res.redirect(data.authorization_url);
      } else {
        res.status(500).json({
          error: 'Failed to get Slack authorization URL',
          message: 'No authorization URL returned from backend',
        });
      }
    } else {
      res.status(500).json({
        error: 'Backend Slack service error',
        message: 'Failed to contact Slack authentication service',
      });
    }
  } catch (error) {
    console.error('Slack OAuth start error:', error);
    return res.status(500).json({
      error: 'Failed to start Slack OAuth flow',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}