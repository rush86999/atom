// MCP Categories API Route
// This route acts as a proxy to the backend MCP categories endpoint

import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Get backend API URL from environment
    const backendUrl = process.env.BACKEND_API_URL || 'http://localhost:8000';

    // Forward request to backend
    const response = await fetch(`${backendUrl}/api/mcp/categories${req.url?.includes('?') ? '?' + new URLSearchParams(req.query as any).toString() : ''}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    const data = await response.json();

    // Forward the response
    return res.status(response.status).json(data);
  } catch (error) {
    console.error('MCP Categories API error:', error);
    return res.status(500).json({
      error: 'Internal server error',
      message: 'Failed to fetch MCP categories'
    });
  }
}