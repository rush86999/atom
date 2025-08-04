import { Request, Response } from 'express';
// Adjust the path based on the final location of gmail-integration relative to google-api-auth
import { refreshGmailAccessToken } from '../google-api-auth/_libs/api-helper';
// Adjust path as necessary for db client and encryption utils
import { createAdminGraphQLClient } from '../_utils/dbService';
import { decrypt, encrypt } from './handle-gmail-auth-callback'; // Reuse encryption from callback

// GraphQL query to get the refresh token
const GET_GMAIL_REFRESH_TOKEN_QUERY = `
query GetUserGmailRefreshToken($userId: uuid!) {
  user_gmail_tokens(where: {user_id: {_eq: $userId}, encrypted_refresh_token: {_is_null: false}}, limit: 1) {
    encrypted_refresh_token
  }
}
`;

// GraphQL mutation to update the access token and expiry
const UPDATE_GMAIL_ACCESS_TOKEN_MUTATION = `
mutation UpdateUserGmailAccessToken($userId: uuid!, $newAccessToken: String!, $newExpiryTimestamp: timestamptz!) {
  update_user_gmail_tokens(
    where: {user_id: {_eq: $userId}},
    _set: {
      encrypted_access_token: $newAccessToken,
      token_expiry_timestamp: $newExpiryTimestamp,
      updated_at: "now()"
    }
  ) {
    affected_rows
    returning {
      id
      token_expiry_timestamp
    }
  }
}
`;

interface RefreshGmailTokenRequestBody {
  session_variables: {
    'x-hasura-user-id': string;
  };
  input: {
    // No specific input needed from client, userId from session is used
  };
}

const handler = async (
  req: Request<{}, {}, RefreshGmailTokenRequestBody>,
  res: Response
) => {
  const userId = req.body.session_variables['x-hasura-user-id'];

  if (!userId) {
    return res
      .status(400)
      .json({ success: false, message: 'User ID is missing from session.' });
  }

  const adminGraphQLClient = createAdminGraphQLClient();

  try {
    // 1. Fetch the encrypted refresh token
    const queryResult = await adminGraphQLClient.request(
      GET_GMAIL_REFRESH_TOKEN_QUERY,
      { userId }
    );
    const storedTokens = queryResult.user_gmail_tokens;

    if (
      !storedTokens ||
      storedTokens.length === 0 ||
      !storedTokens[0].encrypted_refresh_token
    ) {
      return res
        .status(404)
        .json({
          success: false,
          message:
            'No Gmail refresh token found for this user, or integration is incomplete. Please connect/reconnect Gmail.',
        });
    }

    const encryptedRefreshToken = storedTokens[0].encrypted_refresh_token;
    let decryptedRefreshToken;
    try {
      decryptedRefreshToken = decrypt(encryptedRefreshToken);
    } catch (decryptionError: any) {
      console.error(
        `Failed to decrypt refresh token for user ${userId}:`,
        decryptionError.message
      );
      // It's possible the key changed or data is corrupt. User should re-auth.
      return res
        .status(500)
        .json({
          success: false,
          message:
            'Failed to process stored token. Please try reconnecting your Gmail account.',
        });
    }

    if (!decryptedRefreshToken) {
      // This case should ideally be caught by the try-catch above, but as a safeguard.
      return res
        .status(500)
        .json({
          success: false,
          message: 'Decryption of refresh token failed unexpectedly.',
        });
    }

    // 2. Use the refresh token to get a new access token
    const refreshedTokensFromGoogle = await refreshGmailAccessToken(
      decryptedRefreshToken
    );

    if (
      !refreshedTokensFromGoogle.access_token ||
      !refreshedTokensFromGoogle.expires_in
    ) {
      console.error(
        `Failed to refresh Gmail access token from Google for user ${userId}. Response:`,
        refreshedTokensFromGoogle
      );
      // Log the error from Google if available
      // const googleError = (refreshedTokensFromGoogle as any).error_description || (refreshedTokensFromGoogle as any).error || 'Unknown Google error';
      return res
        .status(500)
        .json({
          success: false,
          message: `Could not refresh Gmail access token from Google.`,
        });
    }

    // 3. Encrypt the new access token
    const newEncryptedAccessToken = encrypt(
      refreshedTokensFromGoogle.access_token
    );

    // 4. Calculate new expiry timestamp
    const newExpiryTimestamp = new Date(
      Date.now() + refreshedTokensFromGoogle.expires_in * 1000
    ).toISOString();

    // 5. Update the database
    const updateResult = await adminGraphQLClient.request(
      UPDATE_GMAIL_ACCESS_TOKEN_MUTATION,
      {
        userId: userId,
        newAccessToken: newEncryptedAccessToken,
        newExpiryTimestamp: newExpiryTimestamp,
      }
    );

    if (updateResult.update_user_gmail_tokens.affected_rows === 0) {
      console.warn(
        `Gmail token refresh: No rows updated in DB for user ${userId}. User may have disconnected integration, or an issue occurred.`
      );
      // This might not be a hard error if the user disconnected just before this write.
    }

    return res.status(200).json({
      success: true,
      message: 'Gmail access token refreshed successfully.',
      expires_in: refreshedTokensFromGoogle.expires_in,
    });
  } catch (e: any) {
    console.error(`Error refreshing Gmail token for user ${userId}:`, e);
    // Check if it's a Google error related to the refresh token itself (e.g., revoked)
    // The 'got' library throws HTTPError for non-2xx responses. e.response.body might contain the error.
    let responseBody: any = {};
    if (e.response && e.response.body) {
      try {
        responseBody = JSON.parse(e.response.body);
      } catch (parseError) {
        // Not JSON, or some other issue
      }
    }

    if (responseBody.error === 'invalid_grant') {
      // The refresh token is invalid or revoked. User needs to re-authenticate.
      // Consider actions like deleting the stored tokens or marking them as invalid in DB.
      return res
        .status(401)
        .json({
          success: false,
          message:
            'Gmail refresh token is invalid or revoked by Google. Please reconnect your Gmail account.',
        });
    }
    return res.status(500).json({
      success: false,
      message:
        'An error occurred while refreshing Gmail token: ' +
        (e.message || 'Unknown error'),
    });
  }
};

export default handler;
