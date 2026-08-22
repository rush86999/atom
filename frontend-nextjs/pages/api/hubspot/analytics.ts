import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

  try {
    const response = await fetch(`${backendUrl}/api/hubspot/analytics`, {
      method: req.method,
      headers: {
        'Content-Type': 'application/json',
      },
      body: req.method !== 'GET' ? JSON.stringify(req.body) : undefined,
    });

    const data = await response.json();

    return res.status(response.status).json(data);
  } catch (error) {
    console.error('HubSpot analytics API error:', error);
    return res.status(500).json({
      error: 'Failed to fetch HubSpot analytics',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}