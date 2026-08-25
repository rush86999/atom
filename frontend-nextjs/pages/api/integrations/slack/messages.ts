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
    const { channelId, limit = 10, ...rest } = req.body;
    const userId = rest.user_id || 'current';

    const response = await fetch(
      `${backendUrl}/api/slack/conversations/history?channel=${channelId}&limit=${limit}&user_id=${userId}`,
      {
        method: 'GET',
        headers: { ...fwdAuth,
          'Content-Type': 'application/json',
          'x-user-id': 'current',
        },
      }
    );

    const data = await response.json();

    return res.status(response.status).json(data);
  } catch (error) {
    console.error('Slack messages API error:', error);
    return res.status(500).json({
      error: 'Failed to fetch Slack messages',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}