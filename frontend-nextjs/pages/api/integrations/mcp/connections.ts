// MCP Connections API Route
// This route acts as a proxy to the backend MCP connections endpoint

import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
    // Get backend API URL from environment
    const backendUrl = process.env.BACKEND_API_URL || 'http://localhost:8000';

    let url = `${backendUrl}/api/mcp/connections`;

    if (req.query.server_id) {
      url += `/${req.query.server_id}`;

      if (req.query.tool_name && req.query.tool_name !== 'execute') {
        url += `/tools/${req.query.tool_name}`;
      }

      if (req.query.tool_name === 'execute') {
        url += `/tools/${req.query.server_id}/execute`;
      }
    }

    if (req.url?.includes('?')) {
      const queryString = req.url.split('?')[1];
      url += `?${queryString}`;
    }

    // Forward request to backend
    const response = await fetch(url, {
      method: req.method,
      headers: {
        'Content-Type': 'application/json',
      },
      body: req.method !== 'GET' ? JSON.stringify(req.body) : undefined,
    });

    const data = await response.json();

    // Forward the response
    return res.status(response.status).json(data);
  } catch (error) {
    console.error('MCP Connections API error:', error);
    return res.status(500).json({
      error: 'Internal server error',
      message: 'Failed to process MCP connection request'
    });
  }
}