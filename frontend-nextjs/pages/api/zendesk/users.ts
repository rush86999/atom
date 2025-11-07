import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  try {
    const response = await fetch(`${backendUrl}/api/zendesk/users`, {
      method: req.method,
      headers: {
        'Content-Type': 'application/json',
      },
      body: req.method !== 'GET' ? JSON.stringify(req.body) : undefined,
    });

    const data = await response.json();

    return res.status(response.status).json(data);
  } catch (error) {
    console.error('Zendesk users API error:', error);
    return res.status(500).json({
      error: 'Failed to fetch Zendesk users',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}