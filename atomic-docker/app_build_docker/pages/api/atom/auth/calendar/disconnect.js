"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const googleapis_1 = require("googleapis");
const nextjs_1 = require("supertokens-node/nextjs");
const express_1 = require("supertokens-node/recipe/session/framework/express");
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const backendConfig_1 = require("../../../../../config/backendConfig"); // Adjusted path
const constants_1 = require("../../../../../../project/functions/atom-agent/_libs/constants");
const graphqlClient_1 = require("../../../../../../project/functions/atom-agent/_libs/graphqlClient");
supertokens_node_1.default.init((0, backendConfig_1.backendConfig)());
const GOOGLE_CALENDAR_SERVICE_NAME = 'google_calendar';
async function deleteUserTokensInternal(userId, serviceName) {
    console.log(`DISCONNECT: Deleting tokens for userId: ${userId}, service: ${serviceName}`);
    if (!constants_1.HASURA_GRAPHQL_URL || !constants_1.HASURA_ADMIN_SECRET) {
        console.error('DISCONNECT: GraphQL client is not configured for deleteUserTokensInternal.');
        return {
            ok: false,
            error: {
                code: 'CONFIG_ERROR',
                message: 'GraphQL client is not configured.',
            },
        };
    }
    const mutation = `
        mutation DeleteUserTokens($userId: String!, $serviceName: String!) {
            delete_user_tokens(where: {user_id: {_eq: $userId}, service_name: {_eq: $serviceName}}) {
                affected_rows
            }
        }
    `;
    const variables = { userId, serviceName };
    const operationName = 'DeleteUserTokens';
    try {
        // Ensure userId is passed as the last argument if your executeGraphQLMutation expects it for context/logging
        const response = await (0, graphqlClient_1.executeGraphQLMutation)(mutation, variables, operationName, userId // This argument is for context/logging in executeGraphQLMutation
        );
        if (response && response.delete_user_tokens) {
            console.log(`DISCONNECT: Tokens deleted from user_tokens table for user ${userId}, service ${serviceName}. Affected rows: ${response.delete_user_tokens.affected_rows}`);
            return { ok: true };
        }
        else {
            console.warn(`DISCONNECT: Token delete operation for user ${userId}, service ${serviceName} (user_tokens table) reported no response or unexpected structure.`, response);
            // Even if 0 rows affected (e.g., tokens already deleted), consider it a success for the flow.
            // If an actual error occurred during DB operation, it would be caught in the catch block.
            if (response.delete_user_tokens.affected_rows === 0) {
                console.log(`DISCONNECT: No tokens found to delete for user ${userId}, service ${serviceName}. Considered successful.`);
                return { ok: true }; // No rows deleted can be a valid state
            }
            return {
                ok: false,
                error: {
                    code: 'DB_DELETE_NO_RESPONSE',
                    message: 'Token delete operation returned no response or unexpected data.',
                },
            };
        }
    }
    catch (error) {
        console.error(`DISCONNECT: Exception during deleteUserTokensInternal for userId ${userId}, service ${serviceName}:`, error);
        return {
            ok: false,
            error: {
                code: 'TOKEN_DELETE_FAILED_INTERNAL',
                message: `Failed to delete Google Calendar tokens from user_tokens for user ${userId}.`,
                details: error.message,
            },
        };
    }
}
// Helper to get an OAuth2 client
function getOAuth2Client() {
    if (!constants_1.ATOM_GOOGLE_CALENDAR_CLIENT_ID || !constants_1.ATOM_GOOGLE_CALENDAR_CLIENT_SECRET) {
        console.error('Google Calendar OAuth client ID or secret not configured for Atom Agent.');
        // This is a server configuration issue, should not happen in a properly configured environment.
        throw new Error('OAuth configuration error. Server not properly configured.');
    }
    return new googleapis_1.google.auth.OAuth2(constants_1.ATOM_GOOGLE_CALENDAR_CLIENT_ID, constants_1.ATOM_GOOGLE_CALENDAR_CLIENT_SECRET
    // Redirect URI is not needed for token revocation
    );
}
async function handler(req, res) {
    await (0, nextjs_1.superTokensNextWrapper)(async (next) => (0, express_1.verifySession)()(req, res, next), req, res);
    if (req.method !== 'POST') {
        res.setHeader('Allow', ['POST']);
        return res
            .status(405)
            .json({ success: false, message: `Method ${req.method} Not Allowed` });
    }
    const session = req.session;
    const userId = session?.getUserId();
    if (!userId) {
        console.error('DISCONNECT: User not authenticated for disconnect operation.');
        return res
            .status(401)
            .json({ success: false, message: 'User not authenticated.' });
    }
    try {
        const getTokenQuery = `
            query GetUserRefreshTokenForDisconnect($userId: String!, $serviceName: String!) {
                user_tokens(
                    where: { user_id: { _eq: $userId }, service_name: { _eq: $serviceName }, refresh_token: {_is_null: false} },
                    order_by: { created_at: desc },
                    limit: 1
                ) {
                    refresh_token
                }
            }
        `;
        const tokenVariables = {
            userId,
            serviceName: GOOGLE_CALENDAR_SERVICE_NAME,
        };
        const tokenResponse = await (0, graphqlClient_1.executeGraphQLQuery)(getTokenQuery, tokenVariables, 'GetUserRefreshTokenForDisconnect', userId);
        const refreshToken = tokenResponse?.user_tokens?.[0]?.refresh_token;
        if (refreshToken) {
            const oauth2Client = getOAuth2Client(); // This can throw if not configured
            try {
                await oauth2Client.revokeToken(refreshToken);
                console.log(`DISCONNECT: Google token revoked successfully via API for user ${userId}.`);
            }
            catch (revokeError) {
                console.warn(`DISCONNECT: Failed to revoke Google token via API for user ${userId}. Error: ${revokeError.message}. This may be acceptable if the token was already invalid.`);
                // If Google returns 'invalid_token', it means the token is already unusable.
                // Other errors might be network issues or configuration problems.
                // We will proceed to delete our local copy regardless.
            }
        }
        else {
            console.log(`DISCONNECT: No Google refresh token found in DB for user ${userId} to revoke. Proceeding with local DB deletion.`);
        }
        const deleteDbResult = await deleteUserTokensInternal(userId, GOOGLE_CALENDAR_SERVICE_NAME);
        if (!deleteDbResult.ok) {
            console.error(`DISCONNECT: Failed to delete tokens from DB for user ${userId} after attempting revocation:`, deleteDbResult.error);
            // This is an internal error; the user's grant might still be active with Google if revocation failed AND DB delete failed.
            return res
                .status(500)
                .json({
                success: false,
                message: 'Failed to remove calendar connection details from the database.',
            });
        }
        console.log(`DISCONNECT: Google Calendar disconnected successfully (DB and attempted revocation) for user ${userId}.`);
        // Redirect to settings page with success message
        return res.redirect('/Settings/UserViewSettings?calendar_disconnect_success=true&atom_agent=true');
    }
    catch (error) {
        console.error(`DISCONNECT: General error during Google Calendar disconnect for user ${userId}:`, error);
        // This catch block handles errors from getOAuth2Client or other unexpected issues.
        return res
            .status(500)
            .json({
            success: false,
            message: 'An unexpected error occurred while disconnecting Google Calendar.',
        });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGlzY29ubmVjdC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImRpc2Nvbm5lY3QudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUE0SEEsMEJBc0hDO0FBalBELDJDQUFvQztBQUNwQyxvREFBaUU7QUFDakUsK0VBQWtGO0FBQ2xGLHdFQUEyQztBQUMzQyx1RUFBb0UsQ0FBQyxnQkFBZ0I7QUFDckYsOEZBS3dFO0FBQ3hFLHNHQUc0RTtBQUU1RSwwQkFBVyxDQUFDLElBQUksQ0FBQyxJQUFBLDZCQUFhLEdBQUUsQ0FBQyxDQUFDO0FBRWxDLE1BQU0sNEJBQTRCLEdBQUcsaUJBQWlCLENBQUM7QUFFdkQsS0FBSyxVQUFVLHdCQUF3QixDQUNyQyxNQUFjLEVBQ2QsV0FBbUI7SUFFbkIsT0FBTyxDQUFDLEdBQUcsQ0FDVCwyQ0FBMkMsTUFBTSxjQUFjLFdBQVcsRUFBRSxDQUM3RSxDQUFDO0lBRUYsSUFBSSxDQUFDLDhCQUFrQixJQUFJLENBQUMsK0JBQW1CLEVBQUUsQ0FBQztRQUNoRCxPQUFPLENBQUMsS0FBSyxDQUNYLDRFQUE0RSxDQUM3RSxDQUFDO1FBQ0YsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxjQUFjO2dCQUNwQixPQUFPLEVBQUUsbUNBQW1DO2FBQzdDO1NBQ0YsQ0FBQztJQUNKLENBQUM7SUFFRCxNQUFNLFFBQVEsR0FBRzs7Ozs7O0tBTWQsQ0FBQztJQUNKLE1BQU0sU0FBUyxHQUFHLEVBQUUsTUFBTSxFQUFFLFdBQVcsRUFBRSxDQUFDO0lBQzFDLE1BQU0sYUFBYSxHQUFHLGtCQUFrQixDQUFDO0lBRXpDLElBQUksQ0FBQztRQUNILDZHQUE2RztRQUM3RyxNQUFNLFFBQVEsR0FBRyxNQUFNLElBQUEsc0NBQXNCLEVBRzNDLFFBQVEsRUFDUixTQUFTLEVBQ1QsYUFBYSxFQUNiLE1BQU0sQ0FBQyxpRUFBaUU7U0FDekUsQ0FBQztRQUVGLElBQUksUUFBUSxJQUFJLFFB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Q0FBQztZQUN2QixPQUFPLENBQUMsS0FBSyxDQUNYLHdEQUF3RCxNQUFNLCtCQUErQixFQUM3RixjQUFjLENBQUMsS0FBSyxDQUNyQixDQUFDO1lBQ0YsMkhBQTJIO1lBQzNILE9BQU8sR0FBRztpQkFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2lCQUNYLElBQUksQ0FBQztnQkFDSixPQUFPLEVBQUUsS0FBSztnQkFDZCxPQUFPLEVBQ0wsaUVBQWlFO2FBQ3BFLENBQUMsQ0FBQztRQUNQLENBQUM7UUFFRCxPQUFPLENBQUMsR0FBRyxDQUNULGdHQUFnRyxNQUFNLEdBQUcsQ0FDMUcsQ0FBQztRQUNGLGlEQUFpRDtRQUNqRCxPQUFPLEdBQUcsQ0FBQyxRQUFRLENBQ2pCLDZFQUE2RSxDQUM5RSxDQUFDO0lBQ0osQ0FBQztJQUFDLE9BQU8sS0FBVSxFQUFFLENBQUM7UUFDcEIsT0FBTyxDQUFDLEtBQUssQ0FDWCx3RUFBd0UsTUFBTSxHQUFHLEVBQ2pGLEtBQUssQ0FDTixDQUFDO1FBQ0YsbUZBQW1GO1FBQ25GLE9BQU8sR0FBRzthQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7YUFDWCxJQUFJLENBQUM7WUFDSixPQUFPLEVBQUUsS0FBSztZQUNkLE9BQU8sRUFDTCxtRUFBbUU7U0FDdEUsQ0FBQyxDQUFDO0lBQ1AsQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgdHlwZSB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCB7IGdvb2dsZSB9IGZyb20gJ2dvb2dsZWFwaXMnO1xuaW1wb3J0IHsgc3VwZXJUb2tlbnNOZXh0V3JhcHBlciB9IGZyb20gJ3N1cGVydG9rZW5zLW5vZGUvbmV4dGpzJztcbmltcG9ydCB7IHZlcmlmeVNlc3Npb24gfSBmcm9tICdzdXBlcnRva2Vucy1ub2RlL3JlY2lwZS9zZXNzaW9uL2ZyYW1ld29yay9leHByZXNzJztcbmltcG9ydCBzdXBlcnRva2VucyBmcm9tICdzdXBlcnRva2Vucy1ub2RlJztcbmltcG9ydCB7IGJhY2tlbmRDb25maWcgfSBmcm9tICcuLi8uLi8uLi8uLi8uLi9jb25maWcvYmFja2VuZENvbmZpZyc7IC8vIEFkanVzdGVkIHBhdGhcbmltcG9ydCB7XG4gIEFUT01fR09PR0xFX0NBTEVOREFSX0NMSUVOVF9JRCxcbiAgQVRPTV9HT09HTEVfQ0FMRU5EQVJfQ0xJRU5UX1NFQ1JFVCxcbiAgSEFTVVJBX0FETUlOX1NFQ1JFVCxcbiAgSEFTVVJBX0dSQVBIUUxfVVJMLFxufSBmcm9tICcuLi8uLi8uLi8uLi8uLi8uLi9wcm9qZWN0L2Z1bmN0aW9ucy9hdG9tLWFnZW50L19saWJzL2NvbnN0YW50cyc7XG5pbXBvcnQge1xuICBleGVjdXRlR3JhcGhRTE11dGF0aW9uLFxuICBleGVjdXRlR3JhcGhRTFF1ZXJ5LFxufSBmcm9tICcuLi8uLi8uLi8uLi8uLi8uLi9wcm9qZWN0L2Z1bmN0aW9ucy9hdG9tLWFnZW50L19saWJzL2dyYXBocWxDbGllbnQnO1xuXG5zdXBlcnRva2Vucy5pbml0KGJhY2tlbmRDb25maWcoKSk7XG5cbmNvbnN0IEdPT0dMRV9DQUxFTkRBUl9TRVJWSUNFX05BTUUgPSAnZ29vZ2xlX2NhbGVuZGFyJztcblxuYXN5bmMgZnVuY3Rpb24gZGVsZXRlVXNlclRva2Vuc0ludGVybmFsKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgc2VydmljZU5hbWU6IHN0cmluZ1xuKTogUHJvbWlzZTx7IG9rOiBib29sZWFuOyBlcnJvcj86IGFueSB9PiB7XG4gIGNvbnNvbGUubG9nKFxuICAgIGBESVNDT05ORUNUOiBEZWxldGluZyB0b2tlbnMgZm9yIHVzZXJJZDogJHt1c2VySWR9LCBzZXJ2aWNlOiAke3NlcnZpY2VOYW1lfWBcbiAgKTtcblxuICBpZiAoIUhBU1VSQV9HUkFQSFFMX1VSTCB8fCAhSEFTVVJBX0FETUlOX1NFQ1JFVCkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAnRElTQ09OTkVDVDogR3JhcGhRTCBjbGllbnQgaXMgbm90IGNvbmZpZ3VyZWQgZm9yIGRlbGV0ZVVzZXJUb2tlbnNJbnRlcm5hbC4nXG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdHcmFwaFFMIGNsaWVudCBpcyBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgY29uc3QgbXV0YXRpb24gPSBgXG4gICAgICAgIG11dGF0aW9uIERlbGV0ZVVzZXJUb2tlbnMoJHVzZXJJZDogU3RyaW5nISwgJHNlcnZpY2VOYW1lOiBTdHJpbmchKSB7XG4gICAgICAgICAgICBkZWxldGVfdXNlcl90b2tlbnMod2hlcmU6IHt1c2VyX2lkOiB7X2VxOiAkdXNlcklkfSwgc2VydmljZV9uYW1lOiB7X2VxOiAkc2VydmljZU5hbWV9fSkge1xuICAgICAgICAgICAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgIGA7XG4gIGNvbnN0IHZhcmlhYmxlcyA9IHsgdXNlcklkLCBzZXJ2aWNlTmFtZSB9O1xuICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0RlbGV0ZVVzZXJUb2tlbnMnO1xuXG4gIHRyeSB7XG4gICAgLy8gRW5zdXJlIHVzZXJJZCBpcyBwYXNzZWQgYXMgdGhlIGxhc3QgYXJndW1lbnQgaWYgeW91ciBleGVjdXRlR3JhcGhRTE11dGF0aW9uIGV4cGVjdHMgaXQgZm9yIGNvbnRleHQvbG9nZ2luZ1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZXhlY3V0ZUdyYXBoUUxNdXRhdGlvbjx7XG4gICAgICBkZWxldGVfdXNlcl90b2tlbnM6IHsgYWZmZWN0ZWRfcm93czogbnVtYmVyIH07XG4gICAgfT4oXG4gICAgICBtdXRhdGlvbixcbiAgICAgIHZhcmlhYmxlcyxcbiAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICB1c2VySWQgLy8gVGhpcyBhcmd1bWVudCBpcyBmb3IgY29udGV4dC9sb2dnaW5nIGluIGV4ZWN1dGVHcmFwaFFMTXV0YXRpb25cbiAgICApO1xuXG4gICAgaWYgKHJlc3BvbnNlICYmIHJlc3BvbnNlLmRlbGV0ZV91c2VyX3Rva2Vucykge1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGBESVNDT05ORUNUOiBUb2tlbnMgZGVsZXRlZCBmcm9tIHVzZXJfdG9rZW5zIHRhYmxlIGZvciB1c2VyICR7dXNlcklkfSwgc2VydmljZSAke3NlcnZpY2VOYW1lfS4gQWZmZWN0ZWQgcm93czogJHtyZXNwb25zZS5kZWxldGVfdXNlcl90b2tlbnMuYWZmZWN0ZWRfcm93c31gXG4gICAgICApO1xuICAgICAgcmV0dXJuIHsgb2s6IHRydWUgfTtcbiAgICB9IGVsc2Uge1xuICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICBgRElTQ09OTkVDVDogVG9rZW4gZGVsZXRlIG9wZXJhdGlvbiBmb3IgdXNlciAke3VzZXJJZH0sIHNlcnZpY2UgJHtzZXJ2aWNlTmFtZX0gKHVzZXJfdG9rZW5zIHRhYmxlKSByZXBvcnRlZCBubyByZXNwb25zZSBvciB1bmV4cGVjdGVkIHN0cnVjdHVyZS5gLFxuICAgICAgICByZXNwb25zZVxuICAgICAgKTtcbiAgICAgIC8vIEV2ZW4gaWYgMCByb3dzIGFmZmVjdGVkIChlLmcuLCB0b2tlbnMgYWxyZWFkeSBkZWxldGVkKSwgY29uc2lkZXIgaXQgYSBzdWNjZXNzIGZvciB0aGUgZmxvdy5cbiAgICAgIC8vIElmIGFuIGFjdHVhbCBlcnJvciBvY2N1cnJlZCBkdXJpbmcgREIgb3BlcmF0aW9uLCBpdCB3b3VsZCBiZSBjYXVnaHQgaW4gdGhlIGNhdGNoIGJsb2NrLlxuICAgICAgaWYgKHJlc3BvbnNlLmRlbGV0ZV91c2VyX3Rva2Vucy5hZmZlY3RlZF9yb3dzID09PSAwKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIGBESVNDT05ORUNUOiBObyB0b2tlbnMgZm91bmQgdG8gZGVsZXRlIGZvciB1c2VyICR7dXNlcklkfSwgc2VydmljZSAke3NlcnZpY2VOYW1lfS4gQ29uc2lkZXJlZCBzdWNjZXNzZnVsLmBcbiAgICAgICAgKTtcbiAgICAgICAgcmV0dXJuIHsgb2s6IHRydWUgfTsgLy8gTm8gcm93cyBkZWxldGVkIGNhbiBiZSBhIHZhbGlkIHN0YXRlXG4gICAgICB9XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ0RCX0RFTEVURV9OT19SRVNQT05TRScsXG4gICAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICAgICdUb2tlbiBkZWxldGUgb3BlcmF0aW9uIHJldHVybmVkIG5vIHJlc3BvbnNlIG9yIHVuZXhwZWN0ZWQgZGF0YS4nLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgYERJU0NPTk5FQ1Q6IEV4Y2VwdGlvbiBkdXJpbmcgZGVsZXRlVXNlclRva2Vuc0ludGVybmFsIGZvciB1c2VySWQgJHt1c2VySWR9LCBzZXJ2aWNlICR7c2VydmljZU5hbWV9OmAsXG4gICAgICBlcnJvclxuICAgICk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdUT0tFTl9ERUxFVEVfRkFJTEVEX0lOVEVSTkFMJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBkZWxldGUgR29vZ2xlIENhbGVuZGFyIHRva2VucyBmcm9tIHVzZXJfdG9rZW5zIGZvciB1c2VyICR7dXNlcklkfS5gLFxuICAgICAgICBkZXRhaWxzOiBlcnJvci5tZXNzYWdlLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59XG5cbi8vIEhlbHBlciB0byBnZXQgYW4gT0F1dGgyIGNsaWVudFxuZnVuY3Rpb24gZ2V0T0F1dGgyQ2xpZW50KCkge1xuICBpZiAoIUFUT01fR09PR0xFX0NBTEVOREFSX0NMSUVOVF9JRCB8fCAhQVRPTV9HT09HTEVfQ0FMRU5EQVJfQ0xJRU5UX1NFQ1JFVCkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAnR29vZ2xlIENhbGVuZGFyIE9BdXRoIGNsaWVudCBJRCBvciBzZWNyZXQgbm90IGNvbmZpZ3VyZWQgZm9yIEF0b20gQWdlbnQuJ1xuICAgICk7XG4gICAgLy8gVGhpcyBpcyBhIHNlcnZlciBjb25maWd1cmF0aW9uIGlzc3VlLCBzaG91bGQgbm90IGhhcHBlbiBpbiBhIHByb3Blcmx5IGNvbmZpZ3VyZWQgZW52aXJvbm1lbnQuXG4gICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgJ09BdXRoIGNvbmZpZ3VyYXRpb24gZXJyb3IuIFNlcnZlciBub3QgcHJvcGVybHkgY29uZmlndXJlZC4nXG4gICAgKTtcbiAgfVxuICByZXR1cm4gbmV3IGdvb2dsZS5hdXRoLk9BdXRoMihcbiAgICBBVE9NX0dPT0dMRV9DQUxFTkRBUl9DTElFTlRfSUQsXG4gICAgQVRPTV9HT09HTEVfQ0FMRU5EQVJfQ0xJRU5UX1NFQ1JFVFxuICAgIC8vIFJlZGlyZWN0IFVSSSBpcyBub3QgbmVlZGVkIGZvciB0b2tlbiByZXZvY2F0aW9uXG4gICk7XG59XG5cbmV4cG9ydCBkZWZhdWx0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZXIoXG4gIHJlcTogTmV4dEFwaVJlcXVlc3QsXG4gIHJlczogTmV4dEFwaVJlc3BvbnNlXG4pIHtcbiAgYXdhaXQgc3VwZXJUb2tlbnNOZXh0V3JhcHBlcihcbiAgICBhc3luYyAobmV4dCkgPT4gdmVyaWZ5U2Vzc2lvbigpKHJlcSBhcyBhbnksIHJlcyBhcyBhbnksIG5leHQpLFxuICAgIHJlcSxcbiAgICByZXNcbiAgKTtcblxuICBpZiAocmVxLm1ldGhvZCAhPT0gJ1BPU1QnKSB7XG4gICAgcmVzLnNldEhlYWRlcignQWxsb3cnLCBbJ1BPU1QnXSk7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg0MDUpXG4gICAgICAuanNvbih7IHN1Y2Nlc3M6IGZhbHNlLCBtZXNzYWdlOiBgTWV0aG9kICR7cmVxLm1ldGhvZH0gTm90IEFsbG93ZWRgIH0pO1xuICB9XG5cbiAgY29uc3Qgc2Vzc2lvbiA9IHJlcS5zZXNzaW9uO1xuICBjb25zdCB1c2VySWQgPSBzZXNzaW9uPy5nZXRVc2VySWQoKTtcblxuICBpZiAoIXVzZXJJZCkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAnRElTQ09OTkVDVDogVXNlciBub3QgYXV0aGVudGljYXRlZCBmb3IgZGlzY29ubmVjdCBvcGVyYXRpb24uJ1xuICAgICk7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg0MDEpXG4gICAgICAuanNvbih7IHN1Y2Nlc3M6IGZhbHNlLCBtZXNzYWdlOiAnVXNlciBub3QgYXV0aGVudGljYXRlZC4nIH0pO1xuICB9XG5cbiAgdHJ5IHtcbiAgICBjb25zdCBnZXRUb2tlblF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgR2V0VXNlclJlZnJlc2hUb2tlbkZvckRpc2Nvbm5lY3QoJHVzZXJJZDogU3RyaW5nISwgJHNlcnZpY2VOYW1lOiBTdHJpbmchKSB7XG4gICAgICAgICAgICAgICAgdXNlcl90b2tlbnMoXG4gICAgICAgICAgICAgICAgICAgIHdoZXJlOiB7IHVzZXJfaWQ6IHsgX2VxOiAkdXNlcklkIH0sIHNlcnZpY2VfbmFtZTogeyBfZXE6ICRzZXJ2aWNlTmFtZSB9LCByZWZyZXNoX3Rva2VuOiB7X2lzX251bGw6IGZhbHNlfSB9LFxuICAgICAgICAgICAgICAgICAgICBvcmRlcl9ieTogeyBjcmVhdGVkX2F0OiBkZXNjIH0sXG4gICAgICAgICAgICAgICAgICAgIGxpbWl0OiAxXG4gICAgICAgICAgICAgICAgKSB7XG4gICAgICAgICAgICAgICAgICAgIHJlZnJlc2hfdG9rZW5cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG4gICAgY29uc3QgdG9rZW5WYXJpYWJsZXMgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICBzZXJ2aWNlTmFtZTogR09PR0xFX0NBTEVOREFSX1NFUlZJQ0VfTkFNRSxcbiAgICB9O1xuICAgIGNvbnN0IHRva2VuUmVzcG9uc2UgPSBhd2FpdCBleGVjdXRlR3JhcGhRTFF1ZXJ5PHtcbiAgICAgIHVzZXJfdG9rZW5zOiBbeyByZWZyZXNoX3Rva2VuPzogc3RyaW5nIH1dO1xuICAgIH0+KFxuICAgICAgZ2V0VG9rZW5RdWVyeSxcbiAgICAgIHRva2VuVmFyaWFibGVzLFxuICAgICAgJ0dldFVzZXJSZWZyZXNoVG9rZW5Gb3JEaXNjb25uZWN0JyxcbiAgICAgIHVzZXJJZFxuICAgICk7XG5cbiAgICBjb25zdCByZWZyZXNoVG9rZW4gPSB0b2tlblJlc3BvbnNlPy51c2VyX3Rva2Vucz8uWzBdPy5yZWZyZXNoX3Rva2VuO1xuXG4gICAgaWYgKHJlZnJlc2hUb2tlbikge1xuICAgICAgY29uc3Qgb2F1dGgyQ2xpZW50ID0gZ2V0T0F1dGgyQ2xpZW50KCk7IC8vIFRoaXMgY2FuIHRocm93IGlmIG5vdCBjb25maWd1cmVkXG4gICAgICB0cnkge1xuICAgICAgICBhd2FpdCBvYXV0aDJDbGllbnQucmV2b2tlVG9rZW4ocmVmcmVzaFRva2VuKTtcbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgYERJU0NPTk5FQ1Q6IEdvb2dsZSB0b2tlbiByZXZva2VkIHN1Y2Nlc3NmdWxseSB2aWEgQVBJIGZvciB1c2VyICR7dXNlcklkfS5gXG4gICAgICAgICk7XG4gICAgICB9IGNhdGNoIChyZXZva2VFcnJvcjogYW55KSB7XG4gICAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgICBgRElTQ09OTkVDVDogRmFpbGVkIHRvIHJldm9rZSBHb29nbGUgdG9rZW4gdmlhIEFQSSBmb3IgdXNlciAke3VzZXJJZH0uIEVycm9yOiAke3Jldm9rZUVycm9yLm1lc3NhZ2V9LiBUaGlzIG1heSBiZSBhY2NlcHRhYmxlIGlmIHRoZSB0b2tlbiB3YXMgYWxyZWFkeSBpbnZhbGlkLmBcbiAgICAgICAgKTtcbiAgICAgICAgLy8gSWYgR29vZ2xlIHJldHVybnMgJ2ludmFsaWRfdG9rZW4nLCBpdCBtZWFucyB0aGUgdG9rZW4gaXMgYWxyZWFkeSB1bnVzYWJsZS5cbiAgICAgICAgLy8gT3RoZXIgZXJyb3JzIG1pZ2h0IGJlIG5ldHdvcmsgaXNzdWVzIG9yIGNvbmZpZ3VyYXRpb24gcHJvYmxlbXMuXG4gICAgICAgIC8vIFdlIHdpbGwgcHJvY2VlZCB0byBkZWxldGUgb3VyIGxvY2FsIGNvcHkgcmVnYXJkbGVzcy5cbiAgICAgIH1cbiAgICB9IGVsc2Uge1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGBESVNDT05ORUNUOiBObyBHb29nbGUgcmVmcmVzaCB0b2tlbiBmb3VuZCBpbiBEQiBmb3IgdXNlciAke3VzZXJJZH0gdG8gcmV2b2tlLiBQcm9jZWVkaW5nIHdpdGggbG9jYWwgREIgZGVsZXRpb24uYFxuICAgICAgKTtcbiAgICB9XG5cbiAgICBjb25zdCBkZWxldGVEYlJlc3VsdCA9IGF3YWl0IGRlbGV0ZVVzZXJUb2tlbnNJbnRlcm5hbChcbiAgICAgIHVzZXJJZCxcbiAgICAgIEdPT0dMRV9DQUxFTkRBUl9TRVJWSUNFX05BTUVcbiAgICApO1xuXG4gICAgaWYgKCFkZWxldGVEYlJlc3VsdC5vaykge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgYERJU0NPTk5FQ1Q6IEZhaWxlZCB0byBkZWxldGUgdG9rZW5zIGZyb20gREIgZm9yIHVzZXIgJHt1c2VySWR9IGFmdGVyIGF0dGVtcHRpbmcgcmV2b2NhdGlvbjpgLFxuICAgICAgICBkZWxldGVEYlJlc3VsdC5lcnJvclxuICAgICAgKTtcbiAgICAgIC8vIFRoaXMgaXMgYW4gaW50ZXJuYWwgZXJyb3I7IHRoZSB1c2VyJ3MgZ3JhbnQgbWlnaHQgc3RpbGwgYmUgYWN0aXZlIHdpdGggR29vZ2xlIGlmIHJldm9jYXRpb24gZmFpbGVkIEFORCBEQiBkZWxldGUgZmFpbGVkLlxuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDUwMClcbiAgICAgICAgLmpzb24oe1xuICAgICAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgICAnRmFpbGVkIHRvIHJlbW92ZSBjYWxlbmRhciBjb25uZWN0aW9uIGRldGFpbHMgZnJvbSB0aGUgZGF0YWJhc2UuJyxcbiAgICAgICAgfSk7XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBgRElTQ09OTkVDVDogR29vZ2xlIENhbGVuZGFyIGRpc2Nvbm5lY3RlZCBzdWNjZXNzZnVsbHkgKERCIGFuZCBhdHRlbXB0ZWQgcmV2b2NhdGlvbikgZm9yIHVzZXIgJHt1c2VySWR9LmBcbiAgICApO1xuICAgIC8vIFJlZGlyZWN0IHRvIHNldHRpbmdzIHBhZ2Ugd2l0aCBzdWNjZXNzIG1lc3NhZ2VcbiAgICByZXR1cm4gcmVzLnJlZGlyZWN0KFxuICAgICAgJy9TZXR0aW5ncy9Vc2VyVmlld1NldHRpbmdzP2NhbGVuZGFyX2Rpc2Nvbm5lY3Rfc3VjY2Vzcz10cnVlJmF0b21fYWdlbnQ9dHJ1ZSdcbiAgICApO1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcihcbiAgICAgIGBESVNDT05ORUNUOiBHZW5lcmFsIGVycm9yIGR1cmluZyBHb29nbGUgQ2FsZW5kYXIgZGlzY29ubmVjdCBmb3IgdXNlciAke3VzZXJJZH06YCxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICAvLyBUaGlzIGNhdGNoIGJsb2NrIGhhbmRsZXMgZXJyb3JzIGZyb20gZ2V0T0F1dGgyQ2xpZW50IG9yIG90aGVyIHVuZXhwZWN0ZWQgaXNzdWVzLlxuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoNTAwKVxuICAgICAgLmpzb24oe1xuICAgICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICAnQW4gdW5leHBlY3RlZCBlcnJvciBvY2N1cnJlZCB3aGlsZSBkaXNjb25uZWN0aW5nIEdvb2dsZSBDYWxlbmRhci4nLFxuICAgICAgfSk7XG4gIH1cbn1cbiJdfQ==