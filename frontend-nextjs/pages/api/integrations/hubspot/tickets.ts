import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  try {
    const response = await fetch(`${backendUrl}/api/hubspot/tickets`, {
      method: 'POST',
      headers: {
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
    console.error('HubSpot tickets API error:', error);
    return res.status(500).json({
      error: 'Failed to fetch HubSpot tickets',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}