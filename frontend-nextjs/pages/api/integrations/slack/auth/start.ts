import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5059';

  try {
    // Start OAuth flow
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5059';
    const response = await fetch(`${backendUrl}/api/slack/auth/url`);

    if (response.ok) {
      const data = await response.json();
      // Redirect to Slack authorization URL
      if (data.url) {
        res.redirect(data.url);
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