import type { NextApiRequest, NextApiResponse } from 'next';
import axios from 'axios';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { code, state, error: oauthError } = req.query;

    // Handle OAuth errors
    if (oauthError) {
      console.error('Monday.com OAuth error:', oauthError);
      return res.redirect(`/integrations/monday?error=${encodeURIComponent(oauthError as string)}`);
    }

    if (!code) {
      return res.redirect('/integrations/monday?error=missing_authorization_code');
    }

    // Monday.com OAuth 2.0 token exchange
    const clientId = process.env.MONDAY_CLIENT_ID;
    const clientSecret = process.env.MONDAY_CLIENT_SECRET;
    const redirectUri = process.env.MONDAY_REDIRECT_URI || `${process.env.NEXTAUTH_URL}/api/integrations/monday/callback`;

    if (!clientId || !clientSecret) {
      console.error('Monday.com credentials not configured');
      return res.redirect('/integrations/monday?error=missing_credentials');
    }

    // Exchange authorization code for access token
    const tokenResponse = await axios.post('https://auth.monday.com/oauth2/token', {
      client_id: clientId,
      client_secret: clientSecret,
      code: code,
      redirect_uri: redirectUri,
      grant_type: 'authorization_code'
    }, {
      headers: {
        'Content-Type': 'application/json'
      }
    });

    const tokenData = tokenResponse.data;

    // Store tokens securely (in production, use database)
    // For now, we'll redirect with tokens in URL (not recommended for production)
    const successUrl = new URL('/integrations/monday', process.env.NEXTAUTH_URL || 'http://localhost:3000');
    successUrl.searchParams.set('success', 'true');
    successUrl.searchParams.set('access_token', tokenData.access_token);
    successUrl.searchParams.set('refresh_token', tokenData.refresh_token);
    successUrl.searchParams.set('expires_in', tokenData.expires_in);
    successUrl.searchParams.set('token_type', tokenData.token_type);

    // Redirect to success page
    return res.redirect(successUrl.toString());

  } catch (error) {
    console.error('Monday.com OAuth callback error:', error);

    let errorMessage = 'authentication_failed';
    if (axios.isAxiosError(error) && error.response) {
      errorMessage = error.response.data?.error || 'api_error';
    }

    return res.redirect(`/integrations/monday?error=${encodeURIComponent(errorMessage)}`);
  }
}
