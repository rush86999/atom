import { Request, Response } from 'express';
import { PublicClientApplication, ConfidentialClientApplication } from '@azure/msal-node';
import { getMsalConfig } from '../outlook-service/auth_utils';
import { createAdminGraphQLClient } from '../_utils/dbService';
import { encrypt } from './crypto_utils'; // Assuming a similar crypto utility exists

const UPSERT_OUTLOOK_TOKENS_MUTATION = `
mutation UpsertUserOutlookTokens($userId: uuid!, $encryptedAccessToken: String!, $encryptedRefreshToken: String!, $tokenExpiryTimestamp: timestamptz!) {
  insert_user_outlook_tokens(
    objects: {
      user_id: $userId,
      encrypted_access_token: $encryptedAccessToken,
      encrypted_refresh_token: $encryptedRefreshToken,
      token_expiry_timestamp: $tokenExpiryTimestamp
    },
    on_conflict: {
      constraint: user_outlook_tokens_pkey,
      update_columns: [encrypted_access_token, encrypted_refresh_token, token_expiry_timestamp, updated_at]
    }
  ) {
    affected_rows
  }
}
`;

const handler = async (req: Request, res: Response) => {
  const { code, state } = req.query;
  const userId = state as string;

  if (!code) {
    return res.status(400).send('Authorization code is missing.');
  }
  if (!userId) {
    return res.status(400).send('State (User ID) is missing.');
  }

  const msalConfig = getMsalConfig();
  const pca = new ConfidentialClientApplication(msalConfig);

  const tokenRequest = {
    code: code as string,
    scopes: ['https://graph.microsoft.com/.default'],
    redirectUri: 'http://localhost:3000/outlook-callback',
  };

  try {
    const response = await pca.acquireTokenByCode(tokenRequest);
    const { accessToken, refreshToken, expiresOn } = response;

    const encryptedAccessToken = encrypt(accessToken);
    const encryptedRefreshToken = encrypt(refreshToken);
    const tokenExpiryTimestamp = expiresOn.toISOString();

    const adminGraphQLClient = createAdminGraphQLClient();
    await adminGraphQLClient.request(UPSERT_OUTLOOK_TOKENS_MUTATION, {
      userId,
      encryptedAccessToken,
      encryptedRefreshToken,
      tokenExpiryTimestamp,
    });

    return res.status(200).send('Outlook account connected successfully!');
  } catch (error) {
    console.error('Error handling Outlook auth callback:', error);
    return res.status(500).send('Error connecting Outlook account.');
  }
};

export default handler;
