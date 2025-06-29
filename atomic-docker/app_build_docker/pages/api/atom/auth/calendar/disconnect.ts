import type { NextApiRequest, NextApiResponse } from 'next';
import { google } from 'googleapis';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from 'supertokens-node/recipe/session/framework/express';
import supertokens from 'supertokens-node';
import { backendConfig } from '../../../../../config/backendConfig'; // Adjusted path
import { ATOM_GOOGLE_CALENDAR_CLIENT_ID, ATOM_GOOGLE_CALENDAR_CLIENT_SECRET, HASURA_ADMIN_SECRET, HASURA_GRAPHQL_URL } from '../../../../../../project/functions/atom-agent/_libs/constants';
import { executeGraphQLMutation, executeGraphQLQuery } from '../../../../../../project/functions/atom-agent/_libs/graphqlClient';

supertokens.init(backendConfig());

const GOOGLE_CALENDAR_SERVICE_NAME = 'google_calendar';

async function deleteUserTokensInternal(userId: string, serviceName: string): Promise<{ ok: boolean; error?: any }> {
    console.log(`DISCONNECT: Deleting tokens for userId: ${userId}, service: ${serviceName}`);

    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error("DISCONNECT: GraphQL client is not configured for deleteUserTokensInternal.");
        return { ok: false, error: { code: 'CONFIG_ERROR', message: 'GraphQL client is not configured.' } };
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
        const response = await executeGraphQLMutation<{ delete_user_tokens: { affected_rows: number } }>(
            mutation,
            variables,
            operationName,
            userId // This argument is for context/logging in executeGraphQLMutation
        );

        if (response && response.delete_user_tokens) {
            console.log(`DISCONNECT: Tokens deleted from user_tokens table for user ${userId}, service ${serviceName}. Affected rows: ${response.delete_user_tokens.affected_rows}`);
            return { ok: true };
        } else {
            console.warn(`DISCONNECT: Token delete operation for user ${userId}, service ${serviceName} (user_tokens table) reported no response or unexpected structure.`, response);
            // Even if 0 rows affected (e.g., tokens already deleted), consider it a success for the flow.
            // If an actual error occurred during DB operation, it would be caught in the catch block.
            if (response.delete_user_tokens.affected_rows === 0) {
                 console.log(`DISCONNECT: No tokens found to delete for user ${userId}, service ${serviceName}. Considered successful.`);
                 return { ok: true }; // No rows deleted can be a valid state
            }
            return { ok: false, error: { code: 'DB_DELETE_NO_RESPONSE', message: 'Token delete operation returned no response or unexpected data.' }};
        }
    } catch (error: any) {
        console.error(`DISCONNECT: Exception during deleteUserTokensInternal for userId ${userId}, service ${serviceName}:`, error);
        return {
            ok: false,
            error: {
                code: 'TOKEN_DELETE_FAILED_INTERNAL',
                message: `Failed to delete Google Calendar tokens from user_tokens for user ${userId}.`,
                details: error.message
            }
        };
    }
}

// Helper to get an OAuth2 client
function getOAuth2Client() {
  if (!ATOM_GOOGLE_CALENDAR_CLIENT_ID || !ATOM_GOOGLE_CALENDAR_CLIENT_SECRET) {
    console.error('Google Calendar OAuth client ID or secret not configured for Atom Agent.');
    // This is a server configuration issue, should not happen in a properly configured environment.
    throw new Error('OAuth configuration error. Server not properly configured.');
  }
  return new google.auth.OAuth2(
    ATOM_GOOGLE_CALENDAR_CLIENT_ID,
    ATOM_GOOGLE_CALENDAR_CLIENT_SECRET
    // Redirect URI is not needed for token revocation
  );
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    await superTokensNextWrapper(
        async (next) => verifySession()(req as any, res as any, next),
        req,
        res
    );

    if (req.method !== 'POST') {
        res.setHeader('Allow', ['POST']);
        return res.status(405).json({ success: false, message: `Method ${req.method} Not Allowed` });
    }

    const session = req.session;
    const userId = session?.getUserId();

    if (!userId) {
        console.error("DISCONNECT: User not authenticated for disconnect operation.");
        return res.status(401).json({ success: false, message: 'User not authenticated.' });
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
        const tokenVariables = { userId, serviceName: GOOGLE_CALENDAR_SERVICE_NAME };
        const tokenResponse = await executeGraphQLQuery<{ user_tokens: [{ refresh_token?: string }] }>(
            getTokenQuery, tokenVariables, 'GetUserRefreshTokenForDisconnect', userId
        );

        const refreshToken = tokenResponse?.user_tokens?.[0]?.refresh_token;

        if (refreshToken) {
            const oauth2Client = getOAuth2Client(); // This can throw if not configured
            try {
                await oauth2Client.revokeToken(refreshToken);
                console.log(`DISCONNECT: Google token revoked successfully via API for user ${userId}.`);
            } catch (revokeError: any) {
                console.warn(`DISCONNECT: Failed to revoke Google token via API for user ${userId}. Error: ${revokeError.message}. This may be acceptable if the token was already invalid.`);
                // If Google returns 'invalid_token', it means the token is already unusable.
                // Other errors might be network issues or configuration problems.
                // We will proceed to delete our local copy regardless.
            }
        } else {
            console.log(`DISCONNECT: No Google refresh token found in DB for user ${userId} to revoke. Proceeding with local DB deletion.`);
        }

        const deleteDbResult = await deleteUserTokensInternal(userId, GOOGLE_CALENDAR_SERVICE_NAME);

        if (!deleteDbResult.ok) {
            console.error(`DISCONNECT: Failed to delete tokens from DB for user ${userId} after attempting revocation:`, deleteDbResult.error);
            // This is an internal error; the user's grant might still be active with Google if revocation failed AND DB delete failed.
            return res.status(500).json({ success: false, message: 'Failed to remove calendar connection details from the database.' });
        }

        console.log(`DISCONNECT: Google Calendar disconnected successfully (DB and attempted revocation) for user ${userId}.`);
        // Redirect to settings page with success message
        return res.redirect('/Settings/UserViewSettings?calendar_disconnect_success=true&atom_agent=true');

    } catch (error: any) {
        console.error(`DISCONNECT: General error during Google Calendar disconnect for user ${userId}:`, error);
        // This catch block handles errors from getOAuth2Client or other unexpected issues.
        return res.status(500).json({ success: false, message: 'An unexpected error occurred while disconnecting Google Calendar.' });
    }
}
