import { Request, Response } from 'express';
import { google } from 'googleapis';
import crypto from 'crypto';
// Adjust the path based on the final location of gmail-integration relative to google-api-auth
import { getGmailUserTokens } from '../google-api-auth/_libs/api-helper';
import { googleGmailRedirectUrl } from '../google-api-auth/_libs/constants';
// Assuming a utility for admin client, adjust path as necessary
import { createAdminGraphQLClient } from '../_utils/dbService';

// Encryption Configuration - GMAIL_TOKEN_ENCRYPTION_KEY must be set in environment
const ENCRYPTION_KEY_HEX = process.env.GMAIL_TOKEN_ENCRYPTION_KEY; // Must be 64 hex characters for AES-256 (32 bytes)
const ALGORITHM = 'aes-256-gcm';
const IV_LENGTH = 16; // For AES, this is typically 16 bytes for GCM
const AUTH_TAG_LENGTH = 16; // GCM auth tag is typically 16 bytes

function encrypt(text: string): string {
  if (!ENCRYPTION_KEY_HEX) {
    console.error(
      'GMAIL_TOKEN_ENCRYPTION_KEY is not set. Cannot encrypt token.'
    );
    throw new Error('Server configuration error: Encryption key not set.');
  }
  const key = Buffer.from(ENCRYPTION_KEY_HEX, 'hex');
  if (key.length !== 32) {
    console.error(
      `GMAIL_TOKEN_ENCRYPTION_KEY must be 32 bytes (64 hex characters), current length: ${key.length} bytes.`
    );
    throw new Error(
      'Server configuration error: Invalid encryption key length.'
    );
  }
  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipheriv(ALGORITHM, key, iv);
  let encrypted = cipher.update(text, 'utf8', 'hex');
  encrypted += cipher.final('hex');
  const authTag = cipher.getAuthTag(); // Returns a Buffer
  // Prepend IV and authTag to the encrypted text. Store them as hex.
  return iv.toString('hex') + ':' + authTag.toString('hex') + ':' + encrypted;
}

// Decryption function (for later use when retrieving tokens)
export function decrypt(text: string): string {
  if (!ENCRYPTION_KEY_HEX) {
    console.error(
      'GMAIL_TOKEN_ENCRYPTION_KEY is not set. Cannot decrypt token.'
    );
    throw new Error(
      'Server configuration error: Encryption key not set for decryption.'
    );
  }
  const key = Buffer.from(ENCRYPTION_KEY_HEX, 'hex');
  if (key.length !== 32) {
    console.error(
      `GMAIL_TOKEN_ENCRYPTION_KEY must be 32 bytes (64 hex characters) for decryption. Current length: ${key.length} bytes.`
    );
    throw new Error(
      'Server configuration error: Invalid encryption key length for decryption.'
    );
  }
  const parts = text.split(':');
  if (parts.length !== 3) {
    console.error(
      'Invalid encrypted text format. Expected iv:authTag:encryptedText'
    );
    throw new Error('Decryption error: Invalid encrypted text format.');
  }
  const iv = Buffer.from(parts[0], 'hex');
  const authTag = Buffer.from(parts[1], 'hex');
  const encryptedText = parts[2];

  const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
  decipher.setAuthTag(authTag); // Critical: Must set authTag before updating
  let decrypted = decipher.update(encryptedText, 'hex', 'utf8');
  decrypted += decipher.final('utf8');
  return decrypted;
}

interface HandleGmailAuthCallbackRequestBody {
  session_variables: {
    'x-hasura-user-id': string;
  };
  input: {
    code: string;
    // state?: string; // Optional: if you use state parameter for CSRF protection
  };
}

// Note: The on_conflict constraint `user_gmail_tokens_user_id_key` implies user_id should be unique.
// Add this to your up.sql migration:
// ALTER TABLE public.user_gmail_tokens ADD CONSTRAINT user_gmail_tokens_user_id_key UNIQUE (user_id);
const UPSERT_GMAIL_TOKEN_MUTATION = `
mutation UpsertUserGmailToken($userId: uuid!, $accessToken: String!, $refreshToken: String, $expiryTimestamp: timestamptz, $scopesArr: jsonb) {
  insert_user_gmail_tokens_one(
    object: {
      user_id: $userId,
      encrypted_access_token: $accessToken,
      encrypted_refresh_token: $refreshToken,
      token_expiry_timestamp: $expiryTimestamp,
      scopes: $scopesArr # Ensure your GQL variable matches the column name 'scopes'
    },
    on_conflict: {
      constraint: user_gmail_tokens_user_id_key,
      update_columns: [encrypted_access_token, encrypted_refresh_token, token_expiry_timestamp, scopes, updated_at]
    }
  ) {
    id
    user_id
  }
}
`;

