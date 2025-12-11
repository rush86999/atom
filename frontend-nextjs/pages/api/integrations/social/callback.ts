import { NextApiRequest, NextApiResponse } from "next";
import { getToken } from "next-auth/jwt";

interface SocialPlatformConfig {
  name: string;
  tokenEndpoint: string;
  userInfoEndpoint: string;
  scopes: string[];
  additionalParams?: Record<string, string>;
}

const PLATFORMS_CONFIGS: Record<string, SocialPlatformConfig> = {
  twitter: {
    name: 'Twitter',
    tokenEndpoint: 'https://api.twitter.com/2/oauth2/token',
    userInfoEndpoint: 'https://api.twitter.com/2/users/me',
    scopes: ['tweet.read', 'tweet.write', 'users.read'],
    additionalParams: { 'response_type': 'code' }
  },
  instagram: {
    name: 'Instagram',
    tokenEndpoint: 'https://graph.instagram.com/oauth/access_token',
    userInfoEndpoint: 'https://graph.instagram.com/me',
    scopes: ['user_profile', 'user_media'],
  },
  facebook: {
    name: 'Facebook',
    tokenEndpoint: 'https://graph.facebook.com/v18.0/oauth/access_token',
    userInfoEndpoint: 'https://graph.facebook.com/me',
    scopes: ['email', 'pages_show_list', 'pages_read_engagement'],
  },
  linkedin: {
    name: 'LinkedIn',
    tokenEndpoint: 'https://www.linkedin.com/oauth/v2/accessToken',
    userInfoEndpoint: 'https://api.linkedin.com/v2/people/~:(id,firstName,lastName,emailAddress)',
    scopes: ['r_liteprofile', 'r_emailaddress', 'w_member_social'],
  }
};

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const session = await getToken({
    req,
    secret: process.env.NEXTAUTH_SECRET,
    secureCookie: process.env.NODE_ENV === "production"
  });

  if (!session || !session.email) {
    return res.status(401).json({
      error: 'Unauthorized',
      message: 'You must be logged in to complete OAuth flow'
    });
  }

  try {
    const { code, state, platform, error, verifier } = req.body;

    // Handle OAuth errors
    if (error) {
      console.error(`${platform} OAuth error:`, error);
      return res.status(400).json({
        error: 'OAuth authorization failed',
        platform,
        message: error
      });
    }

    // Validate required parameters
    if (!code) {
      return res.status(400).json({
        error: 'Missing authorization code',
        platform,
        message: 'Authorization code is required'
      });
    }

    if (!platform) {
      return res.status(400).json({
        error: 'Missing platform parameter',
        message: 'Platform is required'
      });
    }

    // Validate platform
    if (!PLATFORMS_CONFIGS[platform]) {
      return res.status(400).json({
        error: 'Unsupported platform',
        platform,
        message: `Supported platforms: ${Object.keys(PLATFORMS_CONFIGS).join(', ')}`
      });
    }

    // Validate state parameter for CSRF protection
    if (!state) {
      return res.status(400).json({
        error: 'Missing state parameter',
        platform,
        message: 'State parameter is required for CSRF protection'
      });
    }

    // Validate state against session
    const storedState = req.cookies[`oauth_state_${session.email}_${platform}`];
    if (!storedState || storedState !== state) {
      console.error(`CSRF attack detected: State mismatch for ${platform}`, {
        expected: storedState,
        received: state,
        user: session.email
      });
      return res.status(400).json({
        error: 'Invalid state parameter',
        platform,
        message: 'CSRF protection: State validation failed'
      });
    }

    // Clear the stored state after successful validation
    res.clearCookie(`oauth_state_${session.email}_${platform}`);

    // Get platform configuration
    const platformConfig = PLATFORMS_CONFIGS[platform];

    // Prepare token exchange request
    const tokenData = {
      code,
      grant_type: 'authorization_code',
      redirect_uri: `${process.env.NEXTAUTH_URL}/api/integrations/social/callback`,
      client_id: process.env[`${platform.toUpperCase()}_CLIENT_ID`],
      client_secret: process.env[`${platform.toUpperCase()}_CLIENT_SECRET`],
      ...(platformConfig.additionalParams || {}),
    };

    // Add PKCE verifier if provided (for LinkedIn)
    if (verifier) {
      tokenData.code_verifier = verifier;
    }

    // Exchange authorization code for access token
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

    // First, get access token from platform
    const tokenResponse = await fetch(platformConfig.tokenEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams(tokenData).toString(),
    });

    if (!tokenResponse.ok) {
      const errorData = await tokenResponse.text();
      console.error(`Token exchange failed for ${platform}:`, errorData);
      return res.status(400).json({
        error: 'Token exchange failed',
        platform,
        message: 'Failed to exchange authorization code for access token'
      });
    }

    const tokenResult = await tokenResponse.json();
    const accessToken = tokenResult.access_token;

    // Get user info from platform
    const userInfoResponse = await fetch(`${platformConfig.userInfoEndpoint}?access_token=${accessToken}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
    });

    let userInfo = null;
    if (userInfoResponse.ok) {
      userInfo = await userInfoResponse.json();
    }

    // Store tokens and user info in backend
    const storageResponse = await fetch(`${backendUrl}/api/integrations/social/store`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Email': session.email,
        'X-User-ID': session.sub || session.id || 'unknown',
      },
      body: JSON.stringify({
        platform,
        access_token: tokenResult.access_token,
        refresh_token: tokenResult.refresh_token || null,
        expires_in: tokenResult.expires_in || null,
        scope: tokenResult.scope || platformConfig.scopes.join(' '),
        user_info: userInfo,
        user_email: session.email,
        user_id: session.sub || session.id,
        timestamp: new Date().toISOString(),
      }),
    });

    if (storageResponse.ok) {
      const storageResult = await storageResponse.json();

      // Redirect to success page with enhanced feedback
      const successUrl = `/integrations/${platform}?success=true&connected=true&user_id=${encodeURIComponent(userInfo?.id || 'unknown')}`;
      return res.redirect(302, successUrl);
    } else {
      const errorData = await storageResponse.json();
      return res.status(400).json({
        error: 'Failed to store integration',
        platform,
        message: errorData.message || 'Unknown storage error',
        details: errorData
      });
    }

  } catch (error) {
    console.error(`${req.body?.platform || 'unknown'} OAuth callback error:`, error);
    return res.status(500).json({
      error: 'Internal server error',
      platform: req.body?.platform,
      message: 'Failed to complete OAuth flow'
    });
  }
}