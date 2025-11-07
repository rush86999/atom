import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { force_full_sync, max_messages, labels } = req.body;

    // Forward request to backend LanceDB memory service
    const response = await fetch('http://localhost:5000/api/integrations/gmail/memory/sync', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        force_full_sync: force_full_sync || false,
        max_messages: max_messages || 1000,
        labels: labels || [],
      }),
    });

    if (response.ok) {
      const data = await response.json();
      return res.status(200).json({
        success: true,
        data: data.data || {},
        message: data.message || 'Memory sync completed successfully',
      });
    } else {
      const errorData = await response.text();
      console.error('Gmail memory sync error:', errorData);
      return res.status(response.status).json({
        error: 'Failed to sync Gmail memory',
        details: errorData,
      });
    }
  } catch (error) {
    console.error('Gmail memory sync error:', error);
    return res.status(500).json({
      error: 'Internal server error',
      details: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}
