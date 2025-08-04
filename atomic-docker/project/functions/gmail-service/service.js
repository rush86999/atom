import { google } from 'googleapis';
// Adjust paths as necessary
import { createAdminGraphQLClient } from '../_utils/dbService';
import { decrypt, encrypt, } from '../gmail-integration/handle-gmail-auth-callback';
import { refreshGmailAccessToken } from '../google-api-auth/_libs/api-helper';
import { googleClientIdGmail, googleClientSecretGmail, } from '../google-api-auth/_libs/constants';
const GET_GMAIL_TOKENS_QUERY = `
query GetUserGmailTokens($userId: uuid!) {
  user_gmail_tokens(where: {user_id: {_eq: $userId}}, limit: 1) {
    encrypted_access_token
    encrypted_refresh_token
    token_expiry_timestamp
  }
}
`;
const UPDATE_GMAIL_ACCESS_TOKEN_MUTATION = `
mutation UpdateUserGmailAccessTokenAfterRefresh($userId: uuid!, $newEncryptedAccessToken: String!, $newExpiryTimestamp: timestamptz!) {
  update_user_gmail_tokens(
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
/**
 * Retrieves a user's stored Gmail tokens, refreshes if necessary,
 * and returns an authenticated OAuth2 client configured for Gmail API.
 * @param userId The ID of the user.
 * @returns An authenticated google.auth.OAuth2 client or null if tokens are not found/valid.
 */
export async function getGmailClientForUser(userId) {
    const adminGraphQLClient = createAdminGraphQLClient();
    try {
        const gqlResponse = await adminGraphQLClient.request(GET_GMAIL_TOKENS_QUERY, { userId });
        const storedTokenRecord = gqlResponse.user_gmail_tokens && gqlResponse.user_gmail_tokens[0];
        if (!storedTokenRecord) {
            console.log(`No Gmail tokens found for user ${userId}. User needs to authorize.`);
            return null;
        }
        let { encrypted_access_token, encrypted_refresh_token, token_expiry_timestamp, } = storedTokenRecord;
        if (!encrypted_access_token && !encrypted_refresh_token) {
            console.log(`Neither access nor refresh token found for user ${userId}. Re-authorization needed.`);
            return null;
        }
        const oauth2Client = new google.auth.OAuth2(googleClientIdGmail, googleClientSecretGmail
        // No redirect URI needed here as we are not starting a new auth flow
        );
        let currentAccessToken = '';
        // Check if token is expired or about to expire (e.g., within next 5 minutes)
        const expiryDate = token_expiry_timestamp
            ? new Date(token_expiry_timestamp).getTime()
            : 0;
        const needsRefresh = Date.now() >= expiryDate - 5 * 60 * 1000;
        if (needsRefresh) {
            if (!encrypted_refresh_token) {
                console.error(`Token for user ${userId} needs refresh, but no refresh token is available. User must re-authorize.`);
                // Optionally, clear the invalid tokens from DB or mark them as needing re-auth
                return null;
            }
            console.log(`Gmail access token for user ${userId} requires refresh. Attempting...`);
            const decryptedRefreshToken = decrypt(encrypted_refresh_token);
            if (!decryptedRefreshToken) {
                console.error(`Failed to decrypt refresh token for user ${userId}.`);
                return null; // Cannot proceed without decrypted refresh token
            }
            const refreshedGoogleTokens = await refreshGmailAccessToken(decryptedRefreshToken);
            if (!refreshedGoogleTokens.access_token ||
                !refreshedGoogleTokens.expires_in) {
                console.error(`Failed to refresh Gmail access token from Google for user ${userId}.`);
                // This could be due to revoked refresh token. User needs to re-authorize.
                // Optionally, clear the invalid tokens from DB or mark them as needing re-auth
                return null;
            }
            currentAccessToken = refreshedGoogleTokens.access_token;
            const newEncryptedAccessToken = encrypt(currentAccessToken);
            const newExpiry = new Date(Date.now() + refreshedGoogleTokens.expires_in * 1000).toISOString();
            // Update the database with the new access token and expiry
            await adminGraphQLClient.request(UPDATE_GMAIL_ACCESS_TOKEN_MUTATION, {
                userId,
                newEncryptedAccessToken: newEncryptedAccessToken,
                newExpiryTimestamp: newExpiry,
            });
            console.log(`Gmail access token for user ${userId} refreshed and updated in DB.`);
            // If the original refresh token was also updated by Google (rare, but possible),
            // you would also update encrypted_refresh_token here.
            // For now, assuming refresh_token remains the same unless Google explicitly changes it.
        }
        else {
            if (!encrypted_access_token) {
                console.error(`Token for user ${userId} not expired, but access token is missing. This state should not occur.`);
                return null; // Should not happen if not expired and no refresh needed.
            }
            const decryptedAccessToken = decrypt(encrypted_access_token);
            if (!decryptedAccessToken) {
                console.error(`Failed to decrypt access token for user ${userId}.`);
                return null;
            }
            currentAccessToken = decryptedAccessToken;
        }
        oauth2Client.setCredentials({ access_token: currentAccessToken });
        // If Google returned a new refresh_token (rare for Google, but some providers do),
        // you'd set it here too: oauth2Client.setCredentials({ access_token: ..., refresh_token: ... });
        // And then re-encrypt and save the new refresh_token.
        return oauth2Client;
    }
    catch (error) {
        console.error(`Error in getGmailClientForUser for user ${userId}:`, error.message);
        if (error.response && error.response.body) {
            // Log Google API errors if available
            console.error('Google API error details:', error.response.body);
        }
        return null;
    }
}
/**
 * Placeholder for searching user's emails.
 * @param userId The ID of the user.
 * @param query The search query (e.g., "from:xyz@example.com subject:contract after:2023/01/01 before:2023/03/31").
 * @param maxResults Maximum number of results to return.
 * @returns A promise that resolves to an array of Gmail messages.
 */
export async function searchUserEmails(userId, query, maxResults = 10) {
    console.log(`Gmail Service: Searching emails for user ${userId} with query "${query}", max ${maxResults}`);
    const authedClient = await getGmailClientForUser(userId);
    if (!authedClient) {
        // Detailed error already logged in getGmailClientForUser if it returns null due to auth issues
        throw new Error('Failed to get authenticated Gmail client. User may need to authorize or re-authorize.');
    }
    const gmail = google.gmail({ version: 'v1', auth: authedClient });
    try {
        const response = await gmail.users.messages.list({
            userId: 'me',
            q: query,
            maxResults: maxResults,
            // consider adding fields parameter to optimize, e.g. 'messages(id,threadId,snippet)'
        });
        // messages.list returns a list of Message resources, which should include id, threadId, and often snippet.
        // If more details like subject, from, date are needed for each item in search results *without* N+1 calls,
        // the query would need to be more complex (e.g. batch requests for messages.get with format: 'metadata')
        // or a different Gmail API endpoint. For now, this is a direct mapping.
        return response.data.messages || [];
    }
    catch (error) {
        console.error(`Error searching emails for user ${userId} (query: "${query}"):`, error.message);
        if (error.code === 401) {
            // Unauthorized, often due to token issues not caught by refresh
            throw new Error('Gmail authentication failed (token might be revoked or insufficient permissions). Please re-authorize.');
        }
        if (error.code === 403) {
            // Forbidden, e.g. Gmail API not enabled for project or usage limits
            throw new Error('Access to Gmail API is forbidden. Please check API configuration or usage limits.');
        }
        // Re-throw a generic error or a more specific one based on Google's error structure
        throw new Error(`Failed to search emails: ${error.message || 'Unknown Gmail API error'}`);
    }
}
/**
 * Fetches the full content of a specific email.
 * @param userId The ID of the user.
 * @param emailId The ID of the email to fetch.
 * @returns A promise that resolves to the full Gmail message content.
 */
export async function getUserEmailContent(userId, emailId) {
    console.log(`Gmail Service: Getting email content for user ${userId}, email ID "${emailId}"`);
    const authedClient = await getGmailClientForUser(userId);
    if (!authedClient) {
        throw new Error('Failed to get authenticated Gmail client. User may need to authorize or re-authorize.');
    }
    const gmail = google.gmail({ version: 'v1', auth: authedClient });
    try {
        const response = await gmail.users.messages.get({
            userId: 'me',
            id: emailId,
            format: 'full', // Fetches full email content, including headers, body, attachments etc.
            // Use 'metadata' for headers only, 'minimal' for id/threadId/labels.
        });
        return response.data;
    }
    catch (error) {
        console.error(`Error fetching email content for user ${userId}, email ID ${emailId}:`, error.message);
        if (error.code === 401) {
            throw new Error('Gmail authentication failed (token might be revoked or insufficient permissions). Please re-authorize.');
        }
        if (error.code === 403) {
            throw new Error('Access to Gmail API is forbidden for this message or user. Please check API configuration or usage limits.');
        }
        if (error.code === 404) {
            throw new Error(`Email with ID ${emailId} not found.`);
        }
        throw new Error(`Failed to fetch email content: ${error.message || 'Unknown Gmail API error'}`);
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2VydmljZS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInNlcnZpY2UudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUFFLE1BQU0sRUFBWSxNQUFNLFlBQVksQ0FBQztBQUM5Qyw0QkFBNEI7QUFDNUIsT0FBTyxFQUFFLHdCQUF3QixFQUFFLE1BQU0scUJBQXFCLENBQUM7QUFDL0QsT0FBTyxFQUNMLE9BQU8sRUFDUCxPQUFPLEdBQ1IsTUFBTSxpREFBaUQsQ0FBQztBQUN6RCxPQUFPLEVBQUUsdUJBQXVCLEVBQUUsTUFBTSxxQ0FBcUMsQ0FBQztBQUM5RSxPQUFPLEVBQ0wsbUJBQW1CLEVBQ25CLHVCQUF1QixHQUN4QixNQUFNLG9DQUFvQyxDQUFDO0FBRTVDLE1BQU0sc0JBQXNCLEdBQUc7Ozs7Ozs7O0NBUTlCLENBQUM7QUFFRixNQUFNLGtDQUFrQyxHQUFHOzs7Ozs7Ozs7Ozs7O0NBYTFDLENBQUM7QUFFRjs7Ozs7R0FLRztBQUNILE1BQU0sQ0FBQyxLQUFLLFVBQVUscUJBQXFCLENBQ3pDLE1BQWM7SUFFZCxNQUFNLGtCQUFrQixHQUFHLHdCQUF3QixFQUFFLENBQUM7SUFFdEQsSUFBSSxDQUFDO1FBQ0gsTUFBTSxXQUFXLEdBQUcsTUFBTSxrQkFBa0IsQ0FBQyxPQUFPLENBQ2xELHNCQUFzQixFQUN0QixFQUFFLE1BQU0sRUFBRSxDQUNYLENBQUM7UUFDRixNQUFNLGlCQUFpQixHQUNyQixXQUFXLENBQUMsaUJBQWlCLElBQUksV0FBVyxDQUFDLGlCQUFpQixDQUFDLENBQUMsQ0FBQyxDQUFDO1FBRXBFLElBQUksQ0FBQyxpQkFBaUIsRUFBRSxDQUFDO1lBQ3ZCLE9BQU8sQ0FBQyxHQUFHLENBQ1Qsa0NBQWtDLE1BQU0sNEJBQTRCLENBQ3JFLENBQUM7WUFDRixPQUFPLElBQUksQ0FBQztRQUNkLENBQUM7UUFFRCxJQUFJLEVBQ0Ysc0JBQXNCLEVBQ3RCLHVCQUF1QixFQUN2QixzQkFBc0IsR0FDdkIsR0FBRyxpQkFB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LEtBQUssQ0FDYixrQ0FBa0MsS0FBSyxDQUFDLE9BQU8sSUFBSSx5QkFBeUIsRUFBRSxDQUMvRSxDQUFDO0lBQ0osQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBnb29nbGUsIGdtYWlsX3YxIH0gZnJvbSAnZ29vZ2xlYXBpcyc7XG4vLyBBZGp1c3QgcGF0aHMgYXMgbmVjZXNzYXJ5XG5pbXBvcnQgeyBjcmVhdGVBZG1pbkdyYXBoUUxDbGllbnQgfSBmcm9tICcuLi9fdXRpbHMvZGJTZXJ2aWNlJztcbmltcG9ydCB7XG4gIGRlY3J5cHQsXG4gIGVuY3J5cHQsXG59IGZyb20gJy4uL2dtYWlsLWludGVncmF0aW9uL2hhbmRsZS1nbWFpbC1hdXRoLWNhbGxiYWNrJztcbmltcG9ydCB7IHJlZnJlc2hHbWFpbEFjY2Vzc1Rva2VuIH0gZnJvbSAnLi4vZ29vZ2xlLWFwaS1hdXRoL19saWJzL2FwaS1oZWxwZXInO1xuaW1wb3J0IHtcbiAgZ29vZ2xlQ2xpZW50SWRHbWFpbCxcbiAgZ29vZ2xlQ2xpZW50U2VjcmV0R21haWwsXG59IGZyb20gJy4uL2dvb2dsZS1hcGktYXV0aC9fbGlicy9jb25zdGFudHMnO1xuXG5jb25zdCBHRVRfR01BSUxfVE9LRU5TX1FVRVJZID0gYFxucXVlcnkgR2V0VXNlckdtYWlsVG9rZW5zKCR1c2VySWQ6IHV1aWQhKSB7XG4gIHVzZXJfZ21haWxfdG9rZW5zKHdoZXJlOiB7dXNlcl9pZDoge19lcTogJHVzZXJJZH19LCBsaW1pdDogMSkge1xuICAgIGVuY3J5cHRlZF9hY2Nlc3NfdG9rZW5cbiAgICBlbmNyeXB0ZWRfcmVmcmVzaF90b2tlblxuICAgIHRva2VuX2V4cGlyeV90aW1lc3RhbXBcbiAgfVxufVxuYDtcblxuY29uc3QgVVBEQVRFX0dNQUlMX0FDQ0VTU19UT0tFTl9NVVRBVElPTiA9IGBcbm11dGF0aW9uIFVwZGF0ZVVzZXJHbWFpbEFjY2Vzc1Rva2VuQWZ0ZXJSZWZyZXNoKCR1c2VySWQ6IHV1aWQhLCAkbmV3RW5jcnlwdGVkQWNjZXNzVG9rZW46IFN0cmluZyEsICRuZXdFeHBpcnlUaW1lc3RhbXA6IHRpbWVzdGFtcHR6ISkge1xuICB1cGRhdGVfdXNlcl9nbWFpbF90b2tlbnMoXG4gICAgd2hlcmU6IHt1c2VyX2lkOiB7X2VxOiAkdXNlcklkfX0sXG4gICAgX3NldDoge1xuICAgICAgZW5jcnlwdGVkX2FjY2Vzc190b2tlbjogJG5ld0VuY3J5cHRlZEFjY2Vzc1Rva2VuLFxuICAgICAgdG9rZW5fZXhwaXJ5X3RpbWVzdGFtcDogJG5ld0V4cGlyeVRpbWVzdGFtcCxcbiAgICAgIHVwZGF0ZWRfYXQ6IFwibm93KClcIlxuICAgIH1cbiAgKSB7XG4gICAgYWZmZWN0ZWRfcm93c1xuICB9XG59XG5gO1xuXG4vKipcbiAqIFJldHJpZXZlcyBhIHVzZXIncyBzdG9yZWQgR21haWwgdG9rZW5zLCByZWZyZXNoZXMgaWYgbmVjZXNzYXJ5LFxuICogYW5kIHJldHVybnMgYW4gYXV0aGVudGljYXRlZCBPQXV0aDIgY2xpZW50IGNvbmZpZ3VyZWQgZm9yIEdtYWlsIEFQSS5cbiAqIEBwYXJhbSB1c2VySWQgVGhlIElEIG9mIHRoZSB1c2VyLlxuICogQHJldHVybnMgQW4gYXV0aGVudGljYXRlZCBnb29nbGUuYXV0aC5PQXV0aDIgY2xpZW50IG9yIG51bGwgaWYgdG9rZW5zIGFyZSBub3QgZm91bmQvdmFsaWQuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRHbWFpbENsaWVudEZvclVzZXIoXG4gIHVzZXJJZDogc3RyaW5nXG4pOiBQcm9taXNlPGdvb2dsZS5hdXRoLk9BdXRoMiB8IG51bGw+IHtcbiAgY29uc3QgYWRtaW5HcmFwaFFMQ2xpZW50ID0gY3JlYXRlQWRtaW5HcmFwaFFMQ2xpZW50KCk7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCBncWxSZXNwb25zZSA9IGF3YWl0IGFkbWluR3JhcGhRTENsaWVudC5yZXF1ZXN0KFxuICAgICAgR0VUX0dNQUlMX1RPS0VOU19RVUVSWSxcbiAgICAgIHsgdXNlcklkIH1cbiAgICApO1xuICAgIGNvbnN0IHN0b3JlZFRva2VuUmVjb3JkID1cbiAgICAgIGdxbFJlc3BvbnNlLnVzZXJfZ21haWxfdG9rZW5zICYmIGdxbFJlc3BvbnNlLnVzZXJfZ21haWxfdG9rZW5zWzBdO1xuXG4gICAgaWYgKCFzdG9yZWRUb2tlblJlY29yZCkge1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGBObyBHbWFpbCB0b2tlbnMgZm91bmQgZm9yIHVzZXIgJHt1c2VySWR9LiBVc2VyIG5lZWRzIHRvIGF1dGhvcml6ZS5gXG4gICAgICApO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuXG4gICAgbGV0IHtcbiAgICAgIGVuY3J5cHRlZF9hY2Nlc3NfdG9rZW4sXG4gICAgICBlbmNyeXB0ZWRfcmVmcmVzaF90b2tlbixcbiAgICAgIHRva2VuX2V4cGlyeV90aW1lc3RhbXAsXG4gICAgfSA9IHN0b3JlZFRva2VuUmVjb3JkO1xuXG4gICAgaWYgKCFlbmNyeXB0ZWRfYWNjZXNzX3Rva2VuICYmICFlbmNyeXB0ZWRfcmVmcmVzaF90b2tlbikge1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGBOZWl0aGVyIGFjY2VzcyBub3IgcmVmcmVzaCB0b2tlbiBmb3VuZCBmb3IgdXNlciAke3VzZXJJZH0uIFJlLWF1dGhvcml6YXRpb24gbmVlZGVkLmBcbiAgICAgICk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG5cbiAgICBjb25zdCBvYXV0aDJDbGllbnQgPSBuZXcgZ29vZ2xlLmF1dGguT0F1dGgyKFxuICAgICAgZ29vZ2xlQ2xpZW50SWRHbWFpbCxcbiAgICAgIGdvb2dsZUNsaWVudFNlY3JldEdtYWlsXG4gICAgICAvLyBObyByZWRpcmVjdCBVUkkgbmVlZGVkIGhlcmUgYXMgd2UgYXJlIG5vdCBzdGFydGluZyBhIG5ldyBhdXRoIGZsb3dcbiAgICApO1xuXG4gICAgbGV0IGN1cnJlbnRBY2Nlc3NUb2tlbiA9ICcnO1xuXG4gICAgLy8gQ2hlY2sgaWYgdG9rZW4gaXMgZXhwaXJlZCBvciBhYm91dCB0byBleHBpcmUgKGUuZy4sIHdpdGhpbiBuZXh0IDUgbWludXRlcylcbiAgICBjb25zdCBleHBpcnlEYXRlID0gdG9rZW5fZXhwaXJ5X3RpbWVzdGFtcFxuICAgICAgPyBuZXcgRGF0ZSh0b2tlbl9leHBpcnlfdGltZXN0YW1wKS5nZXRUaW1lKClcbiAgICAgIDogMDtcbiAgICBjb25zdCBuZWVkc1JlZnJlc2ggPSBEYXRlLm5vdygpID49IGV4cGlyeURhdGUgLSA1ICogNjAgKiAxMDAwO1xuXG4gICAgaWYgKG5lZWRzUmVmcmVzaCkge1xuICAgICAgaWYgKCFlbmNyeXB0ZWRfcmVmcmVzaF90b2tlbikge1xuICAgICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAgIGBUb2tlbiBmb3IgdXNlciAke3VzZXJJZH0gbmVlZHMgcmVmcmVzaCwgYnV0IG5vIHJlZnJlc2ggdG9rZW4gaXMgYXZhaWxhYmxlLiBVc2VyIG11c3QgcmUtYXV0aG9yaXplLmBcbiAgICAgICAgKTtcbiAgICAgICAgLy8gT3B0aW9uYWxseSwgY2xlYXIgdGhlIGludmFsaWQgdG9rZW5zIGZyb20gREIgb3IgbWFyayB0aGVtIGFzIG5lZWRpbmcgcmUtYXV0aFxuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH1cbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBgR21haWwgYWNjZXNzIHRva2VuIGZvciB1c2VyICR7dXNlcklkfSByZXF1aXJlcyByZWZyZXNoLiBBdHRlbXB0aW5nLi4uYFxuICAgICAgKTtcblxuICAgICAgY29uc3QgZGVjcnlwdGVkUmVmcmVzaFRva2VuID0gZGVjcnlwdChlbmNyeXB0ZWRfcmVmcmVzaF90b2tlbik7XG4gICAgICBpZiAoIWRlY3J5cHRlZFJlZnJlc2hUb2tlbikge1xuICAgICAgICBjb25zb2xlLmVycm9yKGBGYWlsZWQgdG8gZGVjcnlwdCByZWZyZXNoIHRva2VuIGZvciB1c2VyICR7dXNlcklkfS5gKTtcbiAgICAgICAgcmV0dXJuIG51bGw7IC8vIENhbm5vdCBwcm9jZWVkIHdpdGhvdXQgZGVjcnlwdGVkIHJlZnJlc2ggdG9rZW5cbiAgICAgIH1cblxuICAgICAgY29uc3QgcmVmcmVzaGVkR29vZ2xlVG9rZW5zID0gYXdhaXQgcmVmcmVzaEdtYWlsQWNjZXNzVG9rZW4oXG4gICAgICAgIGRlY3J5cHRlZFJlZnJlc2hUb2tlblxuICAgICAgKTtcblxuICAgICAgaWYgKFxuICAgICAgICAhcmVmcmVzaGVkR29vZ2xlVG9rZW5zLmFjY2Vzc190b2tlbiB8fFxuICAgICAgICAhcmVmcmVzaGVkR29vZ2xlVG9rZW5zLmV4cGlyZXNfaW5cbiAgICAgICkge1xuICAgICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAgIGBGYWlsZWQgdG8gcmVmcmVzaCBHbWFpbCBhY2Nlc3MgdG9rZW4gZnJvbSBHb29nbGUgZm9yIHVzZXIgJHt1c2VySWR9LmBcbiAgICAgICAgKTtcbiAgICAgICAgLy8gVGhpcyBjb3VsZCBiZSBkdWUgdG8gcmV2b2tlZCByZWZyZXNoIHRva2VuLiBVc2VyIG5lZWRzIHRvIHJlLWF1dGhvcml6ZS5cbiAgICAgICAgLy8gT3B0aW9uYWxseSwgY2xlYXIgdGhlIGludmFsaWQgdG9rZW5zIGZyb20gREIgb3IgbWFyayB0aGVtIGFzIG5lZWRpbmcgcmUtYXV0aFxuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH1cblxuICAgICAgY3VycmVudEFjY2Vzc1Rva2VuID0gcmVmcmVzaGVkR29vZ2xlVG9rZW5zLmFjY2Vzc190b2tlbjtcbiAgICAgIGNvbnN0IG5ld0VuY3J5cHRlZEFjY2Vzc1Rva2VuID0gZW5jcnlwdChjdXJyZW50QWNjZXNzVG9rZW4pO1xuICAgICAgY29uc3QgbmV3RXhwaXJ5ID0gbmV3IERhdGUoXG4gICAgICAgIERhdGUubm93KCkgKyByZWZyZXNoZWRHb29nbGVUb2tlbnMuZXhwaXJlc19pbiAqIDEwMDBcbiAgICAgICkudG9JU09TdHJpbmcoKTtcblxuICAgICAgLy8gVXBkYXRlIHRoZSBkYXRhYmFzZSB3aXRoIHRoZSBuZXcgYWNjZXNzIHRva2VuIGFuZCBleHBpcnlcbiAgICAgIGF3YWl0IGFkbWluR3JhcGhRTENsaWVudC5yZXF1ZXN0KFVQREFURV9HTUFJTF9BQ0NFU1NfVE9LRU5fTVVUQVRJT04sIHtcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBuZXdFbmNyeXB0ZWRBY2Nlc3NUb2tlbjogbmV3RW5jcnlwdGVkQWNjZXNzVG9rZW4sXG4gICAgICAgIG5ld0V4cGlyeVRpbWVzdGFtcDogbmV3RXhwaXJ5LFxuICAgICAgfSk7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYEdtYWlsIGFjY2VzcyB0b2tlbiBmb3IgdXNlciAke3VzZXJJZH0gcmVmcmVzaGVkIGFuZCB1cGRhdGVkIGluIERCLmBcbiAgICAgICk7XG5cbiAgICAgIC8vIElmIHRoZSBvcmlnaW5hbCByZWZyZXNoIHRva2VuIHdhcyBhbHNvIHVwZGF0ZWQgYnkgR29vZ2xlIChyYXJlLCBidXQgcG9zc2libGUpLFxuICAgICAgLy8geW91IHdvdWxkIGFsc28gdXBkYXRlIGVuY3J5cHRlZF9yZWZyZXNoX3Rva2VuIGhlcmUuXG4gICAgICAvLyBGb3Igbm93LCBhc3N1bWluZyByZWZyZXNoX3Rva2VuIHJlbWFpbnMgdGhlIHNhbWUgdW5sZXNzIEdvb2dsZSBleHBsaWNpdGx5IGNoYW5nZXMgaXQuXG4gICAgfSBlbHNlIHtcbiAgICAgIGlmICghZW5jcnlwdGVkX2FjY2Vzc190b2tlbikge1xuICAgICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAgIGBUb2tlbiBmb3IgdXNlciAke3VzZXJJZH0gbm90IGV4cGlyZWQsIGJ1dCBhY2Nlc3MgdG9rZW4gaXMgbWlzc2luZy4gVGhpcyBzdGF0ZSBzaG91bGQgbm90IG9jY3VyLmBcbiAgICAgICAgKTtcbiAgICAgICAgcmV0dXJuIG51bGw7IC8vIFNob3VsZCBub3QgaGFwcGVuIGlmIG5vdCBleHBpcmVkIGFuZCBubyByZWZyZXNoIG5lZWRlZC5cbiAgICAgIH1cbiAgICAgIGNvbnN0IGRlY3J5cHRlZEFjY2Vzc1Rva2VuID0gZGVjcnlwdChlbmNyeXB0ZWRfYWNjZXNzX3Rva2VuKTtcbiAgICAgIGlmICghZGVjcnlwdGVkQWNjZXNzVG9rZW4pIHtcbiAgICAgICAgY29uc29sZS5lcnJvcihgRmFpbGVkIHRvIGRlY3J5cHQgYWNjZXNzIHRva2VuIGZvciB1c2VyICR7dXNlcklkfS5gKTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9XG4gICAgICBjdXJyZW50QWNjZXNzVG9rZW4gPSBkZWNyeXB0ZWRBY2Nlc3NUb2tlbjtcbiAgICB9XG5cbiAgICBvYXV0aDJDbGllbnQuc2V0Q3JlZGVudGlhbHMoeyBhY2Nlc3NfdG9rZW46IGN1cnJlbnRBY2Nlc3NUb2tlbiB9KTtcbiAgICAvLyBJZiBHb29nbGUgcmV0dXJuZWQgYSBuZXcgcmVmcmVzaF90b2tlbiAocmFyZSBmb3IgR29vZ2xlLCBidXQgc29tZSBwcm92aWRlcnMgZG8pLFxuICAgIC8vIHlvdSdkIHNldCBpdCBoZXJlIHRvbzogb2F1dGgyQ2xpZW50LnNldENyZWRlbnRpYWxzKHsgYWNjZXNzX3Rva2VuOiAuLi4sIHJlZnJlc2hfdG9rZW46IC4uLiB9KTtcbiAgICAvLyBBbmQgdGhlbiByZS1lbmNyeXB0IGFuZCBzYXZlIHRoZSBuZXcgcmVmcmVzaF90b2tlbi5cblxuICAgIHJldHVybiBvYXV0aDJDbGllbnQ7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgYEVycm9yIGluIGdldEdtYWlsQ2xpZW50Rm9yVXNlciBmb3IgdXNlciAke3VzZXJJZH06YCxcbiAgICAgIGVycm9yLm1lc3NhZ2VcbiAgICApO1xuICAgIGlmIChlcnJvci5yZXNwb25zZSAmJiBlcnJvci5yZXNwb25zZS5ib2R5KSB7XG4gICAgICAvLyBMb2cgR29vZ2xlIEFQSSBlcnJvcnMgaWYgYXZhaWxhYmxlXG4gICAgICBjb25zb2xlLmVycm9yKCdHb29nbGUgQVBJIGVycm9yIGRldGFpbHM6JywgZXJyb3IucmVzcG9uc2UuYm9keSk7XG4gICAgfVxuICAgIHJldHVybiBudWxsO1xuICB9XG59XG5cbi8qKlxuICogUGxhY2Vob2xkZXIgZm9yIHNlYXJjaGluZyB1c2VyJ3MgZW1haWxzLlxuICogQHBhcmFtIHVzZXJJZCBUaGUgSUQgb2YgdGhlIHVzZXIuXG4gKiBAcGFyYW0gcXVlcnkgVGhlIHNlYXJjaCBxdWVyeSAoZS5nLiwgXCJmcm9tOnh5ekBleGFtcGxlLmNvbSBzdWJqZWN0OmNvbnRyYWN0IGFmdGVyOjIwMjMvMDEvMDEgYmVmb3JlOjIwMjMvMDMvMzFcIikuXG4gKiBAcGFyYW0gbWF4UmVzdWx0cyBNYXhpbXVtIG51bWJlciBvZiByZXN1bHRzIHRvIHJldHVybi5cbiAqIEByZXR1cm5zIEEgcHJvbWlzZSB0aGF0IHJlc29sdmVzIHRvIGFuIGFycmF5IG9mIEdtYWlsIG1lc3NhZ2VzLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gc2VhcmNoVXNlckVtYWlscyhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHF1ZXJ5OiBzdHJpbmcsXG4gIG1heFJlc3VsdHM6IG51bWJlciA9IDEwXG4pOiBQcm9taXNlPGdtYWlsX3YxLlNjaGVtYSRNZXNzYWdlW10+IHtcbiAgY29uc29sZS5sb2coXG4gICAgYEdtYWlsIFNlcnZpY2U6IFNlYXJjaGluZyBlbWFpbHMgZm9yIHVzZXIgJHt1c2VySWR9IHdpdGggcXVlcnkgXCIke3F1ZXJ5fVwiLCBtYXggJHttYXhSZXN1bHRzfWBcbiAgKTtcbiAgY29uc3QgYXV0aGVkQ2xpZW50ID0gYXdhaXQgZ2V0R21haWxDbGllbnRGb3JVc2VyKHVzZXJJZCk7XG4gIGlmICghYXV0aGVkQ2xpZW50KSB7XG4gICAgLy8gRGV0YWlsZWQgZXJyb3IgYWxyZWFkeSBsb2dnZWQgaW4gZ2V0R21haWxDbGllbnRGb3JVc2VyIGlmIGl0IHJldHVybnMgbnVsbCBkdWUgdG8gYXV0aCBpc3N1ZXNcbiAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAnRmFpbGVkIHRvIGdldCBhdXRoZW50aWNhdGVkIEdtYWlsIGNsaWVudC4gVXNlciBtYXkgbmVlZCB0byBhdXRob3JpemUgb3IgcmUtYXV0aG9yaXplLidcbiAgICApO1xuICB9XG5cbiAgY29uc3QgZ21haWwgPSBnb29nbGUuZ21haWwoeyB2ZXJzaW9uOiAndjEnLCBhdXRoOiBhdXRoZWRDbGllbnQgfSk7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGdtYWlsLnVzZXJzLm1lc3NhZ2VzLmxpc3Qoe1xuICAgICAgdXNlcklkOiAnbWUnLFxuICAgICAgcTogcXVlcnksXG4gICAgICBtYXhSZXN1bHRzOiBtYXhSZXN1bHRzLFxuICAgICAgLy8gY29uc2lkZXIgYWRkaW5nIGZpZWxkcyBwYXJhbWV0ZXIgdG8gb3B0aW1pemUsIGUuZy4gJ21lc3NhZ2VzKGlkLHRocmVhZElkLHNuaXBwZXQpJ1xuICAgIH0pO1xuXG4gICAgLy8gbWVzc2FnZXMubGlzdCByZXR1cm5zIGEgbGlzdCBvZiBNZXNzYWdlIHJlc291cmNlcywgd2hpY2ggc2hvdWxkIGluY2x1ZGUgaWQsIHRocmVhZElkLCBhbmQgb2Z0ZW4gc25pcHBldC5cbiAgICAvLyBJZiBtb3JlIGRldGFpbHMgbGlrZSBzdWJqZWN0LCBmcm9tLCBkYXRlIGFyZSBuZWVkZWQgZm9yIGVhY2ggaXRlbSBpbiBzZWFyY2ggcmVzdWx0cyAqd2l0aG91dCogTisxIGNhbGxzLFxuICAgIC8vIHRoZSBxdWVyeSB3b3VsZCBuZWVkIHRvIGJlIG1vcmUgY29tcGxleCAoZS5nLiBiYXRjaCByZXF1ZXN0cyBmb3IgbWVzc2FnZXMuZ2V0IHdpdGggZm9ybWF0OiAnbWV0YWRhdGEnKVxuICAgIC8vIG9yIGEgZGlmZmVyZW50IEdtYWlsIEFQSSBlbmRwb2ludC4gRm9yIG5vdywgdGhpcyBpcyBhIGRpcmVjdCBtYXBwaW5nLlxuICAgIHJldHVybiByZXNwb25zZS5kYXRhLm1lc3NhZ2VzIHx8IFtdO1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcihcbiAgICAgIGBFcnJvciBzZWFyY2hpbmcgZW1haWxzIGZvciB1c2VyICR7dXNlcklkfSAocXVlcnk6IFwiJHtxdWVyeX1cIik6YCxcbiAgICAgIGVycm9yLm1lc3NhZ2VcbiAgICApO1xuICAgIGlmIChlcnJvci5jb2RlID09PSA0MDEpIHtcbiAgICAgIC8vIFVuYXV0aG9yaXplZCwgb2Z0ZW4gZHVlIHRvIHRva2VuIGlzc3VlcyBub3QgY2F1Z2h0IGJ5IHJlZnJlc2hcbiAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgJ0dtYWlsIGF1dGhlbnRpY2F0aW9uIGZhaWxlZCAodG9rZW4gbWlnaHQgYmUgcmV2b2tlZCBvciBpbnN1ZmZpY2llbnQgcGVybWlzc2lvbnMpLiBQbGVhc2UgcmUtYXV0aG9yaXplLidcbiAgICAgICk7XG4gICAgfVxuICAgIGlmIChlcnJvci5jb2RlID09PSA0MDMpIHtcbiAgICAgIC8vIEZvcmJpZGRlbiwgZS5nLiBHbWFpbCBBUEkgbm90IGVuYWJsZWQgZm9yIHByb2plY3Qgb3IgdXNhZ2UgbGltaXRzXG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgICdBY2Nlc3MgdG8gR21haWwgQVBJIGlzIGZvcmJpZGRlbi4gUGxlYXNlIGNoZWNrIEFQSSBjb25maWd1cmF0aW9uIG9yIHVzYWdlIGxpbWl0cy4nXG4gICAgICApO1xuICAgIH1cbiAgICAvLyBSZS10aHJvdyBhIGdlbmVyaWMgZXJyb3Igb3IgYSBtb3JlIHNwZWNpZmljIG9uZSBiYXNlZCBvbiBHb29nbGUncyBlcnJvciBzdHJ1Y3R1cmVcbiAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICBgRmFpbGVkIHRvIHNlYXJjaCBlbWFpbHM6ICR7ZXJyb3IubWVzc2FnZSB8fCAnVW5rbm93biBHbWFpbCBBUEkgZXJyb3InfWBcbiAgICApO1xuICB9XG59XG5cbi8qKlxuICogRmV0Y2hlcyB0aGUgZnVsbCBjb250ZW50IG9mIGEgc3BlY2lmaWMgZW1haWwuXG4gKiBAcGFyYW0gdXNlcklkIFRoZSBJRCBvZiB0aGUgdXNlci5cbiAqIEBwYXJhbSBlbWFpbElkIFRoZSBJRCBvZiB0aGUgZW1haWwgdG8gZmV0Y2guXG4gKiBAcmV0dXJucyBBIHByb21pc2UgdGhhdCByZXNvbHZlcyB0byB0aGUgZnVsbCBHbWFpbCBtZXNzYWdlIGNvbnRlbnQuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRVc2VyRW1haWxDb250ZW50KFxuICB1c2VySWQ6IHN0cmluZyxcbiAgZW1haWxJZDogc3RyaW5nXG4pOiBQcm9taXNlPGdtYWlsX3YxLlNjaGVtYSRNZXNzYWdlIHwgbnVsbD4ge1xuICBjb25zb2xlLmxvZyhcbiAgICBgR21haWwgU2VydmljZTogR2V0dGluZyBlbWFpbCBjb250ZW50IGZvciB1c2VyICR7dXNlcklkfSwgZW1haWwgSUQgXCIke2VtYWlsSWR9XCJgXG4gICk7XG4gIGNvbnN0IGF1dGhlZENsaWVudCA9IGF3YWl0IGdldEdtYWlsQ2xpZW50Rm9yVXNlcih1c2VySWQpO1xuICBpZiAoIWF1dGhlZENsaWVudCkge1xuICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICdGYWlsZWQgdG8gZ2V0IGF1dGhlbnRpY2F0ZWQgR21haWwgY2xpZW50LiBVc2VyIG1heSBuZWVkIHRvIGF1dGhvcml6ZSBvciByZS1hdXRob3JpemUuJ1xuICAgICk7XG4gIH1cblxuICBjb25zdCBnbWFpbCA9IGdvb2dsZS5nbWFpbCh7IHZlcnNpb246ICd2MScsIGF1dGg6IGF1dGhlZENsaWVudCB9KTtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZ21haWwudXNlcnMubWVzc2FnZXMuZ2V0KHtcbiAgICAgIHVzZXJJZDogJ21lJyxcbiAgICAgIGlkOiBlbWFpbElkLFxuICAgICAgZm9ybWF0OiAnZnVsbCcsIC8vIEZldGNoZXMgZnVsbCBlbWFpbCBjb250ZW50LCBpbmNsdWRpbmcgaGVhZGVycywgYm9keSwgYXR0YWNobWVudHMgZXRjLlxuICAgICAgLy8gVXNlICdtZXRhZGF0YScgZm9yIGhlYWRlcnMgb25seSwgJ21pbmltYWwnIGZvciBpZC90aHJlYWRJZC9sYWJlbHMuXG4gICAgfSk7XG4gICAgcmV0dXJuIHJlc3BvbnNlLmRhdGE7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgYEVycm9yIGZldGNoaW5nIGVtYWlsIGNvbnRlbnQgZm9yIHVzZXIgJHt1c2VySWR9LCBlbWFpbCBJRCAke2VtYWlsSWR9OmAsXG4gICAgICBlcnJvci5tZXNzYWdlXG4gICAgKTtcbiAgICBpZiAoZXJyb3IuY29kZSA9PT0gNDAxKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgICdHbWFpbCBhdXRoZW50aWNhdGlvbiBmYWlsZWQgKHRva2VuIG1pZ2h0IGJlIHJldm9rZWQgb3IgaW5zdWZmaWNpZW50IHBlcm1pc3Npb25zKS4gUGxlYXNlIHJlLWF1dGhvcml6ZS4nXG4gICAgICApO1xuICAgIH1cbiAgICBpZiAoZXJyb3IuY29kZSA9PT0gNDAzKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgICdBY2Nlc3MgdG8gR21haWwgQVBJIGlzIGZvcmJpZGRlbiBmb3IgdGhpcyBtZXNzYWdlIG9yIHVzZXIuIFBsZWFzZSBjaGVjayBBUEkgY29uZmlndXJhdGlvbiBvciB1c2FnZSBsaW1pdHMuJ1xuICAgICAgKTtcbiAgICB9XG4gICAgaWYgKGVycm9yLmNvZGUgPT09IDQwNCkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKGBFbWFpbCB3aXRoIElEICR7ZW1haWxJZH0gbm90IGZvdW5kLmApO1xuICAgIH1cbiAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICBgRmFpbGVkIHRvIGZldGNoIGVtYWlsIGNvbnRlbnQ6ICR7ZXJyb3IubWVzc2FnZSB8fCAnVW5rbm93biBHbWFpbCBBUEkgZXJyb3InfWBcbiAgICApO1xuICB9XG59XG4iXX0=