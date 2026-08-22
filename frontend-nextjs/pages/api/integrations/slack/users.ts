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
    // Get user_id from query params, body, or default
    const userId = req.query.user_id || req.body?.user_id || 'current';

    const response = await fetch(`${backendUrl}/api/slack/users/${userId}`, {
      method: 'GET',
      headers: { ...fwdAuth,
        'Content-Type': 'application/json',
        'x-user-id': 'current',
      },
    });

    const data = await response.json();

    return res.status(response.status).json(data);
  } catch (error) {
    console.error('Slack users API error:', error);
    return res.status(500).json({
      error: 'Failed to fetch Slack users',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}