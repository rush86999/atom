import { NextApiRequest, NextApiResponse } from 'next';
import { getSession } from 'supertokens-node/nextjs';
import { SessionContainer } from 'supertokens-node/recipe/session';
import { executeGraphQLQuery } from '../../../../../project/functions/_libs/graphqlClient';
import OAuthClient from 'intuit-oauth';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  let session: SessionContainer;
  try {
    session = await getSession(req, res, {
      overrideGlobalClaimValidators: () => [],
    });
  } catch (err) {
    return res.status(401).json({ message: 'Unauthorized' });
  }

  const userId = session.getUserId();
  const oauthClient = new OAuthClient({
    clientId: process.env.QUICKBOOKS_CLIENT_ID,
    clientSecret: process.env.QUICKBOOKS_CLIENT_SECRET,
    environment: 'sandbox', // or 'production'
    redirectUri: process.env.QUICKBOOKS_REDIRECT_URI,
  });

  try {
    const authResponse = await oauthClient.createToken(req.url);
    const token = authResponse.getJson();

    const accessToken = token.access_token;
    const refreshToken = token.refresh_token;
    const expiresAt = new Date(
      Date.now() + token.expires_in * 1000
    ).toISOString();
    const realmId = token.realmId;

    // Save the tokens to the user_tokens table
    const mutation = `
            mutation InsertUserToken($userId: String!, $service: String!, $accessToken: String!, $refreshToken: String, $expiresAt: timestamptz!, $meta: jsonb) {
                insert_user_tokens_one(object: {user_id: $userId, service: $service, access_token: $accessToken, refresh_token: $refreshToken, expires_at: $expiresAt, meta: $meta}) {
                    id
                }
            }
        `;
    const variables = {
      userId,
      service: 'quickbooks',
      accessToken,
      refreshToken,
      expiresAt,
      meta: { realmId },
    };
    await executeGraphQLQuery(mutation, variables, 'InsertUserToken', userId);

    return res.redirect('/Settings/UserViewSettings');
  } catch (error) {
    console.error('Error during QuickBooks OAuth callback:', error);
    return res
      .status(500)
      .json({ message: 'Failed to complete QuickBooks OAuth flow' });
  }
}
