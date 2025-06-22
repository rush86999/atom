import { Request, Response } from 'express';
import { createAdminGraphQLClient } from '../_utils/dbService'; // Adjust path
import { google } from 'googleapis';
import { decrypt } from './handle-gmail-auth-callback'; // Assuming decrypt is exported and key is available

// GraphQL query to get the access token
const GET_USER_GMAIL_ACCESS_TOKEN_QUERY = `
query GetUserGmailAccessTokenForStatus($userId: uuid!) {
  user_gmail_tokens(where: {user_id: {_eq: $userId}}, limit: 1) {
    encrypted_access_token
    # We could also fetch refresh token here if we want to attempt a refresh on failure
  }
}
`;

interface GetGmailConnectionStatusRequestBody {
  session_variables: {
    'x-hasura-user-id': string;
  };
  // No specific input args from client for this query action
}

// Matches GmailConnectionStatusOutput in actions.graphql
interface GmailConnectionStatusResponse {
  isConnected: boolean;
  userEmail?: string | null;
  message?: string; // Optional message for errors or status
}

const handler = async (
  req: Request<{}, {}, GetGmailConnectionStatusRequestBody>,
  res: Response<GmailConnectionStatusResponse>
) => {
  const userId = req.body.session_variables['x-hasura-user-id'];

  if (!userId) {
    // This case should ideally be blocked by Hasura permissions if session_variables are required
    return res.status(401).json({ isConnected: false, userEmail: null, message: "Unauthorized: User ID missing." });
  }

  const adminGraphQLClient = createAdminGraphQLClient();

  try {
    const tokenRecordResult = await adminGraphQLClient.request(GET_USER_GMAIL_ACCESS_TOKEN_QUERY, { userId });

    if (!tokenRecordResult.user_gmail_tokens || tokenRecordResult.user_gmail_tokens.length === 0) {
      return res.status(200).json({ isConnected: false, userEmail: null });
    }

    const tokenRecord = tokenRecordResult.user_gmail_tokens[0];

    if (!tokenRecord.encrypted_access_token) {
        // This implies a record exists but the access token is missing, which is an inconsistent state.
        // Treat as not connected or needing re-authentication.
        console.warn(`[Connection Status] Token record exists for user ${userId} but no encrypted_access_token found.`);
        return res.status(200).json({ isConnected: false, userEmail: null, message: "Connection data incomplete." });
    }

    let userEmailFromGoogle: string | null = null;
    let isEffectivelyConnected = false;

    try {
        const encryptedAccessToken = tokenRecord.encrypted_access_token;
        const accessToken = decrypt(encryptedAccessToken); // Ensure GMAIL_TOKEN_ENCRYPTION_KEY is available

        if (accessToken) {
            const oauth2Client = new google.auth.OAuth2();
            oauth2Client.setCredentials({ access_token: accessToken });
            const oauth2 = google.oauth2({ version: 'v2', auth: oauth2Client });
            const userInfo = await oauth2.userinfo.get(); // Fetches email, profile, openid scopes by default

            userEmailFromGoogle = userInfo.data.email || null;
            isEffectivelyConnected = !!userEmailFromGoogle; // If we get email, token is valid

            if (!isEffectivelyConnected) {
                 console.warn(`[Connection Status] Could not retrieve user email via Google API for user ${userId}, though token was decrypted. Token might be invalid or lack scopes.`);
            }
        } else {
            console.error(`[Connection Status] Failed to decrypt access token for user ${userId}. Encryption key issue or corrupt data.`);
            // Cannot verify connection without decrypted token.
        }
    } catch (googleApiError: any) {
        console.warn(`[Connection Status] Google API error while verifying token for user ${userId}. Error: ${googleApiError.message}. Token might be stale or revoked.`);
        // isEffectivelyConnected remains false. We know tokens are *stored*, but they might not be *valid*.
        // For the purpose of "isConnected", if tokens are stored, we might still say true,
        // but the frontend can use the absence of userEmail to prompt for re-check or re-auth.
        // Let's be stricter: if API call fails, say not effectively connected.
        isEffectivelyConnected = false;
        // If we had refresh token logic here, we could attempt a refresh.
        // For now, a failed API call means the current access token is not working.
    }

    if (isEffectivelyConnected) {
        return res.status(200).json({
            isConnected: true,
            userEmail: userEmailFromGoogle
        });
    } else {
        // Tokens are stored, but we couldn't verify them with Google API (e.g. stale, revoked, decryption failed)
        // The frontend might interpret this as "Connected, but needs attention" or "Attempting to reconnect..."
        // For simplicity in this boolean status, if we can't get email, let's say connection is not fully active.
        // However, if we just check for token *existence* then isConnected would be true here.
        // Let's return isConnected based on token existence, but userEmail indicates validity.
         return res.status(200).json({
            isConnected: true, // Record exists
            userEmail: userEmailFromGoogle, // null if API call failed
            message: userEmailFromGoogle ? undefined : "Stored token might be invalid or expired."
        });
    }

  } catch (e: any) {
    console.error(`[Connection Status] Outer error for user ${userId}:`, e);
    return res.status(500).json({ isConnected: false, userEmail: null, message: "Error checking connection status." });
  }
};

export default handler;
