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
const handler = async (req, res) => {
    const userId = req.body.session_variables['x-hasura-user-id'];
    if (!userId) {
        return res
            .status(400)
            .json({ success: false, message: 'User ID is missing from session.' });
    }
    const adminGraphQLClient = createAdminGraphQLClient();
    try {
        // 1. Fetch the encrypted refresh token
        const queryResult = await adminGraphQLClient.request(GET_GMAIL_REFRESH_TOKEN_QUERY, { userId });
        const storedTokens = queryResult.user_gmail_tokens;
        if (!storedTokens ||
            storedTokens.length === 0 ||
            !storedTokens[0].encrypted_refresh_token) {
            return res
                .status(404)
                .json({
                success: false,
                message: 'No Gmail refresh token found for this user, or integration is incomplete. Please connect/reconnect Gmail.',
            });
        }
        const encryptedRefreshToken = storedTokens[0].encrypted_refresh_token;
        let decryptedRefreshToken;
        try {
            decryptedRefreshToken = decrypt(encryptedRefreshToken);
        }
        catch (decryptionError) {
            console.error(`Failed to decrypt refresh token for user ${userId}:`, decryptionError.message);
            // It's possible the key changed or data is corrupt. User should re-auth.
            return res
                .status(500)
                .json({
                success: false,
                message: 'Failed to process stored token. Please try reconnecting your Gmail account.',
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
        const refreshedTokensFromGoogle = await refreshGmailAccessToken(decryptedRefreshToken);
        if (!refreshedTokensFromGoogle.access_token ||
            !refreshedTokensFromGoogle.expires_in) {
            console.error(`Failed to refresh Gmail access token from Google for user ${userId}. Response:`, refreshedTokensFromGoogle);
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
        const newEncryptedAccessToken = encrypt(refreshedTokensFromGoogle.access_token);
        // 4. Calculate new expiry timestamp
        const newExpiryTimestamp = new Date(Date.now() + refreshedTokensFromGoogle.expires_in * 1000).toISOString();
        // 5. Update the database
        const updateResult = await adminGraphQLClient.request(UPDATE_GMAIL_ACCESS_TOKEN_MUTATION, {
            userId: userId,
            newAccessToken: newEncryptedAccessToken,
            newExpiryTimestamp: newExpiryTimestamp,
        });
        if (updateResult.update_user_gmail_tokens.affected_rows === 0) {
            console.warn(`Gmail token refresh: No rows updated in DB for user ${userId}. User may have disconnected integration, or an issue occurred.`);
            // This might not be a hard error if the user disconnected just before this write.
        }
        return res.status(200).json({
            success: true,
            message: 'Gmail access token refreshed successfully.',
            expires_in: refreshedTokensFromGoogle.expires_in,
        });
    }
    catch (e) {
        console.error(`Error refreshing Gmail token for user ${userId}:`, e);
        // Check if it's a Google error related to the refresh token itself (e.g., revoked)
        // The 'got' library throws HTTPError for non-2xx responses. e.response.body might contain the error.
        let responseBody = {};
        if (e.response && e.response.body) {
            try {
                responseBody = JSON.parse(e.response.body);
            }
            catch (parseError) {
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
                message: 'Gmail refresh token is invalid or revoked by Google. Please reconnect your Gmail account.',
            });
        }
        return res.status(500).json({
            success: false,
            message: 'An error occurred while refreshing Gmail token: ' +
                (e.message || 'Unknown error'),
        });
    }
};
export default handler;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicmVmcmVzaC11c2VyLWdtYWlsLXRva2VuLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsicmVmcmVzaC11c2VyLWdtYWlsLXRva2VuLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUNBLCtGQUErRjtBQUMvRixPQUFPLEVBQUUsdUJBQXVCLEVBQUUsTUFBTSxxQ0FBcUMsQ0FBQztBQUM5RSw4REFBOEQ7QUFDOUQsT0FBTyxFQUFFLHdCQUF3QixFQUFFLE1BQU0scUJBQXFCLENBQUM7QUFDL0QsT0FBTyxFQUFFLE9BQU8sRUFBRSxPQUFPLEVBQUUsTUFBTSw4QkFBOEIsQ0FBQyxDQUFDLGlDQUFpQztBQUVsRyx5Q0FBeUM7QUFDekMsTUFBTSw2QkFBNkIsR0FBRzs7Ozs7O0NBTXJDLENBQUM7QUFFRix5REFBeUQ7QUFDekQsTUFBTSxrQ0FBa0MsR0FBRzs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FpQjFDLENBQUM7QUFXRixNQUFNLE9BQU8sR0FBRyxLQUFLLEVBQ25CLEdBQWtELEVBQ2xELEdBQWEsRUFDYixFQUFFO0lBQ0YsTUFBTSxNQUFNLEdBQUcsR0FBRyxDQUFDLElBQUksQ0FBQyxpQkFBaUIsQ0FBQyxrQkFBa0IsQ0FBQyxDQUFDO0lBRTlELElBQUksQ0FBQyxNQUFNLEVBQUUsQ0FBQztRQUNaLE9BQU8sR0FBRzthQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7YUFDWCxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxrQ0FBa0MsRUFBRSxDQUFDLENBQUM7SUFDM0UsQ0FBQztJQUVELE1BQU0sa0JBQWtCLEdBQUcsd0JBQXdCLEVBQUUsQ0FBQztJQUV0RCxJQUFJLENBQUM7UUFDSCx1Q0FBdUM7UUFDdkMsTUFBTSxXQUFXLEdBQUcsTUFBTSxrQkFBa0IsQ0FBQyxPQUFPLENBQ2xELDZCQUE2QixFQUM3QixFQUFFLE1BQU0sRUFBRSxDQUNYLENBQUM7UUFDRixNQUFNLFlBQVksR0FBRyxXQUFXLENBQUMsaUJBQWlCLENB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QyxDQUFDO0lBQ0wsQ0FBQztJQUFDLE9BQU8sQ0FBTSxFQUFFLENBQUM7UUFDaEIsT0FBTyxDQUFDLEtBQUssQ0FBQyx5Q0FBeUMsTUFBTSxHQUFHLEVBQUUsQ0FBQyxDQUFDLENBQUM7UUFDckUsbUZBQW1GO1FBQ25GLHFHQUFxRztRQUNyRyxJQUFJLFlBQVksR0FBUSxFQUFFLENBQUM7UUFDM0IsSUFBSSxDQUFDLENBQUMsUUFBUSxJQUFJLENBQUMsQ0FBQyxRQUFRLENBQUMsSUFBSSxFQUFFLENBQUM7WUFDbEMsSUFBSSxDQUFDO2dCQUNILFlBQVksR0FBRyxJQUFJLENBQUMsS0FBSyxDQUFDLENBQUMsQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDLENBQUM7WUFDN0MsQ0FBQztZQUFDLE9BQU8sVUFBVSxFQUFFLENBQUM7Z0JBQ3BCLGdDQUFnQztZQUNsQyxDQUFDO1FBQ0gsQ0FBQztRQUVELElBQUksWUFBWSxDQUFDLEtBQUssS0FBSyxlQUFlLEVBQUUsQ0FBQztZQUMzQywwRUFBMEU7WUFDMUUscUZBQXFGO1lBQ3JGLE9BQU8sR0FBRztpQkFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2lCQUNYLElBQUksQ0FBQztnQkFDSixPQUFPLEVBQUUsS0FBSztnQkFDZCxPQUFPLEVBQ0wsMkZBQTJGO2FBQzlGLENBQUMsQ0FBQztRQUNQLENBQUM7UUFDRCxPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDO1lBQzFCLE9BQU8sRUFBRSxLQUFLO1lBQ2QsT0FBTyxFQUNMLGtEQUFrRDtnQkFDbEQsQ0FBQyxDQUFDLENBQUMsT0FBTyxJQUFJLGVBQWUsQ0FBQztTQUNqQyxDQUFDLENBQUM7SUFDTCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBRUYsZUFBZSxPQUFPLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBSZXF1ZXN0LCBSZXNwb25zZSB9IGZyb20gJ2V4cHJlc3MnO1xuLy8gQWRqdXN0IHRoZSBwYXRoIGJhc2VkIG9uIHRoZSBmaW5hbCBsb2NhdGlvbiBvZiBnbWFpbC1pbnRlZ3JhdGlvbiByZWxhdGl2ZSB0byBnb29nbGUtYXBpLWF1dGhcbmltcG9ydCB7IHJlZnJlc2hHbWFpbEFjY2Vzc1Rva2VuIH0gZnJvbSAnLi4vZ29vZ2xlLWFwaS1hdXRoL19saWJzL2FwaS1oZWxwZXInO1xuLy8gQWRqdXN0IHBhdGggYXMgbmVjZXNzYXJ5IGZvciBkYiBjbGllbnQgYW5kIGVuY3J5cHRpb24gdXRpbHNcbmltcG9ydCB7IGNyZWF0ZUFkbWluR3JhcGhRTENsaWVudCB9IGZyb20gJy4uL191dGlscy9kYlNlcnZpY2UnO1xuaW1wb3J0IHsgZGVjcnlwdCwgZW5jcnlwdCB9IGZyb20gJy4vaGFuZGxlLWdtYWlsLWF1dGgtY2FsbGJhY2snOyAvLyBSZXVzZSBlbmNyeXB0aW9uIGZyb20gY2FsbGJhY2tcblxuLy8gR3JhcGhRTCBxdWVyeSB0byBnZXQgdGhlIHJlZnJlc2ggdG9rZW5cbmNvbnN0IEdFVF9HTUFJTF9SRUZSRVNIX1RPS0VOX1FVRVJZID0gYFxucXVlcnkgR2V0VXNlckdtYWlsUmVmcmVzaFRva2VuKCR1c2VySWQ6IHV1aWQhKSB7XG4gIHVzZXJfZ21haWxfdG9rZW5zKHdoZXJlOiB7dXNlcl9pZDoge19lcTogJHVzZXJJZH0sIGVuY3J5cHRlZF9yZWZyZXNoX3Rva2VuOiB7X2lzX251bGw6IGZhbHNlfX0sIGxpbWl0OiAxKSB7XG4gICAgZW5jcnlwdGVkX3JlZnJlc2hfdG9rZW5cbiAgfVxufVxuYDtcblxuLy8gR3JhcGhRTCBtdXRhdGlvbiB0byB1cGRhdGUgdGhlIGFjY2VzcyB0b2tlbiBhbmQgZXhwaXJ5XG5jb25zdCBVUERBVEVfR01BSUxfQUNDRVNTX1RPS0VOX01VVEFUSU9OID0gYFxubXV0YXRpb24gVXBkYXRlVXNlckdtYWlsQWNjZXNzVG9rZW4oJHVzZXJJZDogdXVpZCEsICRuZXdBY2Nlc3NUb2tlbjogU3RyaW5nISwgJG5ld0V4cGlyeVRpbWVzdGFtcDogdGltZXN0YW1wdHohKSB7XG4gIHVwZGF0ZV91c2VyX2dtYWlsX3Rva2VucyhcbiAgICB3aGVyZToge3VzZXJfaWQ6IHtfZXE6ICR1c2VySWR9fSxcbiAgICBfc2V0OiB7XG4gICAgICBlbmNyeXB0ZWRfYWNjZXNzX3Rva2VuOiAkbmV3QWNjZXNzVG9rZW4sXG4gICAgICB0b2tlbl9leHBpcnlfdGltZXN0YW1wOiAkbmV3RXhwaXJ5VGltZXN0YW1wLFxuICAgICAgdXBkYXRlZF9hdDogXCJub3coKVwiXG4gICAgfVxuICApIHtcbiAgICBhZmZlY3RlZF9yb3dzXG4gICAgcmV0dXJuaW5nIHtcbiAgICAgIGlkXG4gICAgICB0b2tlbl9leHBpcnlfdGltZXN0YW1wXG4gICAgfVxuICB9XG59XG5gO1xuXG5pbnRlcmZhY2UgUmVmcmVzaEdtYWlsVG9rZW5SZXF1ZXN0Qm9keSB7XG4gIHNlc3Npb25fdmFyaWFibGVzOiB7XG4gICAgJ3gtaGFzdXJhLXVzZXItaWQnOiBzdHJpbmc7XG4gIH07XG4gIGlucHV0OiB7XG4gICAgLy8gTm8gc3BlY2lmaWMgaW5wdXQgbmVlZGVkIGZyb20gY2xpZW50LCB1c2VySWQgZnJvbSBzZXNzaW9uIGlzIHVzZWRcbiAgfTtcbn1cblxuY29uc3QgaGFuZGxlciA9IGFzeW5jIChcbiAgcmVxOiBSZXF1ZXN0PHt9LCB7fSwgUmVmcmVzaEdtYWlsVG9rZW5SZXF1ZXN0Qm9keT4sXG4gIHJlczogUmVzcG9uc2VcbikgPT4ge1xuICBjb25zdCB1c2VySWQgPSByZXEuYm9keS5zZXNzaW9uX3ZhcmlhYmxlc1sneC1oYXN1cmEtdXNlci1pZCddO1xuXG4gIGlmICghdXNlcklkKSB7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg0MDApXG4gICAgICAuanNvbih7IHN1Y2Nlc3M6IGZhbHNlLCBtZXNzYWdlOiAnVXNlciBJRCBpcyBtaXNzaW5nIGZyb20gc2Vzc2lvbi4nIH0pO1xuICB9XG5cbiAgY29uc3QgYWRtaW5HcmFwaFFMQ2xpZW50ID0gY3JlYXRlQWRtaW5HcmFwaFFMQ2xpZW50KCk7XG5cbiAgdHJ5IHtcbiAgICAvLyAxLiBGZXRjaCB0aGUgZW5jcnlwdGVkIHJlZnJlc2ggdG9rZW5cbiAgICBjb25zdCBxdWVyeVJlc3VsdCA9IGF3YWl0IGFkbWluR3JhcGhRTENsaWVudC5yZXF1ZXN0KFxuICAgICAgR0VUX0dNQUlMX1JFRlJFU0hfVE9LRU5fUVVFUlksXG4gICAgICB7IHVzZXJJZCB9XG4gICAgKTtcbiAgICBjb25zdCBzdG9yZWRUb2tlbnMgPSBxdWVyeVJlc3VsdC51c2VyX2dtYWlsX3Rva2VucztcblxuICAgIGlmIChcbiAgICAgICFzdG9yZWRUb2tlbnMgfHxcbiAgICAgIHN0b3JlZFRva2Vucy5sZW5ndGggPT09IDAgfHxcbiAgICAgICFzdG9yZWRUb2tlbnNbMF0uZW5jcnlwdGVkX3JlZnJlc2hfdG9rZW5cbiAgICApIHtcbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg0MDQpXG4gICAgICAgIC5qc29uKHtcbiAgICAgICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICAgJ05vIEdtYWlsIHJlZnJlc2ggdG9rZW4gZm91bmQgZm9yIHRoaXMgdXNlciwgb3IgaW50ZWdyYXRpb24gaXMgaW5jb21wbGV0ZS4gUGxlYXNlIGNvbm5lY3QvcmVjb25uZWN0IEdtYWlsLicsXG4gICAgICAgIH0pO1xuICAgIH1cblxuICAgIGNvbnN0IGVuY3J5cHRlZFJlZnJlc2hUb2tlbiA9IHN0b3JlZFRva2Vuc1swXS5lbmNyeXB0ZWRfcmVmcmVzaF90b2tlbjtcbiAgICBsZXQgZGVjcnlwdGVkUmVmcmVzaFRva2VuO1xuICAgIHRyeSB7XG4gICAgICBkZWNyeXB0ZWRSZWZyZXNoVG9rZW4gPSBkZWNyeXB0KGVuY3J5cHRlZFJlZnJlc2hUb2tlbik7XG4gICAgfSBjYXRjaCAoZGVjcnlwdGlvbkVycm9yOiBhbnkpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgIGBGYWlsZWQgdG8gZGVjcnlwdCByZWZyZXNoIHRva2VuIGZvciB1c2VyICR7dXNlcklkfTpgLFxuICAgICAgICBkZWNyeXB0aW9uRXJyb3IubWVzc2FnZVxuICAgICAgKTtcbiAgICAgIC8vIEl0J3MgcG9zc2libGUgdGhlIGtleSBjaGFuZ2VkIG9yIGRhdGEgaXMgY29ycnVwdC4gVXNlciBzaG91bGQgcmUtYXV0aC5cbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAgIC5qc29uKHtcbiAgICAgICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICAgJ0ZhaWxlZCB0byBwcm9jZXNzIHN0b3JlZCB0b2tlbi4gUGxlYXNlIHRyeSByZWNvbm5lY3RpbmcgeW91ciBHbWFpbCBhY2NvdW50LicsXG4gICAgICAgIH0pO1xuICAgIH1cblxuICAgIGlmICghZGVjcnlwdGVkUmVmcmVzaFRva2VuKSB7XG4gICAgICAvLyBUaGlzIGNhc2Ugc2hvdWxkIGlkZWFsbHkgYmUgY2F1Z2h0IGJ5IHRoZSB0cnktY2F0Y2ggYWJvdmUsIGJ1dCBhcyBhIHNhZmVndWFyZC5cbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAgIC5qc29uKHtcbiAgICAgICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgICAgICBtZXNzYWdlOiAnRGVjcnlwdGlvbiBvZiByZWZyZXNoIHRva2VuIGZhaWxlZCB1bmV4cGVjdGVkbHkuJyxcbiAgICAgICAgfSk7XG4gICAgfVxuXG4gICAgLy8gMi4gVXNlIHRoZSByZWZyZXNoIHRva2VuIHRvIGdldCBhIG5ldyBhY2Nlc3MgdG9rZW5cbiAgICBjb25zdCByZWZyZXNoZWRUb2tlbnNGcm9tR29vZ2xlID0gYXdhaXQgcmVmcmVzaEdtYWlsQWNjZXNzVG9rZW4oXG4gICAgICBkZWNyeXB0ZWRSZWZyZXNoVG9rZW5cbiAgICApO1xuXG4gICAgaWYgKFxuICAgICAgIXJlZnJlc2hlZFRva2Vuc0Zyb21Hb29nbGUuYWNjZXNzX3Rva2VuIHx8XG4gICAgICAhcmVmcmVzaGVkVG9rZW5zRnJvbUdvb2dsZS5leHBpcmVzX2luXG4gICAgKSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICBgRmFpbGVkIHRvIHJlZnJlc2ggR21haWwgYWNjZXNzIHRva2VuIGZyb20gR29vZ2xlIGZvciB1c2VyICR7dXNlcklkfS4gUmVzcG9uc2U6YCxcbiAgICAgICAgcmVmcmVzaGVkVG9rZW5zRnJvbUdvb2dsZVxuICAgICAgKTtcbiAgICAgIC8vIExvZyB0aGUgZXJyb3IgZnJvbSBHb29nbGUgaWYgYXZhaWxhYmxlXG4gICAgICAvLyBjb25zdCBnb29nbGVFcnJvciA9IChyZWZyZXNoZWRUb2tlbnNGcm9tR29vZ2xlIGFzIGFueSkuZXJyb3JfZGVzY3JpcHRpb24gfHwgKHJlZnJlc2hlZFRva2Vuc0Zyb21Hb29nbGUgYXMgYW55KS5lcnJvciB8fCAnVW5rbm93biBHb29nbGUgZXJyb3InO1xuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDUwMClcbiAgICAgICAgLmpzb24oe1xuICAgICAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgICAgIG1lc3NhZ2U6IGBDb3VsZCBub3QgcmVmcmVzaCBHbWFpbCBhY2Nlc3MgdG9rZW4gZnJvbSBHb29nbGUuYCxcbiAgICAgICAgfSk7XG4gICAgfVxuXG4gICAgLy8gMy4gRW5jcnlwdCB0aGUgbmV3IGFjY2VzcyB0b2tlblxuICAgIGNvbnN0IG5ld0VuY3J5cHRlZEFjY2Vzc1Rva2VuID0gZW5jcnlwdChcbiAgICAgIHJlZnJlc2hlZFRva2Vuc0Zyb21Hb29nbGUuYWNjZXNzX3Rva2VuXG4gICAgKTtcblxuICAgIC8vIDQuIENhbGN1bGF0ZSBuZXcgZXhwaXJ5IHRpbWVzdGFtcFxuICAgIGNvbnN0IG5ld0V4cGlyeVRpbWVzdGFtcCA9IG5ldyBEYXRlKFxuICAgICAgRGF0ZS5ub3coKSArIHJlZnJlc2hlZFRva2Vuc0Zyb21Hb29nbGUuZXhwaXJlc19pbiAqIDEwMDBcbiAgICApLnRvSVNPU3RyaW5nKCk7XG5cbiAgICAvLyA1LiBVcGRhdGUgdGhlIGRhdGFiYXNlXG4gICAgY29uc3QgdXBkYXRlUmVzdWx0ID0gYXdhaXQgYWRtaW5HcmFwaFFMQ2xpZW50LnJlcXVlc3QoXG4gICAgICBVUERBVEVfR01BSUxfQUNDRVNTX1RPS0VOX01VVEFUSU9OLFxuICAgICAge1xuICAgICAgICB1c2VySWQ6IHVzZXJJZCxcbiAgICAgICAgbmV3QWNjZXNzVG9rZW46IG5ld0VuY3J5cHRlZEFjY2Vzc1Rva2VuLFxuICAgICAgICBuZXdFeHBpcnlUaW1lc3RhbXA6IG5ld0V4cGlyeVRpbWVzdGFtcCxcbiAgICAgIH1cbiAgICApO1xuXG4gICAgaWYgKHVwZGF0ZVJlc3VsdC51cGRhdGVfdXNlcl9nbWFpbF90b2tlbnMuYWZmZWN0ZWRfcm93cyA9PT0gMCkge1xuICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICBgR21haWwgdG9rZW4gcmVmcmVzaDogTm8gcm93cyB1cGRhdGVkIGluIERCIGZvciB1c2VyICR7dXNlcklkfS4gVXNlciBtYXkgaGF2ZSBkaXNjb25uZWN0ZWQgaW50ZWdyYXRpb24sIG9yIGFuIGlzc3VlIG9jY3VycmVkLmBcbiAgICAgICk7XG4gICAgICAvLyBUaGlzIG1pZ2h0IG5vdCBiZSBhIGhhcmQgZXJyb3IgaWYgdGhlIHVzZXIgZGlzY29ubmVjdGVkIGp1c3QgYmVmb3JlIHRoaXMgd3JpdGUuXG4gICAgfVxuXG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoMjAwKS5qc29uKHtcbiAgICAgIHN1Y2Nlc3M6IHRydWUsXG4gICAgICBtZXNzYWdlOiAnR21haWwgYWNjZXNzIHRva2VuIHJlZnJlc2hlZCBzdWNjZXNzZnVsbHkuJyxcbiAgICAgIGV4cGlyZXNfaW46IHJlZnJlc2hlZFRva2Vuc0Zyb21Hb29nbGUuZXhwaXJlc19pbixcbiAgICB9KTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcihgRXJyb3IgcmVmcmVzaGluZyBHbWFpbCB0b2tlbiBmb3IgdXNlciAke3VzZXJJZH06YCwgZSk7XG4gICAgLy8gQ2hlY2sgaWYgaXQncyBhIEdvb2dsZSBlcnJvciByZWxhdGVkIHRvIHRoZSByZWZyZXNoIHRva2VuIGl0c2VsZiAoZS5nLiwgcmV2b2tlZClcbiAgICAvLyBUaGUgJ2dvdCcgbGlicmFyeSB0aHJvd3MgSFRUUEVycm9yIGZvciBub24tMnh4IHJlc3BvbnNlcy4gZS5yZXNwb25zZS5ib2R5IG1pZ2h0IGNvbnRhaW4gdGhlIGVycm9yLlxuICAgIGxldCByZXNwb25zZUJvZHk6IGFueSA9IHt9O1xuICAgIGlmIChlLnJlc3BvbnNlICYmIGUucmVzcG9uc2UuYm9keSkge1xuICAgICAgdHJ5IHtcbiAgICAgICAgcmVzcG9uc2VCb2R5ID0gSlNPTi5wYXJzZShlLnJlc3BvbnNlLmJvZHkpO1xuICAgICAgfSBjYXRjaCAocGFyc2VFcnJvcikge1xuICAgICAgICAvLyBOb3QgSlNPTiwgb3Igc29tZSBvdGhlciBpc3N1ZVxuICAgICAgfVxuICAgIH1cblxuICAgIGlmIChyZXNwb25zZUJvZHkuZXJyb3IgPT09ICdpbnZhbGlkX2dyYW50Jykge1xuICAgICAgLy8gVGhlIHJlZnJlc2ggdG9rZW4gaXMgaW52YWxpZCBvciByZXZva2VkLiBVc2VyIG5lZWRzIHRvIHJlLWF1dGhlbnRpY2F0ZS5cbiAgICAgIC8vIENvbnNpZGVyIGFjdGlvbnMgbGlrZSBkZWxldGluZyB0aGUgc3RvcmVkIHRva2VucyBvciBtYXJraW5nIHRoZW0gYXMgaW52YWxpZCBpbiBEQi5cbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg0MDEpXG4gICAgICAgIC5qc29uKHtcbiAgICAgICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICAgJ0dtYWlsIHJlZnJlc2ggdG9rZW4gaXMgaW52YWxpZCBvciByZXZva2VkIGJ5IEdvb2dsZS4gUGxlYXNlIHJlY29ubmVjdCB5b3VyIEdtYWlsIGFjY291bnQuJyxcbiAgICAgICAgfSk7XG4gICAgfVxuICAgIHJldHVybiByZXMuc3RhdHVzKDUwMCkuanNvbih7XG4gICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgIG1lc3NhZ2U6XG4gICAgICAgICdBbiBlcnJvciBvY2N1cnJlZCB3aGlsZSByZWZyZXNoaW5nIEdtYWlsIHRva2VuOiAnICtcbiAgICAgICAgKGUubWVzc2FnZSB8fCAnVW5rbm93biBlcnJvcicpLFxuICAgIH0pO1xuICB9XG59O1xuXG5leHBvcnQgZGVmYXVsdCBoYW5kbGVyO1xuIl19