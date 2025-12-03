import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { force_full_sync, max_messages, labels } = req.body;

    // Forward request to backend LanceDB memory service to start ingestion stream
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

    // Note: force_full_sync and other params are not currently supported by the stream/start endpoint
    // but we start the real-time stream which will ingest new messages
    const response = await fetch(`${backendUrl}/api/memory/ingestion/stream/start/gmail`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
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
