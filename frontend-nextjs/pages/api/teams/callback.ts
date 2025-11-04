import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { code, state } = req.body;

    if (!code) {
      return res.status(400).json({ error: 'Authorization code is required' });
    }

    if (!state) {
      return res.status(400).json({ error: 'State parameter is required' });
    }

    // Forward the request to the backend Teams OAuth callback endpoint
    const backendResponse = await fetch(
      `http://localhost:5059/api/auth/teams/callback?code=${code}&state=${state}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    if (!backendResponse.ok) {
      const errorText = await backendResponse.text();
      console.error('Backend Teams callback error:', errorText);
      return res.status(backendResponse.status).json({
        error: 'Failed to process Teams OAuth callback',
        details: errorText
      });
    }

    // For GET endpoints that redirect, we need to handle the response differently
    const contentType = backendResponse.headers.get('content-type');

    if (contentType && contentType.includes('application/json')) {
      const data = await backendResponse.json();
      return res.status(200).json({
        success: true,
        ...data
      });
    } else {
      // Handle redirect or other response types
      const responseText = await backendResponse.text();

      // Check if this is a success redirect
      if (backendResponse.status >= 300 && backendResponse.status < 400) {
        const location = backendResponse.headers.get('location');
        return res.status(200).json({
          success: true,
          redirect_url: location,
          message: 'Teams connected successfully'
        });
      }

      return res.status(200).json({
        success: true,
        message: 'Teams OAuth callback processed successfully'
      });
    }

  } catch (error) {
    console.error('Teams OAuth callback error:', error);
    return res.status(500).json({
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error occurred'
    });
  }
}
