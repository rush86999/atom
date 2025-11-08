import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  try {
    // Exchange authorization code for tokens
    const response = await fetch(`${backendUrl}/api/auth/azure/callback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        code: req.query.code,
        state: req.query.state,
        user_id: 'current',
      }),
    });

    if (response.ok) {
      const data = await response.json();
      
      // Redirect to Azure integration page with success message
      res.redirect('/integrations/azure?success=true');
    } else {
      const errorData = await response.json();
      return res.status(400).json({
        error: 'Failed to complete Azure OAuth',
        message: errorData.message || 'Unknown OAuth error',
      });
    }
  } catch (error) {
    console.error('Azure OAuth callback error:', error);
    return res.status(500).json({
      error: 'Failed to complete Azure OAuth flow',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}