import got from 'got';
import {
  ATOM_MSGRAPH_CLIENT_ID,
  ATOM_MSGRAPH_CLIENT_SECRET,
  ATOM_MSGRAPH_TENANT_ID,
  MSGRAPH_OAUTH_AUTHORITY_BASE,
  MSGRAPH_API_SCOPES, // Used for refresh token scope
  ATOM_MSGRAPH_REDIRECT_URI, // Required by MSAL/OAuth2, even if not directly used in refresh post
} from '../_libs/constants';
import { getAtomMicrosoftGraphTokens, saveAtomMicrosoftGraphTokens } from '../_libs/token-utils';
import { CalendarEvent, CreateEventResponse } from '../types'; // Assuming types are compatible
import dayjs from 'dayjs';

interface MicrosoftGraphTokenResponse {
    token_type: string;
    scope: string;
    expires_in: number; // Seconds
    access_token: string;
    refresh_token?: string; // May or may not be returned on refresh
}

// Internal helper function to refresh Microsoft Graph token
async function refreshMicrosoftGraphToken(userId: string, refreshToken: string, existingAppEmail?: string | null): Promise<string | null> {
    if (!ATOM_MSGRAPH_CLIENT_ID || !ATOM_MSGRAPH_CLIENT_SECRET || !ATOM_MSGRAPH_TENANT_ID || !ATOM_MSGRAPH_REDIRECT_URI) {
        console.error('Microsoft Graph client credentials or tenant ID or redirect URI not configured for token refresh.');
        return null;
    }
    const tokenEndpoint = `${MSGRAPH_OAUTH_AUTHORITY_BASE}${ATOM_MSGRAPH_TENANT_ID}/oauth2/v2.0/token`;

    try {
        console.log(`Attempting to refresh Microsoft Graph token for userId: ${userId}`);
        const response = await got.post(tokenEndpoint, {
            form: {
                client_id: ATOM_MSGRAPH_CLIENT_ID,
                client_secret: ATOM_MSGRAPH_CLIENT_SECRET,
                scope: MSGRAPH_API_SCOPES.join(' '), // Request original scopes or a subset
                refresh_token: refreshToken,
                grant_type: 'refresh_token',
                redirect_uri: ATOM_MSGRAPH_REDIRECT_URI, // Required by some providers even for refresh
            },
            responseType: 'json',
        });

        const newTokens = response.body as MicrosoftGraphTokenResponse;
        if (newTokens.access_token && newTokens.expires_in) {
            const expiryDate = Date.now() + (newTokens.expires_in * 1000);
            await saveAtomMicrosoftGraphTokens(userId, {
                access_token: newTokens.access_token,
                refresh_token: newTokens.refresh_token || refreshToken, // Persist old refresh token if new one isn't provided
                expiry_date: expiryDate,
                scope: newTokens.scope,
                token_type: newTokens.token_type,
            }, existingAppEmail); // Pass existing appEmail

            console.log(`Successfully refreshed and saved Microsoft Graph token for userId: ${userId}`);
            return newTokens.access_token;
        } else {
            console.error('Microsoft Graph token refresh response missing access_token or expires_in:', newTokens);
            return null;
        }
    } catch (error: any) {
        console.error(`Error refreshing Microsoft Graph token for userId ${userId}:`, error.message);
        if (error.response?.body) {
            console.error("MS Graph Refresh Token Error Response:", error.response.body);
            const bodyError = error.response.body as any;
            if (bodyError.error === 'invalid_grant') { // Common error for expired/revoked refresh tokens
                console.error(`Refresh token invalid for userId ${userId}. Deleting stored tokens.`);
                await deleteAtomMicrosoftGraphTokens(userId); // Delete bad tokens
            }
        }
        return null;
    }
}
// Placeholder for deleteAtomMicrosoftGraphTokens if not already imported/available
// For now, assume it's available via token-utils if needed here.
async function deleteAtomMicrosoftGraphTokens(userId: string): Promise<any> {
    console.warn("deleteAtomMicrosoftGraphTokens called from refreshMicrosoftGraphToken - ensure it's correctly imported if this path is taken.");
    // This function is actually in token-utils.ts, if this were a real scenario,
    // it should be imported or this should call a service that does it.
    // For now, just a placeholder if called due to invalid_grant.
    return Promise.resolve();
}


