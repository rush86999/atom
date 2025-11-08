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
      console.error('Bitbucket OAuth error:', oauthError);
      return res.redirect(`/integrations/bitbucket?error=${encodeURIComponent(oauthError as string)}`);
    }

    if (!code) {
      return res.redirect('/integrations/bitbucket?error=missing_authorization_code');
    }

    // Bitbucket OAuth 2.0 token exchange
    const clientId = process.env.BITBUCKET_CLIENT_ID;
    const clientSecret = process.env.BITBUCKET_CLIENT_SECRET;
    const redirectUri = process.env.BITBUCKET_REDIRECT_URI || `${process.env.NEXTAUTH_URL}/api/integrations/bitbucket/callback`;

    if (!clientId || !clientSecret) {
      console.error('Bitbucket credentials not configured');
      return res.redirect('/integrations/bitbucket?error=missing_credentials');
    }

    // Exchange authorization code for access token
    const tokenResponse = await axios.post('https://bitbucket.org/site/oauth2/access_token',
      new URLSearchParams({
        grant_type: 'authorization_code',
        code: code as string,
        redirect_uri: redirectUri
      }), {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Authorization': `Basic ${Buffer.from(`${clientId}:${clientSecret}`).toString('base64')}`
        }
      }
    );

    const tokenData = tokenResponse.data;

    // Store tokens securely (in production, use database)
    // For now, we'll redirect with tokens in URL (not recommended for production)
    const successUrl = new URL('/integrations/bitbucket', process.env.NEXTAUTH_URL || 'http://localhost:3000');
    successUrl.searchParams.set('success', 'true');
    successUrl.searchParams.set('access_token', tokenData.access_token);
    successUrl.searchParams.set('refresh_token', tokenData.refresh_token);
    successUrl.searchParams.set('expires_in', tokenData.expires_in);
    successUrl.searchParams.set('token_type', tokenData.token_type);
    successUrl.searchParams.set('scope', tokenData.scope);

    // Redirect to success page
    return res.redirect(successUrl.toString());

  } catch (error) {
    console.error('Bitbucket OAuth callback error:', error);

    let errorMessage = 'authentication_failed';
    if (axios.isAxiosError(error) && error.response) {
      errorMessage = error.response.data?.error || 'api_error';
    }

    return res.redirect(`/integrations/bitbucket?error=${encodeURIComponent(errorMessage)}`);
  }
}
