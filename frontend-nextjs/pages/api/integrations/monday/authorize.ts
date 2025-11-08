import type { NextApiRequest, NextApiResponse } from 'next';
import axios from 'axios';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { state } = req.query;

    // Monday.com OAuth 2.0 configuration
    const clientId = process.env.MONDAY_CLIENT_ID;
    const redirectUri = process.env.MONDAY_REDIRECT_URI || `${process.env.NEXTAUTH_URL}/api/integrations/monday/callback`;
    const scope = 'boards:read boards:write workspaces:read users:read';

    if (!clientId) {
      return res.status(500).json({
        error: 'Monday.com client ID not configured',
        details: 'Please set MONDAY_CLIENT_ID environment variable'
      });
    }

    // Construct authorization URL
    const authUrl = new URL('https://auth.monday.com/oauth2/authorize');
    authUrl.searchParams.append('client_id', clientId);
    authUrl.searchParams.append('redirect_uri', redirectUri);
    authUrl.searchParams.append('response_type', 'code');
    authUrl.searchParams.append('scope', scope);
    authUrl.searchParams.append('state', state as string || 'default');

    // Return authorization URL to frontend
    res.status(200).json({
      authorization_url: authUrl.toString(),
      state: state || 'default'
    });

  } catch (error) {
    console.error('Monday.com authorization error:', error);
    res.status(500).json({
      error: 'Failed to generate authorization URL',
      details: error instanceof Error ? error.message : 'Unknown error'
    });
  }
}