const handler = async (
  req: Request<{}, {}, HandleGmailAuthCallbackRequestBody>,
  res: Response
) => {
  const { code } = req.body.input;
  const userId = req.body.session_variables['x-hasura-user-id'];

  if (!code) {
    return res
      .status(400)
      .json({ success: false, message: 'Authorization code is missing.' });
  }
  if (!userId) {
    return res
      .status(400)
      .json({ success: false, message: 'User ID is missing from session.' });
  }
  if (!ENCRYPTION_KEY_HEX) {
    console.error(
      'GMAIL_TOKEN_ENCRYPTION_KEY is not set. Please configure a 64-character hex key (32 bytes).'
    );
    return res
      .status(500)
      .json({
        success: false,
        message: 'Server configuration error: Encryption key not configured.',
      });
  }
  try {
    Buffer.from(ENCRYPTION_KEY_HEX, 'hex'); // Validate hex format early
  } catch (e) {
    console.error('GMAIL_TOKEN_ENCRYPTION_KEY is not a valid hex string.');
    return res
      .status(500)
      .json({
        success: false,
        message: 'Server configuration error: Invalid encryption key format.',
      });
  }
  if (Buffer.from(ENCRYPTION_KEY_HEX, 'hex').length !== 32) {
    console.error(
      'GMAIL_TOKEN_ENCRYPTION_KEY must be 32 bytes (64 hex characters).'
    );
    return res
      .status(500)
      .json({
        success: false,
        message: 'Server configuration error: Invalid encryption key length.',
      });
  }

  const adminGraphQLClient = createAdminGraphQLClient();

  try {
    const redirectUri = googleGmailRedirectUrl;
    if (!redirectUri) {
      console.error(
        'GOOGLE_GMAIL_REDIRECT_URL environment variable is not configured.'
      );
      return res
        .status(500)
        .json({
          success: false,
          message:
            'Server configuration error: Missing redirect URL for Gmail integration.',
        });
    }

    const tokens: google.auth.Credentials = await getGmailUserTokens(
      code,
      redirectUri
    );

    if (!tokens.access_token) {
      console.error('Failed to obtain access token from Google.');
      return res
        .status(500)
        .json({
          success: false,
          message: 'Failed to obtain access token from Google.',
        });
    }

    const encryptedAccessToken = encrypt(tokens.access_token);
    let encryptedRefreshToken: string | null = null;
    if (tokens.refresh_token) {
      encryptedRefreshToken = encrypt(tokens.refresh_token);
    }

    const expiryTimestamp = tokens.expiry_date
      ? new Date(tokens.expiry_date).toISOString()
      : null;
    // Scopes from Google are space-separated string. Convert to JSON array for storage.
    const scopesArray = tokens.scope ? tokens.scope.split(' ') : [];

    await adminGraphQLClient.request(UPSERT_GMAIL_TOKEN_MUTATION, {
      userId: userId,
      accessToken: encryptedAccessToken,
      refreshToken: encryptedRefreshToken,
      expiryTimestamp: expiryTimestamp,
      scopesArr: scopesArray, // Pass as JSON array
    });

    return res
      .status(200)
      .json({
        success: true,
        message: 'Gmail account connected successfully.',
      });
  } catch (e: any) {
    console.error('Error handling Gmail auth callback:', e);
    let clientMessage =
      'Failed to connect Gmail account due to an unexpected error.';
    if (e.message) {
      if (
        e.message.includes('bad_verification_code') ||
        e.message.includes('invalid_grant')
      ) {
        clientMessage =
          'Invalid or expired authorization code. Please try connecting your Gmail account again.';
      } else if (e.message.includes('redirect_uri_mismatch')) {
        clientMessage = 'Redirect URI mismatch. Please contact support.';
      } else if (e.message.toLowerCase().includes('encryption')) {
        clientMessage =
          'A security configuration error occurred. Please contact support.';
      }
    }

    return res.status(500).json({
      success: false,
      message: clientMessage,
    });
  }
};

export default handler;
