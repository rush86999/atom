import { NextApiRequest, NextApiResponse } from 'next';
import OAuthClient from 'intuit-oauth';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  const oauthClient = new OAuthClient({
    clientId: process.env.QUICKBOOKS_CLIENT_ID,
    clientSecret: process.env.QUICKBOOKS_CLIENT_SECRET,
    environment: 'sandbox', // or 'production'
    redirectUri: process.env.QUICKBOOKS_REDIRECT_URI,
  });

  const authUri = oauthClient.authorizeUri({
    scope: [OAuthClient.scopes.Accounting],
    state: 'some-random-state', // Should be a random, unguessable string
  });

  res.redirect(authUri);
}
