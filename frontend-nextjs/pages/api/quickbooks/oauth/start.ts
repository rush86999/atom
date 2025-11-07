import { NextApiRequest, NextApiResponse } from "next";
import { OAuthClient } from 'intuit-oauth';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  const oauthClient = new OAuthClient({
    clientId: process.env.QUICKBOOKS_CLIENT_ID,
    clientSecret: process.env.QUICKBOOKS_CLIENT_SECRET,
    environment: process.env.QUICKBOOKS_ENVIRONMENT || "sandbox",
    redirectUri: process.env.QUICKBOOKS_REDIRECT_URI,
  });

  const authUri = oauthClient.authorizeUri({
    scope: [OAuthClient.scopes.Accounting],
    state: Math.random().toString(36).substring(7), // Generate random state
  });

  res.redirect(authUri);
}
