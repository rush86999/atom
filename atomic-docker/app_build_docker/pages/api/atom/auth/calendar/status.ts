import type { NextApiRequest, NextApiResponse } from 'next';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from 'supertokens-node/recipe/session/framework/express';
import supertokens from 'supertokens-node';
import { backendConfig } from '../../../../../config/backendConfig'; // Adjusted path
import { HASURA_ADMIN_SECRET, HASURA_GRAPHQL_URL } from '../../../../../../project/functions/atom-agent/_libs/constants';
import { executeGraphQLQuery } from '../../../../../../project/functions/atom-agent/_libs/graphqlClient';
import { google } from 'googleapis';
import { ATOM_GOOGLE_CALENDAR_CLIENT_ID, ATOM_GOOGLE_CALENDAR_CLIENT_SECRET } from '../../../../../../project/functions/atom-agent/_libs/constants';

supertokens.init(backendConfig());

const GOOGLE_CALENDAR_SERVICE_NAME = 'google_calendar';

interface UserTokenRecord {
  access_token: string;
  refresh_token?: string | null;
  expiry_date?: string | null; // ISO String from DB
  // We don't necessarily need email here, but it could be fetched if needed
}

// Basic check if token seems present and not obviously expired
// For a more robust check, an actual API call to Google is better.
async function checkTokenValidity(userId: string): Promise<{ isConnected: boolean; email?: string; error?: string }> {
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error("STATUS: GraphQL client is not configured.");
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
        const response = await executeGraphQLQuery<{ user_tokens: UserTokenRecord[] }>(query, variables, operationName, userId);

        if (!response || !response.user_tokens || response.user_tokens.length === 0 || !response.user_tokens[0].access_token) {
            return { isConnected: false };
        }

        const tokenRecord = response.user_tokens[0];

        // Optional: Check expiry if available and reasonably current.
        // Note: expiry_date from Google is a timestamp. If it's stored as ISO string, parse it.
        // A more reliable check is to try to use the token.
        if (tokenRecord.expiry_date) {
            const expiryTimestamp = new Date(tokenRecord.expiry_date).getTime();
            if (Date.now() > expiryTimestamp - (5 * 60 * 1000)) { // 5 minutes buffer
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
            if (!ATOM_GOOGLE_CALENDAR_CLIENT_ID || !ATOM_GOOGLE_CALENDAR_CLIENT_SECRET) {
                 console.error("STATUS: Google OAuth client credentials not configured for API test call.");
                 // Fallback: if token exists in DB, assume connected for now, but log this issue.
                 return { isConnected: true, email: undefined }; // Cannot fetch email without API call
            }
            const oauth2Client = new google.auth.OAuth2(ATOM_GOOGLE_CALENDAR_CLIENT_ID, ATOM_GOOGLE_CALENDAR_CLIENT_SECRET);
            oauth2Client.setCredentials({ access_token: tokenRecord.access_token, refresh_token: tokenRecord.refresh_token || undefined });

            try {
                const calendar = google.calendar({ version: 'v3', auth: oauth2Client });
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

            } catch (apiError: any) {
                console.warn(`STATUS: Google API call failed for user ${userId} with stored token. Error: ${apiError.message}`);
                // If 'invalid_grant' or similar, token is bad.
                if (apiError.response?.data?.error === 'invalid_grant' || apiError.code === 401) {
                    return { isConnected: false, error: 'token_invalid_or_expired' };
                }
                // Other errors might be temporary, but for status, safer to say not connected if API fails.
                return { isConnected: false, error: 'api_call_failed' };
            }
        }

        return { isConnected: true }; // Fallback if only access_token was found and no expiry check failed.

    } catch (error: any) {
        console.error(`STATUS: Exception during token status check for userId ${userId}:`, error);
        return { isConnected: false, error: 'status_check_exception' };
    }
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    await superTokensNextWrapper(
        async (next) => verifySession()(req as any, res as any, next),
        req,
        res
    );

    if (req.method !== 'GET') {
        res.setHeader('Allow', ['GET']);
        return res.status(405).json({ message: `Method ${req.method} Not Allowed` });
    }

    const session = req.session;
    const userId = session?.getUserId();

    if (!userId) {
        console.error("STATUS: User not authenticated for status check.");
        return res.status(401).json({ isConnected: false, error: 'User not authenticated.' });
    }

    try {
        const status = await checkTokenValidity(userId);
        console.log(`STATUS: Google Calendar connection status for user ${userId}: ${status.isConnected}`);
        return res.status(200).json(status);
    } catch (error: any) {
        console.error(`STATUS: Error getting Google Calendar connection status for user ${userId}:`, error);
        return res.status(500).json({ isConnected: false, error: 'Failed to get connection status.' });
    }
}
