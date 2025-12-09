import { NextApiRequest, NextApiResponse } from "next";
import { getToken } from "next-auth/jwt";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  try {
    // Verify user is authenticated
    const token = await getToken({
      req,
      secret: process.env.NEXTAUTH_SECRET,
      secureCookie: process.env.NODE_ENV === "production"
    });

    if (!token || !token.email) {
      return res.status(401).json({
        error: 'Unauthorized',
        message: 'You must be logged in to complete OAuth flow'
      });
    }

    // Validate required OAuth parameters
    const { code, state, error } = req.query;

    if (error) {
      console.error('OAuth error from Slack:', error);
      return res.status(400).json({
        error: 'OAuth authorization failed',
        message: error as string
      });
    }

    if (!code) {
      return res.status(400).json({
        error: 'Missing authorization code',
        message: 'Authorization code is required'
      });
    }

    // CSRF Protection: Validate state parameter
    if (!state || typeof state !== 'string') {
      return res.status(400).json({
        error: 'Invalid state parameter',
        message: 'CSRF protection: State parameter is missing or invalid'
      });
    }

    // Retrieve stored state from session/cookie for validation
    // In a real implementation, you would store this in the user's session
    const storedState = req.cookies[`oauth_state_${token.email}`] || req.headers['x-oauth-state'];

    if (!storedState || storedState !== state) {
      console.error('CSRF attack detected: State mismatch', {
        expected: storedState,
        received: state,
        user: token.email
      });
      return res.status(400).json({
        error: 'Invalid state parameter',
        message: 'CSRF protection: State validation failed'
      });
    }

    // Clear the stored state after successful validation
    res.clearCookie(`oauth_state_${token.email}`);

    // Exchange authorization code for tokens
    const response = await fetch(`${backendUrl}/api/slack/callback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Email': token.email,
        'X-User-ID': token.sub || token.id || 'unknown',
      },
      body: JSON.stringify({
        code,
        state, // State now validated
        user_id: token.sub || token.id,
        email: token.email,
      }),
    });

    if (response.ok) {
      const data = await response.json();

      // Redirect to Slack integration page with success message
      res.redirect('/integrations/slack?success=true');
    } else {
      const errorData = await response.json();
      return res.status(400).json({
        error: 'Failed to complete Slack OAuth',
        message: errorData.message || 'Unknown OAuth error',
      });
    }
  } catch (error) {
    console.error('Slack OAuth callback error:', error);
    return res.status(500).json({
      error: 'Failed to complete Slack OAuth flow',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}