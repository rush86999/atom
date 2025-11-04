import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { user_id } = req.query;

    if (!user_id) {
      return res.status(400).json({ error: 'user_id parameter is required' });
    }

    // Forward the request to the backend Teams OAuth endpoint
    const backendResponse = await fetch(
      `http://localhost:5059/api/auth/teams/authorize?user_id=${user_id}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json();
      return res.status(backendResponse.status).json({ error: errorData.error || 'Failed to start Teams OAuth' });
    }

    const data = await backendResponse.json();

    return res.status(200).json({
      success: true,
      auth_url: data.auth_url,
      user_id: data.user_id,
      csrf_token: data.csrf_token,
    });

  } catch (error) {
    console.error('Teams OAuth start error:', error);
    return res.status(500).json({
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error occurred'
    });
  }
}
