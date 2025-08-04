"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createDesign = createDesign;
const dbService_1 = require("../../atomic-docker/project/functions/_utils/dbService");
const crypto_1 = require("../../atomic-docker/project/functions/_utils/crypto");
const simple_oauth2_1 = require("simple-oauth2");
const axios_1 = __importDefault(require("axios"));
const GET_CANVA_TOKENS_QUERY = `
query GetCanvaTokens($userId: uuid!) {
  user_canva_tokens(where: {user_id: {_eq: $userId}}) {
    encrypted_access_token
    encrypted_refresh_token
    token_expiry_timestamp
  }
}
`;
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
  }
}
`;
async function getCanvaTokens(userId) {
    const adminGraphQLClient = (0, dbService_1.createAdminGraphQLClient)();
    const result = await adminGraphQLClient.request(GET_CANVA_TOKENS_QUERY, {
        userId,
    });
    if (result.user_canva_tokens.length === 0) {
        return null;
    }
    const tokens = result.user_canva_tokens[0];
    const encryptionKey = process.env.CANVA_TOKEN_ENCRYPTION_KEY;
    if (!encryptionKey) {
        throw new Error('CANVA_TOKEN_ENCRYPTION_KEY is not set');
    }
    const accessToken = (0, crypto_1.decrypt)(tokens.encrypted_access_token, encryptionKey);
    const refreshToken = tokens.encrypted_refresh_token
        ? (0, crypto_1.decrypt)(tokens.encrypted_refresh_token, encryptionKey)
        : null;
    return {
        accessToken,
        refreshToken,
        expiresAt: tokens.token_expiry_timestamp,
    };
}
async function refreshAccessToken(userId, refreshToken) {
    const canvaClientId = process.env.CANVA_CLIENT_ID;
    const canvaClientSecret = process.env.CANVA_CLIENT_SECRET;
    if (!canvaClientId || !canvaClientSecret) {
        throw new Error('Canva client credentials are not configured.');
    }
    const client = new simple_oauth2_1.AuthorizationCode({
        client: {
            id: canvaClientId,
            secret: canvaClientSecret,
        },
        auth: {
            tokenHost: 'https://api.canva.com',
            tokenPath: '/rest/v1/oauth/token',
        },
    });
    const token = client.createToken({ refresh_token: refreshToken });
    try {
        const refreshedToken = await token.refresh();
        const { token: newTokens } = refreshedToken;
        const adminGraphQLClient = (0, dbService_1.createAdminGraphQLClient)();
        const encryptionKey = process.env.CANVA_TOKEN_ENCRYPTION_KEY;
        if (!encryptionKey) {
            throw new Error('CANVA_TOKEN_ENCRYPTION_KEY is not set');
        }
        const encryptedAccessToken = encrypt(newTokens.access_token, encryptionKey);
        let encryptedRefreshToken = null;
        if (newTokens.refresh_token) {
            encryptedRefreshToken = encrypt(newTokens.refresh_token, encryptionKey);
        }
        const expiryTimestamp = newTokens.expires_at
            ? newTokens.expires_at.toISOString()
            : null;
        const scopesArray = typeof newTokens.scope === 'string'
            ? newTokens.scope.split(' ')
            : newTokens.scope || [];
        await adminGraphQLClient.request(UPSERT_CANVA_TOKEN_MUTATION, {
            userId: userId,
            accessToken: encryptedAccessToken,
            refreshToken: encryptedRefreshToken,
            expiryTimestamp: expiryTimestamp,
            scopesArr: scopesArray,
        });
        return newTokens.access_token;
    }
    catch (error) {
        console.error('Error refreshing Canva access token:', error);
        throw new Error('Failed to refresh Canva access token.');
    }
}
async function createDesign(userId, title) {
    let tokens = await getCanvaTokens(userId);
    if (!tokens) {
        throw new Error('User has not connected their Canva account.');
    }
    if (new Date(tokens.expiresAt) < new Date()) {
        if (!tokens.refreshToken) {
            throw new Error('Canva access token is expired and no refresh token is available.');
        }
        tokens.accessToken = await refreshAccessToken(userId, tokens.refreshToken);
    }
    try {
        const response = await axios_1.default.post('https://api.canva.com/rest/v1/designs', {
            title: title,
            design_type: {
                type: 'preset',
                name: 'presentation',
            },
        }, {
            headers: {
                Authorization: `Bearer ${tokens.accessToken}`,
                'Content-Type': 'application/json',
            },
        });
        return response.data;
    }
    catch (error) {
        console.error('Error creating Canva design:', error);
        throw new Error('Failed to create Canva design.');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FudmFTa2lsbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjYW52YVNraWxscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQWtJQSxvQ0FzQ0M7QUF4S0Qsc0ZBQWtHO0FBQ2xHLGdGQUE4RTtBQUM5RSxpREFBa0Q7QUFDbEQsa0RBQTBCO0FBRTFCLE1BQU0sc0JBQXNCLEdBQUc7Ozs7Ozs7O0NBUTlCLENBQUM7QUFFRixNQUFNLDJCQUEyQixHQUFHOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FrQm5DLENBQUM7QUFFRixLQUFLLFVBQVUsY0FBYyxDQUFDLE1BQWM7SUFDMUMsTUFBTSxrQkFBa0IsR0FBRyxJQUFBLG9DQUF3QixHQUFFLENBQUM7SUFDdEQsTUFBTSxNQUFNLEdBQUcsTUFBTSxrQkFBa0IsQ0FBQyxPQUFPLENBQUMsc0JBQXNCLEVBQUU7UUFDdEUsTUFBTTtLQUNQLENBQUMsQ0FBQztJQUVILElBQUksTUFBTSxDQUFDLGlCQUFpQixDQUFDLE1BQU0sS0FBSyxDQUFDLEVBQUUsQ0FBQztRQUMxQyxPQUFPLElBQUksQ0FBQztJQUNkLENBQUM7SUFFRCxNQUFNLE1BQU0sR0FBRyxNQUFNLENBQUMsaUJBQWlCLENBQUMsQ0FBQyxDQUFDLENBQUM7SUFDM0MsTUFBTSxhQUFhLEdBQUcsT0FBTyxDQUFDLEdBQUcsQ0FBQywwQkFBMEIsQ0FBQztJQUU3RCxJQUFJLENBQUMsYUFBYSxFQUFFLENBQUM7UUFDbkIsTUFBTSxJQUFJLEtBQUssQ0FBQyx1Q0FBdUMsQ0FBQyxDQUFDO0lBQzNELENBQUM7SUFFRCxNQUFNLFdBQVcsR0FBRyxJQUFBLGdCQUFPLEVBQUMsTUFBTSxDQUFDLHNCQUFzQixFQUFFLGFBQWEsQ0FBQyxDQUFDO0lBQzFFLE1BQU0sWUFBWSxHQUFHLE1BQU0sQ0FBQyx1QkFBdUI7UUFDakQsQ0FBQyxDQUFDLElBQUEsZ0JBQU8sRUFBQyxNQUFNLENBQUMsdUJBQXVCLEVBQUUsYUFBYSxDQUFDO1FBQ3hELENBQUMsQ0FB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LENBQUMsTUFBTSxDQUFDLENBQUM7SUFFMUMsSUFBSSxDQUFDLE1BQU0sRUFBRSxDQUFDO1FBQ1osTUFBTSxJQUFJLEtBQUssQ0FBQyw2Q0FBNkMsQ0FBQyxDQUFDO0lBQ2pFLENBQUM7SUFFRCxJQUFJLElBQUksSUFBSSxDQUFDLE1BQU0sQ0FBQyxTQUFTLENBQUMsR0FBRyxJQUFJLElBQUksRUFBRSxFQUFFLENBQUM7UUFDNUMsSUFBSSxDQUFDLE1BQU0sQ0FBQyxZQUFZLEVBQUUsQ0FBQztZQUN6QixNQUFNLElBQUksS0FBSyxDQUNiLGtFQUFrRSxDQUNuRSxDQUFDO1FBQ0osQ0FBQztRQUNELE1BQU0sQ0FBQyxXQUFXLEdBQUcsTUFBTSxrQkFBa0IsQ0FBQyxNQUFNLEVBQUUsTUFBTSxDQUFDLFlBQVksQ0FBQyxDQUFDO0lBQzdFLENBQUM7SUFFRCxJQUFJLENBQUM7UUFDSCxNQUFNLFFBQVEsR0FBRyxNQUFNLGVBQUssQ0FBQyxJQUFJLENBQy9CLHVDQUF1QyxFQUN2QztZQUNFLEtBQUssRUFBRSxLQUFLO1lBQ1osV0FBVyxFQUFFO2dCQUNYLElBQUksRUFBRSxRQUFRO2dCQUNkLElBQUksRUFBRSxjQUFjO2FBQ3JCO1NBQ0YsRUFDRDtZQUNFLE9BQU8sRUFBRTtnQkFDUCxhQUFhLEVBQUUsVUFBVSxNQUFNLENBQUMsV0FBVyxFQUFFO2dCQUM3QyxjQUFjLEVBQUUsa0JBQWtCO2FBQ25DO1NBQ0YsQ0FDRixDQUFDO1FBQ0YsT0FBTyxRQUFRLENBQUMsSUFBSSxDQUFDO0lBQ3ZCLENBQUM7SUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO1FBQ2YsT0FBTyxDQUFDLEtBQUssQ0FBQyw4QkFBOEIsRUFBRSxLQUFLLENBQUMsQ0FBQztRQUNyRCxNQUFNLElBQUksS0FBSyxDQUFDLGdDQUFnQyxDQUFDLENBQUM7SUFDcEQsQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBjcmVhdGVBZG1pbkdyYXBoUUxDbGllbnQgfSBmcm9tICcuLi8uLi9hdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL191dGlscy9kYlNlcnZpY2UnO1xuaW1wb3J0IHsgZGVjcnlwdCB9IGZyb20gJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvX3V0aWxzL2NyeXB0byc7XG5pbXBvcnQgeyBBdXRob3JpemF0aW9uQ29kZSB9IGZyb20gJ3NpbXBsZS1vYXV0aDInO1xuaW1wb3J0IGF4aW9zIGZyb20gJ2F4aW9zJztcblxuY29uc3QgR0VUX0NBTlZBX1RPS0VOU19RVUVSWSA9IGBcbnF1ZXJ5IEdldENhbnZhVG9rZW5zKCR1c2VySWQ6IHV1aWQhKSB7XG4gIHVzZXJfY2FudmFfdG9rZW5zKHdoZXJlOiB7dXNlcl9pZDoge19lcTogJHVzZXJJZH19KSB7XG4gICAgZW5jcnlwdGVkX2FjY2Vzc190b2tlblxuICAgIGVuY3J5cHRlZF9yZWZyZXNoX3Rva2VuXG4gICAgdG9rZW5fZXhwaXJ5X3RpbWVzdGFtcFxuICB9XG59XG5gO1xuXG5jb25zdCBVUFNFUlRfQ0FOVkFfVE9LRU5fTVVUQVRJT04gPSBgXG5tdXRhdGlvbiBVcHNlcnRVc2VyQ2FudmFUb2tlbigkdXNlcklkOiB1dWlkISwgJGFjY2Vzc1Rva2VuOiBTdHJpbmchLCAkcmVmcmVzaFRva2VuOiBTdHJpbmcsICRleHBpcnlUaW1lc3RhbXA6IHRpbWVzdGFtcHR6LCAkc2NvcGVzQXJyOiBqc29uYikge1xuICBpbnNlcnRfdXNlcl9jYW52YV90b2tlbnNfb25lKFxuICAgIG9iamVjdDoge1xuICAgICAgdXNlcl9pZDogJHVzZXJJZCxcbiAgICAgIGVuY3J5cHRlZF9hY2Nlc3NfdG9rZW46ICRhY2Nlc3NUb2tlbixcbiAgICAgIGVuY3J5cHRlZF9yZWZyZXNoX3Rva2VuOiAkcmVmcmVzaFRva2VuLFxuICAgICAgdG9rZW5fZXhwaXJ5X3RpbWVzdGFtcDogJGV4cGlyeVRpbWVzdGFtcCxcbiAgICAgIHNjb3BlczogJHNjb3Blc0FyclxuICAgIH0sXG4gICAgb25fY29uZmxpY3Q6IHtcbiAgICAgIGNvbnN0cmFpbnQ6IHVzZXJfY2FudmFfdG9rZW5zX3VzZXJfaWRfa2V5LFxuICAgICAgdXBkYXRlX2NvbHVtbnM6IFtlbmNyeXB0ZWRfYWNjZXNzX3Rva2VuLCBlbmNyeXB0ZWRfcmVmcmVzaF90b2tlbiwgdG9rZW5fZXhwaXJ5X3RpbWVzdGFtcCwgc2NvcGVzLCB1cGRhdGVkX2F0XVxuICAgIH1cbiAgKSB7XG4gICAgaWRcbiAgfVxufVxuYDtcblxuYXN5bmMgZnVuY3Rpb24gZ2V0Q2FudmFUb2tlbnModXNlcklkOiBzdHJpbmcpIHtcbiAgY29uc3QgYWRtaW5HcmFwaFFMQ2xpZW50ID0gY3JlYXRlQWRtaW5HcmFwaFFMQ2xpZW50KCk7XG4gIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGFkbWluR3JhcGhRTENsaWVudC5yZXF1ZXN0KEdFVF9DQU5WQV9UT0tFTlNfUVVFUlksIHtcbiAgICB1c2VySWQsXG4gIH0pO1xuXG4gIGlmIChyZXN1bHQudXNlcl9jYW52YV90b2tlbnMubGVuZ3RoID09PSAwKSB7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICBjb25zdCB0b2tlbnMgPSByZXN1bHQudXNlcl9jYW52YV90b2tlbnNbMF07XG4gIGNvbnN0IGVuY3J5cHRpb25LZXkgPSBwcm9jZXNzLmVudi5DQU5WQV9UT0tFTl9FTkNSWVBUSU9OX0tFWTtcblxuICBpZiAoIWVuY3J5cHRpb25LZXkpIHtcbiAgICB0aHJvdyBuZXcgRXJyb3IoJ0NBTlZBX1RPS0VOX0VOQ1JZUFRJT05fS0VZIGlzIG5vdCBzZXQnKTtcbiAgfVxuXG4gIGNvbnN0IGFjY2Vzc1Rva2VuID0gZGVjcnlwdCh0b2tlbnMuZW5jcnlwdGVkX2FjY2Vzc190b2tlbiwgZW5jcnlwdGlvbktleSk7XG4gIGNvbnN0IHJlZnJlc2hUb2tlbiA9IHRva2Vucy5lbmNyeXB0ZWRfcmVmcmVzaF90b2tlblxuICAgID8gZGVjcnlwdCh0b2tlbnMuZW5jcnlwdGVkX3JlZnJlc2hfdG9rZW4sIGVuY3J5cHRpb25LZXkpXG4gICAgOiBudWxsO1xuXG4gIHJldHVybiB7XG4gICAgYWNjZXNzVG9rZW4sXG4gICAgcmVmcmVzaFRva2VuLFxuICAgIGV4cGlyZXNBdDogdG9rZW5zLnRva2VuX2V4cGlyeV90aW1lc3RhbXAsXG4gIH07XG59XG5cbmFzeW5jIGZ1bmN0aW9uIHJlZnJlc2hBY2Nlc3NUb2tlbih1c2VySWQ6IHN0cmluZywgcmVmcmVzaFRva2VuOiBzdHJpbmcpIHtcbiAgY29uc3QgY2FudmFDbGllbnRJZCA9IHByb2Nlc3MuZW52LkNBTlZBX0NMSUVOVF9JRDtcbiAgY29uc3QgY2FudmFDbGllbnRTZWNyZXQgPSBwcm9jZXNzLmVudi5DQU5WQV9DTElFTlRfU0VDUkVUO1xuXG4gIGlmICghY2FudmFDbGllbnRJZCB8fCAhY2FudmFDbGllbnRTZWNyZXQpIHtcbiAgICB0aHJvdyBuZXcgRXJyb3IoJ0NhbnZhIGNsaWVudCBjcmVkZW50aWFscyBhcmUgbm90IGNvbmZpZ3VyZWQuJyk7XG4gIH1cblxuICBjb25zdCBjbGllbnQgPSBuZXcgQXV0aG9yaXphdGlvbkNvZGUoe1xuICAgIGNsaWVudDoge1xuICAgICAgaWQ6IGNhbnZhQ2xpZW50SWQsXG4gICAgICBzZWNyZXQ6IGNhbnZhQ2xpZW50U2VjcmV0LFxuICAgIH0sXG4gICAgYXV0aDoge1xuICAgICAgdG9rZW5Ib3N0OiAnaHR0cHM6Ly9hcGkuY2FudmEuY29tJyxcbiAgICAgIHRva2VuUGF0aDogJy9yZXN0L3YxL29hdXRoL3Rva2VuJyxcbiAgICB9LFxuICB9KTtcblxuICBjb25zdCB0b2tlbiA9IGNsaWVudC5jcmVhdGVUb2tlbih7IHJlZnJlc2hfdG9rZW46IHJlZnJlc2hUb2tlbiB9KTtcblxuICB0cnkge1xuICAgIGNvbnN0IHJlZnJlc2hlZFRva2VuID0gYXdhaXQgdG9rZW4ucmVmcmVzaCgpO1xuICAgIGNvbnN0IHsgdG9rZW46IG5ld1Rva2VucyB9ID0gcmVmcmVzaGVkVG9rZW47XG5cbiAgICBjb25zdCBhZG1pbkdyYXBoUUxDbGllbnQgPSBjcmVhdGVBZG1pbkdyYXBoUUxDbGllbnQoKTtcbiAgICBjb25zdCBlbmNyeXB0aW9uS2V5ID0gcHJvY2Vzcy5lbnYuQ0FOVkFfVE9LRU5fRU5DUllQVElPTl9LRVk7XG4gICAgaWYgKCFlbmNyeXB0aW9uS2V5KSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ0NBTlZBX1RPS0VOX0VOQ1JZUFRJT05fS0VZIGlzIG5vdCBzZXQnKTtcbiAgICB9XG5cbiAgICBjb25zdCBlbmNyeXB0ZWRBY2Nlc3NUb2tlbiA9IGVuY3J5cHQoXG4gICAgICBuZXdUb2tlbnMuYWNjZXNzX3Rva2VuIGFzIHN0cmluZyxcbiAgICAgIGVuY3J5cHRpb25LZXlcbiAgICApO1xuICAgIGxldCBlbmNyeXB0ZWRSZWZyZXNoVG9rZW46IHN0cmluZyB8IG51bGwgPSBudWxsO1xuICAgIGlmIChuZXdUb2tlbnMucmVmcmVzaF90b2tlbikge1xuICAgICAgZW5jcnlwdGVkUmVmcmVzaFRva2VuID0gZW5jcnlwdChcbiAgICAgICAgbmV3VG9rZW5zLnJlZnJlc2hfdG9rZW4gYXMgc3RyaW5nLFxuICAgICAgICBlbmNyeXB0aW9uS2V5XG4gICAgICApO1xuICAgIH1cblxuICAgIGNvbnN0IGV4cGlyeVRpbWVzdGFtcCA9IG5ld1Rva2Vucy5leHBpcmVzX2F0XG4gICAgICA/IChuZXdUb2tlbnMuZXhwaXJlc19hdCBhcyBEYXRlKS50b0lTT1N0cmluZygpXG4gICAgICA6IG51bGw7XG4gICAgY29uc3Qgc2NvcGVzQXJyYXkgPVxuICAgICAgdHlwZW9mIG5ld1Rva2Vucy5zY29wZSA9PT0gJ3N0cmluZydcbiAgICAgICAgPyBuZXdUb2tlbnMuc2NvcGUuc3BsaXQoJyAnKVxuICAgICAgICA6IG5ld1Rva2Vucy5zY29wZSB8fCBbXTtcblxuICAgIGF3YWl0IGFkbWluR3JhcGhRTENsaWVudC5yZXF1ZXN0KFVQU0VSVF9DQU5WQV9UT0tFTl9NVVRBVElPTiwge1xuICAgICAgdXNlcklkOiB1c2VySWQsXG4gICAgICBhY2Nlc3NUb2tlbjogZW5jcnlwdGVkQWNjZXNzVG9rZW4sXG4gICAgICByZWZyZXNoVG9rZW46IGVuY3J5cHRlZFJlZnJlc2hUb2tlbixcbiAgICAgIGV4cGlyeVRpbWVzdGFtcDogZXhwaXJ5VGltZXN0YW1wLFxuICAgICAgc2NvcGVzQXJyOiBzY29wZXNBcnJheSxcbiAgICB9KTtcblxuICAgIHJldHVybiBuZXdUb2tlbnMuYWNjZXNzX3Rva2VuO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGNvbnNvbGUuZXJyb3IoJ0Vycm9yIHJlZnJlc2hpbmcgQ2FudmEgYWNjZXNzIHRva2VuOicsIGVycm9yKTtcbiAgICB0aHJvdyBuZXcgRXJyb3IoJ0ZhaWxlZCB0byByZWZyZXNoIENhbnZhIGFjY2VzcyB0b2tlbi4nKTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gY3JlYXRlRGVzaWduKHVzZXJJZDogc3RyaW5nLCB0aXRsZTogc3RyaW5nKSB7XG4gIGxldCB0b2tlbnMgPSBhd2FpdCBnZXRDYW52YVRva2Vucyh1c2VySWQpO1xuXG4gIGlmICghdG9rZW5zKSB7XG4gICAgdGhyb3cgbmV3IEVycm9yKCdVc2VyIGhhcyBub3QgY29ubmVjdGVkIHRoZWlyIENhbnZhIGFjY291bnQuJyk7XG4gIH1cblxuICBpZiAobmV3IERhdGUodG9rZW5zLmV4cGlyZXNBdCkgPCBuZXcgRGF0ZSgpKSB7XG4gICAgaWYgKCF0b2tlbnMucmVmcmVzaFRva2VuKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgICdDYW52YSBhY2Nlc3MgdG9rZW4gaXMgZXhwaXJlZCBhbmQgbm8gcmVmcmVzaCB0b2tlbiBpcyBhdmFpbGFibGUuJ1xuICAgICAgKTtcbiAgICB9XG4gICAgdG9rZW5zLmFjY2Vzc1Rva2VuID0gYXdhaXQgcmVmcmVzaEFjY2Vzc1Rva2VuKHVzZXJJZCwgdG9rZW5zLnJlZnJlc2hUb2tlbik7XG4gIH1cblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MucG9zdChcbiAgICAgICdodHRwczovL2FwaS5jYW52YS5jb20vcmVzdC92MS9kZXNpZ25zJyxcbiAgICAgIHtcbiAgICAgICAgdGl0bGU6IHRpdGxlLFxuICAgICAgICBkZXNpZ25fdHlwZToge1xuICAgICAgICAgIHR5cGU6ICdwcmVzZXQnLFxuICAgICAgICAgIG5hbWU6ICdwcmVzZW50YXRpb24nLFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbnMuYWNjZXNzVG9rZW59YCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICB9LFxuICAgICAgfVxuICAgICk7XG4gICAgcmV0dXJuIHJlc3BvbnNlLmRhdGE7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgY3JlYXRpbmcgQ2FudmEgZGVzaWduOicsIGVycm9yKTtcbiAgICB0aHJvdyBuZXcgRXJyb3IoJ0ZhaWxlZCB0byBjcmVhdGUgQ2FudmEgZGVzaWduLicpO1xuICB9XG59XG4iXX0=