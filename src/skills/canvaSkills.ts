import { createAdminGraphQLClient } from '../../atomic-docker/project/functions/_utils/dbService';
import { decrypt } from '../../atomic-docker/project/functions/_utils/crypto';
import { AuthorizationCode } from 'simple-oauth2';
import axios from 'axios';

const GET_CANVA_TOKENS_QUERY = `
query GetCanvaTokens($userId: uuid!) {
  user_canva_tokens(where: {user_id: {_eq: $userId}}) {
    encrypted_access_token
    encrypted_refresh_token
    token_expiry_timestamp
  }
}
`;

const UPSERT_CANVA_TOKEN_MUTATION = `
mutation UpsertUserCanvaToken($userId: uuid!, $accessToken: String!, $refreshToken: String, $expiryTimestamp: timestamptz, $scopesArr: jsonb) {
  insert_user_canva_tokens_one(
    object: {
      user_id: $userId,
      encrypted_access_token: $accessToken,
      encrypted_refresh_token: $refreshToken,
      token_expiry_timestamp: $expiryTimestamp,
      scopes: $scopesArr
    },
    on_conflict: {
      constraint: user_canva_tokens_user_id_key,
      update_columns: [encrypted_access_token, encrypted_refresh_token, token_expiry_timestamp, scopes, updated_at]
    }
  ) {
    id
  }
}
`;

async function getCanvaTokens(userId: string) {
  const adminGraphQLClient = createAdminGraphQLClient();
  const result = await adminGraphQLClient.request(GET_CANVA_TOKENS_QUERY, {
    userId,
  });

  if (result.user_canva_tokens.length === 0) {
    return null;
  }

  const tokens = result.user_canva_tokens[0];
  const encryptionKey = process.env.CANVA_TOKEN_ENCRYPTION_KEY;

  if (!encryptionKey) {
    throw new Error('CANVA_TOKEN_ENCRYPTION_KEY is not set');
  }

  const accessToken = decrypt(tokens.encrypted_access_token, encryptionKey);
  const refreshToken = tokens.encrypted_refresh_token
    ? decrypt(tokens.encrypted_refresh_token, encryptionKey)
    : null;

  return {
    accessToken,
    refreshToken,
    expiresAt: tokens.token_expiry_timestamp,
  };
}

async function refreshAccessToken(userId: string, refreshToken: string) {
  const canvaClientId = process.env.CANVA_CLIENT_ID;
  const canvaClientSecret = process.env.CANVA_CLIENT_SECRET;

  if (!canvaClientId || !canvaClientSecret) {
    throw new Error('Canva client credentials are not configured.');
  }

  const client = new AuthorizationCode({
    client: {
      id: canvaClientId,
      secret: canvaClientSecret,
    },
    auth: {
      tokenHost: 'https://api.canva.com',
      tokenPath: '/rest/v1/oauth/token',
    },
  });

  const token = client.createToken({ refresh_token: refreshToken });

  try {
    const refreshedToken = await token.refresh();
    const { token: newTokens } = refreshedToken;

    const adminGraphQLClient = createAdminGraphQLClient();
    const encryptionKey = process.env.CANVA_TOKEN_ENCRYPTION_KEY;
    if (!encryptionKey) {
      throw new Error('CANVA_TOKEN_ENCRYPTION_KEY is not set');
    }

    const encryptedAccessToken = encrypt(
      newTokens.access_token as string,
      encryptionKey
    );
    let encryptedRefreshToken: string | null = null;
    if (newTokens.refresh_token) {
      encryptedRefreshToken = encrypt(
        newTokens.refresh_token as string,
        encryptionKey
      );
    }

    const expiryTimestamp = newTokens.expires_at
      ? (newTokens.expires_at as Date).toISOString()
      : null;
    const scopesArray =
      typeof newTokens.scope === 'string'
        ? newTokens.scope.split(' ')
        : newTokens.scope || [];

    await adminGraphQLClient.request(UPSERT_CANVA_TOKEN_MUTATION, {
      userId: userId,
      accessToken: encryptedAccessToken,
      refreshToken: encryptedRefreshToken,
      expiryTimestamp: expiryTimestamp,
      scopesArr: scopesArray,
    });

    return newTokens.access_token;
  } catch (error) {
    console.error('Error refreshing Canva access token:', error);
    throw new Error('Failed to refresh Canva access token.');
  }
}

export async function createDesign(userId: string, title: string) {
  let tokens = await getCanvaTokens(userId);

  if (!tokens) {
    throw new Error('User has not connected their Canva account.');
  }

  if (new Date(tokens.expiresAt) < new Date()) {
    if (!tokens.refreshToken) {
      throw new Error(
        'Canva access token is expired and no refresh token is available.'
      );
    }
    tokens.accessToken = await refreshAccessToken(userId, tokens.refreshToken);
  }

  try {
    const response = await axios.post(
      'https://api.canva.com/rest/v1/designs',
      {
        title: title,
        design_type: {
          type: 'preset',
          name: 'presentation',
        },
      },
      {
        headers: {
          Authorization: `Bearer ${tokens.accessToken}`,
          'Content-Type': 'application/json',
        },
      }
    );
    return response.data;
  } catch (error) {
    console.error('Error creating Canva design:', error);
    throw new Error('Failed to create Canva design.');
  }
}
