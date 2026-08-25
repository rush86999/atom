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
    const response = await fetch(`${backendUrl}/api/hubspot/deals`, {
      method: 'POST',
      headers: { ...fwdAuth,
        'Content-Type': 'application/json',
        'x-user-id': 'current',
      },
      body: JSON.stringify({
        ...req.body,
        user_id: 'current',
      }),
    });

    const data = await response.json();

    return res.status(response.status).json(data);
  } catch (error) {
    console.error('HubSpot deals API error:', error);
    return res.status(500).json({
      error: 'Failed to fetch HubSpot deals',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}