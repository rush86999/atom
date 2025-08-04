"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const qs_1 = __importDefault(require("qs"));
const cors_1 = __importDefault(require("cors"));
const api_backend_helper_1 = require("@lib/api-backend-helper"); // Removed unused Google-specific helpers for now
const nextjs_1 = require("supertokens-node/nextjs");
const express_1 = require("supertokens-node/recipe/session/framework/express");
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const backendConfig_1 = require("../../../../../config/backendConfig"); // Adjusted path
// Assuming these are needed for GraphQL client used by saveUserTokensInternal
// These constants might be better sourced from a shared constants file within app-service if possible,
// or ensure the path is robust.
const constants_1 = require("../../../../../../project/functions/atom-agent/_libs/constants");
const graphqlClient_1 = require("../../../../../../project/functions/atom-agent/_libs/graphqlClient");
const logger_1 = __importDefault(require("../../../../../lib/logger")); // Import the shared app-service logger
const GOOGLE_CALENDAR_SERVICE_NAME = 'google_calendar';
const cors = (0, cors_1.default)({
    methods: ['POST', 'GET', 'HEAD'],
    // Allow all origins for simplicity in dev, or specify your frontend URL
    // origin: process.env.NODE_ENV === 'production' ? ["https://atomiclife.app", /\.atomiclife\.app$/] : "*",
});
supertokens_node_1.default.init((0, backendConfig_1.backendConfig)());
function runMiddleware(req, res, fn) {
    return new Promise((resolve, reject) => {
        fn(req, res, (result) => {
            if (result instanceof Error) {
                return reject(result);
            }
            return resolve(result);
        });
    });
}
// This function is an adaptation of saveUserTokens from calendarSkills.ts
// to be used directly within this API route.
async function saveUserTokensInternal(userId, tokens) {
    const operationName = 'saveUserTokensInternal_GoogleCalendarAuthCallback';
    logger_1.default.info(`[${operationName}] Attempting to save tokens.`, {
        userId,
        service: GOOGLE_CALENDAR_SERVICE_NAME,
    });
    if (!constants_1.HASURA_GRAPHQL_URL || !constants_1.HASURA_ADMIN_SECRET) {
        logger_1.default.error(`[${operationName}] GraphQL client configuration missing (Hasura URL/Secret).`, { userId });
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'GraphQL client is not configured.',
            },
        };
    }
    const mutation = `
    mutation UpsertUserToken($objects: [user_tokens_insert_input!]!) {
      insert_user_tokens(
        objects: $objects,
        on_conflict: {
          constraint: user_tokens_user_id_service_name_key,
          update_columns: [access_token, refresh_token, expiry_date, scope, token_type, updated_at]
        }
      ) {
        affected_rows
      }
    }
  `;
    const tokenDataForDb = {
        user_id: userId,
        service_name: GOOGLE_CALENDAR_SERVICE_NAME,
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        expiry_date: tokens.expiry_date
            ? new Date(tokens.expiry_date).toISOString()
            : null,
        scope: tokens.scope,
        token_type: tokens.token_type,
        updated_at: new Date().toISOString(),
    };
    const variables = { objects: [tokenDataForDb] };
    const operationName = 'UpsertUserToken';
    try {
        const response = await (0, graphqlClient_1.executeGraphQLMutation)(mutation, variables, operationName, // This is 'UpsertUserToken' from the GQL mutation name
        userId);
        if (response &&
            response.insert_user_tokens &&
            response.insert_user_tokens.affected_rows > 0) {
            logger_1.default.info(`[${operationName}] Tokens saved successfully to user_tokens table.`, { userId });
            return { ok: true };
        }
        else {
            logger_1.default.warn(`[${operationName}] Token save operation (user_tokens table) reported 0 affected_rows or no/unexpected response.`, { userId, response });
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
        logger_1.default.error(`[${operationName}] Exception during token save.`, {
            userId,
            error: error.message,
            stack: error.stack,
            details: error,
        });
        return {
            ok: false,
            error: {
                code: 'TOKEN_SAVE_FAILED_INTERNAL',
                message: `Failed to save Google Calendar tokens to user_tokens for user ${userId}.`,
                details: error.message,
            },
        };
    }
}
async function handler(req, res) {
    try {
        await runMiddleware(req, res, cors);
        await (0, nextjs_1.superTokensNextWrapper)(async (next) => {
            return await (0, express_1.verifySession)()(req, res, next);
        }, req, res);
        const session = req.session;
        const userId = session?.getUserId();
        const operationName = 'GoogleCalendarAuthCallback'; // For logging context
        if (!userId) {
            logger_1.default.error(`[${operationName}] User not authenticated in callback. Session may be missing or invalid.`, { headers: req.headers });
            return res.redirect('/User/Login/UserLogin?error=session_expired_oauth_callback');
        }
        logger_1.default.info(`[${operationName}] Processing callback for user.`, {
            userId,
        });
        const thisUrl = new URL(req.url, `https://${req.headers.host}`);
        const queryParams = qs_1.default.parse(thisUrl.search.substring(1));
        if (queryParams.error) {
            const error = queryParams.error;
            logger_1.default.warn(`[${operationName}] Error from Google OAuth provider.`, { userId, error, queryParams });
            return res.redirect(`/Settings/UserViewSettings?calendar_auth_error=${encodeURIComponent(error)}&atom_agent=true`);
        }
        const code = queryParams.code;
        const state = queryParams.state;
        if (state !== userId) {
            logger_1.default.error(`[${operationName}] Invalid OAuth state. CSRF attempt?`, { expectedState: userId, receivedState: state });
            return res.redirect(`/Settings/UserViewSettings?calendar_auth_error=invalid_state&atom_agent=true`);
        }
        if (!code) {
            logger_1.default.error(`[${operationName}] No authorization code received from Google.`, { userId });
            return res.redirect(`/Settings/UserViewSettings?calendar_auth_error=no_code_received&atom_agent=true`);
        }
        logger_1.default.debug(`[${operationName}] Authorization code received.`, {
            userId,
            codePrefix: code?.substring(0, 10),
        });
        const tokens = await (0, api_backend_helper_1.exchangeCodeForTokens)(code);
        if (!tokens || !tokens.access_token) {
            logger_1.default.error(`[${operationName}] Failed to exchange code for tokens or access_token missing.`, {
                userId,
                tokensReceived: !!tokens,
                accessTokenPresent: !!tokens?.access_token,
            });
            return res.redirect(`/Settings/UserViewSettings?calendar_auth_error=token_exchange_failed&atom_agent=true`);
        }
        logger_1.default.info(`[${operationName}] Tokens received from Google successfully.`, {
            userId,
            accessTokenPresent: !!tokens.access_token,
            refreshTokenPresent: !!tokens.refresh_token,
            expiresAt: tokens.expiry_date,
            scope: tokens.scope,
        });
        const saveResult = await saveUserTokensInternal(userId, tokens);
        if (!saveResult.ok) {
            logger_1.default.error(`[${operationName}] Failed to save tokens to user_tokens table.`, { userId, errorDetails: saveResult.error });
            const errorMessage = saveResult.error?.message || 'failed_to_save_tokens';
            return res.redirect(`/Settings/UserViewSettings?calendar_auth_error=${encodeURIComponent(errorMessage)}&atom_agent=true`);
        }
        logger_1.default.info(`[${operationName}] Google Calendar connected and tokens saved successfully.`, { userId });
        return res.redirect('/Settings/UserViewSettings?calendar_auth_success=true&atom_agent=true');
    }
    catch (e) {
        // Catching 'any' to access potential properties like 'message'
        const operationName = 'GoogleCalendarAuthCallback_OuterCatch'; // Specific for this catch
        logger_1.default.error(`[${operationName}] General error in Google OAuth callback handler.`, { error: e.message, stack: e.stack, details: e });
        // Avoid exposing sensitive error details in redirect.
        return res.redirect(`/Settings/UserViewSettings?calendar_auth_error=${encodeURIComponent('callback_processing_failed')}&atom_agent=true`);
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsbGJhY2suanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjYWxsYmFjay50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQTBKQSwwQkFvSUM7QUE3UkQsNENBQW9CO0FBQ3BCLGdEQUF3QjtBQUN4QixnRUFBZ0UsQ0FBQyxpREFBaUQ7QUFHbEgsb0RBQWlFO0FBQ2pFLCtFQUFrRjtBQUNsRix3RUFBMkM7QUFDM0MsdUVBQW9FLENBQUMsZ0JBQWdCO0FBR3JGLDhFQUE4RTtBQUM5RSx1R0FBdUc7QUFDdkcsZ0NBQWdDO0FBQ2hDLDhGQUd3RTtBQUN4RSxzR0FBNEc7QUFDNUcsdUVBQXlELENBQUMsdUNBQXVDO0FBRWpHLE1BQU0sNEJBQTRCLEdBQUcsaUJBQWlCLENBQUM7QUFFdkQsTUFBTSxJQUFJLEdBQUcsSUFBQSxjQUFJLEVBQUM7SUFDaEIsT0FBTyxFQUFFLENBQUMsTUFBTSxFQUFFLEtBQUssRUFBRSxNQUFNLENBQUM7SUFDaEMsd0VBQXdFO0lBQ3hFLDBHQUEwRztDQUMzRyxDQUFDLENBQUM7QUFFSCwwQkFBVyxDQUFDLElBQUksQ0FBQyxJQUFBLDZCQUFhLEdBQUUsQ0FBQyxDQUFDO0FBRWxDLFNBQVMsYUFBYSxDQUNwQixHQUFtQixFQUNuQixHQUFvQixFQUNwQixFQUFZO0lBRVosT0FBTyxJQUFJLE9BQU8sQ0FBQyxDQUFDLE9BQU8sRUFBRSxNQUFNLEVBQUUsRUFBRTtRQUNyQyxFQUFFLENBQUMsR0FBRyxFQUFFLEdBQUcsRUFBRSxDQUFDLE1BQVcsRUFBRSxFQUFFO1lBQzNCLElBQUksTUFBTSxZQUFZLEtBQUssRUFBRSxDQUFDO2dCQUM1QixPQUFPLE1BQU0sQ0FBQyxNQUFNLENBQUMsQ0FBQztZQUN4QixDQUFDO1lBQ0QsT0FBTyxPQUFPLENBQUMsTUFBTSxDQUFDLENBQUM7UUFDekIsQ0FBQyxDQUFDLENBQUM7SUFDTCxDQUFDLENBQUMsQ0FBQztBQUNMLENBQUM7QUFFRCwwRUFBMEU7QUFDMUUsNkNBQTZDO0FBQzdD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RSxNQUFNLEVBQUUsQ0FDWCxDQUFDO1FBQ0YsT0FBTyxHQUFHLENBQUMsUUFBUSxDQUNqQix1RUFBdUUsQ0FDeEUsQ0FBQztJQUNKLENBQUM7SUFBQyxPQUFPLENBQU0sRUFBRSxDQUFDO1FBQ2hCLCtEQUErRDtRQUMvRCxNQUFNLGFBQWEsR0FBRyx1Q0FBdUMsQ0FBQyxDQUFDLDBCQUEwQjtRQUN6RixnQkFBZ0IsQ0FBQyxLQUFLLENBQ3BCLElBQUksYUFBYSxtREFBbUQsRUFDcEUsRUFBRSxLQUFLLEVBQUUsQ0FBQyxDQUFDLE9BQU8sRUFBRSxLQUFLLEVBQUUsQ0FBQyxDQUFDLEtBQUssRUFBRSxPQUFPLEVBQUUsQ0FBQyxFQUFFLENBQ2pELENBQUM7UUFDRixzREFBc0Q7UUFDdEQsT0FBTyxHQUFHLENBQUMsUUFBUSxDQUNqQixrREFBa0Qsa0JBQWtCLENBQUMsNEJBQTRCLENBQUMsa0JBQWtCLENBQ3JILENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB0eXBlIHsgTmV4dEFwaVJlcXVlc3QsIE5leHRBcGlSZXNwb25zZSB9IGZyb20gJ25leHQnO1xuaW1wb3J0IHFzIGZyb20gJ3FzJztcbmltcG9ydCBDb3JzIGZyb20gJ2NvcnMnO1xuaW1wb3J0IHsgZXhjaGFuZ2VDb2RlRm9yVG9rZW5zIH0gZnJvbSAnQGxpYi9hcGktYmFja2VuZC1oZWxwZXInOyAvLyBSZW1vdmVkIHVudXNlZCBHb29nbGUtc3BlY2lmaWMgaGVscGVycyBmb3Igbm93XG5pbXBvcnQgeyBkYXlqcyB9IGZyb20gJ0BsaWIvZGF0ZS11dGlscyc7XG5cbmltcG9ydCB7IHN1cGVyVG9rZW5zTmV4dFdyYXBwZXIgfSBmcm9tICdzdXBlcnRva2Vucy1ub2RlL25leHRqcyc7XG5pbXBvcnQgeyB2ZXJpZnlTZXNzaW9uIH0gZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZS9yZWNpcGUvc2Vzc2lvbi9mcmFtZXdvcmsvZXhwcmVzcyc7XG5pbXBvcnQgc3VwZXJ0b2tlbnMgZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZSc7XG5pbXBvcnQgeyBiYWNrZW5kQ29uZmlnIH0gZnJvbSAnLi4vLi4vLi4vLi4vLi4vY29uZmlnL2JhY2tlbmRDb25maWcnOyAvLyBBZGp1c3RlZCBwYXRoXG5pbXBvcnQgeyBDcmVkZW50aWFscyBhcyBPQXV0aDJUb2tlbiB9IGZyb20gJ2dvb2dsZS1hdXRoLWxpYnJhcnknO1xuXG4vLyBBc3N1bWluZyB0aGVzZSBhcmUgbmVlZGVkIGZvciBHcmFwaFFMIGNsaWVudCB1c2VkIGJ5IHNhdmVVc2VyVG9rZW5zSW50ZXJuYWxcbi8vIFRoZXNlIGNvbnN0YW50cyBtaWdodCBiZSBiZXR0ZXIgc291cmNlZCBmcm9tIGEgc2hhcmVkIGNvbnN0YW50cyBmaWxlIHdpdGhpbiBhcHAtc2VydmljZSBpZiBwb3NzaWJsZSxcbi8vIG9yIGVuc3VyZSB0aGUgcGF0aCBpcyByb2J1c3QuXG5pbXBvcnQge1xuICBIQVNVUkFfR1JBUEhRTF9VUkwsXG4gIEhBU1VSQV9BRE1JTl9TRUNSRVQsXG59IGZyb20gJy4uLy4uLy4uLy4uLy4uLy4uL3Byb2plY3QvZnVuY3Rpb25zL2F0b20tYWdlbnQvX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7IGV4ZWN1dGVHcmFwaFFMTXV0YXRpb24gfSBmcm9tICcuLi8uLi8uLi8uLi8uLi8uLi9wcm9qZWN0L2Z1bmN0aW9ucy9hdG9tLWFnZW50L19saWJzL2dyYXBocWxDbGllbnQnO1xuaW1wb3J0IGFwcFNlcnZpY2VMb2dnZXIgZnJvbSAnLi4vLi4vLi4vLi4vLi4vbGliL2xvZ2dlcic7IC8vIEltcG9ydCB0aGUgc2hhcmVkIGFwcC1zZXJ2aWNlIGxvZ2dlclxuXG5jb25zdCBHT09HTEVfQ0FMRU5EQVJfU0VSVklDRV9OQU1FID0gJ2dvb2dsZV9jYWxlbmRhcic7XG5cbmNvbnN0IGNvcnMgPSBDb3JzKHtcbiAgbWV0aG9kczogWydQT1NUJywgJ0dFVCcsICdIRUFEJ10sXG4gIC8vIEFsbG93IGFsbCBvcmlnaW5zIGZvciBzaW1wbGljaXR5IGluIGRldiwgb3Igc3BlY2lmeSB5b3VyIGZyb250ZW5kIFVSTFxuICAvLyBvcmlnaW46IHByb2Nlc3MuZW52Lk5PREVfRU5WID09PSAncHJvZHVjdGlvbicgPyBbXCJodHRwczovL2F0b21pY2xpZmUuYXBwXCIsIC9cXC5hdG9taWNsaWZlXFwuYXBwJC9dIDogXCIqXCIsXG59KTtcblxuc3VwZXJ0b2tlbnMuaW5pdChiYWNrZW5kQ29uZmlnKCkpO1xuXG5mdW5jdGlvbiBydW5NaWRkbGV3YXJlKFxuICByZXE6IE5leHRBcGlSZXF1ZXN0LFxuICByZXM6IE5leHRBcGlSZXNwb25zZSxcbiAgZm46IEZ1bmN0aW9uXG4pIHtcbiAgcmV0dXJuIG5ldyBQcm9taXNlKChyZXNvbHZlLCByZWplY3QpID0+IHtcbiAgICBmbihyZXEsIHJlcywgKHJlc3VsdDogYW55KSA9PiB7XG4gICAgICBpZiAocmVzdWx0IGluc3RhbmNlb2YgRXJyb3IpIHtcbiAgICAgICAgcmV0dXJuIHJlamVjdChyZXN1bHQpO1xuICAgICAgfVxuICAgICAgcmV0dXJuIHJlc29sdmUocmVzdWx0KTtcbiAgICB9KTtcbiAgfSk7XG59XG5cbi8vIFRoaXMgZnVuY3Rpb24gaXMgYW4gYWRhcHRhdGlvbiBvZiBzYXZlVXNlclRva2VucyBmcm9tIGNhbGVuZGFyU2tpbGxzLnRzXG4vLyB0byBiZSB1c2VkIGRpcmVjdGx5IHdpdGhpbiB0aGlzIEFQSSByb3V0ZS5cbmFzeW5jIGZ1bmN0aW9uIHNhdmVVc2VyVG9rZW5zSW50ZXJuYWwoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0b2tlbnM6IE9BdXRoMlRva2VuXG4pOiBQcm9taXNlPHsgb2s6IGJvb2xlYW47IGVycm9yPzogYW55IH0+IHtcbiAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdzYXZlVXNlclRva2Vuc0ludGVybmFsX0dvb2dsZUNhbGVuZGFyQXV0aENhbGxiYWNrJztcbiAgYXBwU2VydmljZUxvZ2dlci5pbmZvKGBbJHtvcGVyYXRpb25OYW1lfV0gQXR0ZW1wdGluZyB0byBzYXZlIHRva2Vucy5gLCB7XG4gICAgdXNlcklkLFxuICAgIHNlcnZpY2U6IEdPT0dMRV9DQUxFTkRBUl9TRVJWSUNFX05BTUUsXG4gIH0pO1xuXG4gIGlmICghSEFTVVJBX0dSQVBIUUxfVVJMIHx8ICFIQVNVUkFfQURNSU5fU0VDUkVUKSB7XG4gICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gR3JhcGhRTCBjbGllbnQgY29uZmlndXJhdGlvbiBtaXNzaW5nIChIYXN1cmEgVVJML1NlY3JldCkuYCxcbiAgICAgIHsgdXNlcklkIH1cbiAgICApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ09ORklHX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ0dyYXBoUUwgY2xpZW50IGlzIG5vdCBjb25maWd1cmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cblxuICBjb25zdCBtdXRhdGlvbiA9IGBcbiAgICBtdXRhdGlvbiBVcHNlcnRVc2VyVG9rZW4oJG9iamVjdHM6IFt1c2VyX3Rva2Vuc19pbnNlcnRfaW5wdXQhXSEpIHtcbiAgICAgIGluc2VydF91c2VyX3Rva2VucyhcbiAgICAgICAgb2JqZWN0czogJG9iamVjdHMsXG4gICAgICAgIG9uX2NvbmZsaWN0OiB7XG4gICAgICAgICAgY29uc3RyYWludDogdXNlcl90b2tlbnNfdXNlcl9pZF9zZXJ2aWNlX25hbWVfa2V5LFxuICAgICAgICAgIHVwZGF0ZV9jb2x1bW5zOiBbYWNjZXNzX3Rva2VuLCByZWZyZXNoX3Rva2VuLCBleHBpcnlfZGF0ZSwgc2NvcGUsIHRva2VuX3R5cGUsIHVwZGF0ZWRfYXRdXG4gICAgICAgIH1cbiAgICAgICkge1xuICAgICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICB9XG4gICAgfVxuICBgO1xuXG4gIGNvbnN0IHRva2VuRGF0YUZvckRiID0ge1xuICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICBzZXJ2aWNlX25hbWU6IEdPT0dMRV9DQUxFTkRBUl9TRVJWSUNFX05BTUUsXG4gICAgYWNjZXNzX3Rva2VuOiB0b2tlbnMuYWNjZXNzX3Rva2VuLFxuICAgIHJlZnJlc2hfdG9rZW46IHRva2Vucy5yZWZyZXNoX3Rva2VuLFxuICAgIGV4cGlyeV9kYXRlOiB0b2tlbnMuZXhwaXJ5X2RhdGVcbiAgICAgID8gbmV3IERhdGUodG9rZW5zLmV4cGlyeV9kYXRlKS50b0lTT1N0cmluZygpXG4gICAgICA6IG51bGwsXG4gICAgc2NvcGU6IHRva2Vucy5zY29wZSxcbiAgICB0b2tlbl90eXBlOiB0b2tlbnMudG9rZW5fdHlwZSxcbiAgICB1cGRhdGVkX2F0OiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXG4gIH07XG5cbiAgY29uc3QgdmFyaWFibGVzID0geyBvYmplY3RzOiBbdG9rZW5EYXRhRm9yRGJdIH07XG4gIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnVXBzZXJ0VXNlclRva2VuJztcblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZXhlY3V0ZUdyYXBoUUxNdXRhdGlvbjx7XG4gICAgICBpbnNlcnRfdXNlcl90b2tlbnM6IHsgYWZmZWN0ZWRfcm93czogbnVtYmVyIH07XG4gICAgfT4oXG4gICAgICBtdXRhdGlvbixcbiAgICAgIHZhcmlhYmxlcyxcbiAgICAgIG9wZXJhdGlvbk5hbWUsIC8vIFRoaXMgaXMgJ1Vwc2VydFVzZXJUb2tlbicgZnJvbSB0aGUgR1FMIG11dGF0aW9uIG5hbWVcbiAgICAgIHVzZXJJZFxuICAgICk7XG5cbiAgICBpZiAoXG4gICAgICByZXNwb25zZSAmJlxuICAgICAgcmVzcG9uc2UuaW5zZXJ0X3VzZXJfdG9rZW5zICYmXG4gICAgICByZXNwb25zZS5pbnNlcnRfdXNlcl90b2tlbnMuYWZmZWN0ZWRfcm93cyA+IDBcbiAgICApIHtcbiAgICAgIGFwcFNlcnZpY2VMb2dnZXIuaW5mbyhcbiAgICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBUb2tlbnMgc2F2ZWQgc3VjY2Vzc2Z1bGx5IHRvIHVzZXJfdG9rZW5zIHRhYmxlLmAsXG4gICAgICAgIHsgdXNlcklkIH1cbiAgICAgICk7XG4gICAgICByZXR1cm4geyBvazogdHJ1ZSB9O1xuICAgIH0gZWxzZSB7XG4gICAgICBhcHBTZXJ2aWNlTG9nZ2VyLndhcm4oXG4gICAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gVG9rZW4gc2F2ZSBvcGVyYXRpb24gKHVzZXJfdG9rZW5zIHRhYmxlKSByZXBvcnRlZCAwIGFmZmVjdGVkX3Jvd3Mgb3Igbm8vdW5leHBlY3RlZCByZXNwb25zZS5gLFxuICAgICAgICB7IHVzZXJJZCwgcmVzcG9uc2UgfVxuICAgICAgKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnREJfTk9fUk9XU19BRkZFQ1RFRCcsXG4gICAgICAgICAgbWVzc2FnZTogJ1Rva2VuIHNhdmUgZGlkIG5vdCBhZmZlY3QgYW55IHJvd3MuJyxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihgWyR7b3BlcmF0aW9uTmFtZX1dIEV4Y2VwdGlvbiBkdXJpbmcgdG9rZW4gc2F2ZS5gLCB7XG4gICAgICB1c2VySWQsXG4gICAgICBlcnJvcjogZXJyb3IubWVzc2FnZSxcbiAgICAgIHN0YWNrOiBlcnJvci5zdGFjayxcbiAgICAgIGRldGFpbHM6IGVycm9yLFxuICAgIH0pO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnVE9LRU5fU0FWRV9GQUlMRURfSU5URVJOQUwnLFxuICAgICAgICBtZXNzYWdlOiBgRmFpbGVkIHRvIHNhdmUgR29vZ2xlIENhbGVuZGFyIHRva2VucyB0byB1c2VyX3Rva2VucyBmb3IgdXNlciAke3VzZXJJZH0uYCxcbiAgICAgICAgZGV0YWlsczogZXJyb3IubWVzc2FnZSxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufVxuXG5leHBvcnQgZGVmYXVsdCBhc3luYyBmdW5jdGlvbiBoYW5kbGVyKFxuICByZXE6IE5leHRBcGlSZXF1ZXN0LFxuICByZXM6IE5leHRBcGlSZXNwb25zZVxuKSB7XG4gIHRyeSB7XG4gICAgYXdhaXQgcnVuTWlkZGxld2FyZShyZXEsIHJlcywgY29ycyk7XG5cbiAgICBhd2FpdCBzdXBlclRva2Vuc05leHRXcmFwcGVyKFxuICAgICAgYXN5bmMgKG5leHQpID0+IHtcbiAgICAgICAgcmV0dXJuIGF3YWl0IHZlcmlmeVNlc3Npb24oKShyZXEgYXMgYW55LCByZXMgYXMgYW55LCBuZXh0KTtcbiAgICAgIH0sXG4gICAgICByZXEsXG4gICAgICByZXNcbiAgICApO1xuXG4gICAgY29uc3Qgc2Vzc2lvbiA9IHJlcS5zZXNzaW9uO1xuICAgIGNvbnN0IHVzZXJJZCA9IHNlc3Npb24/LmdldFVzZXJJZCgpO1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnR29vZ2xlQ2FsZW5kYXJBdXRoQ2FsbGJhY2snOyAvLyBGb3IgbG9nZ2luZyBjb250ZXh0XG5cbiAgICBpZiAoIXVzZXJJZCkge1xuICAgICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihcbiAgICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBVc2VyIG5vdCBhdXRoZW50aWNhdGVkIGluIGNhbGxiYWNrLiBTZXNzaW9uIG1heSBiZSBtaXNzaW5nIG9yIGludmFsaWQuYCxcbiAgICAgICAgeyBoZWFkZXJzOiByZXEuaGVhZGVycyB9XG4gICAgICApO1xuICAgICAgcmV0dXJuIHJlcy5yZWRpcmVjdChcbiAgICAgICAgJy9Vc2VyL0xvZ2luL1VzZXJMb2dpbj9lcnJvcj1zZXNzaW9uX2V4cGlyZWRfb2F1dGhfY2FsbGJhY2snXG4gICAgICApO1xuICAgIH1cbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oYFske29wZXJhdGlvbk5hbWV9XSBQcm9jZXNzaW5nIGNhbGxiYWNrIGZvciB1c2VyLmAsIHtcbiAgICAgIHVzZXJJZCxcbiAgICB9KTtcblxuICAgIGNvbnN0IHRoaXNVcmwgPSBuZXcgVVJMKHJlcS51cmwgYXMgc3RyaW5nLCBgaHR0cHM6Ly8ke3JlcS5oZWFkZXJzLmhvc3R9YCk7XG4gICAgY29uc3QgcXVlcnlQYXJhbXMgPSBxcy5wYXJzZSh0aGlzVXJsLnNlYXJjaC5zdWJzdHJpbmcoMSkpO1xuXG4gICAgaWYgKHF1ZXJ5UGFyYW1zLmVycm9yKSB7XG4gICAgICBjb25zdCBlcnJvciA9IHF1ZXJ5UGFyYW1zLmVycm9yIGFzIHN0cmluZztcbiAgICAgIGFwcFNlcnZpY2VMb2dnZXIud2FybihcbiAgICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBFcnJvciBmcm9tIEdvb2dsZSBPQXV0aCBwcm92aWRlci5gLFxuICAgICAgICB7IHVzZXJJZCwgZXJyb3IsIHF1ZXJ5UGFyYW1zIH1cbiAgICAgICk7XG4gICAgICByZXR1cm4gcmVzLnJlZGlyZWN0KFxuICAgICAgICBgL1NldHRpbmdzL1VzZXJWaWV3U2V0dGluZ3M/Y2FsZW5kYXJfYXV0aF9lcnJvcj0ke2VuY29kZVVSSUNvbXBvbmVudChlcnJvcil9JmF0b21fYWdlbnQ9dHJ1ZWBcbiAgICAgICk7XG4gICAgfVxuXG4gICAgY29uc3QgY29kZSA9IHF1ZXJ5UGFyYW1zLmNvZGUgYXMgc3RyaW5nO1xuICAgIGNvbnN0IHN0YXRlID0gcXVlcnlQYXJhbXMuc3RhdGUgYXMgc3RyaW5nO1xuXG4gICAgaWYgKHN0YXRlICE9PSB1c2VySWQpIHtcbiAgICAgIGFwcFNlcnZpY2VMb2dnZXIuZXJyb3IoXG4gICAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gSW52YWxpZCBPQXV0aCBzdGF0ZS4gQ1NSRiBhdHRlbXB0P2AsXG4gICAgICAgIHsgZXhwZWN0ZWRTdGF0ZTogdXNlcklkLCByZWNlaXZlZFN0YXRlOiBzdGF0ZSB9XG4gICAgICApO1xuICAgICAgcmV0dXJuIHJlcy5yZWRpcmVjdChcbiAgICAgICAgYC9TZXR0aW5ncy9Vc2VyVmlld1NldHRpbmdzP2NhbGVuZGFyX2F1dGhfZXJyb3I9aW52YWxpZF9zdGF0ZSZhdG9tX2FnZW50PXRydWVgXG4gICAgICApO1xuICAgIH1cblxuICAgIGlmICghY29kZSkge1xuICAgICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihcbiAgICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBObyBhdXRob3JpemF0aW9uIGNvZGUgcmVjZWl2ZWQgZnJvbSBHb29nbGUuYCxcbiAgICAgICAgeyB1c2VySWQgfVxuICAgICAgKTtcbiAgICAgIHJldHVybiByZXMucmVkaXJlY3QoXG4gICAgICAgIGAvU2V0dGluZ3MvVXNlclZpZXdTZXR0aW5ncz9jYWxlbmRhcl9hdXRoX2Vycm9yPW5vX2NvZGVfcmVjZWl2ZWQmYXRvbV9hZ2VudD10cnVlYFxuICAgICAgKTtcbiAgICB9XG4gICAgYXBwU2VydmljZUxvZ2dlci5kZWJ1ZyhgWyR7b3BlcmF0aW9uTmFtZX1dIEF1dGhvcml6YXRpb24gY29kZSByZWNlaXZlZC5gLCB7XG4gICAgICB1c2VySWQsXG4gICAgICBjb2RlUHJlZml4OiBjb2RlPy5zdWJzdHJpbmcoMCwgMTApLFxuICAgIH0pO1xuXG4gICAgY29uc3QgdG9rZW5zID0gYXdhaXQgZXhjaGFuZ2VDb2RlRm9yVG9rZW5zKGNvZGUpO1xuXG4gICAgaWYgKCF0b2tlbnMgfHwgIXRva2Vucy5hY2Nlc3NfdG9rZW4pIHtcbiAgICAgIGFwcFNlcnZpY2VMb2dnZXIuZXJyb3IoXG4gICAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRmFpbGVkIHRvIGV4Y2hhbmdlIGNvZGUgZm9yIHRva2VucyBvciBhY2Nlc3NfdG9rZW4gbWlzc2luZy5gLFxuICAgICAgICB7XG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIHRva2Vuc1JlY2VpdmVkOiAhIXRva2VucyxcbiAgICAgICAgICBhY2Nlc3NUb2tlblByZXNlbnQ6ICEhdG9rZW5zPy5hY2Nlc3NfdG9rZW4sXG4gICAgICAgIH1cbiAgICAgICk7XG4gICAgICByZXR1cm4gcmVzLnJlZGlyZWN0KFxuICAgICAgICBgL1NldHRpbmdzL1VzZXJWaWV3U2V0dGluZ3M/Y2FsZW5kYXJfYXV0aF9lcnJvcj10b2tlbl9leGNoYW5nZV9mYWlsZWQmYXRvbV9hZ2VudD10cnVlYFxuICAgICAgKTtcbiAgICB9XG5cbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIFRva2VucyByZWNlaXZlZCBmcm9tIEdvb2dsZSBzdWNjZXNzZnVsbHkuYCxcbiAgICAgIHtcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBhY2Nlc3NUb2tlblByZXNlbnQ6ICEhdG9rZW5zLmFjY2Vzc190b2tlbixcbiAgICAgICAgcmVmcmVzaFRva2VuUHJlc2VudDogISF0b2tlbnMucmVmcmVzaF90b2tlbixcbiAgICAgICAgZXhwaXJlc0F0OiB0b2tlbnMuZXhwaXJ5X2RhdGUsXG4gICAgICAgIHNjb3BlOiB0b2tlbnMuc2NvcGUsXG4gICAgICB9XG4gICAgKTtcblxuICAgIGNvbnN0IHNhdmVSZXN1bHQgPSBhd2FpdCBzYXZlVXNlclRva2Vuc0ludGVybmFsKHVzZXJJZCwgdG9rZW5zKTtcblxuICAgIGlmICghc2F2ZVJlc3VsdC5vaykge1xuICAgICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihcbiAgICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBGYWlsZWQgdG8gc2F2ZSB0b2tlbnMgdG8gdXNlcl90b2tlbnMgdGFibGUuYCxcbiAgICAgICAgeyB1c2VySWQsIGVycm9yRGV0YWlsczogc2F2ZVJlc3VsdC5lcnJvciB9XG4gICAgICApO1xuICAgICAgY29uc3QgZXJyb3JNZXNzYWdlID0gc2F2ZVJlc3VsdC5lcnJvcj8ubWVzc2FnZSB8fCAnZmFpbGVkX3RvX3NhdmVfdG9rZW5zJztcbiAgICAgIHJldHVybiByZXMucmVkaXJlY3QoXG4gICAgICAgIGAvU2V0dGluZ3MvVXNlclZpZXdTZXR0aW5ncz9jYWxlbmRhcl9hdXRoX2Vycm9yPSR7ZW5jb2RlVVJJQ29tcG9uZW50KGVycm9yTWVzc2FnZSl9JmF0b21fYWdlbnQ9dHJ1ZWBcbiAgICAgICk7XG4gICAgfVxuXG4gICAgYXBwU2VydmljZUxvZ2dlci5pbmZvKFxuICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBHb29nbGUgQ2FsZW5kYXIgY29ubmVjdGVkIGFuZCB0b2tlbnMgc2F2ZWQgc3VjY2Vzc2Z1bGx5LmAsXG4gICAgICB7IHVzZXJJZCB9XG4gICAgKTtcbiAgICByZXR1cm4gcmVzLnJlZGlyZWN0KFxuICAgICAgJy9TZXR0aW5ncy9Vc2VyVmlld1NldHRpbmdzP2NhbGVuZGFyX2F1dGhfc3VjY2Vzcz10cnVlJmF0b21fYWdlbnQ9dHJ1ZSdcbiAgICApO1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICAvLyBDYXRjaGluZyAnYW55JyB0byBhY2Nlc3MgcG90ZW50aWFsIHByb3BlcnRpZXMgbGlrZSAnbWVzc2FnZSdcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0dvb2dsZUNhbGVuZGFyQXV0aENhbGxiYWNrX091dGVyQ2F0Y2gnOyAvLyBTcGVjaWZpYyBmb3IgdGhpcyBjYXRjaFxuICAgIGFwcFNlcnZpY2VMb2dnZXIuZXJyb3IoXG4gICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEdlbmVyYWwgZXJyb3IgaW4gR29vZ2xlIE9BdXRoIGNhbGxiYWNrIGhhbmRsZXIuYCxcbiAgICAgIHsgZXJyb3I6IGUubWVzc2FnZSwgc3RhY2s6IGUuc3RhY2ssIGRldGFpbHM6IGUgfVxuICAgICk7XG4gICAgLy8gQXZvaWQgZXhwb3Npbmcgc2Vuc2l0aXZlIGVycm9yIGRldGFpbHMgaW4gcmVkaXJlY3QuXG4gICAgcmV0dXJuIHJlcy5yZWRpcmVjdChcbiAgICAgIGAvU2V0dGluZ3MvVXNlclZpZXdTZXR0aW5ncz9jYWxlbmRhcl9hdXRoX2Vycm9yPSR7ZW5jb2RlVVJJQ29tcG9uZW50KCdjYWxsYmFja19wcm9jZXNzaW5nX2ZhaWxlZCcpfSZhdG9tX2FnZW50PXRydWVgXG4gICAgKTtcbiAgfVxufVxuIl19