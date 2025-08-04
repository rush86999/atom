"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const nextjs_1 = require("supertokens-node/nextjs");
const graphqlClient_1 = require("../../../../../project/functions/_libs/graphqlClient");
const intuit_oauth_1 = __importDefault(require("intuit-oauth"));
async function handler(req, res) {
    let session;
    try {
        session = await (0, nextjs_1.getSession)(req, res, {
            overrideGlobalClaimValidators: () => [],
        });
    }
    catch (err) {
        return res.status(401).json({ message: 'Unauthorized' });
    }
    const userId = session.getUserId();
    const oauthClient = new intuit_oauth_1.default({
        clientId: process.env.QUICKBOOKS_CLIENT_ID,
        clientSecret: process.env.QUICKBOOKS_CLIENT_SECRET,
        environment: 'sandbox', // or 'production'
        redirectUri: process.env.QUICKBOOKS_REDIRECT_URI,
    });
    try {
        const authResponse = await oauthClient.createToken(req.url);
        const token = authResponse.getJson();
        const accessToken = token.access_token;
        const refreshToken = token.refresh_token;
        const expiresAt = new Date(Date.now() + token.expires_in * 1000).toISOString();
        const realmId = token.realmId;
        // Save the tokens to the user_tokens table
        const mutation = `
            mutation InsertUserToken($userId: String!, $service: String!, $accessToken: String!, $refreshToken: String, $expiresAt: timestamptz!, $meta: jsonb) {
                insert_user_tokens_one(object: {user_id: $userId, service: $service, access_token: $accessToken, refresh_token: $refreshToken, expires_at: $expiresAt, meta: $meta}) {
                    id
                }
            }
        `;
        const variables = {
            userId,
            service: 'quickbooks',
            accessToken,
            refreshToken,
            expiresAt,
            meta: { realmId },
        };
        await (0, graphqlClient_1.executeGraphQLQuery)(mutation, variables, 'InsertUserToken', userId);
        return res.redirect('/Settings/UserViewSettings');
    }
    catch (error) {
        console.error('Error during QuickBooks OAuth callback:', error);
        return res
            .status(500)
            .json({ message: 'Failed to complete QuickBooks OAuth flow' });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsbGJhY2suanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjYWxsYmFjay50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQU1BLDBCQXlEQztBQTlERCxvREFBcUQ7QUFFckQsd0ZBQTJGO0FBQzNGLGdFQUF1QztBQUV4QixLQUFLLFVBQVUsT0FBTyxDQUNuQyxHQUFtQixFQUNuQixHQUFvQjtJQUVwQixJQUFJLE9BQXlCLENBQUM7SUFDOUIsSUFBSSxDQUFDO1FBQ0gsT0FBTyxHQUFHLE1BQU0sSUFBQSxtQkFBVSxFQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUU7WUFDbkMsNkJBQTZCLEVBQUUsR0FBRyxFQUFFLENBQUMsRUFBRTtTQUN4QyxDQUFDLENBQUM7SUFDTCxDQUFDO0lBQUMsT0FBTyxHQUFHLEVBQUUsQ0FBQztRQUNiLE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUsY0FBYyxFQUFFLENBQUMsQ0FBQztJQUMzRCxDQUFDO0lBRUQsTUFBTSxNQUFNLEdBQUcsT0FBTyxDQUFDLFNBQVMsRUFBRSxDQUFDO0lBQ25DLE1BQU0sV0FBVyxHQUFHLElBQUksc0JBQVcsQ0FBQztRQUNsQyxRQUFRLEVBQUUsT0FBTyxDQUFDLEdBQUcsQ0FBQyxvQkFBb0I7UUFDMUMsWUFBWSxFQUFFLE9BQU8sQ0FBQyxHQUFHLENBQUMsd0JBQXdCO1FBQ2xELFdBQVcsRUFBRSxTQUFTLEVBQUUsa0JBQWtCO1FBQzFDLFdBQVcsRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLHVCQUF1QjtLQUNqRCxDQUFDLENBQUM7SUFFSCxJQUFJLENBQUM7UUFDSCxNQUFNLFlBQVksR0FBRyxNQUFNLFdBQVcsQ0FBQyxXQUFXLENBQUMsR0FBRyxDQUFDLEdBQUcsQ0FBQyxDQUFDO1FBQzVELE1BQU0sS0FBSyxHQUFHLFlBQVksQ0FBQyxPQUFPLEVBQUUsQ0FBQztRQUVyQyxNQUFNLFdBQVcsR0FBRyxLQUFLLENBQUMsWUFBWSxDQUFDO1FBQ3ZDLE1BQU0sWUFBWSxHQUFHLEtBQUssQ0FBQyxhQUFhLENBQUM7UUFDekMsTUFBTSxTQUFTLEdBQUcsSUFBSSxJQUFJLENBQ3hCLElBQUksQ0FBQyxHQUFHLEVBQUUsR0FBRyxLQUFLLENBQUMsVUFBVSxHQUFHLElBQUksQ0FDckMsQ0FBQyxXQUFXLEVBQUUsQ0FBQztRQUNoQixNQUFNLE9BQU8sR0FBRyxLQUFLLENBQUMsT0FBTyxDQUFDO1FBRTlCLDJDQUEyQztRQUMzQyxNQUFNLFFBQVEsR0FBRzs7Ozs7O1NBTVosQ0FBQztRQUNOLE1BQU0sU0FBUyxHQUFHO1lBQ2hCLE1BQU07WUFDTixPQUFPLEVBQUUsWUFBWTtZQUNyQixXQUFXO1lBQ1gsWUFBWTtZQUNaLFNBQVM7WUFDVCxJQUFJLEVBQUUsRUFBRSxPQUFPLEVBQUU7U0FDbEIsQ0FBQztRQUNGLE1BQU0sSUFBQSxtQ0FBbUIsRUFBQyxRQUFRLEVBQUUsU0FBUyxFQUFFLGlCQUFpQixFQUFFLE1BQU0sQ0FBQyxDQUFDO1FBRTFFLE9BQU8sR0FBRyxDQUFDLFFBQVEsQ0FBQyw0QkFBNEIsQ0FBQyxDQUFDO0lBQ3BELENBQUM7SUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO1FBQ2YsT0FBTyxDQUFDLEtBQUssQ0FBQyx5Q0FBeUMsRUFBRSxLQUFLLENBQUMsQ0FBQztRQUNoRSxPQUFPLEdBQUc7YUFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2FBQ1gsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLDBDQUEwQyxFQUFFLENBQUMsQ0FBQztJQUNuRSxDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCB7IGdldFNlc3Npb24gfSBmcm9tICdzdXBlcnRva2Vucy1ub2RlL25leHRqcyc7XG5pbXBvcnQgeyBTZXNzaW9uQ29udGFpbmVyIH0gZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZS9yZWNpcGUvc2Vzc2lvbic7XG5pbXBvcnQgeyBleGVjdXRlR3JhcGhRTFF1ZXJ5IH0gZnJvbSAnLi4vLi4vLi4vLi4vLi4vcHJvamVjdC9mdW5jdGlvbnMvX2xpYnMvZ3JhcGhxbENsaWVudCc7XG5pbXBvcnQgT0F1dGhDbGllbnQgZnJvbSAnaW50dWl0LW9hdXRoJztcblxuZXhwb3J0IGRlZmF1bHQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlcihcbiAgcmVxOiBOZXh0QXBpUmVxdWVzdCxcbiAgcmVzOiBOZXh0QXBpUmVzcG9uc2Vcbikge1xuICBsZXQgc2Vzc2lvbjogU2Vzc2lvbkNvbnRhaW5lcjtcbiAgdHJ5IHtcbiAgICBzZXNzaW9uID0gYXdhaXQgZ2V0U2Vzc2lvbihyZXEsIHJlcywge1xuICAgICAgb3ZlcnJpZGVHbG9iYWxDbGFpbVZhbGlkYXRvcnM6ICgpID0+IFtdLFxuICAgIH0pO1xuICB9IGNhdGNoIChlcnIpIHtcbiAgICByZXR1cm4gcmVzLnN0YXR1cyg0MDEpLmpzb24oeyBtZXNzYWdlOiAnVW5hdXRob3JpemVkJyB9KTtcbiAgfVxuXG4gIGNvbnN0IHVzZXJJZCA9IHNlc3Npb24uZ2V0VXNlcklkKCk7XG4gIGNvbnN0IG9hdXRoQ2xpZW50ID0gbmV3IE9BdXRoQ2xpZW50KHtcbiAgICBjbGllbnRJZDogcHJvY2Vzcy5lbnYuUVVJQ0tCT09LU19DTElFTlRfSUQsXG4gICAgY2xpZW50U2VjcmV0OiBwcm9jZXNzLmVudi5RVUlDS0JPT0tTX0NMSUVOVF9TRUNSRVQsXG4gICAgZW52aXJvbm1lbnQ6ICdzYW5kYm94JywgLy8gb3IgJ3Byb2R1Y3Rpb24nXG4gICAgcmVkaXJlY3RVcmk6IHByb2Nlc3MuZW52LlFVSUNLQk9PS1NfUkVESVJFQ1RfVVJJLFxuICB9KTtcblxuICB0cnkge1xuICAgIGNvbnN0IGF1dGhSZXNwb25zZSA9IGF3YWl0IG9hdXRoQ2xpZW50LmNyZWF0ZVRva2VuKHJlcS51cmwpO1xuICAgIGNvbnN0IHRva2VuID0gYXV0aFJlc3BvbnNlLmdldEpzb24oKTtcblxuICAgIGNvbnN0IGFjY2Vzc1Rva2VuID0gdG9rZW4uYWNjZXNzX3Rva2VuO1xuICAgIGNvbnN0IHJlZnJlc2hUb2tlbiA9IHRva2VuLnJlZnJlc2hfdG9rZW47XG4gICAgY29uc3QgZXhwaXJlc0F0ID0gbmV3IERhdGUoXG4gICAgICBEYXRlLm5vdygpICsgdG9rZW4uZXhwaXJlc19pbiAqIDEwMDBcbiAgICApLnRvSVNPU3RyaW5nKCk7XG4gICAgY29uc3QgcmVhbG1JZCA9IHRva2VuLnJlYWxtSWQ7XG5cbiAgICAvLyBTYXZlIHRoZSB0b2tlbnMgdG8gdGhlIHVzZXJfdG9rZW5zIHRhYmxlXG4gICAgY29uc3QgbXV0YXRpb24gPSBgXG4gICAgICAgICAgICBtdXRhdGlvbiBJbnNlcnRVc2VyVG9rZW4oJHVzZXJJZDogU3RyaW5nISwgJHNlcnZpY2U6IFN0cmluZyEsICRhY2Nlc3NUb2tlbjogU3RyaW5nISwgJHJlZnJlc2hUb2tlbjogU3RyaW5nLCAkZXhwaXJlc0F0OiB0aW1lc3RhbXB0eiEsICRtZXRhOiBqc29uYikge1xuICAgICAgICAgICAgICAgIGluc2VydF91c2VyX3Rva2Vuc19vbmUob2JqZWN0OiB7dXNlcl9pZDogJHVzZXJJZCwgc2VydmljZTogJHNlcnZpY2UsIGFjY2Vzc190b2tlbjogJGFjY2Vzc1Rva2VuLCByZWZyZXNoX3Rva2VuOiAkcmVmcmVzaFRva2VuLCBleHBpcmVzX2F0OiAkZXhwaXJlc0F0LCBtZXRhOiAkbWV0YX0pIHtcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgc2VydmljZTogJ3F1aWNrYm9va3MnLFxuICAgICAgYWNjZXNzVG9rZW4sXG4gICAgICByZWZyZXNoVG9rZW4sXG4gICAgICBleHBpcmVzQXQsXG4gICAgICBtZXRhOiB7IHJlYWxtSWQgfSxcbiAgICB9O1xuICAgIGF3YWl0IGV4ZWN1dGVHcmFwaFFMUXVlcnkobXV0YXRpb24sIHZhcmlhYmxlcywgJ0luc2VydFVzZXJUb2tlbicsIHVzZXJJZCk7XG5cbiAgICByZXR1cm4gcmVzLnJlZGlyZWN0KCcvU2V0dGluZ3MvVXNlclZpZXdTZXR0aW5ncycpO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGNvbnNvbGUuZXJyb3IoJ0Vycm9yIGR1cmluZyBRdWlja0Jvb2tzIE9BdXRoIGNhbGxiYWNrOicsIGVycm9yKTtcbiAgICByZXR1cm4gcmVzXG4gICAgICAuc3RhdHVzKDUwMClcbiAgICAgIC5qc29uKHsgbWVzc2FnZTogJ0ZhaWxlZCB0byBjb21wbGV0ZSBRdWlja0Jvb2tzIE9BdXRoIGZsb3cnIH0pO1xuICB9XG59XG4iXX0=