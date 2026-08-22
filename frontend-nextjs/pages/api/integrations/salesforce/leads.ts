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
  const { id, ...queryParams } = req.query;

  try {
    let url = `${backendUrl}/api/salesforce/leads`;
    
    if (id && typeof id === 'string') {
      url += `/${id}`;
    }

    // Add query parameters
    const queryString = new URLSearchParams(queryParams as Record<string, string>).toString();
    if (queryString) {
      url += `?${queryString}`;
    }

    const response = await fetch(url, {
      method: req.method,
      headers: { ...fwdAuth,
        'Content-Type': 'application/json',
      },
      body: req.method !== 'GET' ? JSON.stringify(req.body) : undefined,
    });

    const data = await response.json();

    return res.status(response.status).json(data);
  } catch (error) {
    console.error('Salesforce leads API error:', error);
    return res.status(500).json({
      error: 'Failed to fetch Salesforce leads',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}