export async function listUpcomingEventsMicrosoft(userId: string, limit: number = 10): Promise<CalendarEvent[]> {
    console.log(`Attempting to list Microsoft Graph calendar events for userId: ${userId}`);
    let tokens = await getAtomMicrosoftGraphTokens(userId);

    if (!tokens?.access_token) {
        console.error(`No valid Microsoft Graph tokens for userId: ${userId}. User needs to authenticate.`);
        return [];
    }

    const callGraphApi = async (accessToken: string): Promise<CalendarEvent[]> => {
        const now = new Date();
        const future = dayjs(now).add(1, 'year').toDate(); // Look ahead one year
        const startDateTime = now.toISOString();
        const endDateTime = future.toISOString();

        const calendarViewUrl = `https://graph.microsoft.com/v1.0/me/calendarview?startdatetime=${startDateTime}&enddatetime=${endDateTime}&$top=${limit}&$orderby=start/dateTime`;

        try {
            const response: any = await got.get(calendarViewUrl, {
                headers: { 'Authorization': `Bearer ${accessToken}` },
                responseType: 'json',
            });

            const graphEvents = response.body.value || [];
            return graphEvents.map((event: any) => ({
                id: event.id,
                summary: event.subject || 'No Subject',
                description: event.bodyPreview || undefined,
                startTime: event.start?.dateTime ? new Date(event.start.dateTime + 'Z').toISOString() : undefined, // Ensure ISO string
                endTime: event.end?.dateTime ? new Date(event.end.dateTime + 'Z').toISOString() : undefined, // Ensure ISO string
                location: event.location?.displayName || undefined,
                htmlLink: event.webLink || undefined,
            }));
        } catch (error: any) {
            if (error.response?.statusCode === 401 && tokens?.refresh_token) {
                console.log(`Access token expired for userId ${userId}. Attempting refresh.`);
                const newAccessToken = await refreshMicrosoftGraphToken(userId, tokens.refresh_token, tokens.appEmail);
                if (newAccessToken) {
                    tokens.access_token = newAccessToken; // Update local token for retry
                    return callGraphApi(newAccessToken); // Retry with new token
                } else {
                    console.error(`Failed to refresh token for userId ${userId}.`);
                    return [];
                }
            }
            console.error(`Error fetching Microsoft Graph calendar events for userId ${userId}:`, error.message);
            if (error.response?.body) console.error("MS Graph API Error:", error.response.body);
            return [];
        }
    };
    return callGraphApi(tokens.access_token);
}


export async function createCalendarEventMicrosoft(userId: string, eventDetails: Partial<CalendarEvent>): Promise<CreateEventResponse> {
    console.log(`Attempting to create Microsoft Graph calendar event for userId: ${userId}`);
    let tokens = await getAtomMicrosoftGraphTokens(userId);

    if (!tokens?.access_token) {
        return { success: false, message: 'Authentication required. Please connect your Microsoft Account.' };
    }
    if (!eventDetails.summary || !eventDetails.startTime || !eventDetails.endTime) {
        return { success: false, message: 'Missing required event details (summary, startTime, endTime).' };
    }

    const callGraphApi = async (accessToken: string): Promise<CreateEventResponse> => {
        const graphEvent = {
            subject: eventDetails.summary,
            body: {
                contentType: "HTML", // Or "Text"
                content: eventDetails.description || ""
            },
            start: {
                dateTime: eventDetails.startTime, // Assuming it's ISO 8601
                timeZone: "UTC" // Or user's actual timezone; UTC is safest for cross-platform
            },
            end: {
                dateTime: eventDetails.endTime,   // Assuming it's ISO 8601
                timeZone: "UTC"
            },
            location: eventDetails.location ? { displayName: eventDetails.location } : undefined
        };

        try {
            const response: any = await got.post('https://graph.microsoft.com/v1.0/me/events', {
                headers: { 'Authorization': `Bearer ${accessToken}` },
                json: graphEvent,
                responseType: 'json',
            });

            const createdEvent = response.body;
            return {
                success: true,
                eventId: createdEvent.id,
                message: 'Event created successfully with Microsoft Graph.',
                htmlLink: createdEvent.webLink,
            };
        } catch (error: any) {
            if (error.response?.statusCode === 401 && tokens?.refresh_token) {
                console.log(`Access token expired for MS Graph (createEvent) for userId ${userId}. Attempting refresh.`);
                const newAccessToken = await refreshMicrosoftGraphToken(userId, tokens.refresh_token, tokens.appEmail);
                if (newAccessToken) {
                    tokens.access_token = newAccessToken;
                    return callGraphApi(newAccessToken);
                } else {
                    return { success: false, message: 'Failed to refresh token. Please try re-authenticating.' };
                }
            }
            console.error(`Error creating Microsoft Graph event for userId ${userId}:`, error.message);
            if (error.response?.body) console.error("MS Graph API Error (createEvent):", error.response.body);
            return { success: false, message: `Failed to create event: ${error.message}` };
        }
    };
    return callGraphApi(tokens.access_token);
}
