import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  try {
    const userId = req.query.user_id || req.body?.user_id || 'current';
    const response = await fetch(`${backendUrl}/api/slack/channels?user_id=${userId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'x-user-id': 'current',
      },
    });

    const data = await response.json();

    return res.status(response.status).json(data);
  } catch (error) {
    console.error('Slack channels API error:', error);
    return res.status(500).json({
      error: 'Failed to fetch Slack channels',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}