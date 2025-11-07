import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { query, limit, include_body, labels, date_range } = req.body;

    if (!query) {
      return res.status(400).json({ error: 'Search query is required' });
    }

    // Forward request to backend LanceDB memory service
    const response = await fetch('http://localhost:5000/api/integrations/gmail/memory/search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        limit: limit || 10,
        include_body: include_body || false,
        labels: labels || [],
        date_range: date_range || null,
      }),
    });

    if (response.ok) {
      const data = await response.json();
      return res.status(200).json({
        success: true,
        data: data.data || [],
        message: data.message || 'Search completed successfully',
      });
    } else {
      const errorData = await response.text();
      console.error('Gmail memory search error:', errorData);
      return res.status(response.status).json({
        error: 'Failed to search Gmail memory',
        details: errorData,
      });
    }
  } catch (error) {
    console.error('Gmail memory search error:', error);
    return res.status(500).json({
      error: 'Internal server error',
      details: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}
