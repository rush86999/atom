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
    const limit = req.query.limit || req.body?.limit || 100;
    const offset = req.query.offset || req.body?.offset || 0;
    const userId = req.query.user_id || req.body?.user_id || 'current';

    const response = await fetch(
      `${backendUrl}/api/hubspot/companies?limit=${limit}&offset=${offset}&user_id=${userId}`,
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
    console.error('HubSpot companies API error:', error);
    return res.status(500).json({
      error: 'Failed to fetch HubSpot companies',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}