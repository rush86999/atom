import { google } from 'googleapis';
import { OAuth2Client } from 'google-auth-library';
import { decrypt } from '../_libs/crypto';
import { executeGraphQLQuery } from '../_libs/graphqlClient';

async function getGoogleCalendarToken(userId: string): Promise<string | null> {
    const query = `
        query GetUserToken($userId: String!, $service: String!) {
            user_tokens(where: {user_id: {_eq: $userId}, service: {_eq: $service}}) {
                access_token
            }
        }
    `;
    const variables = {
        userId,
        service: 'google',
    };
    const response = await executeGraphQLQuery<{ user_tokens: { access_token: string }[] }>(query, variables, 'GetUserToken', userId);
    if (response.user_tokens && response.user_tokens.length > 0) {
        return decrypt(response.user_tokens[0].access_token);
    }
    return null;
}

export async function getMeetingLoad(userId: string, timeMin: string, timeMax: string): Promise<any> {
    const token = await getGoogleCalendarToken(userId);
    if (!token) {
        throw new Error("Google Calendar token not configured for this user.");
    }
    const auth = new google.auth.OAuth2();
    auth.setCredentials({ access_token: token });
    const calendar = google.calendar({ version: 'v3', auth });

    try {
        const response = await calendar.events.list({
            calendarId: 'primary',
            timeMin,
            timeMax,
            singleEvents: true,
            orderBy: 'startTime',
        });
        return response.data.items;
    } catch (error) {
        console.error("Error fetching calendar events:", error);
        return null;
    }
}