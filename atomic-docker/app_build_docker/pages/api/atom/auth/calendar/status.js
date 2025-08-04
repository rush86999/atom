"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const nextjs_1 = require("supertokens-node/nextjs");
const express_1 = require("supertokens-node/recipe/session/framework/express");
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const backendConfig_1 = require("../../../../../config/backendConfig"); // Adjusted path
const constants_1 = require("../../../../../../project/functions/atom-agent/_libs/constants");
const graphqlClient_1 = require("../../../../../../project/functions/atom-agent/_libs/graphqlClient");
const googleapis_1 = require("googleapis");
const constants_2 = require("../../../../../../project/functions/atom-agent/_libs/constants");
supertokens_node_1.default.init((0, backendConfig_1.backendConfig)());
const GOOGLE_CALENDAR_SERVICE_NAME = 'google_calendar';
// Basic check if token seems present and not obviously expired
// For a more robust check, an actual API call to Google is better.
async function checkTokenValidity(userId) {
    if (!constants_1.HASURA_GRAPHQL_URL || !constants_1.HASURA_ADMIN_SECRET) {
        console.error('STATUS: GraphQL client is not configured.');
        return { isConnected: false, error: 'config_error' };
    }
    const query = `
        query GetUserTokenForStatusCheck($userId: String!, $serviceName: String!) {
            user_tokens(
                where: { user_id: { _eq: $userId }, service_name: { _eq: $serviceName } },
                order_by: { created_at: desc },
                limit: 1
            ) {
                access_token
                refresh_token
                expiry_date
            }
        }
    `;
    const variables = { userId, serviceName: GOOGLE_CALENDAR_SERVICE_NAME };
    const operationName = 'GetUserTokenForStatusCheck';
    try {
        const response = await (0, graphqlClient_1.executeGraphQLQuery)(query, variables, operationName, userId);
        if (!response ||
            !response.user_tokens ||
            response.user_tokens.length === 0 ||
            !response.user_tokens[0].access_token) {
            return { isConnected: false };
        }
        const tokenRecord = response.user_tokens[0];
        // Optional: Check expiry if available and reasonably current.
        // Note: expiry_date from Google is a timestamp. If it's stored as ISO string, parse it.
        // A more reliable check is to try to use the token.
        if (tokenRecord.expiry_date) {
            const expiryTimestamp = new Date(tokenRecord.expiry_date).getTime();
            if (Date.now() > expiryTimestamp - 5 * 60 * 1000) {
                // 5 minutes buffer
                // Token is expired or close to expiring. If there's a refresh token, it might be auto-refreshed on next use.
                // For status, if there's a refresh token, we can still consider it "connected" as it's refreshable.
                if (!tokenRecord.refresh_token) {
                    console.log(`STATUS: Access token for user ${userId} is expired and no refresh token found.`);
                    return { isConnected: false, error: 'token_expired_no_refresh' };
                }
                console.log(`STATUS: Access token for user ${userId} is near expiry/expired, but refresh token exists.`);
            }
        }
        // Attempt a lightweight API call to verify the token
        if (tokenRecord.access_token) {
            if (!constants_2.ATOM_GOOGLE_CALENDAR_CLIENT_ID ||
                !constants_2.ATOM_GOOGLE_CALENDAR_CLIENT_SECRET) {
                console.error('STATUS: Google OAuth client credentials not configured for API test call.');
                // Fallback: if token exists in DB, assume connected for now, but log this issue.
                return { isConnected: true, email: undefined }; // Cannot fetch email without API call
            }
            const oauth2Client = new googleapis_1.google.auth.OAuth2(constants_2.ATOM_GOOGLE_CALENDAR_CLIENT_ID, constants_2.ATOM_GOOGLE_CALENDAR_CLIENT_SECRET);
            oauth2Client.setCredentials({
                access_token: tokenRecord.access_token,
                refresh_token: tokenRecord.refresh_token || undefined,
            });
            try {
                const calendar = googleapis_1.google.calendar({ version: 'v3', auth: oauth2Client });
                await calendar.calendarList.get({ calendarId: 'primary' }); // A simple, lightweight call
                // Try to get user's email from People API if scope allows (optional)
                // Requires 'https://www.googleapis.com/auth/userinfo.email' or similar scope
                // const people = google.people({ version: 'v1', auth: oauth2Client });
                // const { data: person } = await people.people.get({
                //     resourceName: 'people/me',
                //     personFields: 'emailAddresses',
                // });
                // const userEmail = person.emailAddresses?.[0]?.value;
                // return { isConnected: true, email: userEmail || undefined };
                console.log(`STATUS: Token for user ${userId} is valid (tested with calendarList.get).`);
                return { isConnected: true }; // Email fetching can be added if needed and scopes permit
            }
            catch (apiError) {
                console.warn(`STATUS: Google API call failed for user ${userId} with stored token. Error: ${apiError.message}`);
                // If 'invalid_grant' or similar, token is bad.
                if (apiError.response?.data?.error === 'invalid_grant' ||
                    apiError.code === 401) {
                    return { isConnected: false, error: 'token_invalid_or_expired' };
                }
                // Other errors might be temporary, but for status, safer to say not connected if API fails.
                return { isConnected: false, error: 'api_call_failed' };
            }
        }
        return { isConnected: true }; // Fallback if only access_token was found and no expiry check failed.
    }
    catch (error) {
        console.error(`STATUS: Exception during token status check for userId ${userId}:`, error);
        return { isConnected: false, error: 'status_check_exception' };
    }
}
async function handler(req, res) {
    await (0, nextjs_1.superTokensNextWrapper)(async (next) => (0, express_1.verifySession)()(req, res, next), req, res);
    if (req.method !== 'GET') {
        res.setHeader('Allow', ['GET']);
        return res
            .status(405)
            .json({ message: `Method ${req.method} Not Allowed` });
    }
    const session = req.session;
    const userId = session?.getUserId();
    if (!userId) {
        console.error('STATUS: User not authenticated for status check.');
        return res
            .status(401)
            .json({ isConnected: false, error: 'User not authenticated.' });
    }
    try {
        const status = await checkTokenValidity(userId);
        console.log(`STATUS: Google Calendar connection status for user ${userId}: ${status.isConnected}`);
        return res.status(200).json(status);
    }
    catch (error) {
        console.error(`STATUS: Error getting Google Calendar connection status for user ${userId}:`, error);
        return res
            .status(500)
            .json({ isConnected: false, error: 'Failed to get connection status.' });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic3RhdHVzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsic3RhdHVzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7O0FBMEpBLDBCQTBDQztBQW5NRCxvREFBaUU7QUFDakUsK0VBQWtGO0FBQ2xGLHdFQUEyQztBQUMzQyx1RUFBb0UsQ0FBQyxnQkFBZ0I7QUFDckYsOEZBR3dFO0FBQ3hFLHNHQUF5RztBQUN6RywyQ0FBb0M7QUFDcEMsOEZBR3dFO0FBRXhFLDBCQUFXLENBQUMsSUFBSSxDQUFDLElBQUEsNkJBQWEsR0FBRSxDQUFDLENBQUM7QUFFbEMsTUFBTSw0QkFBNEIsR0FBRyxpQkFBaUIsQ0FBQztBQVN2RCwrREFBK0Q7QUFDL0QsbUVBQW1FO0FBQ25FLEtBQUssVUFBVSxrQkFBa0IsQ0FDL0IsTUFBYztJQUVkLElBQUksQ0FBQyw4QkFBa0IsSUFBSSxDQUFDLCtCQUFtQixFQUFFLENBQUM7UUFDaEQsT0FBTyxDQUFDLEtBQUssQ0FBQywyQ0FBMkMsQ0FBQyxDQUFDO1FBQzNELE9BQU8sRUFBRSxXQUFXLEVBQUUsS0FBSyxFQUFFLEtBQUssRUFBRSxjQUFjLEVBQUUsQ0FBQztJQUN2RCxDQUFDO0lBRUQsTUFBTSxLQUFLLEdBQUc7Ozs7Ozs7Ozs7OztLQVlYLENBQUM7SUFDSixNQUFNLFNBQVMsR0FBRyxFQUFFLE1BQU0sRUFBRSxXQUFXLEVBQUUsNEJBQTRCLEVBQUUsQ0FBQztJQUN4RSxNQUFNLGFBQWEsR0FBRyw0QkFBNEIsQ0FBQztJQUVuRCxJQUFJLENBQUM7UUFDSCxNQUFNLFFBQVEsR0FBRyxNQUFNLElBQUEsbUNBQW1CLEVBRXZDLEtBQUssRUFBRSxTQUFTLEVBQUUsYUFBYSxFQUFFLE1BQU0sQ0FBQyxDQUFDO1FBRTVDLElBQ0UsQ0FBQyxRQUFRO1lBQ1QsQ0FBQyxRQUFRLENBQUMsV0FBVztZQUNyQixRQUFRLENBQUMsV0FBVyxDQUFDLE1BQU0sS0FBSyxDQUFDO1lBQ2pDLENBQUMsUUFBUSxDQUFDLFdBQVcsQ0FBQyxD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QUFDO1FBQ1osT0FBTyxDQUFDLEtBQUssQ0FBQyxrREFBa0QsQ0FBQyxDQUFDO1FBQ2xFLE9BQU8sR0FBRzthQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7YUFDWCxJQUFJLENBQUMsRUFBRSxXQUFXLEVBQUUsS0FBSyxFQUFFLEtBQUssRUFBRSx5QkFBeUIsRUFBRSxDQUFDLENBQUM7SUFDcEUsQ0FBQztJQUVELElBQUksQ0FBQztRQUNILE1BQU0sTUFBTSxHQUFHLE1BQU0sa0JBQWtCLENBQUMsTUFBTSxDQUFDLENBQUM7UUFDaEQsT0FBTyxDQUFDLEdBQUcsQ0FDVCxzREFBc0QsTUFBTSxLQUFLLE1BQU0sQ0FBQyxXQUFXLEVBQUUsQ0FDdEYsQ0FBQztRQUNGLE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsTUFBTSxDQUFDLENBQUM7SUFDdEMsQ0FBQztJQUFDLE9BQU8sS0FBVSxFQUFFLENBQUM7UUFDcEIsT0FBTyxDQUFDLEtBQUssQ0FDWCxvRUFBb0UsTUFBTSxHQUFHLEVBQzdFLEtBQUssQ0FDTixDQUFDO1FBQ0YsT0FBTyxHQUFHO2FBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQzthQUNYLElBQUksQ0FBQyxFQUFFLFdBQVcsRUFBRSxLQUFLLEVBQUUsS0FBSyxFQUFFLGtDQUFrQyxFQUFFLENBQUMsQ0FBQztJQUM3RSxDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB0eXBlIHsgTmV4dEFwaVJlcXVlc3QsIE5leHRBcGlSZXNwb25zZSB9IGZyb20gJ25leHQnO1xuaW1wb3J0IHsgc3VwZXJUb2tlbnNOZXh0V3JhcHBlciB9IGZyb20gJ3N1cGVydG9rZW5zLW5vZGUvbmV4dGpzJztcbmltcG9ydCB7IHZlcmlmeVNlc3Npb24gfSBmcm9tICdzdXBlcnRva2Vucy1ub2RlL3JlY2lwZS9zZXNzaW9uL2ZyYW1ld29yay9leHByZXNzJztcbmltcG9ydCBzdXBlcnRva2VucyBmcm9tICdzdXBlcnRva2Vucy1ub2RlJztcbmltcG9ydCB7IGJhY2tlbmRDb25maWcgfSBmcm9tICcuLi8uLi8uLi8uLi8uLi9jb25maWcvYmFja2VuZENvbmZpZyc7IC8vIEFkanVzdGVkIHBhdGhcbmltcG9ydCB7XG4gIEhBU1VSQV9BRE1JTl9TRUNSRVQsXG4gIEhBU1VSQV9HUkFQSFFMX1VSTCxcbn0gZnJvbSAnLi4vLi4vLi4vLi4vLi4vLi4vcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IHsgZXhlY3V0ZUdyYXBoUUxRdWVyeSB9IGZyb20gJy4uLy4uLy4uLy4uLy4uLy4uL3Byb2plY3QvZnVuY3Rpb25zL2F0b20tYWdlbnQvX2xpYnMvZ3JhcGhxbENsaWVudCc7XG5pbXBvcnQgeyBnb29nbGUgfSBmcm9tICdnb29nbGVhcGlzJztcbmltcG9ydCB7XG4gIEFUT01fR09PR0xFX0NBTEVOREFSX0NMSUVOVF9JRCxcbiAgQVRPTV9HT09HTEVfQ0FMRU5EQVJfQ0xJRU5UX1NFQ1JFVCxcbn0gZnJvbSAnLi4vLi4vLi4vLi4vLi4vLi4vcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC9fbGlicy9jb25zdGFudHMnO1xuXG5zdXBlcnRva2Vucy5pbml0KGJhY2tlbmRDb25maWcoKSk7XG5cbmNvbnN0IEdPT0dMRV9DQUxFTkRBUl9TRVJWSUNFX05BTUUgPSAnZ29vZ2xlX2NhbGVuZGFyJztcblxuaW50ZXJmYWNlIFVzZXJUb2tlblJlY29yZCB7XG4gIGFjY2Vzc190b2tlbjogc3RyaW5nO1xuICByZWZyZXNoX3Rva2VuPzogc3RyaW5nIHwgbnVsbDtcbiAgZXhwaXJ5X2RhdGU/OiBzdHJpbmcgfCBudWxsOyAvLyBJU08gU3RyaW5nIGZyb20gREJcbiAgLy8gV2UgZG9uJ3QgbmVjZXNzYXJpbHkgbmVlZCBlbWFpbCBoZXJlLCBidXQgaXQgY291bGQgYmUgZmV0Y2hlZCBpZiBuZWVkZWRcbn1cblxuLy8gQmFzaWMgY2hlY2sgaWYgdG9rZW4gc2VlbXMgcHJlc2VudCBhbmQgbm90IG9idmlvdXNseSBleHBpcmVkXG4vLyBGb3IgYSBtb3JlIHJvYnVzdCBjaGVjaywgYW4gYWN0dWFsIEFQSSBjYWxsIHRvIEdvb2dsZSBpcyBiZXR0ZXIuXG5hc3luYyBmdW5jdGlvbiBjaGVja1Rva2VuVmFsaWRpdHkoXG4gIHVzZXJJZDogc3RyaW5nXG4pOiBQcm9taXNlPHsgaXNDb25uZWN0ZWQ6IGJvb2xlYW47IGVtYWlsPzogc3RyaW5nOyBlcnJvcj86IHN0cmluZyB9PiB7XG4gIGlmICghSEFTVVJBX0dSQVBIUUxfVVJMIHx8ICFIQVNVUkFfQURNSU5fU0VDUkVUKSB7XG4gICAgY29uc29sZS5lcnJvcignU1RBVFVTOiBHcmFwaFFMIGNsaWVudCBpcyBub3QgY29uZmlndXJlZC4nKTtcbiAgICByZXR1cm4geyBpc0Nvbm5lY3RlZDogZmFsc2UsIGVycm9yOiAnY29uZmlnX2Vycm9yJyB9O1xuICB9XG5cbiAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgIHF1ZXJ5IEdldFVzZXJUb2tlbkZvclN0YXR1c0NoZWNrKCR1c2VySWQ6IFN0cmluZyEsICRzZXJ2aWNlTmFtZTogU3RyaW5nISkge1xuICAgICAgICAgICAgdXNlcl90b2tlbnMoXG4gICAgICAgICAgICAgICAgd2hlcmU6IHsgdXNlcl9pZDogeyBfZXE6ICR1c2VySWQgfSwgc2VydmljZV9uYW1lOiB7IF9lcTogJHNlcnZpY2VOYW1lIH0gfSxcbiAgICAgICAgICAgICAgICBvcmRlcl9ieTogeyBjcmVhdGVkX2F0OiBkZXNjIH0sXG4gICAgICAgICAgICAgICAgbGltaXQ6IDFcbiAgICAgICAgICAgICkge1xuICAgICAgICAgICAgICAgIGFjY2Vzc190b2tlblxuICAgICAgICAgICAgICAgIHJlZnJlc2hfdG9rZW5cbiAgICAgICAgICAgICAgICBleHBpcnlfZGF0ZVxuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgYDtcbiAgY29uc3QgdmFyaWFibGVzID0geyB1c2VySWQsIHNlcnZpY2VOYW1lOiBHT09HTEVfQ0FMRU5EQVJfU0VSVklDRV9OQU1FIH07XG4gIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnR2V0VXNlclRva2VuRm9yU3RhdHVzQ2hlY2snO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBleGVjdXRlR3JhcGhRTFF1ZXJ5PHtcbiAgICAgIHVzZXJfdG9rZW5zOiBVc2VyVG9rZW5SZWNvcmRbXTtcbiAgICB9PihxdWVyeSwgdmFyaWFibGVzLCBvcGVyYXRpb25OYW1lLCB1c2VySWQpO1xuXG4gICAgaWYgKFxuICAgICAgIXJlc3BvbnNlIHx8XG4gICAgICAhcmVzcG9uc2UudXNlcl90b2tlbnMgfHxcbiAgICAgIHJlc3BvbnNlLnVzZXJfdG9rZW5zLmxlbmd0aCA9PT0gMCB8fFxuICAgICAgIXJlc3BvbnNlLnVzZXJfdG9rZW5zWzBdLmFjY2Vzc190b2tlblxuICAgICkge1xuICAgICAgcmV0dXJuIHsgaXNDb25uZWN0ZWQ6IGZhbHNlIH07XG4gICAgfVxuXG4gICAgY29uc3QgdG9rZW5SZWNvcmQgPSByZXNwb25zZS51c2VyX3Rva2Vuc1swXTtcblxuICAgIC8vIE9wdGlvbmFsOiBDaGVjayBleHBpcnkgaWYgYXZhaWxhYmxlIGFuZCByZWFzb25hYmx5IGN1cnJlbnQuXG4gICAgLy8gTm90ZTogZXhwaXJ5X2RhdGUgZnJvbSBHb29nbGUgaXMgYSB0aW1lc3RhbXAuIElmIGl0J3Mgc3RvcmVkIGFzIElTTyBzdHJpbmcsIHBhcnNlIGl0LlxuICAgIC8vIEEgbW9yZSByZWxpYWJsZSBjaGVjayBpcyB0byB0cnkgdG8gdXNlIHRoZSB0b2tlbi5cbiAgICBpZiAodG9rZW5SZWNvcmQuZXhwaXJ5X2RhdGUpIHtcbiAgICAgIGNvbnN0IGV4cGlyeVRpbWVzdGFtcCA9IG5ldyBEYXRlKHRva2VuUmVjb3JkLmV4cGlyeV9kYXRlKS5nZXRUaW1lKCk7XG4gICAgICBpZiAoRGF0ZS5ub3coKSA+IGV4cGlyeVRpbWVzdGFtcCAtIDUgKiA2MCAqIDEwMDApIHtcbiAgICAgICAgLy8gNSBtaW51dGVzIGJ1ZmZlclxuICAgICAgICAvLyBUb2tlbiBpcyBleHBpcmVkIG9yIGNsb3NlIHRvIGV4cGlyaW5nLiBJZiB0aGVyZSdzIGEgcmVmcmVzaCB0b2tlbiwgaXQgbWlnaHQgYmUgYXV0by1yZWZyZXNoZWQgb24gbmV4dCB1c2UuXG4gICAgICAgIC8vIEZvciBzdGF0dXMsIGlmIHRoZXJlJ3MgYSByZWZyZXNoIHRva2VuLCB3ZSBjYW4gc3RpbGwgY29uc2lkZXIgaXQgXCJjb25uZWN0ZWRcIiBhcyBpdCdzIHJlZnJlc2hhYmxlLlxuICAgICAgICBpZiAoIXRva2VuUmVjb3JkLnJlZnJlc2hfdG9rZW4pIHtcbiAgICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICAgIGBTVEFUVVM6IEFjY2VzcyB0b2tlbiBmb3IgdXNlciAke3VzZXJJZH0gaXMgZXhwaXJlZCBhbmQgbm8gcmVmcmVzaCB0b2tlbiBmb3VuZC5gXG4gICAgICAgICAgKTtcbiAgICAgICAgICByZXR1cm4geyBpc0Nvbm5lY3RlZDogZmFsc2UsIGVycm9yOiAndG9rZW5fZXhwaXJlZF9ub19yZWZyZXNoJyB9O1xuICAgICAgICB9XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIGBTVEFUVVM6IEFjY2VzcyB0b2tlbiBmb3IgdXNlciAke3VzZXJJZH0gaXMgbmVhciBleHBpcnkvZXhwaXJlZCwgYnV0IHJlZnJlc2ggdG9rZW4gZXhpc3RzLmBcbiAgICAgICAgKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyBBdHRlbXB0IGEgbGlnaHR3ZWlnaHQgQVBJIGNhbGwgdG8gdmVyaWZ5IHRoZSB0b2tlblxuICAgIGlmICh0b2tlblJlY29yZC5hY2Nlc3NfdG9rZW4pIHtcbiAgICAgIGlmIChcbiAgICAgICAgIUFUT01fR09PR0xFX0NBTEVOREFSX0NMSUVOVF9JRCB8fFxuICAgICAgICAhQVRPTV9HT09HTEVfQ0FMRU5EQVJfQ0xJRU5UX1NFQ1JFVFxuICAgICAgKSB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICAgJ1NUQVRVUzogR29vZ2xlIE9BdXRoIGNsaWVudCBjcmVkZW50aWFscyBub3QgY29uZmlndXJlZCBmb3IgQVBJIHRlc3QgY2FsbC4nXG4gICAgICAgICk7XG4gICAgICAgIC8vIEZhbGxiYWNrOiBpZiB0b2tlbiBleGlzdHMgaW4gREIsIGFzc3VtZSBjb25uZWN0ZWQgZm9yIG5vdywgYnV0IGxvZyB0aGlzIGlzc3VlLlxuICAgICAgICByZXR1cm4geyBpc0Nvbm5lY3RlZDogdHJ1ZSwgZW1haWw6IHVuZGVmaW5lZCB9OyAvLyBDYW5ub3QgZmV0Y2ggZW1haWwgd2l0aG91dCBBUEkgY2FsbFxuICAgICAgfVxuICAgICAgY29uc3Qgb2F1dGgyQ2xpZW50ID0gbmV3IGdvb2dsZS5hdXRoLk9BdXRoMihcbiAgICAgICAgQVRPTV9HT09HTEVfQ0FMRU5EQVJfQ0xJRU5UX0lELFxuICAgICAgICBBVE9NX0dPT0dMRV9DQUxFTkRBUl9DTElFTlRfU0VDUkVUXG4gICAgICApO1xuICAgICAgb2F1dGgyQ2xpZW50LnNldENyZWRlbnRpYWxzKHtcbiAgICAgICAgYWNjZXNzX3Rva2VuOiB0b2tlblJlY29yZC5hY2Nlc3NfdG9rZW4sXG4gICAgICAgIHJlZnJlc2hfdG9rZW46IHRva2VuUmVjb3JkLnJlZnJlc2hfdG9rZW4gfHwgdW5kZWZpbmVkLFxuICAgICAgfSk7XG5cbiAgICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IGNhbGVuZGFyID0gZ29vZ2xlLmNhbGVuZGFyKHsgdmVyc2lvbjogJ3YzJywgYXV0aDogb2F1dGgyQ2xpZW50IH0pO1xuICAgICAgICBhd2FpdCBjYWxlbmRhci5jYWxlbmRhckxpc3QuZ2V0KHsgY2FsZW5kYXJJZDogJ3ByaW1hcnknIH0pOyAvLyBBIHNpbXBsZSwgbGlnaHR3ZWlnaHQgY2FsbFxuXG4gICAgICAgIC8vIFRyeSB0byBnZXQgdXNlcidzIGVtYWlsIGZyb20gUGVvcGxlIEFQSSBpZiBzY29wZSBhbGxvd3MgKG9wdGlvbmFsKVxuICAgICAgICAvLyBSZXF1aXJlcyAnaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vYXV0aC91c2VyaW5mby5lbWFpbCcgb3Igc2ltaWxhciBzY29wZVxuICAgICAgICAvLyBjb25zdCBwZW9wbGUgPSBnb29nbGUucGVvcGxlKHsgdmVyc2lvbjogJ3YxJywgYXV0aDogb2F1dGgyQ2xpZW50IH0pO1xuICAgICAgICAvLyBjb25zdCB7IGRhdGE6IHBlcnNvbiB9ID0gYXdhaXQgcGVvcGxlLnBlb3BsZS5nZXQoe1xuICAgICAgICAvLyAgICAgcmVzb3VyY2VOYW1lOiAncGVvcGxlL21lJyxcbiAgICAgICAgLy8gICAgIHBlcnNvbkZpZWxkczogJ2VtYWlsQWRkcmVzc2VzJyxcbiAgICAgICAgLy8gfSk7XG4gICAgICAgIC8vIGNvbnN0IHVzZXJFbWFpbCA9IHBlcnNvbi5lbWFpbEFkZHJlc3Nlcz8uWzBdPy52YWx1ZTtcbiAgICAgICAgLy8gcmV0dXJuIHsgaXNDb25uZWN0ZWQ6IHRydWUsIGVtYWlsOiB1c2VyRW1haWwgfHwgdW5kZWZpbmVkIH07XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIGBTVEFUVVM6IFRva2VuIGZvciB1c2VyICR7dXNlcklkfSBpcyB2YWxpZCAodGVzdGVkIHdpdGggY2FsZW5kYXJMaXN0LmdldCkuYFxuICAgICAgICApO1xuICAgICAgICByZXR1cm4geyBpc0Nvbm5lY3RlZDogdHJ1ZSB9OyAvLyBFbWFpbCBmZXRjaGluZyBjYW4gYmUgYWRkZWQgaWYgbmVlZGVkIGFuZCBzY29wZXMgcGVybWl0XG4gICAgICB9IGNhdGNoIChhcGlFcnJvcjogYW55KSB7XG4gICAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgICBgU1RBVFVTOiBHb29nbGUgQVBJIGNhbGwgZmFpbGVkIGZvciB1c2VyICR7dXNlcklkfSB3aXRoIHN0b3JlZCB0b2tlbi4gRXJyb3I6ICR7YXBpRXJyb3IubWVzc2FnZX1gXG4gICAgICAgICk7XG4gICAgICAgIC8vIElmICdpbnZhbGlkX2dyYW50JyBvciBzaW1pbGFyLCB0b2tlbiBpcyBiYWQuXG4gICAgICAgIGlmIChcbiAgICAgICAgICBhcGlFcnJvci5yZXNwb25zZT8uZGF0YT8uZXJyb3IgPT09ICdpbnZhbGlkX2dyYW50JyB8fFxuICAgICAgICAgIGFwaUVycm9yLmNvZGUgPT09IDQwMVxuICAgICAgICApIHtcbiAgICAgICAgICByZXR1cm4geyBpc0Nvbm5lY3RlZDogZmFsc2UsIGVycm9yOiAndG9rZW5faW52YWxpZF9vcl9leHBpcmVkJyB9O1xuICAgICAgICB9XG4gICAgICAgIC8vIE90aGVyIGVycm9ycyBtaWdodCBiZSB0ZW1wb3JhcnksIGJ1dCBmb3Igc3RhdHVzLCBzYWZlciB0byBzYXkgbm90IGNvbm5lY3RlZCBpZiBBUEkgZmFpbHMuXG4gICAgICAgIHJldHVybiB7IGlzQ29ubmVjdGVkOiBmYWxzZSwgZXJyb3I6ICdhcGlfY2FsbF9mYWlsZWQnIH07XG4gICAgICB9XG4gICAgfVxuXG4gICAgcmV0dXJuIHsgaXNDb25uZWN0ZWQ6IHRydWUgfTsgLy8gRmFsbGJhY2sgaWYgb25seSBhY2Nlc3NfdG9rZW4gd2FzIGZvdW5kIGFuZCBubyBleHBpcnkgY2hlY2sgZmFpbGVkLlxuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcihcbiAgICAgIGBTVEFUVVM6IEV4Y2VwdGlvbiBkdXJpbmcgdG9rZW4gc3RhdHVzIGNoZWNrIGZvciB1c2VySWQgJHt1c2VySWR9OmAsXG4gICAgICBlcnJvclxuICAgICk7XG4gICAgcmV0dXJuIHsgaXNDb25uZWN0ZWQ6IGZhbHNlLCBlcnJvcjogJ3N0YXR1c19jaGVja19leGNlcHRpb24nIH07XG4gIH1cbn1cblxuZXhwb3J0IGRlZmF1bHQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlcihcbiAgcmVxOiBOZXh0QXBpUmVxdWVzdCxcbiAgcmVzOiBOZXh0QXBpUmVzcG9uc2Vcbikge1xuICBhd2FpdCBzdXBlclRva2Vuc05leHRXcmFwcGVyKFxuICAgIGFzeW5jIChuZXh0KSA9PiB2ZXJpZnlTZXNzaW9uKCkocmVxIGFzIGFueSwgcmVzIGFzIGFueSwgbmV4dCksXG4gICAgcmVxLFxuICAgIHJlc1xuICApO1xuXG4gIGlmIChyZXEubWV0aG9kICE9PSAnR0VUJykge1xuICAgIHJlcy5zZXRIZWFkZXIoJ0FsbG93JywgWydHRVQnXSk7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg0MDUpXG4gICAgICAuanNvbih7IG1lc3NhZ2U6IGBNZXRob2QgJHtyZXEubWV0aG9kfSBOb3QgQWxsb3dlZGAgfSk7XG4gIH1cblxuICBjb25zdCBzZXNzaW9uID0gcmVxLnNlc3Npb247XG4gIGNvbnN0IHVzZXJJZCA9IHNlc3Npb24/LmdldFVzZXJJZCgpO1xuXG4gIGlmICghdXNlcklkKSB7XG4gICAgY29uc29sZS5lcnJvcignU1RBVFVTOiBVc2VyIG5vdCBhdXRoZW50aWNhdGVkIGZvciBzdGF0dXMgY2hlY2suJyk7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg0MDEpXG4gICAgICAuanNvbih7IGlzQ29ubmVjdGVkOiBmYWxzZSwgZXJyb3I6ICdVc2VyIG5vdCBhdXRoZW50aWNhdGVkLicgfSk7XG4gIH1cblxuICB0cnkge1xuICAgIGNvbnN0IHN0YXR1cyA9IGF3YWl0IGNoZWNrVG9rZW5WYWxpZGl0eSh1c2VySWQpO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYFNUQVRVUzogR29vZ2xlIENhbGVuZGFyIGNvbm5lY3Rpb24gc3RhdHVzIGZvciB1c2VyICR7dXNlcklkfTogJHtzdGF0dXMuaXNDb25uZWN0ZWR9YFxuICAgICk7XG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoMjAwKS5qc29uKHN0YXR1cyk7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgYFNUQVRVUzogRXJyb3IgZ2V0dGluZyBHb29nbGUgQ2FsZW5kYXIgY29ubmVjdGlvbiBzdGF0dXMgZm9yIHVzZXIgJHt1c2VySWR9OmAsXG4gICAgICBlcnJvclxuICAgICk7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAuanNvbih7IGlzQ29ubmVjdGVkOiBmYWxzZSwgZXJyb3I6ICdGYWlsZWQgdG8gZ2V0IGNvbm5lY3Rpb24gc3RhdHVzLicgfSk7XG4gIH1cbn1cbiJdfQ==