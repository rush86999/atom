import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';
  const { id, ...queryParams } = req.query;

  try {
    let url = `${backendUrl}/api/slack/channels`;
    
    // Add query parameters
    const queryString = new URLSearchParams(queryParams as Record<string, string>).toString();
    if (queryString) {
      url += `?${queryString}`;
    }

    const response = await fetch(url, {
      method: req.method,
      headers: {
        'Content-Type': 'application/json',
        'x-user-id': 'current',
      },
      body: req.method !== 'GET' ? JSON.stringify(req.body) : undefined,
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