import { Request, Response } from 'express';
import { AuthorizationCode } from 'simple-oauth2';
import { createAdminGraphQLClient } from '../_utils/dbService';
import { encrypt } from '../_utils/crypto';

const ENCRYPTION_KEY_HEX = process.env.CANVA_TOKEN_ENCRYPTION_KEY;

// NOTE: A new table 'user_canva_tokens' is required.
// Migration should be created with the following columns:
// id (uuid, primary key), user_id (uuid, foreign key to users.id),
// encrypted_access_token (text), encrypted_refresh_token (text),
// token_expiry_timestamp (timestamptz), scopes (jsonb),
// created_at (timestamptz, default now()), updated_at (timestamptz, default now())
// Also, add a unique constraint on user_id:
// ALTER TABLE public.user_canva_tokens ADD CONSTRAINT user_canva_tokens_user_id_key UNIQUE (user_id);
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
    user_id
  }
}
`;

interface HandleCanvaAuthCallbackRequestBody {
  session_variables: {
    'x-hasura-user-id': string;
  };
  input: {
    code: string;
  };
}

const handler = async (req: Request<{}, {}, HandleCanvaAuthCallbackRequestBody>, res: Response) => {
  const { code } = req.body.input;
  const userId = req.body.session_variables['x-hasura-user-id'];

  if (!code) {
    return res.status(400).json({ success: false, message: 'Authorization code is missing.' });
  }
  if (!userId) {
    return res.status(400).json({ success: false, message: 'User ID is missing from session.' });
  }
  if (!ENCRYPTION_KEY_HEX) {
    console.error('CANVA_TOKEN_ENCRYPTION_KEY is not set. Please configure a 64-character hex key (32 bytes).');
    return res.status(500).json({ success: false, message: 'Server configuration error: Encryption key not configured.' });
  }

  const adminGraphQLClient = createAdminGraphQLClient();
  const canvaClientId = process.env.CANVA_CLIENT_ID;
  const canvaClientSecret = process.env.CANVA_CLIENT_SECRET;
  const canvaRedirectUrl = process.env.CANVA_REDIRECT_URL;

  if (!canvaClientId || !canvaClientSecret || !canvaRedirectUrl) {
    console.error('Canva environment variables are not configured.');
    return res.status(500).json({ message: 'Server configuration error: Missing Canva integration credentials.' });
  }

  const client = new AuthorizationCode({
    client: {
      id: canvaClientId,
      secret: canvaClientSecret,
    },
    auth: {
      tokenHost: 'https://api.canva.com',
      tokenPath: '/rest/v1/oauth/token',
      authorizeHost: 'https://www.canva.com',
      authorizePath: '/api/oauth/authorize',
    },
  });

  try {
    const tokenParams = {
      code: code,
      redirect_uri: canvaRedirectUrl,
    };
    const accessToken = await client.getToken(tokenParams);
    const { token } = accessToken;

    if (!token.access_token) {
      console.error('Failed to obtain access token from Canva.');
      return res.status(500).json({ success: false, message: 'Failed to obtain access token from Canva.' });
    }

    const encryptedAccessToken = encrypt(token.access_token as string, ENCRYPTION_KEY_HEX);
    let encryptedRefreshToken: string | null = null;
    if (token.refresh_token) {
      encryptedRefreshToken = encrypt(token.refresh_token as string, ENCRYPTION_KEY_HEX);
    }

    const expiryTimestamp = token.expires_at ? (token.expires_at as Date).toISOString() : null;
    const scopesArray = typeof token.scope === 'string' ? token.scope.split(' ') : token.scope || [];

    await adminGraphQLClient.request(UPSERT_CANVA_TOKEN_MUTATION, {
      userId: userId,
      accessToken: encryptedAccessToken,
      refreshToken: encryptedRefreshToken,
      expiryTimestamp: expiryTimestamp,
      scopesArr: scopesArray,
    });

    return res.status(200).json({ success: true, message: 'Canva account connected successfully.' });

  } catch (e: any) {
    console.error('Error handling Canva auth callback:', e);
    return res.status(500).json({
      success: false,
      message: 'Failed to connect Canva account due to an unexpected error.',
    });
  }
};

export default handler;
