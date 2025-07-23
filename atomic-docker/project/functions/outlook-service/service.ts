import { Client } from '@microsoft/microsoft-graph-client';
import { ConfidentialClientApplication, OnBehalfOfRequest } from '@azure/msal-node';
import { getMsalConfig } from './auth_utils';
import { createAdminGraphQLClient } from '../_utils/dbService';
import { decrypt, encrypt } from '../outlook-integration/crypto_utils';

const GET_OUTLOOK_TOKENS_QUERY = `
query GetUserOutlookTokens($userId: uuid!) {
  user_outlook_tokens(where: {user_id: {_eq: $userId}}, limit: 1) {
    encrypted_access_token
    encrypted_refresh_token
    token_expiry_timestamp
  }
}
`;

const UPDATE_OUTLOOK_ACCESS_TOKEN_MUTATION = `
mutation UpdateUserOutlookAccessTokenAfterRefresh($userId: uuid!, $newEncryptedAccessToken: String!, $newExpiryTimestamp: timestamptz!) {
  update_user_outlook_tokens(
    where: {user_id: {_eq: $userId}},
    _set: {
      encrypted_access_token: $newEncryptedAccessToken,
      token_expiry_timestamp: $newExpiryTimestamp,
      updated_at: "now()"
    }
  ) {
    affected_rows
  }
}
`;

export async function getAuthenticatedClient(userId: string): Promise<Client> {
  const adminGraphQLClient = createAdminGraphQLClient();

  const gqlResponse = await adminGraphQLClient.request(GET_OUTLOOK_TOKENS_QUERY, { userId });
  const storedTokenRecord = gqlResponse.user_outlook_tokens && gqlResponse.user_outlook_tokens[0];

  if (!storedTokenRecord) {
    throw new Error('Outlook tokens not found for user.');
  }

  let { encrypted_access_token, encrypted_refresh_token, token_expiry_timestamp } = storedTokenRecord;

  const expiryDate = token_expiry_timestamp ? new Date(token_expiry_timestamp).getTime() : 0;
  const needsRefresh = Date.now() >= expiryDate - (5 * 60 * 1000);

  let accessToken = '';

  if (needsRefresh) {
    const decryptedRefreshToken = decrypt(encrypted_refresh_token);
    const msalConfig = getMsalConfig();
    const cca = new ConfidentialClientApplication(msalConfig);
    const refreshTokenRequest = {
      refreshToken: decryptedRefreshToken,
      scopes: ['https://graph.microsoft.com/.default'],
    };
    const response = await cca.acquireTokenByRefreshToken(refreshTokenRequest);
    accessToken = response.accessToken;
    const newEncryptedAccessToken = encrypt(accessToken);
    const newExpiry = response.expiresOn.toISOString();

    await adminGraphQLClient.request(UPDATE_OUTLOOK_ACCESS_TOKEN_MUTATION, {
      userId,
      newEncryptedAccessToken: newEncryptedAccessToken,
      newExpiryTimestamp: newExpiry,
    });
  } else {
    accessToken = decrypt(encrypted_access_token);
  }

  const client = Client.init({
    authProvider: (done) => {
      done(null, accessToken);
    },
  });

  return client;
}

export async function searchUserOutlookEmails(userId: string, query: string, maxResults: number = 10) {
  const client: Client = await getAuthenticatedClient(userId);
  const searchResults = await client.api('/me/messages')
    .search(query)
    .top(maxResults)
    .get();
  return searchResults.value;
}

export async function getUserOutlookEmailContent(userId: string, emailId: string) {
  const client: Client = await getAuthenticatedClient(userId);
  const email = await client.api(`/me/messages/${emailId}`).get();
  return email;
}
