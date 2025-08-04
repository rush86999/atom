"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const msal_node_1 = require("@azure/msal-node");
const nextjs_1 = require("supertokens-node/nextjs");
const express_1 = require("supertokens-node/recipe/session/framework/express"); // For state validation if needed, though state contains userId
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const backendConfig_1 = require("../../../../../config/backendConfig"); // Adjusted path
const logger_1 = require("../../../../../../project/functions/_utils/logger");
const constants_1 = require("../../../../../../project/functions/atom-agent/_libs/constants");
const graphqlClient_1 = require("../../../../../../project/functions/atom-agent/_libs/graphqlClient");
// TODO: Move these to a central constants file and manage via environment variables
const MSTEAMS_CLIENT_ID = process.env.MSTEAMS_CLIENT_ID || 'YOUR_MSTEAMS_APP_CLIENT_ID';
const MSTEAMS_CLIENT_SECRET = process.env.MSTEAMS_CLIENT_SECRET || 'YOUR_MSTEAMS_APP_CLIENT_SECRET';
const MSTEAMS_REDIRECT_URI = process.env.MSTEAMS_REDIRECT_URI ||
    'http://localhost:3000/api/atom/auth/msteams/callback';
const MSTEAMS_AUTHORITY = process.env.MSTEAMS_AUTHORITY || 'https://login.microsoftonline.com/common';
const MSTEAMS_SCOPES = [
    'Chat.Read',
    'ChannelMessage.Read.All',
    'User.Read',
    'offline_access',
]; // Ensure offline_access for refresh token
const MSTEAMS_TOKEN_SERVICE_NAME = 'msteams_graph'; // Or 'microsoft_graph'
supertokens_node_1.default.init((0, backendConfig_1.backendConfig)());
const msalConfig = {
    auth: {
        clientId: MSTEAMS_CLIENT_ID,
        authority: MSTEAMS_AUTHORITY,
        clientSecret: MSTEAMS_CLIENT_SECRET,
    },
    system: {
    /* ... logger config ... */
    },
};
// Adapted from Google OAuth callback
async function saveMSTeamsUserTokens(userId, tokens) {
    logger_1.logger.info(`[MSTeamsAuthCallback] Saving MS Teams tokens for userId: ${userId}`);
    if (!constants_1.HASURA_GRAPHQL_URL || !constants_1.HASURA_ADMIN_SECRET) {
        logger_1.logger.error('[MSTeamsAuthCallback] GraphQL client not configured for saveMSTeamsUserTokens.');
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'GraphQL client is not configured.',
            },
        };
    }
    if (!tokens.accessToken || !tokens.account) {
        logger_1.logger.error('[MSTeamsAuthCallback] Critical token information missing from MSAL response.');
        return {
            ok: false,
            error: {
                code: 'TOKEN_ERROR',
                message: 'Essential token information missing from MSAL response.',
            },
        };
    }
    const mutation = `
    mutation UpsertUserToken($objects: [user_tokens_insert_input!]!) {
      insert_user_tokens(
        objects: $objects,
        on_conflict: {
          constraint: user_tokens_user_id_service_name_key,
          update_columns: [access_token, refresh_token, expiry_date, scope, token_type, id_token, other_data, updated_at]
        }
      ) {
        affected_rows
      }
    }
  `;
    // MSAL's AuthenticationResult has account.idTokenClaims.exp (seconds since epoch) for id_token expiry
    // tokens.expiresOn is a Date object for access_token expiry
    const tokenDataForDb = {
        user_id: userId,
        service_name: MSTEAMS_TOKEN_SERVICE_NAME,
        access_token: tokens.accessToken,
        refresh_token: tokens.refreshToken, // This should be present if offline_access scope was granted
        expiry_date: tokens.expiresOn ? tokens.expiresOn.toISOString() : null,
        scope: tokens.scopes.join(' '),
        token_type: 'Bearer', // Typically Bearer for MS Graph
        id_token: tokens.idToken, // Store ID token if needed
        other_data: {
            accountHomeAccountId: tokens.account.homeAccountId, // Useful for MSAL cache lookups later if needed
            accountEnvironment: tokens.account.environment,
            accountTenantId: tokens.account.tenantId,
        },
        updated_at: new Date().toISOString(),
    };
    const variables = { objects: [tokenDataForDb] };
    try {
        const response = await (0, graphqlClient_1.executeGraphQLMutation)(mutation, variables, 'UpsertMSTeamsUserToken', userId);
        if (response &&
            response.insert_user_tokens &&
            response.insert_user_tokens.affected_rows > 0) {
            logger_1.logger.info(`[MSTeamsAuthCallback] MS Teams tokens saved successfully for user ${userId}.`);
            return { ok: true };
        }
        else {
            logger_1.logger.warn(`[MSTeamsAuthCallback] MS Teams token save reported 0 affected_rows for user ${userId}.`, response);
            return {
                ok: false,
                error: {
                    code: 'DB_NO_ROWS_AFFECTED',
                    message: 'Token save did not affect any rows.',
                },
            };
        }
    }
    catch (error) {
        logger_1.logger.error(`[MSTeamsAuthCallback] Exception saving MS Teams tokens for user ${userId}:`, error);
        return {
            ok: false,
            error: { code: 'TOKEN_SAVE_FAILED', message: error.message },
        };
    }
}
async function handler(req, res) {
    // It's important to verify the session of the user who initiated the flow,
    // usually by checking the 'state' parameter returned by Microsoft.
    // The 'state' should match what was sent in the initiate step (e.g., SuperTokens userId).
    const receivedState = req.query.state;
    // TODO: Securely validate the state parameter against a stored value from the initiate step if not using userId directly.
    // For now, we assume state IS the userId for simplicity as set in initiate.ts
    // Verify SuperTokens session for the user ID passed in state
    // This ensures the callback is for a valid, currently logged-in user session.
    let session;
    try {
        session = await (0, nextjs_1.superTokensNextWrapper)(async (next) => (0, express_1.verifySession)({ sessionRequired: true })(req, res, next), req, res);
    }
    catch (error) {
        // verifySession throws if no session
        logger_1.logger.error('[MSTeamsAuthCallback] SuperTokens session verification failed in callback:', error);
        return res
            .status(401)
            .redirect('/Auth/UserLogin?error=session_expired_oauth');
    }
    const sessionUserId = session?.getUserId();
    if (!sessionUserId || sessionUserId !== receivedState) {
        logger_1.logger.error(`[MSTeamsAuthCallback] Invalid state or session mismatch. Session UserID: ${sessionUserId}, State: ${receivedState}`);
        return res
            .status(400)
            .redirect('/Settings/UserViewSettings?msteams_auth_error=invalid_state');
    }
    const userId = sessionUserId; // Confirmed user
    if (req.query.error) {
        logger_1.logger.error(`[MSTeamsAuthCallback] Error from MS Identity platform for user ${userId}: ${req.query.error_description || req.query.error}`);
        return res.redirect(`/Settings/UserViewSettings?msteams_auth_error=${encodeURIComponent(req.query.error)}`);
    }
    if (!req.query.code || typeof req.query.code !== 'string') {
        logger_1.logger.error(`[MSTeamsAuthCallback] No authorization code received for user ${userId}.`);
        return res.redirect('/Settings/UserViewSettings?msteams_auth_error=no_code');
    }
    if (!MSTEAMS_CLIENT_ID ||
        MSTEAMS_CLIENT_ID === 'YOUR_MSTEAMS_APP_CLIENT_ID' ||
        !MSTEAMS_CLIENT_SECRET ||
        MSTEAMS_CLIENT_SECRET === 'YOUR_MSTEAMS_APP_CLIENT_SECRET') {
        logger_1.logger.error('[MSTeamsAuthCallback] MS Teams Client ID or Secret not configured.');
        return res
            .status(500)
            .json({
            message: 'MS Teams OAuth configuration error on server (callback).',
        });
    }
    const cca = new msal_node_1.ConfidentialClientApplication(msalConfig);
    const tokenRequest = {
        code: req.query.code,
        scopes: MSTEAMS_SCOPES,
        redirectUri: MSTEAMS_REDIRECT_URI,
    };
    try {
        const msalResponse = await cca.acquireTokenByCode(tokenRequest);
        if (!msalResponse || !msalResponse.accessToken) {
            logger_1.logger.error(`[MSTeamsAuthCallback] Failed to acquire MS Teams token for user ${userId}. MSAL response empty or missing accessToken.`, msalResponse);
            throw new Error('Failed to acquire MS Teams token.');
        }
        logger_1.logger.info(`[MSTeamsAuthCallback] MS Teams token acquired successfully for user ${userId}. Account: ${msalResponse.account?.username}`);
        const saveResult = await saveMSTeamsUserTokens(userId, msalResponse);
        if (!saveResult.ok) {
            logger_1.logger.error(`[MSTeamsAuthCallback] Failed to save MS Teams tokens for user ${userId}:`, saveResult.error);
            const errMsg = saveResult.error?.message || 'token_save_failed';
            return res.redirect(`/Settings/UserViewSettings?msteams_auth_error=${encodeURIComponent(errMsg)}`);
        }
        logger_1.logger.info(`[MSTeamsAuthCallback] MS Teams successfully connected and tokens stored for user ${userId}.`);
        // Redirect to a success page or settings page
        return res.redirect('/Settings/UserViewSettings?msteams_auth_success=true');
    }
    catch (error) {
        logger_1.logger.error(`[MSTeamsAuthCallback] Error acquiring/saving MS Teams token for user ${userId}:`, error);
        const errMsg = error.message || error.errorCode || 'msteams_token_acquisition_failed';
        return res.redirect(`/Settings/UserViewSettings?msteams_auth_error=${encodeURIComponent(errMsg)}`);
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsbGJhY2suanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjYWxsYmFjay50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQThKQSwwQkFnSUM7QUE3UkQsZ0RBTTBCO0FBQzFCLG9EQUFpRTtBQUNqRSwrRUFBa0YsQ0FBQywrREFBK0Q7QUFDbEosd0VBQTJDO0FBQzNDLHVFQUFvRSxDQUFDLGdCQUFnQjtBQUNyRiw4RUFBMkU7QUFFM0UsOEZBR3dFO0FBQ3hFLHNHQUE0RztBQUU1RyxvRkFBb0Y7QUFDcEYsTUFBTSxpQkFBaUIsR0FDckIsT0FBTyxDQUFDLEdBQUcsQ0FBQyxpQkFBaUIsSUFBSSw0QkFBNEIsQ0FBQztBQUNoRSxNQUFNLHFCQUFxQixHQUN6QixPQUFPLENBQUMsR0FBRyxDQUFDLHFCQUFxQixJQUFJLGdDQUFnQyxDQUFDO0FBQ3hFLE1BQU0sb0JBQW9CLEdBQ3hCLE9BQU8sQ0FBQyxHQUFHLENBQUMsb0JBQW9CO0lBQ2hDLHNEQUFzRCxDQUFDO0FBQ3pELE1BQU0saUJBQWlCLEdBQ3JCLE9BQU8sQ0FBQyxHQUFHLENBQUMsaUJBQWlCLElBQUksMENBQTBDLENBQUM7QUFDOUUsTUFBTSxjQUFjLEdBQUc7SUFDckIsV0FBVztJQUNYLHlCQUF5QjtJQUN6QixXQUFXO0lBQ1gsZ0JBQWdCO0NBQ2pCLENBQUMsQ0FBQywwQ0FBMEM7QUFFN0MsTUFBTSwwQkFBMEIsR0FBRyxlQUFlLENBQUMsQ0FBQyx1QkFBdUI7QUFFM0UsMEJBQVcsQ0FBQyxJQUFJLENBQUMsSUFBQSw2QkFBYSxHQUFFLENBQUMsQ0FBQztBQUVsQyxNQUFNLFVBQVUsR0FBa0I7SUFDaEMsSUFBSSxFQUFFO1FBQ0osUUFBUSxFQUFFLGlCQUFpQjtRQUMzQixTQUFTLEVBQUUsaUJBQWlCO1FBQzVCLFlBQVksRUFBRSxxQkFBcUI7S0FDcEM7SUFDRCxNQUFNLEVBQUU7SUFDTiwyQkFBMkI7S0FDNUI7Q0FDRixDQUFDO0FBRUYscUNBQXFDO0FBQ3JDLEtBQUssVUFB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LENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLGVBQU0sQ0FBQyxLQUFLLENBQ1Ysd0VBQXdFLE1BQU0sR0FBRyxFQUNqRixLQUFLLENBQ04sQ0FBQztRQUNGLE1BQU0sTUFBTSxHQUNWLEtBQUssQ0FBQyxPQUFPLElBQUksS0FBSyxDQUFDLFNBQVMsSUFBSSxrQ0FBa0MsQ0FBQztRQUN6RSxPQUFPLEdBQUcsQ0FBQyxRQUFRLENBQ2pCLGlEQUFpRCxrQkFBa0IsQ0FBQyxNQUFNLENBQUMsRUFBRSxDQUM5RSxDQUFDO0lBQ0osQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgdHlwZSB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCB7XG4gIENvbmZpZGVudGlhbENsaWVudEFwcGxpY2F0aW9uLFxuICBDb25maWd1cmF0aW9uLFxuICBMb2dMZXZlbCxcbiAgQXV0aGVudGljYXRpb25SZXN1bHQsXG4gIEF1dGhvcml6YXRpb25Db2RlUmVxdWVzdCxcbn0gZnJvbSAnQGF6dXJlL21zYWwtbm9kZSc7XG5pbXBvcnQgeyBzdXBlclRva2Vuc05leHRXcmFwcGVyIH0gZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZS9uZXh0anMnO1xuaW1wb3J0IHsgdmVyaWZ5U2Vzc2lvbiB9IGZyb20gJ3N1cGVydG9rZW5zLW5vZGUvcmVjaXBlL3Nlc3Npb24vZnJhbWV3b3JrL2V4cHJlc3MnOyAvLyBGb3Igc3RhdGUgdmFsaWRhdGlvbiBpZiBuZWVkZWQsIHRob3VnaCBzdGF0ZSBjb250YWlucyB1c2VySWRcbmltcG9ydCBzdXBlcnRva2VucyBmcm9tICdzdXBlcnRva2Vucy1ub2RlJztcbmltcG9ydCB7IGJhY2tlbmRDb25maWcgfSBmcm9tICcuLi8uLi8uLi8uLi8uLi9jb25maWcvYmFja2VuZENvbmZpZyc7IC8vIEFkanVzdGVkIHBhdGhcbmltcG9ydCB7IGxvZ2dlciB9IGZyb20gJy4uLy4uLy4uLy4uLy4uLy4uL3Byb2plY3QvZnVuY3Rpb25zL191dGlscy9sb2dnZXInO1xuaW1wb3J0IHsgQ3JlZGVudGlhbHMgYXMgT0F1dGgyVG9rZW4gfSBmcm9tICdnb29nbGUtYXV0aC1saWJyYXJ5JzsgLy8gUmUtdXNpbmcgdGhpcyB0eXBlIGZvciBzdHJ1Y3R1cmUsIHRob3VnaCBub3Qgc3RyaWN0bHkgR29vZ2xlXG5pbXBvcnQge1xuICBIQVNVUkFfR1JBUEhRTF9VUkwsXG4gIEhBU1VSQV9BRE1JTl9TRUNSRVQsXG59IGZyb20gJy4uLy4uLy4uLy4uLy4uLy4uL3Byb2plY3QvZnVuY3Rpb25zL2F0b20tYWdlbnQvX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7IGV4ZWN1dGVHcmFwaFFMTXV0YXRpb24gfSBmcm9tICcuLi8uLi8uLi8uLi8uLi8uLi9wcm9qZWN0L2Z1bmN0aW9ucy9hdG9tLWFnZW50L19saWJzL2dyYXBocWxDbGllbnQnO1xuXG4vLyBUT0RPOiBNb3ZlIHRoZXNlIHRvIGEgY2VudHJhbCBjb25zdGFudHMgZmlsZSBhbmQgbWFuYWdlIHZpYSBlbnZpcm9ubWVudCB2YXJpYWJsZXNcbmNvbnN0IE1TVEVBTVNfQ0xJRU5UX0lEID1cbiAgcHJvY2Vzcy5lbnYuTVNURUFNU19DTElFTlRfSUQgfHwgJ1lPVVJfTVNURUFNU19BUFBfQ0xJRU5UX0lEJztcbmNvbnN0IE1TVEVBTVNfQ0xJRU5UX1NFQ1JFVCA9XG4gIHByb2Nlc3MuZW52Lk1TVEVBTVNfQ0xJRU5UX1NFQ1JFVCB8fCAnWU9VUl9NU1RFQU1TX0FQUF9DTElFTlRfU0VDUkVUJztcbmNvbnN0IE1TVEVBTVNfUkVESVJFQ1RfVVJJID1cbiAgcHJvY2Vzcy5lbnYuTVNURUFNU19SRURJUkVDVF9VUkkgfHxcbiAgJ2h0dHA6Ly9sb2NhbGhvc3Q6MzAwMC9hcGkvYXRvbS9hdXRoL21zdGVhbXMvY2FsbGJhY2snO1xuY29uc3QgTVNURUFNU19BVVRIT1JJVFkgPVxuICBwcm9jZXNzLmVudi5NU1RFQU1TX0FVVEhPUklUWSB8fCAnaHR0cHM6Ly9sb2dpbi5taWNyb3NvZnRvbmxpbmUuY29tL2NvbW1vbic7XG5jb25zdCBNU1RFQU1TX1NDT1BFUyA9IFtcbiAgJ0NoYXQuUmVhZCcsXG4gICdDaGFubmVsTWVzc2FnZS5SZWFkLkFsbCcsXG4gICdVc2VyLlJlYWQnLFxuICAnb2ZmbGluZV9hY2Nlc3MnLFxuXTsgLy8gRW5zdXJlIG9mZmxpbmVfYWNjZXNzIGZvciByZWZyZXNoIHRva2VuXG5cbmNvbnN0IE1TVEVBTVNfVE9LRU5fU0VSVklDRV9OQU1FID0gJ21zdGVhbXNfZ3JhcGgnOyAvLyBPciAnbWljcm9zb2Z0X2dyYXBoJ1xuXG5zdXBlcnRva2Vucy5pbml0KGJhY2tlbmRDb25maWcoKSk7XG5cbmNvbnN0IG1zYWxDb25maWc6IENvbmZpZ3VyYXRpb24gPSB7XG4gIGF1dGg6IHtcbiAgICBjbGllbnRJZDogTVNURUFNU19DTElFTlRfSUQsXG4gICAgYXV0aG9yaXR5OiBNU1RFQU1TX0FVVEhPUklUWSxcbiAgICBjbGllbnRTZWNyZXQ6IE1TVEVBTVNfQ0xJRU5UX1NFQ1JFVCxcbiAgfSxcbiAgc3lzdGVtOiB7XG4gICAgLyogLi4uIGxvZ2dlciBjb25maWcgLi4uICovXG4gIH0sXG59O1xuXG4vLyBBZGFwdGVkIGZyb20gR29vZ2xlIE9BdXRoIGNhbGxiYWNrXG5hc3luYyBmdW5jdGlvbiBzYXZlTVNUZWFtc1VzZXJUb2tlbnMoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0b2tlbnM6IEF1dGhlbnRpY2F0aW9uUmVzdWx0XG4pOiBQcm9taXNlPHsgb2s6IGJvb2xlYW47IGVycm9yPzogYW55IH0+IHtcbiAgbG9nZ2VyLmluZm8oXG4gICAgYFtNU1RlYW1zQXV0aENhbGxiYWNrXSBTYXZpbmcgTVMgVGVhbXMgdG9rZW5zIGZvciB1c2VySWQ6ICR7dXNlcklkfWBcbiAgKTtcblxuICBpZiAoIUhBU1VSQV9HUkFQSFFMX1VSTCB8fCAhSEFTVVJBX0FETUlOX1NFQ1JFVCkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICdbTVNUZWFtc0F1dGhDYWxsYmFja10gR3JhcGhRTCBjbGllbnQgbm90IGNvbmZpZ3VyZWQgZm9yIHNhdmVNU1RlYW1zVXNlclRva2Vucy4nXG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdHcmFwaFFMIGNsaWVudCBpcyBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIGlmICghdG9rZW5zLmFjY2Vzc1Rva2VuIHx8ICF0b2tlbnMuYWNjb3VudCkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICdbTVNUZWFtc0F1dGhDYWxsYmFja10gQ3JpdGljYWwgdG9rZW4gaW5mb3JtYXRpb24gbWlzc2luZyBmcm9tIE1TQUwgcmVzcG9uc2UuJ1xuICAgICk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdUT0tFTl9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdFc3NlbnRpYWwgdG9rZW4gaW5mb3JtYXRpb24gbWlzc2luZyBmcm9tIE1TQUwgcmVzcG9uc2UuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIGNvbnN0IG11dGF0aW9uID0gYFxuICAgIG11dGF0aW9uIFVwc2VydFVzZXJUb2tlbigkb2JqZWN0czogW3VzZXJfdG9rZW5zX2luc2VydF9pbnB1dCFdISkge1xuICAgICAgaW5zZXJ0X3VzZXJfdG9rZW5zKFxuICAgICAgICBvYmplY3RzOiAkb2JqZWN0cyxcbiAgICAgICAgb25fY29uZmxpY3Q6IHtcbiAgICAgICAgICBjb25zdHJhaW50OiB1c2VyX3Rva2Vuc191c2VyX2lkX3NlcnZpY2VfbmFtZV9rZXksXG4gICAgICAgICAgdXBkYXRlX2NvbHVtbnM6IFthY2Nlc3NfdG9rZW4sIHJlZnJlc2hfdG9rZW4sIGV4cGlyeV9kYXRlLCBzY29wZSwgdG9rZW5fdHlwZSwgaWRfdG9rZW4sIG90aGVyX2RhdGEsIHVwZGF0ZWRfYXRdXG4gICAgICAgIH1cbiAgICAgICkge1xuICAgICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICB9XG4gICAgfVxuICBgO1xuXG4gIC8vIE1TQUwncyBBdXRoZW50aWNhdGlvblJlc3VsdCBoYXMgYWNjb3VudC5pZFRva2VuQ2xhaW1zLmV4cCAoc2Vjb25kcyBzaW5jZSBlcG9jaCkgZm9yIGlkX3Rva2VuIGV4cGlyeVxuICAvLyB0b2tlbnMuZXhwaXJlc09uIGlzIGEgRGF0ZSBvYmplY3QgZm9yIGFjY2Vzc190b2tlbiBleHBpcnlcbiAgY29uc3QgdG9rZW5EYXRhRm9yRGIgPSB7XG4gICAgdXNlcl9pZDogdXNlcklkLFxuICAgIHNlcnZpY2VfbmFtZTogTVNURUFNU19UT0tFTl9TRVJWSUNFX05BTUUsXG4gICAgYWNjZXNzX3Rva2VuOiB0b2tlbnMuYWNjZXNzVG9rZW4sXG4gICAgcmVmcmVzaF90b2tlbjogdG9rZW5zLnJlZnJlc2hUb2tlbiwgLy8gVGhpcyBzaG91bGQgYmUgcHJlc2VudCBpZiBvZmZsaW5lX2FjY2VzcyBzY29wZSB3YXMgZ3JhbnRlZFxuICAgIGV4cGlyeV9kYXRlOiB0b2tlbnMuZXhwaXJlc09uID8gdG9rZW5zLmV4cGlyZXNPbi50b0lTT1N0cmluZygpIDogbnVsbCxcbiAgICBzY29wZTogdG9rZW5zLnNjb3Blcy5qb2luKCcgJyksXG4gICAgdG9rZW5fdHlwZTogJ0JlYXJlcicsIC8vIFR5cGljYWxseSBCZWFyZXIgZm9yIE1TIEdyYXBoXG4gICAgaWRfdG9rZW46IHRva2Vucy5pZFRva2VuLCAvLyBTdG9yZSBJRCB0b2tlbiBpZiBuZWVkZWRcbiAgICBvdGhlcl9kYXRhOiB7XG4gICAgICBhY2NvdW50SG9tZUFjY291bnRJZDogdG9rZW5zLmFjY291bnQuaG9tZUFjY291bnRJZCwgLy8gVXNlZnVsIGZvciBNU0FMIGNhY2hlIGxvb2t1cHMgbGF0ZXIgaWYgbmVlZGVkXG4gICAgICBhY2NvdW50RW52aXJvbm1lbnQ6IHRva2Vucy5hY2NvdW50LmVudmlyb25tZW50LFxuICAgICAgYWNjb3VudFRlbmFudElkOiB0b2tlbnMuYWNjb3VudC50ZW5hbnRJZCxcbiAgICB9LFxuICAgIHVwZGF0ZWRfYXQ6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgfTtcblxuICBjb25zdCB2YXJpYWJsZXMgPSB7IG9iamVjdHM6IFt0b2tlbkRhdGFGb3JEYl0gfTtcbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGV4ZWN1dGVHcmFwaFFMTXV0YXRpb248e1xuICAgICAgaW5zZXJ0X3VzZXJfdG9rZW5zOiB7IGFmZmVjdGVkX3Jvd3M6IG51bWJlciB9O1xuICAgIH0+KG11dGF0aW9uLCB2YXJpYWJsZXMsICdVcHNlcnRNU1RlYW1zVXNlclRva2VuJywgdXNlcklkKTtcbiAgICBpZiAoXG4gICAgICByZXNwb25zZSAmJlxuICAgICAgcmVzcG9uc2UuaW5zZXJ0X3VzZXJfdG9rZW5zICYmXG4gICAgICByZXNwb25zZS5pbnNlcnRfdXNlcl90b2tlbnMuYWZmZWN0ZWRfcm93cyA+IDBcbiAgICApIHtcbiAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICBgW01TVGVhbXNBdXRoQ2FsbGJhY2tdIE1TIFRlYW1zIHRva2VucyBzYXZlZCBzdWNjZXNzZnVsbHkgZm9yIHVzZXIgJHt1c2VySWR9LmBcbiAgICAgICk7XG4gICAgICByZXR1cm4geyBvazogdHJ1ZSB9O1xuICAgIH0gZWxzZSB7XG4gICAgICBsb2dnZXIud2FybihcbiAgICAgICAgYFtNU1RlYW1zQXV0aENhbGxiYWNrXSBNUyBUZWFtcyB0b2tlbiBzYXZlIHJlcG9ydGVkIDAgYWZmZWN0ZWRfcm93cyBmb3IgdXNlciAke3VzZXJJZH0uYCxcbiAgICAgICAgcmVzcG9uc2VcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ0RCX05PX1JPV1NfQUZGRUNURUQnLFxuICAgICAgICAgIG1lc3NhZ2U6ICdUb2tlbiBzYXZlIGRpZCBub3QgYWZmZWN0IGFueSByb3dzLicsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbTVNUZWFtc0F1dGhDYWxsYmFja10gRXhjZXB0aW9uIHNhdmluZyBNUyBUZWFtcyB0b2tlbnMgZm9yIHVzZXIgJHt1c2VySWR9OmAsXG4gICAgICBlcnJvclxuICAgICk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7IGNvZGU6ICdUT0tFTl9TQVZFX0ZBSUxFRCcsIG1lc3NhZ2U6IGVycm9yLm1lc3NhZ2UgfSxcbiAgICB9O1xuICB9XG59XG5cbmV4cG9ydCBkZWZhdWx0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZXIoXG4gIHJlcTogTmV4dEFwaVJlcXVlc3QsXG4gIHJlczogTmV4dEFwaVJlc3BvbnNlXG4pIHtcbiAgLy8gSXQncyBpbXBvcnRhbnQgdG8gdmVyaWZ5IHRoZSBzZXNzaW9uIG9mIHRoZSB1c2VyIHdobyBpbml0aWF0ZWQgdGhlIGZsb3csXG4gIC8vIHVzdWFsbHkgYnkgY2hlY2tpbmcgdGhlICdzdGF0ZScgcGFyYW1ldGVyIHJldHVybmVkIGJ5IE1pY3Jvc29mdC5cbiAgLy8gVGhlICdzdGF0ZScgc2hvdWxkIG1hdGNoIHdoYXQgd2FzIHNlbnQgaW4gdGhlIGluaXRpYXRlIHN0ZXAgKGUuZy4sIFN1cGVyVG9rZW5zIHVzZXJJZCkuXG4gIGNvbnN0IHJlY2VpdmVkU3RhdGUgPSByZXEucXVlcnkuc3RhdGUgYXMgc3RyaW5nO1xuICAvLyBUT0RPOiBTZWN1cmVseSB2YWxpZGF0ZSB0aGUgc3RhdGUgcGFyYW1ldGVyIGFnYWluc3QgYSBzdG9yZWQgdmFsdWUgZnJvbSB0aGUgaW5pdGlhdGUgc3RlcCBpZiBub3QgdXNpbmcgdXNlcklkIGRpcmVjdGx5LlxuICAvLyBGb3Igbm93LCB3ZSBhc3N1bWUgc3RhdGUgSVMgdGhlIHVzZXJJZCBmb3Igc2ltcGxpY2l0eSBhcyBzZXQgaW4gaW5pdGlhdGUudHNcblxuICAvLyBWZXJpZnkgU3VwZXJUb2tlbnMgc2Vzc2lvbiBmb3IgdGhlIHVzZXIgSUQgcGFzc2VkIGluIHN0YXRlXG4gIC8vIFRoaXMgZW5zdXJlcyB0aGUgY2FsbGJhY2sgaXMgZm9yIGEgdmFsaWQsIGN1cnJlbnRseSBsb2dnZWQtaW4gdXNlciBzZXNzaW9uLlxuICBsZXQgc2Vzc2lvbjtcbiAgdHJ5IHtcbiAgICBzZXNzaW9uID0gYXdhaXQgc3VwZXJUb2tlbnNOZXh0V3JhcHBlcihcbiAgICAgIGFzeW5jIChuZXh0KSA9PlxuICAgICAgICB2ZXJpZnlTZXNzaW9uKHsgc2Vzc2lvblJlcXVpcmVkOiB0cnVlIH0pKHJlcSBhcyBhbnksIHJlcyBhcyBhbnksIG5leHQpLFxuICAgICAgcmVxLFxuICAgICAgcmVzXG4gICAgKTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICAvLyB2ZXJpZnlTZXNzaW9uIHRocm93cyBpZiBubyBzZXNzaW9uXG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgJ1tNU1RlYW1zQXV0aENhbGxiYWNrXSBTdXBlclRva2VucyBzZXNzaW9uIHZlcmlmaWNhdGlvbiBmYWlsZWQgaW4gY2FsbGJhY2s6JyxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICByZXR1cm4gcmVzXG4gICAgICAuc3RhdHVzKDQwMSlcbiAgICAgIC5yZWRpcmVjdCgnL0F1dGgvVXNlckxvZ2luP2Vycm9yPXNlc3Npb25fZXhwaXJlZF9vYXV0aCcpO1xuICB9XG5cbiAgY29uc3Qgc2Vzc2lvblVzZXJJZCA9IHNlc3Npb24/LmdldFVzZXJJZCgpO1xuXG4gIGlmICghc2Vzc2lvblVzZXJJZCB8fCBzZXNzaW9uVXNlcklkICE9PSByZWNlaXZlZFN0YXRlKSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFtNU1RlYW1zQXV0aENhbGxiYWNrXSBJbnZhbGlkIHN0YXRlIG9yIHNlc3Npb24gbWlzbWF0Y2guIFNlc3Npb24gVXNlcklEOiAke3Nlc3Npb25Vc2VySWR9LCBTdGF0ZTogJHtyZWNlaXZlZFN0YXRlfWBcbiAgICApO1xuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoNDAwKVxuICAgICAgLnJlZGlyZWN0KCcvU2V0dGluZ3MvVXNlclZpZXdTZXR0aW5ncz9tc3RlYW1zX2F1dGhfZXJyb3I9aW52YWxpZF9zdGF0ZScpO1xuICB9XG5cbiAgY29uc3QgdXNlcklkID0gc2Vzc2lvblVzZXJJZDsgLy8gQ29uZmlybWVkIHVzZXJcblxuICBpZiAocmVxLnF1ZXJ5LmVycm9yKSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFtNU1RlYW1zQXV0aENhbGxiYWNrXSBFcnJvciBmcm9tIE1TIElkZW50aXR5IHBsYXRmb3JtIGZvciB1c2VyICR7dXNlcklkfTogJHtyZXEucXVlcnkuZXJyb3JfZGVzY3JpcHRpb24gfHwgcmVxLnF1ZXJ5LmVycm9yfWBcbiAgICApO1xuICAgIHJldHVybiByZXMucmVkaXJlY3QoXG4gICAgICBgL1NldHRpbmdzL1VzZXJWaWV3U2V0dGluZ3M/bXN0ZWFtc19hdXRoX2Vycm9yPSR7ZW5jb2RlVVJJQ29tcG9uZW50KHJlcS5xdWVyeS5lcnJvciBhcyBzdHJpbmcpfWBcbiAgICApO1xuICB9XG5cbiAgaWYgKCFyZXEucXVlcnkuY29kZSB8fCB0eXBlb2YgcmVxLnF1ZXJ5LmNvZGUgIT09ICdzdHJpbmcnKSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFtNU1RlYW1zQXV0aENhbGxiYWNrXSBObyBhdXRob3JpemF0aW9uIGNvZGUgcmVjZWl2ZWQgZm9yIHVzZXIgJHt1c2VySWR9LmBcbiAgICApO1xuICAgIHJldHVybiByZXMucmVkaXJlY3QoXG4gICAgICAnL1NldHRpbmdzL1VzZXJWaWV3U2V0dGluZ3M/bXN0ZWFtc19hdXRoX2Vycm9yPW5vX2NvZGUnXG4gICAgKTtcbiAgfVxuXG4gIGlmIChcbiAgICAhTVNURUFNU19DTElFTlRfSUQgfHxcbiAgICBNU1RFQU1TX0NMSUVOVF9JRCA9PT0gJ1lPVVJfTVNURUFNU19BUFBfQ0xJRU5UX0lEJyB8fFxuICAgICFNU1RFQU1TX0NMSUVOVF9TRUNSRVQgfHxcbiAgICBNU1RFQU1TX0NMSUVOVF9TRUNSRVQgPT09ICdZT1VSX01TVEVBTVNfQVBQX0NMSUVOVF9TRUNSRVQnXG4gICkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICdbTVNUZWFtc0F1dGhDYWxsYmFja10gTVMgVGVhbXMgQ2xpZW50IElEIG9yIFNlY3JldCBub3QgY29uZmlndXJlZC4nXG4gICAgKTtcbiAgICByZXR1cm4gcmVzXG4gICAgICAuc3RhdHVzKDUwMClcbiAgICAgIC5qc29uKHtcbiAgICAgICAgbWVzc2FnZTogJ01TIFRlYW1zIE9BdXRoIGNvbmZpZ3VyYXRpb24gZXJyb3Igb24gc2VydmVyIChjYWxsYmFjaykuJyxcbiAgICAgIH0pO1xuICB9XG5cbiAgY29uc3QgY2NhID0gbmV3IENvbmZpZGVudGlhbENsaWVudEFwcGxpY2F0aW9uKG1zYWxDb25maWcpO1xuICBjb25zdCB0b2tlblJlcXVlc3Q6IEF1dGhvcml6YXRpb25Db2RlUmVxdWVzdCA9IHtcbiAgICBjb2RlOiByZXEucXVlcnkuY29kZSxcbiAgICBzY29wZXM6IE1TVEVBTVNfU0NPUEVTLFxuICAgIHJlZGlyZWN0VXJpOiBNU1RFQU1TX1JFRElSRUNUX1VSSSxcbiAgfTtcblxuICB0cnkge1xuICAgIGNvbnN0IG1zYWxSZXNwb25zZSA9IGF3YWl0IGNjYS5hY3F1aXJlVG9rZW5CeUNvZGUodG9rZW5SZXF1ZXN0KTtcbiAgICBpZiAoIW1zYWxSZXNwb25zZSB8fCAhbXNhbFJlc3BvbnNlLmFjY2Vzc1Rva2VuKSB7XG4gICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgIGBbTVNUZWFtc0F1dGhDYWxsYmFja10gRmFpbGVkIHRvIGFjcXVpcmUgTVMgVGVhbXMgdG9rZW4gZm9yIHVzZXIgJHt1c2VySWR9LiBNU0FMIHJlc3BvbnNlIGVtcHR5IG9yIG1pc3NpbmcgYWNjZXNzVG9rZW4uYCxcbiAgICAgICAgbXNhbFJlc3BvbnNlXG4gICAgICApO1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdGYWlsZWQgdG8gYWNxdWlyZSBNUyBUZWFtcyB0b2tlbi4nKTtcbiAgICB9XG5cbiAgICBsb2dnZXIuaW5mbyhcbiAgICAgIGBbTVNUZWFtc0F1dGhDYWxsYmFja10gTVMgVGVhbXMgdG9rZW4gYWNxdWlyZWQgc3VjY2Vzc2Z1bGx5IGZvciB1c2VyICR7dXNlcklkfS4gQWNjb3VudDogJHttc2FsUmVzcG9uc2UuYWNjb3VudD8udXNlcm5hbWV9YFxuICAgICk7XG5cbiAgICBjb25zdCBzYXZlUmVzdWx0ID0gYXdhaXQgc2F2ZU1TVGVhbXNVc2VyVG9rZW5zKHVzZXJJZCwgbXNhbFJlc3BvbnNlKTtcbiAgICBpZiAoIXNhdmVSZXN1bHQub2spIHtcbiAgICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICAgYFtNU1RlYW1zQXV0aENhbGxiYWNrXSBGYWlsZWQgdG8gc2F2ZSBNUyBUZWFtcyB0b2tlbnMgZm9yIHVzZXIgJHt1c2VySWR9OmAsXG4gICAgICAgIHNhdmVSZXN1bHQuZXJyb3JcbiAgICAgICk7XG4gICAgICBjb25zdCBlcnJNc2cgPSBzYXZlUmVzdWx0LmVycm9yPy5tZXNzYWdlIHx8ICd0b2tlbl9zYXZlX2ZhaWxlZCc7XG4gICAgICByZXR1cm4gcmVzLnJlZGlyZWN0KFxuICAgICAgICBgL1NldHRpbmdzL1VzZXJWaWV3U2V0dGluZ3M/bXN0ZWFtc19hdXRoX2Vycm9yPSR7ZW5jb2RlVVJJQ29tcG9uZW50KGVyck1zZyl9YFxuICAgICAgKTtcbiAgICB9XG5cbiAgICBsb2dnZXIuaW5mbyhcbiAgICAgIGBbTVNUZWFtc0F1dGhDYWxsYmFja10gTVMgVGVhbXMgc3VjY2Vzc2Z1bGx5IGNvbm5lY3RlZCBhbmQgdG9rZW5zIHN0b3JlZCBmb3IgdXNlciAke3VzZXJJZH0uYFxuICAgICk7XG4gICAgLy8gUmVkaXJlY3QgdG8gYSBzdWNjZXNzIHBhZ2Ugb3Igc2V0dGluZ3MgcGFnZVxuICAgIHJldHVybiByZXMucmVkaXJlY3QoJy9TZXR0aW5ncy9Vc2VyVmlld1NldHRpbmdzP21zdGVhbXNfYXV0aF9zdWNjZXNzPXRydWUnKTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgIGBbTVNUZWFtc0F1dGhDYWxsYmFja10gRXJyb3IgYWNxdWlyaW5nL3NhdmluZyBNUyBUZWFtcyB0b2tlbiBmb3IgdXNlciAke3VzZXJJZH06YCxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICBjb25zdCBlcnJNc2cgPVxuICAgICAgZXJyb3IubWVzc2FnZSB8fCBlcnJvci5lcnJvckNvZGUgfHwgJ21zdGVhbXNfdG9rZW5fYWNxdWlzaXRpb25fZmFpbGVkJztcbiAgICByZXR1cm4gcmVzLnJlZGlyZWN0KFxuICAgICAgYC9TZXR0aW5ncy9Vc2VyVmlld1NldHRpbmdzP21zdGVhbXNfYXV0aF9lcnJvcj0ke2VuY29kZVVSSUNvbXBvbmVudChlcnJNc2cpfWBcbiAgICApO1xuICB9XG59XG4iXX0=