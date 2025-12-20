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
  const backendToken = (session as any).backendToken;
  if (!backendToken) {
    return res.status(401).json({ error: 'Missing authentication token' });
  }

  try {
    const { code, state, error, verifier } = req.body;

    // Handle OAuth errors
    if (error) {
      console.error('Zoom OAuth error:', error);
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

    // Validate PKCE verifier for Zoom OAuth
    if (!verifier) {
      return res.status(400).json({
        error: 'Missing PKCE verifier',
        message: 'PKCE verifier is required for Zoom OAuth'
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

    const response = await fetch(`${backendUrl}/api/integrations/zoom/oauth/callback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Email': session.user.email,
        'X-User-ID': session.user.id || 'unknown',
        'Authorization': `Bearer ${backendToken}`,
      },
      body: JSON.stringify({
        code,
        state,
        verifier,
        user_email: session.user.email,
        user_id: session.user.id,
      }),
    });

    if (response.ok) {
      const data = await response.json();

      // Redirect to success page
      res.redirect(302, '/integrations/zoom?success=true&connected=true');
    } else {
      const errorData = await response.json();
      return res.status(400).json({
        error: 'Failed to complete Zoom OAuth',
        message: errorData.message || 'Unknown OAuth error',
        details: errorData
      });
    }

  } catch (error) {
    console.error('Zoom OAuth callback error:', error);
    return res.status(500).json({
      error: 'Internal server error',
      message: 'Failed to complete Zoom OAuth flow'
    });
  }
}
