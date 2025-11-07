import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { code, state, error: oauthError } = req.query;

    // Handle OAuth errors
    if (oauthError) {
      console.error('Gmail OAuth error:', oauthError);
      return res.redirect('/integrations/gmail?error=auth_failed');
    }

    if (!code) {
      return res.redirect('/integrations/gmail?error=missing_code');
    }

    // Exchange authorization code for access token
    const tokenResponse = await fetch('http://localhost:5000/api/auth/gmail/callback', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        code,
        state,
        redirect_uri: 'http://localhost:3000/oauth/gmail/callback',
      }),
    });

    if (tokenResponse.ok) {
      const tokenData = await tokenResponse.json();

      // Store tokens securely (in session or database)
      // For now, we'll redirect with success

      return res.redirect('/integrations/gmail?success=true');
    } else {
      console.error('Gmail token exchange failed:', await tokenResponse.text());
      return res.redirect('/integrations/gmail?error=token_exchange_failed');
    }
  } catch (error) {
    console.error('Gmail callback error:', error);
    return res.redirect('/integrations/gmail?error=callback_failed');
  }
}
