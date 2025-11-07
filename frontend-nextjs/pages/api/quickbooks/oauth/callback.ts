import { NextApiRequest, NextApiResponse } from "next";
import { getSession } from "supertokens-node/nextjs";
import { SessionContainer } from "supertokens-node/recipe/session";
import { OAuthClient } from 'intuit-oauth';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  let session: SessionContainer;
  try {
    session = await getSession(req, res, {
      overrideGlobalClaimValidators: () => [],
    });
  } catch (err) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  const userId = session.getUserId();
  const oauthClient = new OAuthClient({
      clientId: process.env.QUICKBOOKS_CLIENT_ID!,
      clientSecret: process.env.QUICKBOOKS_CLIENT_SECRET!,
      environment: process.env.QUICKBOOKS_ENVIRONMENT || 'sandbox',
      redirectUri: process.env.QUICKBOOKS_REDIRECT_URI!,
  });

  try {
    const authResponse = await oauthClient.createToken(req.url);
    const token = authResponse.getJson();

    const accessToken = token.access_token;
    const refreshToken = token.refresh_token;
    const expiresAt = new Date(
      Date.now() + token.expires_in * 1000,
    ).toISOString();
    const realmId = token.realmId;

    // Save tokens to backend
    const backendResponse = await fetch(`${process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058'}/api/quickbooks/auth/store-tokens`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: userId,
        access_token: accessToken,
        refresh_token: refreshToken,
        expires_at: expiresAt,
        realm_id: realmId,
      }),
    });

    if (!backendResponse.ok) {
      throw new Error('Failed to store tokens in backend');
    }

    // Redirect to QuickBooks integration page
    res.redirect('/integrations/quickbooks?success=true');
  } catch (error) {
    console.error("Error during QuickBooks OAuth callback:", error);
    return res
      .status(500)
      .json({ message: "Failed to complete QuickBooks OAuth flow" });
  }
}
