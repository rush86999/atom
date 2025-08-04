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
        console.error('CANVA_TOKEN_ENCRYPTION_KEY is not set. Please configure a 64-character hex key (32 bytes).');
        return res
            .status(500)
            .json({
            success: false,
            message: 'Server configuration error: Encryption key not configured.',
        });
    }
    const adminGraphQLClient = createAdminGraphQLClient();
    const canvaClientId = process.env.CANVA_CLIENT_ID;
    const canvaClientSecret = process.env.CANVA_CLIENT_SECRET;
    const canvaRedirectUrl = process.env.CANVA_REDIRECT_URL;
    if (!canvaClientId || !canvaClientSecret || !canvaRedirectUrl) {
        console.error('Canva environment variables are not configured.');
        return res
            .status(500)
            .json({
            message: 'Server configuration error: Missing Canva integration credentials.',
        });
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
            return res
                .status(500)
                .json({
                success: false,
                message: 'Failed to obtain access token from Canva.',
            });
        }
        const encryptedAccessToken = encrypt(token.access_token, ENCRYPTION_KEY_HEX);
        let encryptedRefreshToken = null;
        if (token.refresh_token) {
            encryptedRefreshToken = encrypt(token.refresh_token, ENCRYPTION_KEY_HEX);
        }
        const expiryTimestamp = token.expires_at
            ? token.expires_at.toISOString()
            : null;
        const scopesArray = typeof token.scope === 'string'
            ? token.scope.split(' ')
            : token.scope || [];
        await adminGraphQLClient.request(UPSERT_CANVA_TOKEN_MUTATION, {
            userId: userId,
            accessToken: encryptedAccessToken,
            refreshToken: encryptedRefreshToken,
            expiryTimestamp: expiryTimestamp,
            scopesArr: scopesArray,
        });
        return res
            .status(200)
            .json({
            success: true,
            message: 'Canva account connected successfully.',
        });
    }
    catch (e) {
        console.error('Error handling Canva auth callback:', e);
        return res.status(500).json({
            success: false,
            message: 'Failed to connect Canva account due to an unexpected error.',
        });
    }
};
export default handler;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FudmEtY2FsbGJhY2suanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjYW52YS1jYWxsYmFjay50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFDQSxPQUFPLEVBQUUsaUJBQWlCLEVBQUUsTUFBTSxlQUFlLENBQUM7QUFDbEQsT0FBTyxFQUFFLHdCQUF3QixFQUFFLE1BQU0scUJBQXFCLENBQUM7QUFDL0QsT0FBTyxFQUFFLE9BQU8sRUFBRSxNQUFNLGtCQUFrQixDQUFDO0FBRTNDLE1BQU0sa0JBQWtCLEdBQUcsT0FBTyxDQUFDLEdBQUcsQ0FBQywwQkFBMEIsQ0FBQztBQUVsRSxxREFBcUQ7QUFDckQsMERBQTBEO0FBQzFELG1FQUFtRTtBQUNuRSxpRUFBaUU7QUFDakUsd0RBQXdEO0FBQ3hELG1GQUFtRjtBQUNuRiw0Q0FBNEM7QUFDNUMsc0dBQXNHO0FBQ3RHLE1BQU0sMkJBQTJCLEdBQUc7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FtQm5DLENBQUM7QUFXRixNQUFNLE9BQU8sR0FBRyxLQUFLLEVBQ25CLEdBQXdELEVBQ3hELEdBQWEsRUFDYixFQUFFO0lBQ0YsTUFBTSxFQUFFLElBQUksRUFBRSxHQUFHLEdBQUcsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDO0lBQ2hDLE1BQU0sTUFBTSxHQUFHLEdBQUcsQ0FBQyxJQUFJLENBQUMsaUJBQWlCLENBQUMsa0JBQWtCLENBQUMsQ0FBQztJQUU5RCxJQUFJLENBQUMsSUFBSSxFQUFFLENBQUM7UUFDVixPQUFPLEdBQUc7YUFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2FBQ1gsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsZ0NBQWdDLEVBQUUsQ0FBQyxDQUFDO0lBQ3pFLENBQUM7SUFDRCxJQUFJLENBQUMsTUFBTSxFQUFFLENBQUM7UUFDWixPQUFPLEdBQUc7YUFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2FBQ1gsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsa0NBQWtDLEVBQUUsQ0FBQyxDQUFDO0lBQzNFLENBQUM7SUFDRCxJQUFJLENBQUMsa0JBQWtCLEVBQUUsQ0FBQztRQUN4QixPQUFPLENBQUMsS0FBSyxDQUNYLDRGQUE0RixDQUM3RixDQUFDO1FBQ0YsT0FBTyxHQUFHO2FBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQzthQUNYLElBQUksQ0FBQztZQUNKLE9BQU8sRUFBRSxLQUFLO1lBQ2QsT0FBTyxFQUFFLDREQUE0RDtTQUN0RSxDQUFDLENBQUM7SUFDUCxDQUFDO0lBRUQsTUFBTSxrQkFBa0IsR0FBRyx3QkFBd0IsRUFBRSxDQUFDO0lBQ3RELE1BQU0sYUFBYSxHQUFHLE9BQU8sQ0FBQyxHQUFHLENBQUMsZUFBZSxDQUFDO0lBQ2xELE1BQU0saUJBQWlCLEdBQUcsT0FBTyxDQUFDLEdBQUcsQ0FBQyxtQkFBbUIsQ0FBQztJQUMxRCxNQUFNLGdCQUFnQixHQUFHLE9BQU8sQ0FBQyxHQUFHLENBQUMsa0JBQWtCLENBQUM7SUFFeEQsSUFBSSxDQUFDLGFBQWEsSUFBSSxDQUFDLGlCQUFpQixJQUFJLENBQUMsZ0JBQWdCLEVBQUUsQ0FBQztRQUM5RCxPQUFPLENBQUMsS0FBSyxDQUFDLGlEQUFpRCxDQUFDLENBQUM7UUFDakUsT0FBTyxHQUFHO2FBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQzthQUNYLElBQUksQ0FBQztZQUNKLE9BQU8sRUFDTCxvRUFBb0U7U0FDdkUsQ0FBQyxDQUFDO0lBQ1AsQ0FBQztJQUVELE1BQU0sTUFBTSxHQUFHLElBQUksaUJBQWlCLENBQUM7UUFDbkMsTUFBTSxFQUFFO1lBQ04sRUFBRSxFQUFFLGFBQWE7WUFDakIsTUFBTSxFQUFFLGlCQUFpQjtTQUMxQjtRQUNELElBQUksRUFBRTtZQUNKLFNBQVMsRUFBRSx1QkFBdUI7WUFDbEMsU0FBUyxFQUFFLHNCQUFzQjtZQUNqQyxhQUFhLEVBQUUsdUJBQXVCO1lBQ3RDLGFBQWEsRUFBRSxzQkFBc0I7U0FDdEM7S0FDRixDQUFDLENBQUM7SUFFSCxJQUFJLENBQUM7UUFDSCxNQUFNLFdBQVcsR0FBRztZQUNsQixJQUFJLEVBQUUsSUFBSTtZQUNWLFlBQVksRUFBRSxnQkFBZ0I7U0FDL0IsQ0FBQztRQUNGLE1BQU0sV0FBVyxHQUFHLE1BQU0sTUFBTSxDQUFDLFFBQVEsQ0FBQyxXQUFXLENBQUMsQ0FBQztRQUN2RCxNQUFNLEVBQUUsS0FBSyxFQUFFLEdBQUcsV0FBVyxDQUFDO1FBRTlCLElBQUksQ0FBQyxLQUFLLENBQUMsWUFBWSxFQUFFLENBQUM7WUFDeEIsT0FBTyxDQUFDLEtBQUssQ0FBQywyQ0FBMkMsQ0FBQyxDQUFDO1lBQzNELE9BQU8sR0FBRztpQkFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2lCQUNYLElBQUksQ0FBQztnQkFDSixPQUFPLEVBQUUsS0FBSztnQkFDZCxPQUFPLEVBQUUsMkNBQTJDO2FBQ3JELENBQUMsQ0FBQztRQUNQLENBQUM7UUFFRCxNQUFNLG9CQUFvQixHQUFHLE9BQU8sQ0FDbEMsS0FBSyxDQUFDLFlBQXNCLEVBQzVCLGtCQUFrQixDQUNuQixDQUFDO1FBQ0YsSUFBSSxxQkFBcUIsR0FBa0IsSUFBSSxDQUFDO1FBQ2hELElBQUksS0FBSyxDQUFDLGFBQWEsRUFBRSxDQUFDO1lBQ3hCLHFCQUFxQixHQUFHLE9BQU8sQ0FDN0IsS0FBSyxDQUFDLGFBQXVCLEVBQzdCLGtCQUFrQixDQUNuQixDQUFDO1FBQ0osQ0FBQztRQUVELE1BQU0sZUFBZSxHQUFHLEtBQUssQ0FBQyxVQUFVO1lBQ3RDLENBQUMsQ0FBRSxLQUFLLENBQUMsVUFBbUIsQ0FBQyxXQUFXLEVBQUU7WUFDMUMsQ0FBQyxDQUFDLElBQUksQ0FBQztRQUNULE1BQU0sV0FBVyxHQUNmLE9BQU8sS0FBSyxDQUFDLEtBQUssS0FBSyxRQUFRO1lBQzdCLENBQUMsQ0FBQyxLQUFLLENBQUMsS0FBSyxDQUFDLEtBQUssQ0FBQyxHQUFHLENBQUM7WUFDeEIsQ0FBQyxDQUFDLEtBQUssQ0FBQyxLQUFLLElBQUksRUFBRSxDQUFDO1FBRXhCLE1BQU0sa0JBQWtCLENBQUMsT0FBTyxDQUFDLDJCQUEyQixFQUFFO1lBQzVELE1BQU0sRUFBRSxNQUFNO1lBQ2QsV0FBVyxFQUFFLG9CQUFvQjtZQUNqQyxZQUFZLEVBQUUscUJBQXFCO1lBQ25DLGVBQWUsRUFBRSxlQUFlO1lBQ2hDLFNBQVMsRUFBRSxXQUFXO1NBQ3ZCLENBQUMsQ0FBQztRQUVILE9BQU8sR0FBRzthQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7YUFDWCxJQUFJLENBQUM7WUFDSixPQUFPLEVBQUUsSUFBSTtZQUNiLE9BQU8sRUFBRSx1Q0FBdUM7U0FDakQsQ0FBQyxDQUFDO0lBQ1AsQ0FBQztJQUFDLE9BQU8sQ0FBTSxFQUFFLENBQUM7UUFDaEIsT0FBTyxDQUFDLEtBQUssQ0FBQyxxQ0FBcUMsRUFBRSxDQUFDLENBQUMsQ0FBQztRQUN4RCxPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDO1lBQzFCLE9BQU8sRUFBRSxLQUFLO1lBQ2QsT0FBTyxFQUFFLDZEQUE2RDtTQUN2RSxDQUFDLENBQUM7SUFDTCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBRUYsZUFBZSxPQUFPLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBSZXF1ZXN0LCBSZXNwb25zZSB9IGZyb20gJ2V4cHJlc3MnO1xuaW1wb3J0IHsgQXV0aG9yaXphdGlvbkNvZGUgfSBmcm9tICdzaW1wbGUtb2F1dGgyJztcbmltcG9ydCB7IGNyZWF0ZUFkbWluR3JhcGhRTENsaWVudCB9IGZyb20gJy4uL191dGlscy9kYlNlcnZpY2UnO1xuaW1wb3J0IHsgZW5jcnlwdCB9IGZyb20gJy4uL191dGlscy9jcnlwdG8nO1xuXG5jb25zdCBFTkNSWVBUSU9OX0tFWV9IRVggPSBwcm9jZXNzLmVudi5DQU5WQV9UT0tFTl9FTkNSWVBUSU9OX0tFWTtcblxuLy8gTk9URTogQSBuZXcgdGFibGUgJ3VzZXJfY2FudmFfdG9rZW5zJyBpcyByZXF1aXJlZC5cbi8vIE1pZ3JhdGlvbiBzaG91bGQgYmUgY3JlYXRlZCB3aXRoIHRoZSBmb2xsb3dpbmcgY29sdW1uczpcbi8vIGlkICh1dWlkLCBwcmltYXJ5IGtleSksIHVzZXJfaWQgKHV1aWQsIGZvcmVpZ24ga2V5IHRvIHVzZXJzLmlkKSxcbi8vIGVuY3J5cHRlZF9hY2Nlc3NfdG9rZW4gKHRleHQpLCBlbmNyeXB0ZWRfcmVmcmVzaF90b2tlbiAodGV4dCksXG4vLyB0b2tlbl9leHBpcnlfdGltZXN0YW1wICh0aW1lc3RhbXB0eiksIHNjb3BlcyAoanNvbmIpLFxuLy8gY3JlYXRlZF9hdCAodGltZXN0YW1wdHosIGRlZmF1bHQgbm93KCkpLCB1cGRhdGVkX2F0ICh0aW1lc3RhbXB0eiwgZGVmYXVsdCBub3coKSlcbi8vIEFsc28sIGFkZCBhIHVuaXF1ZSBjb25zdHJhaW50IG9uIHVzZXJfaWQ6XG4vLyBBTFRFUiBUQUJMRSBwdWJsaWMudXNlcl9jYW52YV90b2tlbnMgQUREIENPTlNUUkFJTlQgdXNlcl9jYW52YV90b2tlbnNfdXNlcl9pZF9rZXkgVU5JUVVFICh1c2VyX2lkKTtcbmNvbnN0IFVQU0VSVF9DQU5WQV9UT0tFTl9NVVRBVElPTiA9IGBcbm11dGF0aW9uIFVwc2VydFVzZXJDYW52YVRva2VuKCR1c2VySWQ6IHV1aWQhLCAkYWNjZXNzVG9rZW46IFN0cmluZyEsICRyZWZyZXNoVG9rZW46IFN0cmluZywgJGV4cGlyeVRpbWVzdGFtcDogdGltZXN0YW1wdHosICRzY29wZXNBcnI6IGpzb25iKSB7XG4gIGluc2VydF91c2VyX2NhbnZhX3Rva2Vuc19vbmUoXG4gICAgb2JqZWN0OiB7XG4gICAgICB1c2VyX2lkOiAkdXNlcklkLFxuICAgICAgZW5jcnlwdGVkX2FjY2Vzc190b2tlbjogJGFjY2Vzc1Rva2VuLFxuICAgICAgZW5jcnlwdGVkX3JlZnJlc2hfdG9rZW46ICRyZWZyZXNoVG9rZW4sXG4gICAgICB0b2tlbl9leHBpcnlfdGltZXN0YW1wOiAkZXhwaXJ5VGltZXN0YW1wLFxuICAgICAgc2NvcGVzOiAkc2NvcGVzQXJyXG4gICAgfSxcbiAgICBvbl9jb25mbGljdDoge1xuICAgICAgY29uc3RyYWludDogdXNlcl9jYW52YV90b2tlbnNfdXNlcl9pZF9rZXksXG4gICAgICB1cGRhdGVfY29sdW1uczogW2VuY3J5cHRlZF9hY2Nlc3NfdG9rZW4sIGVuY3J5cHRlZF9yZWZyZXNoX3Rva2VuLCB0b2tlbl9leHBpcnlfdGltZXN0YW1wLCBzY29wZXMsIHVwZGF0ZWRfYXRdXG4gICAgfVxuICApIHtcbiAgICBpZFxuICAgIHVzZXJfaWRcbiAgfVxufVxuYDtcblxuaW50ZXJmYWNlIEhhbmRsZUNhbnZhQXV0aENhbGxiYWNrUmVxdWVzdEJvZHkge1xuICBzZXNzaW9uX3ZhcmlhYmxlczoge1xuICAgICd4LWhhc3VyYS11c2VyLWlkJzogc3RyaW5nO1xuICB9O1xuICBpbnB1dDoge1xuICAgIGNvZGU6IHN0cmluZztcbiAgfTtcbn1cblxuY29uc3QgaGFuZGxlciA9IGFzeW5jIChcbiAgcmVxOiBSZXF1ZXN0PHt9LCB7fSwgSGFuZGxlQ2FudmFBdXRoQ2FsbGJhY2tSZXF1ZXN0Qm9keT4sXG4gIHJlczogUmVzcG9uc2VcbikgPT4ge1xuICBjb25zdCB7IGNvZGUgfSA9IHJlcS5ib2R5LmlucHV0O1xuICBjb25zdCB1c2VySWQgPSByZXEuYm9keS5zZXNzaW9uX3ZhcmlhYmxlc1sneC1oYXN1cmEtdXNlci1pZCddO1xuXG4gIGlmICghY29kZSkge1xuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoNDAwKVxuICAgICAgLmpzb24oeyBzdWNjZXNzOiBmYWxzZSwgbWVzc2FnZTogJ0F1dGhvcml6YXRpb24gY29kZSBpcyBtaXNzaW5nLicgfSk7XG4gIH1cbiAgaWYgKCF1c2VySWQpIHtcbiAgICByZXR1cm4gcmVzXG4gICAgICAuc3RhdHVzKDQwMClcbiAgICAgIC5qc29uKHsgc3VjY2VzczogZmFsc2UsIG1lc3NhZ2U6ICdVc2VyIElEIGlzIG1pc3NpbmcgZnJvbSBzZXNzaW9uLicgfSk7XG4gIH1cbiAgaWYgKCFFTkNSWVBUSU9OX0tFWV9IRVgpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgJ0NBTlZBX1RPS0VOX0VOQ1JZUFRJT05fS0VZIGlzIG5vdCBzZXQuIFBsZWFzZSBjb25maWd1cmUgYSA2NC1jaGFyYWN0ZXIgaGV4IGtleSAoMzIgYnl0ZXMpLidcbiAgICApO1xuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoNTAwKVxuICAgICAgLmpzb24oe1xuICAgICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgICAgbWVzc2FnZTogJ1NlcnZlciBjb25maWd1cmF0aW9uIGVycm9yOiBFbmNyeXB0aW9uIGtleSBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSk7XG4gIH1cblxuICBjb25zdCBhZG1pbkdyYXBoUUxDbGllbnQgPSBjcmVhdGVBZG1pbkdyYXBoUUxDbGllbnQoKTtcbiAgY29uc3QgY2FudmFDbGllbnRJZCA9IHByb2Nlc3MuZW52LkNBTlZBX0NMSUVOVF9JRDtcbiAgY29uc3QgY2FudmFDbGllbnRTZWNyZXQgPSBwcm9jZXNzLmVudi5DQU5WQV9DTElFTlRfU0VDUkVUO1xuICBjb25zdCBjYW52YVJlZGlyZWN0VXJsID0gcHJvY2Vzcy5lbnYuQ0FOVkFfUkVESVJFQ1RfVVJMO1xuXG4gIGlmICghY2FudmFDbGllbnRJZCB8fCAhY2FudmFDbGllbnRTZWNyZXQgfHwgIWNhbnZhUmVkaXJlY3RVcmwpIHtcbiAgICBjb25zb2xlLmVycm9yKCdDYW52YSBlbnZpcm9ubWVudCB2YXJpYWJsZXMgYXJlIG5vdCBjb25maWd1cmVkLicpO1xuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoNTAwKVxuICAgICAgLmpzb24oe1xuICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICdTZXJ2ZXIgY29uZmlndXJhdGlvbiBlcnJvcjogTWlzc2luZyBDYW52YSBpbnRlZ3JhdGlvbiBjcmVkZW50aWFscy4nLFxuICAgICAgfSk7XG4gIH1cblxuICBjb25zdCBjbGllbnQgPSBuZXcgQXV0aG9yaXphdGlvbkNvZGUoe1xuICAgIGNsaWVudDoge1xuICAgICAgaWQ6IGNhbnZhQ2xpZW50SWQsXG4gICAgICBzZWNyZXQ6IGNhbnZhQ2xpZW50U2VjcmV0LFxuICAgIH0sXG4gICAgYXV0aDoge1xuICAgICAgdG9rZW5Ib3N0OiAnaHR0cHM6Ly9hcGkuY2FudmEuY29tJyxcbiAgICAgIHRva2VuUGF0aDogJy9yZXN0L3YxL29hdXRoL3Rva2VuJyxcbiAgICAgIGF1dGhvcml6ZUhvc3Q6ICdodHRwczovL3d3dy5jYW52YS5jb20nLFxuICAgICAgYXV0aG9yaXplUGF0aDogJy9hcGkvb2F1dGgvYXV0aG9yaXplJyxcbiAgICB9LFxuICB9KTtcblxuICB0cnkge1xuICAgIGNvbnN0IHRva2VuUGFyYW1zID0ge1xuICAgICAgY29kZTogY29kZSxcbiAgICAgIHJlZGlyZWN0X3VyaTogY2FudmFSZWRpcmVjdFVybCxcbiAgICB9O1xuICAgIGNvbnN0IGFjY2Vzc1Rva2VuID0gYXdhaXQgY2xpZW50LmdldFRva2VuKHRva2VuUGFyYW1zKTtcbiAgICBjb25zdCB7IHRva2VuIH0gPSBhY2Nlc3NUb2tlbjtcblxuICAgIGlmICghdG9rZW4uYWNjZXNzX3Rva2VuKSB7XG4gICAgICBjb25zb2xlLmVycm9yKCdGYWlsZWQgdG8gb2J0YWluIGFjY2VzcyB0b2tlbiBmcm9tIENhbnZhLicpO1xuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDUwMClcbiAgICAgICAgLmpzb24oe1xuICAgICAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgICAgIG1lc3NhZ2U6ICdGYWlsZWQgdG8gb2J0YWluIGFjY2VzcyB0b2tlbiBmcm9tIENhbnZhLicsXG4gICAgICAgIH0pO1xuICAgIH1cblxuICAgIGNvbnN0IGVuY3J5cHRlZEFjY2Vzc1Rva2VuID0gZW5jcnlwdChcbiAgICAgIHRva2VuLmFjY2Vzc190b2tlbiBhcyBzdHJpbmcsXG4gICAgICBFTkNSWVBUSU9OX0tFWV9IRVhcbiAgICApO1xuICAgIGxldCBlbmNyeXB0ZWRSZWZyZXNoVG9rZW46IHN0cmluZyB8IG51bGwgPSBudWxsO1xuICAgIGlmICh0b2tlbi5yZWZyZXNoX3Rva2VuKSB7XG4gICAgICBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4gPSBlbmNyeXB0KFxuICAgICAgICB0b2tlbi5yZWZyZXNoX3Rva2VuIGFzIHN0cmluZyxcbiAgICAgICAgRU5DUllQVElPTl9LRVlfSEVYXG4gICAgICApO1xuICAgIH1cblxuICAgIGNvbnN0IGV4cGlyeVRpbWVzdGFtcCA9IHRva2VuLmV4cGlyZXNfYXRcbiAgICAgID8gKHRva2VuLmV4cGlyZXNfYXQgYXMgRGF0ZSkudG9JU09TdHJpbmcoKVxuICAgICAgOiBudWxsO1xuICAgIGNvbnN0IHNjb3Blc0FycmF5ID1cbiAgICAgIHR5cGVvZiB0b2tlbi5zY29wZSA9PT0gJ3N0cmluZydcbiAgICAgICAgPyB0b2tlbi5zY29wZS5zcGxpdCgnICcpXG4gICAgICAgIDogdG9rZW4uc2NvcGUgfHwgW107XG5cbiAgICBhd2FpdCBhZG1pbkdyYXBoUUxDbGllbnQucmVxdWVzdChVUFNFUlRfQ0FOVkFfVE9LRU5fTVVUQVRJT04sIHtcbiAgICAgIHVzZXJJZDogdXNlcklkLFxuICAgICAgYWNjZXNzVG9rZW46IGVuY3J5cHRlZEFjY2Vzc1Rva2VuLFxuICAgICAgcmVmcmVzaFRva2VuOiBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4sXG4gICAgICBleHBpcnlUaW1lc3RhbXA6IGV4cGlyeVRpbWVzdGFtcCxcbiAgICAgIHNjb3Blc0Fycjogc2NvcGVzQXJyYXksXG4gICAgfSk7XG5cbiAgICByZXR1cm4gcmVzXG4gICAgICAuc3RhdHVzKDIwMClcbiAgICAgIC5qc29uKHtcbiAgICAgICAgc3VjY2VzczogdHJ1ZSxcbiAgICAgICAgbWVzc2FnZTogJ0NhbnZhIGFjY291bnQgY29ubmVjdGVkIHN1Y2Nlc3NmdWxseS4nLFxuICAgICAgfSk7XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoJ0Vycm9yIGhhbmRsaW5nIENhbnZhIGF1dGggY2FsbGJhY2s6JywgZSk7XG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoNTAwKS5qc29uKHtcbiAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgbWVzc2FnZTogJ0ZhaWxlZCB0byBjb25uZWN0IENhbnZhIGFjY291bnQgZHVlIHRvIGFuIHVuZXhwZWN0ZWQgZXJyb3IuJyxcbiAgICB9KTtcbiAgfVxufTtcblxuZXhwb3J0IGRlZmF1bHQgaGFuZGxlcjtcbiJdfQ==