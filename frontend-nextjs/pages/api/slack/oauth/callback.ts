import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../../auth/[...nextauth]";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  // Only handle POST requests for OAuth callback
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const session = await getServerSession(req, res, authOptions);

  if (!session || !session.user?.email) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  try {
    const { code, state, error } = req.body;

    // Handle OAuth errors
    if (error) {
      console.error('Slack OAuth error:', error);
      return res.status(400).json({
        error: 'OAuth authorization failed',
        message: error
      });
    }

    // Validate required parameters
    if (!code) {
      return res.status(400).json({
        error: 'Missing authorization code',
        message: 'Authorization code is required'
      });
    }

    // Validate state parameter for CSRF protection
    if (!state) {
      return res.status(400).json({
        error: 'Missing state parameter',
        message: 'State parameter is required for CSRF protection'
      });
    }

    // Exchange authorization code for access token
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

    const response = await fetch(`${backendUrl}/api/integrations/slack/oauth/callback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Email': session.user.email,
        'X-User-ID': session.user.id || 'unknown',
      },
      body: JSON.stringify({
        code,
        state,
        user_email: session.user.email,
        user_id: session.user.id,
      }),
    });

    if (response.ok) {
      const data = await response.json();

      // Redirect to success page or return success response
      res.redirect(302, '/integrations/slack?success=true&connected=true');
    } else {
      const errorData = await response.json();
      return res.status(400).json({
        error: 'Failed to complete Slack OAuth',
        message: errorData.message || 'Unknown OAuth error',
        details: errorData
      });
    }

  } catch (error) {
    console.error('Slack OAuth callback error:', error);
    return res.status(500).json({
      error: 'Internal server error',
      message: 'Failed to complete Slack OAuth flow'
    });
  }
}
