import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';
  const { id, ...queryParams } = req.query;

  try {
    let url = `${backendUrl}/api/salesforce/opportunities`;
    
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
      headers: {
        'Content-Type': 'application/json',
      },
      body: req.method !== 'GET' ? JSON.stringify(req.body) : undefined,
    });

    const data = await response.json();

    return res.status(response.status).json(data);
  } catch (error) {
    console.error('Salesforce opportunities API error:', error);
    return res.status(500).json({
      error: 'Failed to fetch Salesforce opportunities',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}