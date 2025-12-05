import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Forward request to backend LanceDB memory service
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/memory/ingestion/memory/stats`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (response.ok) {
      const data = await response.json();
      return res.status(200).json({
        success: true,
        data: data.data || {},
        message: data.message || 'Memory stats retrieved successfully',
      });
    } else {
      const errorData = await response.text();
      console.error('Gmail memory stats error:', errorData);
      return res.status(response.status).json({
        error: 'Failed to get Gmail memory stats',
        details: errorData,
      });
    }
  } catch (error) {
    console.error('Gmail memory stats error:', error);
    return res.status(500).json({
      error: 'Internal server error',
      details: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}
