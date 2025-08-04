// Adjust the path based on the final location of mcp-service relative to google-api-auth
import { getMcpUserTokens } from '../google-api-auth/_libs/api-helper';
import { googleMcpRedirectUrl } from '../google-api-auth/_libs/constants';
// Assuming a utility for admin client, adjust path as necessary
import { createAdminGraphQLClient } from '../_utils/dbService';
import { encrypt } from '../_utils/crypto';
const ENCRYPTION_KEY_HEX = process.env.MCP_TOKEN_ENCRYPTION_KEY;
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
const handler = async (req, res) => {
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
        console.error('MCP_TOKEN_ENCRYPTION_KEY is not set. Please configure a 64-character hex key (32 bytes).');
        return res
            .status(500)
            .json({
            success: false,
            message: 'Server configuration error: Encryption key not configured.',
        });
    }
    try {
        Buffer.from(ENCRYPTION_KEY_HEX, 'hex'); // Validate hex format early
    }
    catch (e) {
        console.error('MCP_TOKEN_ENCRYPTION_KEY is not a valid hex string.');
        return res
            .status(500)
            .json({
            success: false,
            message: 'Server configuration error: Invalid encryption key format.',
        });
    }
    if (Buffer.from(ENCRYPTION_KEY_HEX, 'hex').length !== 32) {
        console.error('MCP_TOKEN_ENCRYPTION_KEY must be 32 bytes (64 hex characters).');
        return res
            .status(500)
            .json({
            success: false,
            message: 'Server configuration error: Invalid encryption key length.',
        });
    }
    const adminGraphQLClient = createAdminGraphQLClient();
    try {
        const redirectUri = googleMcpRedirectUrl;
        if (!redirectUri) {
            console.error('GOOGLE_MCP_REDIRECT_URL environment variable is not configured.');
            return res
                .status(500)
                .json({
                success: false,
                message: 'Server configuration error: Missing redirect URL for Mcp integration.',
            });
        }
        const tokens = await getMcpUserTokens(code, redirectUri);
        if (!tokens.access_token) {
            console.error('Failed to obtain access token from Google.');
            return res
                .status(500)
                .json({
                success: false,
                message: 'Failed to obtain access token from Google.',
            });
        }
        const encryptedAccessToken = encrypt(tokens.access_token, ENCRYPTION_KEY_HEX);
        let encryptedRefreshToken = null;
        if (tokens.refresh_token) {
            encryptedRefreshToken = encrypt(tokens.refresh_token, ENCRYPTION_KEY_HEX);
        }
        const expiryTimestamp = tokens.expiry_date
            ? new Date(tokens.expiry_date).toISOString()
            : null;
        // Scopes from Google are space-separated string. Convert to JSON array for storage.
        const scopesArray = tokens.scope ? tokens.scope.split(' ') : [];
        await adminGraphQLClient.request(UPSERT_MCP_TOKEN_MUTATION, {
            userId: userId,
            accessToken: encryptedAccessToken,
            refreshToken: encryptedRefreshToken,
            expiryTimestamp: expiryTimestamp,
            scopesArr: scopesArray, // Pass as JSON array
        });
        return res
            .status(200)
            .json({ success: true, message: 'Mcp account connected successfully.' });
    }
    catch (e) {
        console.error('Error handling Mcp auth callback:', e);
        let clientMessage = 'Failed to connect Mcp account due to an unexpected error.';
        if (e.message) {
            if (e.message.includes('bad_verification_code') ||
                e.message.includes('invalid_grant')) {
                clientMessage =
                    'Invalid or expired authorization code. Please try connecting your Mcp account again.';
            }
            else if (e.message.includes('redirect_uri_mismatch')) {
                clientMessage = 'Redirect URI mismatch. Please contact support.';
            }
            else if (e.message.toLowerCase().includes('encryption')) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaGFuZGxlLWF1dGgtY2FsbGJhY2suanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJoYW5kbGUtYXV0aC1jYWxsYmFjay50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFHQSx5RkFBeUY7QUFDekYsT0FBTyxFQUFFLGdCQUFnQixFQUFFLE1BQU0scUNBQXFDLENBQUM7QUFDdkUsT0FBTyxFQUFFLG9CQUFvQixFQUFFLE1BQU0sb0NBQW9DLENBQUM7QUFDMUUsZ0VBQWdFO0FBQ2hFLE9BQU8sRUFBRSx3QkFBd0IsRUFBRSxNQUFNLHFCQUFxQixDQUFDO0FBQy9ELE9BQU8sRUFBRSxPQUFPLEVBQVcsTUFBTSxrQkFBa0IsQ0FBQztBQUVwRCxNQUFNLGtCQUFrQixHQUFHLE9BQU8sQ0FBQyxHQUFHLENBQUMsd0JBQXdCLENBQUM7QUFZaEUsbUdBQW1HO0FBQ25HLHFDQUFxQztBQUNyQyxrR0FBa0c7QUFDbEcsTUFBTSx5QkFBeUIsR0FBRzs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQW1CakMsQ0FBQztBQUVGLE1BQU0sT0FBTyxHQUFHLEtBQUssRUFDbkIsR0FBc0QsRUFDdEQsR0FBYSxFQUNiLEVBQUU7SUFDRixNQUFNLEVBQUUsSUFBSSxFQUFFLEdBQUcsR0FBRyxDQUFDLElBQUksQ0FBQyxLQUFLLENBQUM7SUFDaEMsTUFBTSxNQUFNLEdBQUcsR0FBRyxDQUFDLElBQUksQ0FBQyxpQkFBaUIsQ0FBQyxrQkFBa0IsQ0FBQyxDQUFDO0lBRTlELElBQUksQ0FBQyxJQUFJLEVBQUUsQ0FBQztRQUNWLE9BQU8sR0FBRzthQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7YUFDWCxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxnQ0FBZ0MsRUFBRSxDQUFDLENBQUM7SUFDekUsQ0FBQztJQUNELElBQUksQ0FBQyxNQUFNLEVBQUUsQ0FBQztRQUNaLE9BQU8sR0FBRzthQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7YUFDWCxJQUFJLENBQUMs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QUFDLENBQUMsSUFBSSxDQUFDO1lBQzFCLE9BQU8sRUFBRSxLQUFLO1lBQ2QsT0FBTyxFQUFFLGFBQWE7U0FDdkIsQ0FBQyxDQUFDO0lBQ0wsQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLGVBQWUsT0FBTyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgUmVxdWVzdCwgUmVzcG9uc2UgfSBmcm9tICdleHByZXNzJztcbmltcG9ydCB7IGdvb2dsZSB9IGZyb20gJ2dvb2dsZWFwaXMnO1xuaW1wb3J0IGNyeXB0byBmcm9tICdjcnlwdG8nO1xuLy8gQWRqdXN0IHRoZSBwYXRoIGJhc2VkIG9uIHRoZSBmaW5hbCBsb2NhdGlvbiBvZiBtY3Atc2VydmljZSByZWxhdGl2ZSB0byBnb29nbGUtYXBpLWF1dGhcbmltcG9ydCB7IGdldE1jcFVzZXJUb2tlbnMgfSBmcm9tICcuLi9nb29nbGUtYXBpLWF1dGgvX2xpYnMvYXBpLWhlbHBlcic7XG5pbXBvcnQgeyBnb29nbGVNY3BSZWRpcmVjdFVybCB9IGZyb20gJy4uL2dvb2dsZS1hcGktYXV0aC9fbGlicy9jb25zdGFudHMnO1xuLy8gQXNzdW1pbmcgYSB1dGlsaXR5IGZvciBhZG1pbiBjbGllbnQsIGFkanVzdCBwYXRoIGFzIG5lY2Vzc2FyeVxuaW1wb3J0IHsgY3JlYXRlQWRtaW5HcmFwaFFMQ2xpZW50IH0gZnJvbSAnLi4vX3V0aWxzL2RiU2VydmljZSc7XG5pbXBvcnQgeyBlbmNyeXB0LCBkZWNyeXB0IH0gZnJvbSAnLi4vX3V0aWxzL2NyeXB0byc7XG5cbmNvbnN0IEVOQ1JZUFRJT05fS0VZX0hFWCA9IHByb2Nlc3MuZW52Lk1DUF9UT0tFTl9FTkNSWVBUSU9OX0tFWTtcblxuaW50ZXJmYWNlIEhhbmRsZU1jcEF1dGhDYWxsYmFja1JlcXVlc3RCb2R5IHtcbiAgc2Vzc2lvbl92YXJpYWJsZXM6IHtcbiAgICAneC1oYXN1cmEtdXNlci1pZCc6IHN0cmluZztcbiAgfTtcbiAgaW5wdXQ6IHtcbiAgICBjb2RlOiBzdHJpbmc7XG4gICAgLy8gc3RhdGU/OiBzdHJpbmc7IC8vIE9wdGlvbmFsOiBpZiB5b3UgdXNlIHN0YXRlIHBhcmFtZXRlciBmb3IgQ1NSRiBwcm90ZWN0aW9uXG4gIH07XG59XG5cbi8vIE5vdGU6IFRoZSBvbl9jb25mbGljdCBjb25zdHJhaW50IGB1c2VyX21jcF90b2tlbnNfdXNlcl9pZF9rZXlgIGltcGxpZXMgdXNlcl9pZCBzaG91bGQgYmUgdW5pcXVlLlxuLy8gQWRkIHRoaXMgdG8geW91ciB1cC5zcWwgbWlncmF0aW9uOlxuLy8gQUxURVIgVEFCTEUgcHVibGljLnVzZXJfbWNwX3Rva2VucyBBREQgQ09OU1RSQUlOVCB1c2VyX21jcF90b2tlbnNfdXNlcl9pZF9rZXkgVU5JUVVFICh1c2VyX2lkKTtcbmNvbnN0IFVQU0VSVF9NQ1BfVE9LRU5fTVVUQVRJT04gPSBgXG5tdXRhdGlvbiBVcHNlcnRVc2VyTWNwVG9rZW4oJHVzZXJJZDogdXVpZCEsICRhY2Nlc3NUb2tlbjogU3RyaW5nISwgJHJlZnJlc2hUb2tlbjogU3RyaW5nLCAkZXhwaXJ5VGltZXN0YW1wOiB0aW1lc3RhbXB0eiwgJHNjb3Blc0FycjoganNvbmIpIHtcbiAgaW5zZXJ0X3VzZXJfbWNwX3Rva2Vuc19vbmUoXG4gICAgb2JqZWN0OiB7XG4gICAgICB1c2VyX2lkOiAkdXNlcklkLFxuICAgICAgZW5jcnlwdGVkX2FjY2Vzc190b2tlbjogJGFjY2Vzc1Rva2VuLFxuICAgICAgZW5jcnlwdGVkX3JlZnJlc2hfdG9rZW46ICRyZWZyZXNoVG9rZW4sXG4gICAgICB0b2tlbl9leHBpcnlfdGltZXN0YW1wOiAkZXhwaXJ5VGltZXN0YW1wLFxuICAgICAgc2NvcGVzOiAkc2NvcGVzQXJyICMgRW5zdXJlIHlvdXIgR1FMIHZhcmlhYmxlIG1hdGNoZXMgdGhlIGNvbHVtbiBuYW1lICdzY29wZXMnXG4gICAgfSxcbiAgICBvbl9jb25mbGljdDoge1xuICAgICAgY29uc3RyYWludDogdXNlcl9tY3BfdG9rZW5zX3VzZXJfaWRfa2V5LFxuICAgICAgdXBkYXRlX2NvbHVtbnM6IFtlbmNyeXB0ZWRfYWNjZXNzX3Rva2VuLCBlbmNyeXB0ZWRfcmVmcmVzaF90b2tlbiwgdG9rZW5fZXhwaXJ5X3RpbWVzdGFtcCwgc2NvcGVzLCB1cGRhdGVkX2F0XVxuICAgIH1cbiAgKSB7XG4gICAgaWRcbiAgICB1c2VyX2lkXG4gIH1cbn1cbmA7XG5cbmNvbnN0IGhhbmRsZXIgPSBhc3luYyAoXG4gIHJlcTogUmVxdWVzdDx7fSwge30sIEhhbmRsZU1jcEF1dGhDYWxsYmFja1JlcXVlc3RCb2R5PixcbiAgcmVzOiBSZXNwb25zZVxuKSA9PiB7XG4gIGNvbnN0IHsgY29kZSB9ID0gcmVxLmJvZHkuaW5wdXQ7XG4gIGNvbnN0IHVzZXJJZCA9IHJlcS5ib2R5LnNlc3Npb25fdmFyaWFibGVzWyd4LWhhc3VyYS11c2VyLWlkJ107XG5cbiAgaWYgKCFjb2RlKSB7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg0MDApXG4gICAgICAuanNvbih7IHN1Y2Nlc3M6IGZhbHNlLCBtZXNzYWdlOiAnQXV0aG9yaXphdGlvbiBjb2RlIGlzIG1pc3NpbmcuJyB9KTtcbiAgfVxuICBpZiAoIXVzZXJJZCkge1xuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoNDAwKVxuICAgICAgLmpzb24oeyBzdWNjZXNzOiBmYWxzZSwgbWVzc2FnZTogJ1VzZXIgSUQgaXMgbWlzc2luZyBmcm9tIHNlc3Npb24uJyB9KTtcbiAgfVxuICBpZiAoIUVOQ1JZUFRJT05fS0VZX0hFWCkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAnTUNQX1RPS0VOX0VOQ1JZUFRJT05fS0VZIGlzIG5vdCBzZXQuIFBsZWFzZSBjb25maWd1cmUgYSA2NC1jaGFyYWN0ZXIgaGV4IGtleSAoMzIgYnl0ZXMpLidcbiAgICApO1xuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoNTAwKVxuICAgICAgLmpzb24oe1xuICAgICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgICAgbWVzc2FnZTogJ1NlcnZlciBjb25maWd1cmF0aW9uIGVycm9yOiBFbmNyeXB0aW9uIGtleSBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSk7XG4gIH1cbiAgdHJ5IHtcbiAgICBCdWZmZXIuZnJvbShFTkNSWVBUSU9OX0tFWV9IRVgsICdoZXgnKTsgLy8gVmFsaWRhdGUgaGV4IGZvcm1hdCBlYXJseVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5lcnJvcignTUNQX1RPS0VOX0VOQ1JZUFRJT05fS0VZIGlzIG5vdCBhIHZhbGlkIGhleCBzdHJpbmcuJyk7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAuanNvbih7XG4gICAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgICBtZXNzYWdlOiAnU2VydmVyIGNvbmZpZ3VyYXRpb24gZXJyb3I6IEludmFsaWQgZW5jcnlwdGlvbiBrZXkgZm9ybWF0LicsXG4gICAgICB9KTtcbiAgfVxuICBpZiAoQnVmZmVyLmZyb20oRU5DUllQVElPTl9LRVlfSEVYLCAnaGV4JykubGVuZ3RoICE9PSAzMikge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAnTUNQX1RPS0VOX0VOQ1JZUFRJT05fS0VZIG11c3QgYmUgMzIgYnl0ZXMgKDY0IGhleCBjaGFyYWN0ZXJzKS4nXG4gICAgKTtcbiAgICByZXR1cm4gcmVzXG4gICAgICAuc3RhdHVzKDUwMClcbiAgICAgIC5qc29uKHtcbiAgICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICAgIG1lc3NhZ2U6ICdTZXJ2ZXIgY29uZmlndXJhdGlvbiBlcnJvcjogSW52YWxpZCBlbmNyeXB0aW9uIGtleSBsZW5ndGguJyxcbiAgICAgIH0pO1xuICB9XG5cbiAgY29uc3QgYWRtaW5HcmFwaFFMQ2xpZW50ID0gY3JlYXRlQWRtaW5HcmFwaFFMQ2xpZW50KCk7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZWRpcmVjdFVyaSA9IGdvb2dsZU1jcFJlZGlyZWN0VXJsO1xuICAgIGlmICghcmVkaXJlY3RVcmkpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICdHT09HTEVfTUNQX1JFRElSRUNUX1VSTCBlbnZpcm9ubWVudCB2YXJpYWJsZSBpcyBub3QgY29uZmlndXJlZC4nXG4gICAgICApO1xuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDUwMClcbiAgICAgICAgLmpzb24oe1xuICAgICAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgICAnU2VydmVyIGNvbmZpZ3VyYXRpb24gZXJyb3I6IE1pc3NpbmcgcmVkaXJlY3QgVVJMIGZvciBNY3AgaW50ZWdyYXRpb24uJyxcbiAgICAgICAgfSk7XG4gICAgfVxuXG4gICAgY29uc3QgdG9rZW5zOiBnb29nbGUuYXV0aC5DcmVkZW50aWFscyA9IGF3YWl0IGdldE1jcFVzZXJUb2tlbnMoXG4gICAgICBjb2RlLFxuICAgICAgcmVkaXJlY3RVcmlcbiAgICApO1xuXG4gICAgaWYgKCF0b2tlbnMuYWNjZXNzX3Rva2VuKSB7XG4gICAgICBjb25zb2xlLmVycm9yKCdGYWlsZWQgdG8gb2J0YWluIGFjY2VzcyB0b2tlbiBmcm9tIEdvb2dsZS4nKTtcbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAgIC5qc29uKHtcbiAgICAgICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgICAgICBtZXNzYWdlOiAnRmFpbGVkIHRvIG9idGFpbiBhY2Nlc3MgdG9rZW4gZnJvbSBHb29nbGUuJyxcbiAgICAgICAgfSk7XG4gICAgfVxuXG4gICAgY29uc3QgZW5jcnlwdGVkQWNjZXNzVG9rZW4gPSBlbmNyeXB0KFxuICAgICAgdG9rZW5zLmFjY2Vzc190b2tlbixcbiAgICAgIEVOQ1JZUFRJT05fS0VZX0hFWFxuICAgICk7XG4gICAgbGV0IGVuY3J5cHRlZFJlZnJlc2hUb2tlbjogc3RyaW5nIHwgbnVsbCA9IG51bGw7XG4gICAgaWYgKHRva2Vucy5yZWZyZXNoX3Rva2VuKSB7XG4gICAgICBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4gPSBlbmNyeXB0KHRva2Vucy5yZWZyZXNoX3Rva2VuLCBFTkNSWVBUSU9OX0tFWV9IRVgpO1xuICAgIH1cblxuICAgIGNvbnN0IGV4cGlyeVRpbWVzdGFtcCA9IHRva2Vucy5leHBpcnlfZGF0ZVxuICAgICAgPyBuZXcgRGF0ZSh0b2tlbnMuZXhwaXJ5X2RhdGUpLnRvSVNPU3RyaW5nKClcbiAgICAgIDogbnVsbDtcbiAgICAvLyBTY29wZXMgZnJvbSBHb29nbGUgYXJlIHNwYWNlLXNlcGFyYXRlZCBzdHJpbmcuIENvbnZlcnQgdG8gSlNPTiBhcnJheSBmb3Igc3RvcmFnZS5cbiAgICBjb25zdCBzY29wZXNBcnJheSA9IHRva2Vucy5zY29wZSA/IHRva2Vucy5zY29wZS5zcGxpdCgnICcpIDogW107XG5cbiAgICBhd2FpdCBhZG1pbkdyYXBoUUxDbGllbnQucmVxdWVzdChVUFNFUlRfTUNQX1RPS0VOX01VVEFUSU9OLCB7XG4gICAgICB1c2VySWQ6IHVzZXJJZCxcbiAgICAgIGFjY2Vzc1Rva2VuOiBlbmNyeXB0ZWRBY2Nlc3NUb2tlbixcbiAgICAgIHJlZnJlc2hUb2tlbjogZW5jcnlwdGVkUmVmcmVzaFRva2VuLFxuICAgICAgZXhwaXJ5VGltZXN0YW1wOiBleHBpcnlUaW1lc3RhbXAsXG4gICAgICBzY29wZXNBcnI6IHNjb3Blc0FycmF5LCAvLyBQYXNzIGFzIEpTT04gYXJyYXlcbiAgICB9KTtcblxuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoMjAwKVxuICAgICAgLmpzb24oeyBzdWNjZXNzOiB0cnVlLCBtZXNzYWdlOiAnTWNwIGFjY291bnQgY29ubmVjdGVkIHN1Y2Nlc3NmdWxseS4nIH0pO1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBoYW5kbGluZyBNY3AgYXV0aCBjYWxsYmFjazonLCBlKTtcbiAgICBsZXQgY2xpZW50TWVzc2FnZSA9XG4gICAgICAnRmFpbGVkIHRvIGNvbm5lY3QgTWNwIGFjY291bnQgZHVlIHRvIGFuIHVuZXhwZWN0ZWQgZXJyb3IuJztcbiAgICBpZiAoZS5tZXNzYWdlKSB7XG4gICAgICBpZiAoXG4gICAgICAgIGUubWVzc2FnZS5pbmNsdWRlcygnYmFkX3ZlcmlmaWNhdGlvbl9jb2RlJykgfHxcbiAgICAgICAgZS5tZXNzYWdlLmluY2x1ZGVzKCdpbnZhbGlkX2dyYW50JylcbiAgICAgICkge1xuICAgICAgICBjbGllbnRNZXNzYWdlID1cbiAgICAgICAgICAnSW52YWxpZCBvciBleHBpcmVkIGF1dGhvcml6YXRpb24gY29kZS4gUGxlYXNlIHRyeSBjb25uZWN0aW5nIHlvdXIgTWNwIGFjY291bnQgYWdhaW4uJztcbiAgICAgIH0gZWxzZSBpZiAoZS5tZXNzYWdlLmluY2x1ZGVzKCdyZWRpcmVjdF91cmlfbWlzbWF0Y2gnKSkge1xuICAgICAgICBjbGllbnRNZXNzYWdlID0gJ1JlZGlyZWN0IFVSSSBtaXNtYXRjaC4gUGxlYXNlIGNvbnRhY3Qgc3VwcG9ydC4nO1xuICAgICAgfSBlbHNlIGlmIChlLm1lc3NhZ2UudG9Mb3dlckNhc2UoKS5pbmNsdWRlcygnZW5jcnlwdGlvbicpKSB7XG4gICAgICAgIGNsaWVudE1lc3NhZ2UgPVxuICAgICAgICAgICdBIHNlY3VyaXR5IGNvbmZpZ3VyYXRpb24gZXJyb3Igb2NjdXJyZWQuIFBsZWFzZSBjb250YWN0IHN1cHBvcnQuJztcbiAgICAgIH1cbiAgICB9XG5cbiAgICByZXR1cm4gcmVzLnN0YXR1cyg1MDApLmpzb24oe1xuICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICBtZXNzYWdlOiBjbGllbnRNZXNzYWdlLFxuICAgIH0pO1xuICB9XG59O1xuXG5leHBvcnQgZGVmYXVsdCBoYW5kbGVyO1xuIl19