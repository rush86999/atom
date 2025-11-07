import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Check if Gmail integration is available
    const response = await fetch('http://localhost:5000/api/integrations/gmail/health', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (response.ok) {
      const data = await response.json();
      return res.status(200).json({
        connected: true,
        service: 'gmail',
        status: 'healthy',
        data: data.data || {},
        timestamp: new Date().toISOString(),
      });
    } else {
      return res.status(200).json({
        connected: false,
        service: 'gmail',
        status: 'disconnected',
        error: 'Gmail service not available',
        timestamp: new Date().toISOString(),
      });
    }
  } catch (error) {
    console.error('Gmail status check error:', error);
    return res.status(200).json({
      connected: false,
      service: 'gmail',
      status: 'error',
      error: 'Failed to check Gmail status',
      timestamp: new Date().toISOString(),
    });
  }
}
