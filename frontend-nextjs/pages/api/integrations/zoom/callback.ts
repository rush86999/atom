import { NextApiRequest, NextApiResponse } from "next";
import { getToken } from "next-auth/jwt";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  // Only allow POST requests
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

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

    const { code, state, error } = req.body;

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

    if (!state) {
      return res.status(400).json({
        error: 'Missing state parameter',
        message: 'State parameter is required for CSRF protection'
      });
    }

    // Validate state parameter for CSRF protection
    const storedState = req.cookies[`zoom_oauth_state_${token.email}`];
    if (!storedState || storedState !== state) {
      console.error('CSRF attack detected: State mismatch for Zoom OAuth', {
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
    res.clearCookie(`zoom_oauth_state_${token.email}`);

    // Prepare token exchange request
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';
    const redirectUri = `${process.env.NEXTAUTH_URL}/api/integrations/zoom/callback`;

    const tokenData = {
      code,
      redirect_uri: redirectUri,
      state,
      use_pkce: true
    };

    // Exchange authorization code for access token
    const response = await fetch(`${backendUrl}/api/zoom/exchange-code`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Email': token.email,
        'X-User-ID': token.sub || token.id || 'unknown',
      },
      body: JSON.stringify(tokenData),
    });

    if (response.ok) {
      const result = await response.json();

      // Redirect to Zoom integration page with success message
      const successUrl = `/integrations/zoom?success=true&connected=true&timestamp=${Date.now()}`;
      return res.redirect(302, successUrl);
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