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
const handler = async (req, res) => {
    const userId = req.body.session_variables['x-hasura-user-id'];
    if (!userId) {
        // This case should ideally be blocked by Hasura permissions if session_variables are required
        return res
            .status(401)
            .json({
            isConnected: false,
            userEmail: null,
            message: 'Unauthorized: User ID missing.',
        });
    }
    const adminGraphQLClient = createAdminGraphQLClient();
    try {
        const tokenRecordResult = await adminGraphQLClient.request(GET_USER_GMAIL_ACCESS_TOKEN_QUERY, { userId });
        if (!tokenRecordResult.user_gmail_tokens ||
            tokenRecordResult.user_gmail_tokens.length === 0) {
            return res.status(200).json({ isConnected: false, userEmail: null });
        }
        const tokenRecord = tokenRecordResult.user_gmail_tokens[0];
        if (!tokenRecord.encrypted_access_token) {
            // This implies a record exists but the access token is missing, which is an inconsistent state.
            // Treat as not connected or needing re-authentication.
            console.warn(`[Connection Status] Token record exists for user ${userId} but no encrypted_access_token found.`);
            return res
                .status(200)
                .json({
                isConnected: false,
                userEmail: null,
                message: 'Connection data incomplete.',
            });
        }
        let userEmailFromGoogle = null;
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
            }
            else {
                console.error(`[Connection Status] Failed to decrypt access token for user ${userId}. Encryption key issue or corrupt data.`);
                // Cannot verify connection without decrypted token.
            }
        }
        catch (googleApiError) {
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
                userEmail: userEmailFromGoogle,
            });
        }
        else {
            // Tokens are stored, but we couldn't verify them with Google API (e.g. stale, revoked, decryption failed)
            // The frontend might interpret this as "Connected, but needs attention" or "Attempting to reconnect..."
            // For simplicity in this boolean status, if we can't get email, let's say connection is not fully active.
            // However, if we just check for token *existence* then isConnected would be true here.
            // Let's return isConnected based on token existence, but userEmail indicates validity.
            return res.status(200).json({
                isConnected: true, // Record exists
                userEmail: userEmailFromGoogle, // null if API call failed
                message: userEmailFromGoogle
                    ? undefined
                    : 'Stored token might be invalid or expired.',
            });
        }
    }
    catch (e) {
        console.error(`[Connection Status] Outer error for user ${userId}:`, e);
        return res
            .status(500)
            .json({
            isConnected: false,
            userEmail: null,
            message: 'Error checking connection status.',
        });
    }
};
export default handler;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0LWdtYWlsLWNvbm5lY3Rpb24tc3RhdHVzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZ2V0LWdtYWlsLWNvbm5lY3Rpb24tc3RhdHVzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUNBLE9BQU8sRUFBRSx3QkFBd0IsRUFBRSxNQUFNLHFCQUFxQixDQUFDLENBQUMsY0FBYztBQUM5RSxPQUFPLEVBQUUsTUFBTSxFQUFFLE1BQU0sWUFBWSxDQUFDO0FBQ3BDLE9BQU8sRUFBRSxPQUFPLEVBQUUsTUFBTSw4QkFBOEIsQ0FBQyxDQUFDLG9EQUFvRDtBQUU1Ryx3Q0FBd0M7QUFDeEMsTUFBTSxpQ0FBaUMsR0FBRzs7Ozs7OztDQU96QyxDQUFDO0FBZ0JGLE1BQU0sT0FBTyxHQUFHLEtBQUssRUFDbkIsR0FBeUQsRUFDekQsR0FBNEMsRUFDNUMsRUFBRTtJQUNGLE1BQU0sTUFBTSxHQUFHLEdBQUcsQ0FBQyxJQUFJLENBQUMsaUJBQWlCLENBQUMsa0JBQWtCLENBQUMsQ0FBQztJQUU5RCxJQUFJLENBQUMsTUFBTSxFQUFFLENBQUM7UUFDWiw4RkFBOEY7UUFDOUYsT0FBTyxHQUFHO2FBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQzthQUNYLElBQUksQ0FBQztZQUNKLFdBQVcsRUFBRSxLQUFLO1lBQ2xCLFNBQVMsRUFBRSxJQUFJO1lBQ2YsT0FBTyxFQUFFLGdDQUFnQztTQUMxQyxDQUFDLENBQUM7SUFDUCxDQUFDO0lBRUQsTUFBTSxrQkFBa0IsR0FBRyx3QkFBd0IsRUFBRSxDQUFDO0lBRXRELElBQUksQ0FBQztRQUNILE1BQU0saUJBQWlCLEdBQUcsTUFBTSxrQkFBa0IsQ0FBQyxPQUFPLENBQ3hELGlDQUFpQyxFQUNqQyxFQUFFLE1BQU0sRUFBRSxDQUNYLENBQUM7UUFFRixJQUNFLENBQUMsaUJBQWlCLENBQUMsaUJBQWlCO1lBQ3BDLGlCQUFpQixDQUFDLGlCQUFpQixDQUFDLE1BQU0sS0FBSyxDQUFDLEVBQ2hELENBQUM7WUFDRCxPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDLEVBQUUsV0FBVyxFQUFFLEtBQUssRUFBRSxTQUFTLEVBQUUsSUFBSSxFQUFFLENBQUMsQ0FBQztRQUN2RSxDQUFDO1FBRUQsTUFBTSxXQUFXLEdBQUcsaUJBQWlCLENBQUMsaUJBQWlCLENBQUMsQ0FBQyxDQUFDLENBQUM7UUFFM0QsSUFBSSxDQUFDLFdBQVcsQ0FBQyxzQkFBc0IsRUFBRSxDQUFDO1lBQ3hDLGdHQUFnRztZQUNoRyx1REFBdUQ7WUFDdkQsT0FBTyxDQUFDLElBQUksQ0FDVixvREFBb0QsTUFBTSx1Q0FBdUMsQ0FDbEcsQ0FBQztZQUNGLE9BQU8sR0FBRztpQkFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2lCQUNYLElBQUksQ0FBQztnQkFDSixXQUFXLEVBQUUsS0FBSztnQkFDbEIsU0FBUyxFQUFFLElBQUk7Z0JBQ2YsT0FBTyxFQUFFLDZCQUE2QjthQUN2QyxDQUFDLENBQUM7UUFDUCxDQUFDO1FBRUQsSUFBSSxtQkFBbUIsR0FBa0IsSUFBSSxDQUFDO1FBQzlDLElBQUksc0JBQXNCLEdBQUcsS0FBSyxDQUFDO1FBRW5DLElBQUksQ0FBQztZQUNILE1BQU0sb0JBQW9CLEdBQUcsV0FBVyxDQUFDLHNCQUFzQixDQUFDO1lBQ2hFLE1BQU0sV0FBVyxHQUFHLE9BQU8sQ0FBQyxvQkFBb0IsQ0FBQyxDQUFDLENBQUMsaURBQWlEO1lBRXBHLElBQUksV0FBVyxFQUFFLENBQUM7Z0JBQ2hCLE1BQU0sWUFBWSxHQUFHLElBQUksTUFBTSxDQUFDLElBQUksQ0FBQyxNQUFNLEVBQUUsQ0FBQztnQkFDOUMsWUFBWSxDQUFDLGNBQWMsQ0FBQyxFQUFFLFlBQVksRUFBRSxXQUFXLEVBQUUsQ0FBQyxDQUFDO2dCQUMzRCxNQUFNLE1BQU0sR0FBRyxNQUFNLENBQUMsTUFBTSxDQUFDLEVBQUUsT0FBTyxFQUFFLElBQUksRUFBRSxJQUFJLEVBQUUsWUFBWSxFQUFFLENBQUMsQ0FBQztnQkFDcEUsTUFBTSxRQUFRLEdBQUcsTUFBTSxNQUFNLENBQUMsUUFBUSxDQUFDLEdBQUcsRUFBRSxDQUFDLENBQUMsbURBQW1EO2dCQUVqRyxtQkFBbUIsR0FBRyxRQUFRLENBQUMsSUFBSSxDQUFDLEtBQUssSUFBSSxJQUFJLENBQUM7Z0JBQ2xELHNCQUFzQixHQUFHLENBQUMsQ0FBQyxtQkFBbUIsQ0FBQyxDQUFDLGtDQUFrQztnQkFFbEYsSUFBSSxDQUFDLHNCQUFzQixFQUFFLENBQUM7b0JBQzVCLE9BQU8sQ0FBQyxJQUFJLENBQ1YsNkVBQTZFLE1BQU0sc0VBQXNFLENBQzFKLENBQUM7Z0JBQ0osQ0FBQztZQUNILENBQUM7aUJBQU0sQ0FBQztnQkFDTixPQUFPLENBQUMsS0FBSyxDQUNYLCtEQUErRCxNQUFNLHlDQUF5QyxDQUMvRyxDQUFDO2dCQUNGLG9EQUFvRDtZQUN0RCxDQUFDO1FBQ0gsQ0FBQztRQUFDLE9BQU8sY0FBbUIsRUFBRSxDQUFDO1lBQzdCLE9BQU8sQ0FBQyxJQUFJLENBQ1YsdUVBQXVFLE1BQU0sWUFBWSxjQUFjLENBQUMsT0FBTyxvQ0FBb0MsQ0FDcEosQ0FBQztZQUNGLG9HQUFvRztZQUNwRyxtRkFBbUY7WUFDbkYsdUZBQXVGO1lBQ3ZGLHVFQUF1RTtZQUN2RSxzQkFBc0IsR0FBRyxLQUFLLENBQUM7WUFDL0Isa0VBQWtFO1lBQ2xFLDRFQUE0RTtRQUM5RSxDQUFDO1FBRUQsSUFBSSxzQkFBc0IsRUFBRSxDQUFDO1lBQzNCLE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUM7Z0JBQzFCLFdBQVcsRUFBRSxJQUFJO2dCQUNqQixTQUFTLEVBQUUsbUJBQW1CO2FBQy9CLENBQUMsQ0FBQztRQUNMLENBQUM7YUFBTSxDQUFDO1lBQ04sMEdBQTBHO1lBQzFHLHdHQUF3RztZQUN4RywwR0FBMEc7WUFDMUcsdUZBQXVGO1lBQ3ZGLHVGQUF1RjtZQUN2RixPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDO2dCQUMxQixXQUFXLEVBQUUsSUFBSSxFQUFFLGdCQUFnQjtnQkFDbkMsU0FBUyxFQUFFLG1CQUFtQixFQUFFLDBCQUEwQjtnQkFDMUQsT0FBTyxFQUFFLG1CQUFtQjtvQkFDMUIsQ0FBQyxDQUFDLFNBQVM7b0JBQ1gsQ0FBQyxDQUFDLDJDQUEyQzthQUNoRCxDQUFDLENBQUM7UUFDTCxDQUFDO0lBQ0gsQ0FBQztJQUFDLE9BQU8sQ0FBTSxFQUFFLENBQUM7UUFDaEIsT0FBTyxDQUFDLEtBQUssQ0FBQyw0Q0FBNEMsTUFBTSxHQUFHLEVBQUUsQ0FBQyxDQUFDLENBQUM7UUFDeEUsT0FBTyxHQUFHO2FBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQzthQUNYLElBQUksQ0FBQztZQUNKLFdBQVcsRUFBRSxLQUFLO1lBQ2xCLFNBQVMsRUFBRSxJQUFJO1lBQ2YsT0FBTyxFQUFFLG1DQUFtQztTQUM3QyxDQUFDLENBQUM7SUFDUCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBRUYsZUFBZSxPQUFPLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBSZXF1ZXN0LCBSZXNwb25zZSB9IGZyb20gJ2V4cHJlc3MnO1xuaW1wb3J0IHsgY3JlYXRlQWRtaW5HcmFwaFFMQ2xpZW50IH0gZnJvbSAnLi4vX3V0aWxzL2RiU2VydmljZSc7IC8vIEFkanVzdCBwYXRoXG5pbXBvcnQgeyBnb29nbGUgfSBmcm9tICdnb29nbGVhcGlzJztcbmltcG9ydCB7IGRlY3J5cHQgfSBmcm9tICcuL2hhbmRsZS1nbWFpbC1hdXRoLWNhbGxiYWNrJzsgLy8gQXNzdW1pbmcgZGVjcnlwdCBpcyBleHBvcnRlZCBhbmQga2V5IGlzIGF2YWlsYWJsZVxuXG4vLyBHcmFwaFFMIHF1ZXJ5IHRvIGdldCB0aGUgYWNjZXNzIHRva2VuXG5jb25zdCBHRVRfVVNFUl9HTUFJTF9BQ0NFU1NfVE9LRU5fUVVFUlkgPSBgXG5xdWVyeSBHZXRVc2VyR21haWxBY2Nlc3NUb2tlbkZvclN0YXR1cygkdXNlcklkOiB1dWlkISkge1xuICB1c2VyX2dtYWlsX3Rva2Vucyh3aGVyZToge3VzZXJfaWQ6IHtfZXE6ICR1c2VySWR9fSwgbGltaXQ6IDEpIHtcbiAgICBlbmNyeXB0ZWRfYWNjZXNzX3Rva2VuXG4gICAgIyBXZSBjb3VsZCBhbHNvIGZldGNoIHJlZnJlc2ggdG9rZW4gaGVyZSBpZiB3ZSB3YW50IHRvIGF0dGVtcHQgYSByZWZyZXNoIG9uIGZhaWx1cmVcbiAgfVxufVxuYDtcblxuaW50ZXJmYWNlIEdldEdtYWlsQ29ubmVjdGlvblN0YXR1c1JlcXVlc3RCb2R5IHtcbiAgc2Vzc2lvbl92YXJpYWJsZXM6IHtcbiAgICAneC1oYXN1cmEtdXNlci1pZCc6IHN0cmluZztcbiAgfTtcbiAgLy8gTm8gc3BlY2lmaWMgaW5wdXQgYXJncyBmcm9tIGNsaWVudCBmb3IgdGhpcyBxdWVyeSBhY3Rpb25cbn1cblxuLy8gTWF0Y2hlcyBHbWFpbENvbm5lY3Rpb25TdGF0dXNPdXRwdXQgaW4gYWN0aW9ucy5ncmFwaHFsXG5pbnRlcmZhY2UgR21haWxDb25uZWN0aW9uU3RhdHVzUmVzcG9uc2Uge1xuICBpc0Nvbm5lY3RlZDogYm9vbGVhbjtcbiAgdXNlckVtYWlsPzogc3RyaW5nIHwgbnVsbDtcbiAgbWVzc2FnZT86IHN0cmluZzsgLy8gT3B0aW9uYWwgbWVzc2FnZSBmb3IgZXJyb3JzIG9yIHN0YXR1c1xufVxuXG5jb25zdCBoYW5kbGVyID0gYXN5bmMgKFxuICByZXE6IFJlcXVlc3Q8e30sIHt9LCBHZXRHbWFpbENvbm5lY3Rpb25TdGF0dXNSZXF1ZXN0Qm9keT4sXG4gIHJlczogUmVzcG9uc2U8R21haWxDb25uZWN0aW9uU3RhdHVzUmVzcG9uc2U+XG4pID0+IHtcbiAgY29uc3QgdXNlcklkID0gcmVxLmJvZHkuc2Vzc2lvbl92YXJpYWJsZXNbJ3gtaGFzdXJhLXVzZXItaWQnXTtcblxuICBpZiAoIXVzZXJJZCkge1xuICAgIC8vIFRoaXMgY2FzZSBzaG91bGQgaWRlYWxseSBiZSBibG9ja2VkIGJ5IEhhc3VyYSBwZXJtaXNzaW9ucyBpZiBzZXNzaW9uX3ZhcmlhYmxlcyBhcmUgcmVxdWlyZWRcbiAgICByZXR1cm4gcmVzXG4gICAgICAuc3RhdHVzKDQwMSlcbiAgICAgIC5qc29uKHtcbiAgICAgICAgaXNDb25uZWN0ZWQ6IGZhbHNlLFxuICAgICAgICB1c2VyRW1haWw6IG51bGwsXG4gICAgICAgIG1lc3NhZ2U6ICdVbmF1dGhvcml6ZWQ6IFVzZXIgSUQgbWlzc2luZy4nLFxuICAgICAgfSk7XG4gIH1cblxuICBjb25zdCBhZG1pbkdyYXBoUUxDbGllbnQgPSBjcmVhdGVBZG1pbkdyYXBoUUxDbGllbnQoKTtcblxuICB0cnkge1xuICAgIGNvbnN0IHRva2VuUmVjb3JkUmVzdWx0ID0gYXdhaXQgYWRtaW5HcmFwaFFMQ2xpZW50LnJlcXVlc3QoXG4gICAgICBHRVRfVVNFUl9HTUFJTF9BQ0NFU1NfVE9LRU5fUVVFUlksXG4gICAgICB7IHVzZXJJZCB9XG4gICAgKTtcblxuICAgIGlmIChcbiAgICAgICF0b2tlblJlY29yZFJlc3VsdC51c2VyX2dtYWlsX3Rva2VucyB8fFxuICAgICAgdG9rZW5SZWNvcmRSZXN1bHQudXNlcl9nbWFpbF90b2tlbnMubGVuZ3RoID09PSAwXG4gICAgKSB7XG4gICAgICByZXR1cm4gcmVzLnN0YXR1cygyMDApLmpzb24oeyBpc0Nvbm5lY3RlZDogZmFsc2UsIHVzZXJFbWFpbDogbnVsbCB9KTtcbiAgICB9XG5cbiAgICBjb25zdCB0b2tlblJlY29yZCA9IHRva2VuUmVjb3JkUmVzdWx0LnVzZXJfZ21haWxfdG9rZW5zWzBdO1xuXG4gICAgaWYgKCF0b2tlblJlY29yZC5lbmNyeXB0ZWRfYWNjZXNzX3Rva2VuKSB7XG4gICAgICAvLyBUaGlzIGltcGxpZXMgYSByZWNvcmQgZXhpc3RzIGJ1dCB0aGUgYWNjZXNzIHRva2VuIGlzIG1pc3NpbmcsIHdoaWNoIGlzIGFuIGluY29uc2lzdGVudCBzdGF0ZS5cbiAgICAgIC8vIFRyZWF0IGFzIG5vdCBjb25uZWN0ZWQgb3IgbmVlZGluZyByZS1hdXRoZW50aWNhdGlvbi5cbiAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgYFtDb25uZWN0aW9uIFN0YXR1c10gVG9rZW4gcmVjb3JkIGV4aXN0cyBmb3IgdXNlciAke3VzZXJJZH0gYnV0IG5vIGVuY3J5cHRlZF9hY2Nlc3NfdG9rZW4gZm91bmQuYFxuICAgICAgKTtcbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cygyMDApXG4gICAgICAgIC5qc29uKHtcbiAgICAgICAgICBpc0Nvbm5lY3RlZDogZmFsc2UsXG4gICAgICAgICAgdXNlckVtYWlsOiBudWxsLFxuICAgICAgICAgIG1lc3NhZ2U6ICdDb25uZWN0aW9uIGRhdGEgaW5jb21wbGV0ZS4nLFxuICAgICAgICB9KTtcbiAgICB9XG5cbiAgICBsZXQgdXNlckVtYWlsRnJvbUdvb2dsZTogc3RyaW5nIHwgbnVsbCA9IG51bGw7XG4gICAgbGV0IGlzRWZmZWN0aXZlbHlDb25uZWN0ZWQgPSBmYWxzZTtcblxuICAgIHRyeSB7XG4gICAgICBjb25zdCBlbmNyeXB0ZWRBY2Nlc3NUb2tlbiA9IHRva2VuUmVjb3JkLmVuY3J5cHRlZF9hY2Nlc3NfdG9rZW47XG4gICAgICBjb25zdCBhY2Nlc3NUb2tlbiA9IGRlY3J5cHQoZW5jcnlwdGVkQWNjZXNzVG9rZW4pOyAvLyBFbnN1cmUgR01BSUxfVE9LRU5fRU5DUllQVElPTl9LRVkgaXMgYXZhaWxhYmxlXG5cbiAgICAgIGlmIChhY2Nlc3NUb2tlbikge1xuICAgICAgICBjb25zdCBvYXV0aDJDbGllbnQgPSBuZXcgZ29vZ2xlLmF1dGguT0F1dGgyKCk7XG4gICAgICAgIG9hdXRoMkNsaWVudC5zZXRDcmVkZW50aWFscyh7IGFjY2Vzc190b2tlbjogYWNjZXNzVG9rZW4gfSk7XG4gICAgICAgIGNvbnN0IG9hdXRoMiA9IGdvb2dsZS5vYXV0aDIoeyB2ZXJzaW9uOiAndjInLCBhdXRoOiBvYXV0aDJDbGllbnQgfSk7XG4gICAgICAgIGNvbnN0IHVzZXJJbmZvID0gYXdhaXQgb2F1dGgyLnVzZXJpbmZvLmdldCgpOyAvLyBGZXRjaGVzIGVtYWlsLCBwcm9maWxlLCBvcGVuaWQgc2NvcGVzIGJ5IGRlZmF1bHRcblxuICAgICAgICB1c2VyRW1haWxGcm9tR29vZ2xlID0gdXNlckluZm8uZGF0YS5lbWFpbCB8fCBudWxsO1xuICAgICAgICBpc0VmZmVjdGl2ZWx5Q29ubmVjdGVkID0gISF1c2VyRW1haWxGcm9tR29vZ2xlOyAvLyBJZiB3ZSBnZXQgZW1haWwsIHRva2VuIGlzIHZhbGlkXG5cbiAgICAgICAgaWYgKCFpc0VmZmVjdGl2ZWx5Q29ubmVjdGVkKSB7XG4gICAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgICAgYFtDb25uZWN0aW9uIFN0YXR1c10gQ291bGQgbm90IHJldHJpZXZlIHVzZXIgZW1haWwgdmlhIEdvb2dsZSBBUEkgZm9yIHVzZXIgJHt1c2VySWR9LCB0aG91Z2ggdG9rZW4gd2FzIGRlY3J5cHRlZC4gVG9rZW4gbWlnaHQgYmUgaW52YWxpZCBvciBsYWNrIHNjb3Blcy5gXG4gICAgICAgICAgKTtcbiAgICAgICAgfVxuICAgICAgfSBlbHNlIHtcbiAgICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgICBgW0Nvbm5lY3Rpb24gU3RhdHVzXSBGYWlsZWQgdG8gZGVjcnlwdCBhY2Nlc3MgdG9rZW4gZm9yIHVzZXIgJHt1c2VySWR9LiBFbmNyeXB0aW9uIGtleSBpc3N1ZSBvciBjb3JydXB0IGRhdGEuYFxuICAgICAgICApO1xuICAgICAgICAvLyBDYW5ub3QgdmVyaWZ5IGNvbm5lY3Rpb24gd2l0aG91dCBkZWNyeXB0ZWQgdG9rZW4uXG4gICAgICB9XG4gICAgfSBjYXRjaCAoZ29vZ2xlQXBpRXJyb3I6IGFueSkge1xuICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICBgW0Nvbm5lY3Rpb24gU3RhdHVzXSBHb29nbGUgQVBJIGVycm9yIHdoaWxlIHZlcmlmeWluZyB0b2tlbiBmb3IgdXNlciAke3VzZXJJZH0uIEVycm9yOiAke2dvb2dsZUFwaUVycm9yLm1lc3NhZ2V9LiBUb2tlbiBtaWdodCBiZSBzdGFsZSBvciByZXZva2VkLmBcbiAgICAgICk7XG4gICAgICAvLyBpc0VmZmVjdGl2ZWx5Q29ubmVjdGVkIHJlbWFpbnMgZmFsc2UuIFdlIGtub3cgdG9rZW5zIGFyZSAqc3RvcmVkKiwgYnV0IHRoZXkgbWlnaHQgbm90IGJlICp2YWxpZCouXG4gICAgICAvLyBGb3IgdGhlIHB1cnBvc2Ugb2YgXCJpc0Nvbm5lY3RlZFwiLCBpZiB0b2tlbnMgYXJlIHN0b3JlZCwgd2UgbWlnaHQgc3RpbGwgc2F5IHRydWUsXG4gICAgICAvLyBidXQgdGhlIGZyb250ZW5kIGNhbiB1c2UgdGhlIGFic2VuY2Ugb2YgdXNlckVtYWlsIHRvIHByb21wdCBmb3IgcmUtY2hlY2sgb3IgcmUtYXV0aC5cbiAgICAgIC8vIExldCdzIGJlIHN0cmljdGVyOiBpZiBBUEkgY2FsbCBmYWlscywgc2F5IG5vdCBlZmZlY3RpdmVseSBjb25uZWN0ZWQuXG4gICAgICBpc0VmZmVjdGl2ZWx5Q29ubmVjdGVkID0gZmFsc2U7XG4gICAgICAvLyBJZiB3ZSBoYWQgcmVmcmVzaCB0b2tlbiBsb2dpYyBoZXJlLCB3ZSBjb3VsZCBhdHRlbXB0IGEgcmVmcmVzaC5cbiAgICAgIC8vIEZvciBub3csIGEgZmFpbGVkIEFQSSBjYWxsIG1lYW5zIHRoZSBjdXJyZW50IGFjY2VzcyB0b2tlbiBpcyBub3Qgd29ya2luZy5cbiAgICB9XG5cbiAgICBpZiAoaXNFZmZlY3RpdmVseUNvbm5lY3RlZCkge1xuICAgICAgcmV0dXJuIHJlcy5zdGF0dXMoMjAwKS5qc29uKHtcbiAgICAgICAgaXNDb25uZWN0ZWQ6IHRydWUsXG4gICAgICAgIHVzZXJFbWFpbDogdXNlckVtYWlsRnJvbUdvb2dsZSxcbiAgICAgIH0pO1xuICAgIH0gZWxzZSB7XG4gICAgICAvLyBUb2tlbnMgYXJlIHN0b3JlZCwgYnV0IHdlIGNvdWxkbid0IHZlcmlmeSB0aGVtIHdpdGggR29vZ2xlIEFQSSAoZS5nLiBzdGFsZSwgcmV2b2tlZCwgZGVjcnlwdGlvbiBmYWlsZWQpXG4gICAgICAvLyBUaGUgZnJvbnRlbmQgbWlnaHQgaW50ZXJwcmV0IHRoaXMgYXMgXCJDb25uZWN0ZWQsIGJ1dCBuZWVkcyBhdHRlbnRpb25cIiBvciBcIkF0dGVtcHRpbmcgdG8gcmVjb25uZWN0Li4uXCJcbiAgICAgIC8vIEZvciBzaW1wbGljaXR5IGluIHRoaXMgYm9vbGVhbiBzdGF0dXMsIGlmIHdlIGNhbid0IGdldCBlbWFpbCwgbGV0J3Mgc2F5IGNvbm5lY3Rpb24gaXMgbm90IGZ1bGx5IGFjdGl2ZS5cbiAgICAgIC8vIEhvd2V2ZXIsIGlmIHdlIGp1c3QgY2hlY2sgZm9yIHRva2VuICpleGlzdGVuY2UqIHRoZW4gaXNDb25uZWN0ZWQgd291bGQgYmUgdHJ1ZSBoZXJlLlxuICAgICAgLy8gTGV0J3MgcmV0dXJuIGlzQ29ubmVjdGVkIGJhc2VkIG9uIHRva2VuIGV4aXN0ZW5jZSwgYnV0IHVzZXJFbWFpbCBpbmRpY2F0ZXMgdmFsaWRpdHkuXG4gICAgICByZXR1cm4gcmVzLnN0YXR1cygyMDApLmpzb24oe1xuICAgICAgICBpc0Nvbm5lY3RlZDogdHJ1ZSwgLy8gUmVjb3JkIGV4aXN0c1xuICAgICAgICB1c2VyRW1haWw6IHVzZXJFbWFpbEZyb21Hb29nbGUsIC8vIG51bGwgaWYgQVBJIGNhbGwgZmFpbGVkXG4gICAgICAgIG1lc3NhZ2U6IHVzZXJFbWFpbEZyb21Hb29nbGVcbiAgICAgICAgICA/IHVuZGVmaW5lZFxuICAgICAgICAgIDogJ1N0b3JlZCB0b2tlbiBtaWdodCBiZSBpbnZhbGlkIG9yIGV4cGlyZWQuJyxcbiAgICAgIH0pO1xuICAgIH1cbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcihgW0Nvbm5lY3Rpb24gU3RhdHVzXSBPdXRlciBlcnJvciBmb3IgdXNlciAke3VzZXJJZH06YCwgZSk7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAuanNvbih7XG4gICAgICAgIGlzQ29ubmVjdGVkOiBmYWxzZSxcbiAgICAgICAgdXNlckVtYWlsOiBudWxsLFxuICAgICAgICBtZXNzYWdlOiAnRXJyb3IgY2hlY2tpbmcgY29ubmVjdGlvbiBzdGF0dXMuJyxcbiAgICAgIH0pO1xuICB9XG59O1xuXG5leHBvcnQgZGVmYXVsdCBoYW5kbGVyO1xuIl19