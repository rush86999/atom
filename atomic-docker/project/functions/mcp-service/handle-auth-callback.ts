import { Request, Response } from 'express';
import { google } from 'googleapis';
import crypto from 'crypto';
// Adjust the path based on the final location of mcp-service relative to google-api-auth
import { getMcpUserTokens } from '../google-api-auth/_libs/api-helper';
import { googleMcpRedirectUrl } from '../google-api-auth/_libs/constants';
// Assuming a utility for admin client, adjust path as necessary
import { createAdminGraphQLClient } from '../_utils/dbService';
import { encrypt, decrypt } from '../_utils/crypto';

const ENCRYPTION_KEY_HEX = process.env.MCP_TOKEN_ENCRYPTION_KEY;

interface HandleMcpAuthCallbackRequestBody {
  session_variables: {
    'x-hasura-user-id': string;
  };
  input: {
    code: string;
    // state?: string; // Optional: if you use state parameter for CSRF protection
  };
}

// Note: The on_conflict constraint `user_mcp_tokens_user_id_key` implies user_id should be unique.
// Add this to your up.sql migration:
// ALTER TABLE public.user_mcp_tokens ADD CONSTRAINT user_mcp_tokens_user_id_key UNIQUE (user_id);
const UPSERT_MCP_TOKEN_MUTATION = `
mutation UpsertUserMcpToken($userId: uuid!, $accessToken: String!, $refreshToken: String, $expiryTimestamp: timestamptz, $scopesArr: jsonb) {
  insert_user_mcp_tokens_one(
    object: {
      user_id: $userId,
      encrypted_access_token: $accessToken,
      encrypted_refresh_token: $refreshToken,
      token_expiry_timestamp: $expiryTimestamp,
      scopes: $scopesArr # Ensure your GQL variable matches the column name 'scopes'
    },
    on_conflict: {
      constraint: user_mcp_tokens_user_id_key,
      update_columns: [encrypted_access_token, encrypted_refresh_token, token_expiry_timestamp, scopes, updated_at]
    }
  ) {
    id
    user_id
  }
}
`;

const handler = async (req: Request<{}, {}, HandleMcpAuthCallbackRequestBody>, res: Response) => {
  const { code } = req.body.input;
  const userId = req.body.session_variables['x-hasura-user-id'];

  if (!code) {
    return res.status(400).json({ success: false, message: 'Authorization code is missing.' });
  }
  if (!userId) {
    return res.status(400).json({ success: false, message: 'User ID is missing from session.' });
  }
  if (!ENCRYPTION_KEY_HEX) {
    console.error('MCP_TOKEN_ENCRYPTION_KEY is not set. Please configure a 64-character hex key (32 bytes).');
    return res.status(500).json({ success: false, message: 'Server configuration error: Encryption key not configured.' });
  }
  try {
    Buffer.from(ENCRYPTION_KEY_HEX, 'hex'); // Validate hex format early
  } catch (e) {
    console.error('MCP_TOKEN_ENCRYPTION_KEY is not a valid hex string.');
    return res.status(500).json({ success: false, message: 'Server configuration error: Invalid encryption key format.'});
  }
   if (Buffer.from(ENCRYPTION_KEY_HEX, 'hex').length !== 32) {
    console.error('MCP_TOKEN_ENCRYPTION_KEY must be 32 bytes (64 hex characters).');
    return res.status(500).json({ success: false, message: 'Server configuration error: Invalid encryption key length.' });
  }

  const adminGraphQLClient = createAdminGraphQLClient();

  try {
    const redirectUri = googleMcpRedirectUrl;
    if (!redirectUri) {
      console.error('GOOGLE_MCP_REDIRECT_URL environment variable is not configured.');
      return res.status(500).json({ success: false, message: 'Server configuration error: Missing redirect URL for Mcp integration.' });
    }

    const tokens: google.auth.Credentials = await getMcpUserTokens(code, redirectUri);

    if (!tokens.access_token) {
      console.error('Failed to obtain access token from Google.');
      return res.status(500).json({ success: false, message: 'Failed to obtain access token from Google.' });
    }

    const encryptedAccessToken = encrypt(tokens.access_token, ENCRYPTION_KEY_HEX);
    let encryptedRefreshToken: string | null = null;
    if (tokens.refresh_token) {
      encryptedRefreshToken = encrypt(tokens.refresh_token, ENCRYPTION_KEY_HEX);
    }

    const expiryTimestamp = tokens.expiry_date ? new Date(tokens.expiry_date).toISOString() : null;
    // Scopes from Google are space-separated string. Convert to JSON array for storage.
    const scopesArray = tokens.scope ? tokens.scope.split(' ') : [];

    await adminGraphQLClient.request(UPSERT_MCP_TOKEN_MUTATION, {
      userId: userId,
      accessToken: encryptedAccessToken,
      refreshToken: encryptedRefreshToken,
      expiryTimestamp: expiryTimestamp,
      scopesArr: scopesArray, // Pass as JSON array
    });

    return res.status(200).json({ success: true, message: 'Mcp account connected successfully.' });

  } catch (e: any) {
    console.error('Error handling Mcp auth callback:', e);
    let clientMessage = 'Failed to connect Mcp account due to an unexpected error.';
    if (e.message) {
        if (e.message.includes('bad_verification_code') || e.message.includes('invalid_grant')) {
            clientMessage = 'Invalid or expired authorization code. Please try connecting your Mcp account again.';
        } else if (e.message.includes('redirect_uri_mismatch')) {
            clientMessage = 'Redirect URI mismatch. Please contact support.';
        } else if (e.message.toLowerCase().includes('encryption')) {
            clientMessage = 'A security configuration error occurred. Please contact support.';
        }
    }

    return res.status(500).json({
      success: false,
      message: clientMessage,
    });
  }
};

export default handler;
