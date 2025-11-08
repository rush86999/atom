import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { access_token } = req.query;

    if (!access_token) {
      return res.status(400).json({
        error: 'Access token required',
        details: 'Please provide Bitbucket access token'
      });
    }

    // Forward health check to backend
    const backendResponse = await fetch('http://localhost:8000/api/bitbucket/health', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${access_token}`,
        'Content-Type': 'application/json'
      }
    });

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json();
      return res.status(backendResponse.status).json({
        error: 'Bitbucket health check failed',
        details: errorData.detail || 'Unknown error'
      });
    }

    const healthData = await backendResponse.json();

    return res.status(200).json(healthData);

  } catch (error) {
    console.error('Bitbucket health check error:', error);

    return res.status(500).json({
      error: 'Bitbucket service unavailable',
      details: error instanceof Error ? error.message : 'Unknown error',
      timestamp: new Date().toISOString()
    });
  }
}
