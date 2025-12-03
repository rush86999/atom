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
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

    const tokenResponse = await fetch(`${backendUrl}/api/auth/google/callback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        code,
        state,
        // redirect_uri is handled by backend env var, but passing it doesn't hurt
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
