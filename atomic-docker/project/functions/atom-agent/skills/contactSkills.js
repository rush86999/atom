import { google } from 'googleapis';
import { ATOM_GOOGLE_CALENDAR_CLIENT_ID, // Assuming similar setup for People API
ATOM_GOOGLE_CALENDAR_CLIENT_SECRET, HASURA_GRAPHQL_URL, HASURA_ADMIN_SECRET, } from '../_libs/constants';
import { executeGraphQLQuery } from '../_libs/graphqlClient';
import { getStoredUserTokens as getGoogleUserTokens } from './calendarSkills'; // Re-use for token fetching logic
import { getHubspotClient as getHubSpotApiClient } from './hubspotSkills'; // Re-use for client
const GOOGLE_PEOPLE_API_SCOPES = [
    'https://www.googleapis.com/auth/contacts.readonly',
];
// Helper to get an authenticated Google People API client
async function getGooglePeopleClient(userId) {
    if (!ATOM_GOOGLE_CALENDAR_CLIENT_ID || !ATOM_GOOGLE_CALENDAR_CLIENT_SECRET) {
        return {
            error: {
                code: 'CONFIG_ERROR',
                message: 'Google client ID or secret not configured.',
            },
        };
    }
    // We need to ensure getGoogleUserTokens can fetch tokens for People API scopes.
    // This might require a modification to getGoogleUserTokens or a new function
    // if service_name in DB distinguishes token types. For now, assume it can work.
    const tokenResponse = await getGoogleUserTokens(userId); // Pass 'google_people' if service_name specific
    if (!tokenResponse.ok || !tokenResponse.data) {
        return {
            error: tokenResponse.error || {
                code: 'AUTH_REQUIRED',
                message: 'Google authentication tokens are missing or invalid for People API.',
            },
        };
    }
    const currentTokens = tokenResponse.data;
    if (!currentTokens.access_token) {
        return {
            error: {
                code: 'AUTH_TOKEN_INVALID',
                message: 'Fetched Google token is invalid (missing access_token).',
            },
        };
    }
    const oauth2Client = new google.auth.OAuth2(ATOM_GOOGLE_CALENDAR_CLIENT_ID, ATOM_GOOGLE_CALENDAR_CLIENT_SECRET);
    oauth2Client.setCredentials(currentTokens);
    // TODO: Add token refresh listener similar to calendarSkills if not already handled globally by getGoogleUserTokens
    // oauth2Client.on('tokens', ...);
    return { client: google.people({ version: 'v1', auth: oauth2Client }) };
}
async function _findAtomUser(identifier) {
    console.log(`[_findAtomUser] Searching for Atom user with identifier: ${identifier}`);
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        console.error('[_findAtomUser] GraphQL client not configured.');
        return null; // Or throw an error
    }
    // Determine if identifier is an email or potentially a name
    const isEmail = identifier.includes('@');
    let query;
    let variables;
    if (isEmail) {
        query = `
      query GetUserByEmail($email: String!) {
        users(where: {email: {_eq: $email}}, limit: 1) {
          id
          name
          email
        }
      }
    `;
        variables = { email: identifier };
    }
    else {
        // Assuming 'name' field exists and is queryable. This might need to be split into first/last name.
        query = `
      query GetUserByName($name: String!) {
        users(where: {name: {_ilike: $name}}, limit: 1) { # Using ilike for case-insensitive partial match
          id
          name
          email
        }
      }
    `;
        variables = { name: `%${identifier}%` };
    }
    try {
        const response = await executeGraphQLQuery(query, variables, isEmail ? 'GetUserByEmail' : 'GetUserByName'
        // No userId needed here, as we're searching globally for users (admin operation)
        );
        if (response && response.users && response.users.length > 0) {
            const user = response.users[0];
            console.log(`[_findAtomUser] Found Atom user:`, user);
            return {
                email: user.email,
                name: user.name || identifier,
                userId: user.id,
                source: 'atom_user',
                status: 'found',
            };
        }
        console.log(`[_findAtomUser] No Atom user found for identifier: ${identifier}`);
        return null;
    }
    catch (error) {
        console.error(`[_findAtomUser] Error searching for Atom user ${identifier}:`, error);
        return null; // Or return an error status within ResolvedAttendee
    }
}
async function _findGoogleContact(nameOrEmail, requesterId) {
    console.log(`[_findGoogleContact] Searching Google Contacts for: "${nameOrEmail}" for requester ${requesterId}`);
    const { client: peopleClient, error: clientError } = await getGooglePeopleClient(requesterId);
    if (clientError || !peopleClient) {
        console.error(`[_findGoogleContact] Error getting People API client:`, clientError);
        return {
            email: nameOrEmail,
            source: 'google_contact',
            status: 'error_resolving',
            errorMessage: clientError?.message || 'Failed to get People API client',
        };
    }
    try {
        const response = await peopleClient.people.connections.list({
            resourceName: 'people/me',
            personFields: 'names,emailAddresses',
            query: nameOrEmail, // Use the query parameter for searching
            pageSize: 5, // Limit results
        });
        const connections = response.data.connections;
        if (connections && connections.length > 0) {
            // Prioritize exact matches or make a best guess. For simplicity, take the first one.
            const contact = connections[0];
            const primaryName = contact.names?.find((n) => n.metadata?.primary)?.displayName ||
                contact.names?.[0]?.displayName;
            const primaryEmail = contact.emailAddresses?.find((e) => e.metadata?.primary)?.value ||
                contact.emailAddresses?.[0]?.value;
            if (primaryEmail) {
                console.log(`[_findGoogleContact] Found Google Contact: Name: ${primaryName}, Email: ${primaryEmail}`);
                // Check if this Google Contact email also corresponds to an Atom user
                const atomUserMatch = await _findAtomUser(primaryEmail);
                if (atomUserMatch && atomUserMatch.userId) {
                    return {
                        ...atomUserMatch,
                        source: 'google_contact',
                        name: primaryName || atomUserMatch.name,
                    };
                }
                return {
                    email: primaryEmail,
                    name: primaryName || nameOrEmail,
                    source: 'google_contact',
                    status: 'found',
                };
            }
        }
        console.log(`[_findGoogleContact] No Google Contact found for: "${nameOrEmail}"`);
        return null;
    }
    catch (error) {
        console.error(`[_findGoogleContact] Error searching Google Contacts for ${nameOrEmail}:`, error);
        return {
            email: nameOrEmail,
            source: 'google_contact',
            status: 'error_resolving',
            errorMessage: error.message,
        };
    }
}
async function _findHubspotContact(nameOrEmail, requesterId) {
    console.log(`[_findHubspotContact] Searching HubSpot for: "${nameOrEmail}" for requester ${requesterId}`);
    const hubspotClient = getHubSpotApiClient(); // This is synchronous
    if (!hubspotClient) {
        return {
            email: nameOrEmail,
            source: 'hubspot_contact',
            status: 'error_resolving',
            errorMessage: 'HubSpot client not configured.',
        };
    }
    try {
        const searchRequest = {
            query: nameOrEmail, // General search query
            properties: ['email', 'firstname', 'lastname', 'hs_object_id'],
            limit: 5,
            filterGroups: [
                {
                    filters: [
                        // Attempt to search by email first if it looks like one
                        nameOrEmail.includes('@')
                            ? { propertyName: 'email', operator: 'EQ', value: nameOrEmail }
                            : // Otherwise, try to search by name parts (this is simplified)
                                {
                                    propertyName: 'firstname',
                                    operator: 'CONTAINS_TOKEN',
                                    value: nameOrEmail.split(' ')[0],
                                },
                        // More sophisticated name searching would involve multiple filters or better query construction
                    ],
                },
            ],
        };
        const response = await hubspotClient.crm.contacts.searchApi.doSearch(searchRequest);
        if (response.results && response.results.length > 0) {
            const contact = response.results[0]; // Take the first result for simplicity
            const contactEmail = contact.properties.email;
            const contactName = `${contact.properties.firstname || ''} ${contact.properties.lastname || ''}`.trim();
            if (contactEmail) {
                console.log(`[_findHubspotContact] Found HubSpot Contact: Name: ${contactName}, Email: ${contactEmail}`);
                // Check if this HubSpot Contact email also corresponds to an Atom user
                const atomUserMatch = await _findAtomUser(contactEmail);
                if (atomUserMatch && atomUserMatch.userId) {
                    return {
                        ...atomUserMatch,
                        source: 'hubspot_contact',
                        name: contactName || atomUserMatch.name,
                    };
                }
                return {
                    email: contactEmail,
                    name: contactName || nameOrEmail,
                    source: 'hubspot_contact',
                    status: 'found',
                };
            }
        }
        console.log(`[_findHubspotContact] No HubSpot contact found for: "${nameOrEmail}"`);
        return null;
    }
    catch (error) {
        console.error(`[_findHubspotContact] Error searching HubSpot contacts for ${nameOrEmail}:`, error);
        return {
            email: nameOrEmail,
            source: 'hubspot_contact',
            status: 'error_resolving',
            errorMessage: error.message,
        };
    }
}
export async function resolveAttendees(attendeeStrings, requesterId) {
    console.log(`[contactSkills] Resolving attendees: ${attendeeStrings.join(', ')} for requester ${requesterId}`);
    const resolvedAttendees = [];
    for (const attendeeStr of attendeeStrings) {
        let resolved = null;
        if (attendeeStr.includes('@')) {
            // Simple check for email
            resolved = await _findAtomUser(attendeeStr); // Check if it's an Atom user first
            if (resolved) {
                resolved.source = 'atom_user'; // Correct source if found as Atom user by email
            }
            else {
                resolved = {
                    email: attendeeStr,
                    source: 'email_direct',
                    status: 'found',
                    name: attendeeStr.split('@')[0],
                }; // Assume it's a valid external email
            }
        }
        else {
            // It's likely a name, try resolving through different sources
            resolved = await _findAtomUser(attendeeStr);
            if (!resolved) {
                resolved = await _findGoogleContact(attendeeStr, requesterId);
            }
            if (!resolved) {
                resolved = await _findHubspotContact(attendeeStr, requesterId);
            }
        }
        if (resolved) {
            resolvedAttendees.push(resolved);
        }
        else {
            // Could not resolve by name, and it wasn't an email
            console.warn(`[contactSkills] Could not resolve attendee: "${attendeeStr}"`);
            resolvedAttendees.push({
                email: attendeeStr, // Keep original string if cannot resolve to actual email
                name: attendeeStr,
                source: 'unresolved',
                status: 'not_found',
            });
        }
    }
    // Filter out any nulls just in case, though logic above tries to push a placeholder
    const finalAttendees = resolvedAttendees.filter(Boolean);
    console.log('[contactSkills] Final resolved attendees:', finalAttendees);
    return { ok: true, data: finalAttendees };
}
// Placeholder for fetching user availability (work times and calendar events)
// This would typically live in schedulingSkills.ts or calendarSkills.ts
// and involve DB queries for work preferences and calendar API calls.
// For now, this is a conceptual placeholder within this file.
/*
import { UserAvailability, UserWorkTime, CalendarEvent } from '../types';
import { listUpcomingEvents } from './calendarSkills';

async function _fetchUserWorkTimes(userId: string): Promise<UserWorkTime[]> {
    // Placeholder: Query your database for user_work_preferences by userId
    console.log(`[_fetchUserWorkTimes] Fetching work times for user ${userId} (Placeholder)`);
    // Example:
    // const query = `query GetUserWorkTimes($userId: String!) { user_work_preferences(where: {user_id: {_eq: $userId}}) { day_of_week start_time end_time } }`;
    // const response = await executeGraphQLQuery(query, { userId }, 'GetUserWorkTimes', userId);
    // return response.user_work_preferences.map(pref => ({ dayOfWeek: pref.day_of_week, startTime: pref.start_time, endTime: pref.end_time }));
    return [ // Dummy data
        { dayOfWeek: 'MONDAY', startTime: '09:00', endTime: '17:00' },
        { dayOfWeek: 'TUESDAY', startTime: '09:00', endTime: '17:00' },
        { dayOfWeek: 'WEDNESDAY', startTime: '09:00', endTime: '17:00' },
        { dayOfWeek: 'THURSDAY', startTime: '09:00', endTime: '17:00' },
        { dayOfWeek: 'FRIDAY', startTime: '09:00', endTime: '17:00' },
    ];
}

export async function getUserAvailability(
    userIds: string[],
    windowStart: string, // ISO string
    windowEnd: string   // ISO string
): Promise<ContactSkillResponse<UserAvailability[]>> {
    console.log(`[contactSkills] Getting availability for users: ${userIds.join(', ')} within window: ${windowStart} to ${windowEnd}`);
    const allUsersAvailability: UserAvailability[] = [];

    for (const userId of userIds) {
        try {
            const workTimes = await _fetchUserWorkTimes(userId);

            // Fetch calendar events for this user within the window
            // Note: listUpcomingEvents fetches from 'now'. We need a version that takes a time window.
            // For now, this is a conceptual adaptation.
            // A more precise listUpcomingEventsInWindow(userId, timeMin, timeMax, limit) would be needed.
            const eventsResponse = await listUpcomingEvents(userId, 50); // Fetch a decent number
            let relevantEvents: CalendarEvent[] = [];
            if (eventsResponse.ok && eventsResponse.data) {
                 relevantEvents = eventsResponse.data.filter(event => {
                    const eventStart = new Date(event.startTime).getTime();
                    const eventEnd = new Date(event.endTime).getTime();
                    const windowStartTime = new Date(windowStart).getTime();
                    const windowEndTime = new Date(windowEnd).getTime();
                    // Check for overlap
                    return Math.max(eventStart, windowStartTime) < Math.min(eventEnd, windowEndTime);
                });
            } else {
                console.warn(`[contactSkills] Could not fetch calendar events for user ${userId}: ${eventsResponse.error?.message}`);
            }

            allUsersAvailability.push({
                userId,
                workTimes,
                calendarEvents: relevantEvents,
            });
        } catch (error: any) {
            console.error(`[contactSkills] Error getting availability for user ${userId}: ${error.message}`);
            // Optionally add error state for this user or skip them
        }
    }
    return { ok: true, data: allUsersAvailability };
}
*/
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY29udGFjdFNraWxscy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImNvbnRhY3RTa2lsbHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUFFLE1BQU0sRUFBYSxNQUFNLFlBQVksQ0FBQztBQUUvQyxPQUFPLEVBQ0wsOEJBQThCLEVBQUUsd0NBQXdDO0FBQ3hFLGtDQUFrQyxFQUVsQyxrQkFBa0IsRUFDbEIsbUJBQW1CLEdBQ3BCLE1BQU0sb0JBQW9CLENBQUM7QUFDNUIsT0FBTyxFQUFFLG1CQUFtQixFQUFFLE1BQU0sd0JBQXdCLENBQUM7QUFDN0QsT0FBTyxFQUFFLG1CQUFtQixJQUFJLG1CQUFtQixFQUFFLE1BQU0sa0JBQWtCLENBQUMsQ0FBQyxrQ0FBa0M7QUFDakgsT0FBTyxFQUFFLGdCQUFnQixJQUFJLG1CQUFtQixFQUFFLE1BQU0saUJBQWlCLENBQUMsQ0FBQyxvQkFBb0I7QUFTL0YsTUFBTSx3QkFBd0IsR0FBRztJQUMvQixtREFBbUQ7Q0FDcEQsQ0FBQztBQUVGLDBEQUEwRDtBQUMxRCxLQUFLLFVBQVUscUJBQXFCLENBQ2xDLE1BQWM7SUFFZCxJQUFJLENBQUMsOEJBQThCLElBQUksQ0FBQyxrQ0FBa0MsRUFBRSxDQUFDO1FBQzNFLE9BQU87WUFDTCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLGNBQWM7Z0JBQ3BCLE9BQU8sRUFBRSw0Q0FBNEM7YUFDdEQ7U0FDRixDQUFDO0lBQ0osQ0FBQztJQUVELGdGQUFnRjtJQUNoRiw2RUFBNkU7SUFDN0UsZ0ZBQWdGO0lBQ2hGLE1BQU0sYUFBYSxHQUFHLE1BQU0sbUJBQW1CLENBQUMsTUFBTSxDQUFDLENBQUMsQ0FBQyxnREFBZ0Q7SUFDekcsSUFBSSxDQUFDLGFBQWEsQ0FBQyxFQUFFLElBQUksQ0FBQyxhQUFhLENBQUMsSUFBSSxFQUFFLENBQUM7UUFDN0MsT0FBTztZQUNMLEtBQUssRUFBRSxhQUFhLENBQUMsS0FBSyxJQUFJO2dCQUM1QixJQUFJLEVBQUUs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RUFBOEU7QUFDOUUsd0VBQXdFO0FBQ3hFLHNFQUFzRTtBQUN0RSw4REFBOEQ7QUFDOUQ7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztFQStERSIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdvb2dsZSwgcGVvcGxlX3YxIH0gZnJvbSAnZ29vZ2xlYXBpcyc7XG5pbXBvcnQgeyBDbGllbnQgYXMgSHViU3BvdENsaWVudCB9IGZyb20gJ0BodWJzcG90L2FwaS1jbGllbnQnO1xuaW1wb3J0IHtcbiAgQVRPTV9HT09HTEVfQ0FMRU5EQVJfQ0xJRU5UX0lELCAvLyBBc3N1bWluZyBzaW1pbGFyIHNldHVwIGZvciBQZW9wbGUgQVBJXG4gIEFUT01fR09PR0xFX0NBTEVOREFSX0NMSUVOVF9TRUNSRVQsIC8vIEFzc3VtaW5nIHNpbWlsYXIgc2V0dXAgZm9yIFBlb3BsZSBBUElcbiAgQVRPTV9IVUJTUE9UX0FQSV9LRVksXG4gIEhBU1VSQV9HUkFQSFFMX1VSTCxcbiAgSEFTVVJBX0FETUlOX1NFQ1JFVCxcbn0gZnJvbSAnLi4vX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7IGV4ZWN1dGVHcmFwaFFMUXVlcnkgfSBmcm9tICcuLi9fbGlicy9ncmFwaHFsQ2xpZW50JztcbmltcG9ydCB7IGdldFN0b3JlZFVzZXJUb2tlbnMgYXMgZ2V0R29vZ2xlVXNlclRva2VucyB9IGZyb20gJy4vY2FsZW5kYXJTa2lsbHMnOyAvLyBSZS11c2UgZm9yIHRva2VuIGZldGNoaW5nIGxvZ2ljXG5pbXBvcnQgeyBnZXRIdWJzcG90Q2xpZW50IGFzIGdldEh1YlNwb3RBcGlDbGllbnQgfSBmcm9tICcuL2h1YnNwb3RTa2lsbHMnOyAvLyBSZS11c2UgZm9yIGNsaWVudFxuaW1wb3J0IHtcbiAgUmVzb2x2ZWRBdHRlbmRlZSxcbiAgQ29udGFjdFNraWxsUmVzcG9uc2UsXG4gIFNraWxsRXJyb3IsXG4gIE9BdXRoMlRva2VuLCAvLyBGcm9tIHR5cGVzLnRzXG4gIEh1YlNwb3RDb250YWN0LCAvLyBGcm9tIHR5cGVzLnRzXG59IGZyb20gJy4uL3R5cGVzJztcblxuY29uc3QgR09PR0xFX1BFT1BMRV9BUElfU0NPUEVTID0gW1xuICAnaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vYXV0aC9jb250YWN0cy5yZWFkb25seScsXG5dO1xuXG4vLyBIZWxwZXIgdG8gZ2V0IGFuIGF1dGhlbnRpY2F0ZWQgR29vZ2xlIFBlb3BsZSBBUEkgY2xpZW50XG5hc3luYyBmdW5jdGlvbiBnZXRHb29nbGVQZW9wbGVDbGllbnQoXG4gIHVzZXJJZDogc3RyaW5nXG4pOiBQcm9taXNlPHsgY2xpZW50PzogcGVvcGxlX3YxLlBlb3BsZTsgZXJyb3I/OiBTa2lsbEVycm9yIH0+IHtcbiAgaWYgKCFBVE9NX0dPT0dMRV9DQUxFTkRBUl9DTElFTlRfSUQgfHwgIUFUT01fR09PR0xFX0NBTEVOREFSX0NMSUVOVF9TRUNSRVQpIHtcbiAgICByZXR1cm4ge1xuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0NPTkZJR19FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdHb29nbGUgY2xpZW50IElEIG9yIHNlY3JldCBub3QgY29uZmlndXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgLy8gV2UgbmVlZCB0byBlbnN1cmUgZ2V0R29vZ2xlVXNlclRva2VucyBjYW4gZmV0Y2ggdG9rZW5zIGZvciBQZW9wbGUgQVBJIHNjb3Blcy5cbiAgLy8gVGhpcyBtaWdodCByZXF1aXJlIGEgbW9kaWZpY2F0aW9uIHRvIGdldEdvb2dsZVVzZXJUb2tlbnMgb3IgYSBuZXcgZnVuY3Rpb25cbiAgLy8gaWYgc2VydmljZV9uYW1lIGluIERCIGRpc3Rpbmd1aXNoZXMgdG9rZW4gdHlwZXMuIEZvciBub3csIGFzc3VtZSBpdCBjYW4gd29yay5cbiAgY29uc3QgdG9rZW5SZXNwb25zZSA9IGF3YWl0IGdldEdvb2dsZVVzZXJUb2tlbnModXNlcklkKTsgLy8gUGFzcyAnZ29vZ2xlX3Blb3BsZScgaWYgc2VydmljZV9uYW1lIHNwZWNpZmljXG4gIGlmICghdG9rZW5SZXNwb25zZS5vayB8fCAhdG9rZW5SZXNwb25zZS5kYXRhKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIGVycm9yOiB0b2tlblJlc3BvbnNlLmVycm9yIHx8IHtcbiAgICAgICAgY29kZTogJ0FVVEhfUkVRVUlSRUQnLFxuICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICdHb29nbGUgYXV0aGVudGljYXRpb24gdG9rZW5zIGFyZSBtaXNzaW5nIG9yIGludmFsaWQgZm9yIFBlb3BsZSBBUEkuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICBjb25zdCBjdXJyZW50VG9rZW5zID0gdG9rZW5SZXNwb25zZS5kYXRhO1xuXG4gIGlmICghY3VycmVudFRva2Vucy5hY2Nlc3NfdG9rZW4pIHtcbiAgICByZXR1cm4ge1xuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0FVVEhfVE9LRU5fSU5WQUxJRCcsXG4gICAgICAgIG1lc3NhZ2U6ICdGZXRjaGVkIEdvb2dsZSB0b2tlbiBpcyBpbnZhbGlkIChtaXNzaW5nIGFjY2Vzc190b2tlbikuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIGNvbnN0IG9hdXRoMkNsaWVudCA9IG5ldyBnb29nbGUuYXV0aC5PQXV0aDIoXG4gICAgQVRPTV9HT09HTEVfQ0FMRU5EQVJfQ0xJRU5UX0lELFxuICAgIEFUT01fR09PR0xFX0NBTEVOREFSX0NMSUVOVF9TRUNSRVRcbiAgKTtcbiAgb2F1dGgyQ2xpZW50LnNldENyZWRlbnRpYWxzKGN1cnJlbnRUb2tlbnMpO1xuXG4gIC8vIFRPRE86IEFkZCB0b2tlbiByZWZyZXNoIGxpc3RlbmVyIHNpbWlsYXIgdG8gY2FsZW5kYXJTa2lsbHMgaWYgbm90IGFscmVhZHkgaGFuZGxlZCBnbG9iYWxseSBieSBnZXRHb29nbGVVc2VyVG9rZW5zXG4gIC8vIG9hdXRoMkNsaWVudC5vbigndG9rZW5zJywgLi4uKTtcblxuICByZXR1cm4geyBjbGllbnQ6IGdvb2dsZS5wZW9wbGUoeyB2ZXJzaW9uOiAndjEnLCBhdXRoOiBvYXV0aDJDbGllbnQgfSkgfTtcbn1cblxuYXN5bmMgZnVuY3Rpb24gX2ZpbmRBdG9tVXNlcihcbiAgaWRlbnRpZmllcjogc3RyaW5nXG4pOiBQcm9taXNlPFJlc29sdmVkQXR0ZW5kZWUgfCBudWxsPiB7XG4gIGNvbnNvbGUubG9nKFxuICAgIGBbX2ZpbmRBdG9tVXNlcl0gU2VhcmNoaW5nIGZvciBBdG9tIHVzZXIgd2l0aCBpZGVudGlmaWVyOiAke2lkZW50aWZpZXJ9YFxuICApO1xuICBpZiAoIUhBU1VSQV9HUkFQSFFMX1VSTCB8fCAhSEFTVVJBX0FETUlOX1NFQ1JFVCkge1xuICAgIGNvbnNvbGUuZXJyb3IoJ1tfZmluZEF0b21Vc2VyXSBHcmFwaFFMIGNsaWVudCBub3QgY29uZmlndXJlZC4nKTtcbiAgICByZXR1cm4gbnVsbDsgLy8gT3IgdGhyb3cgYW4gZXJyb3JcbiAgfVxuXG4gIC8vIERldGVybWluZSBpZiBpZGVudGlmaWVyIGlzIGFuIGVtYWlsIG9yIHBvdGVudGlhbGx5IGEgbmFtZVxuICBjb25zdCBpc0VtYWlsID0gaWRlbnRpZmllci5pbmNsdWRlcygnQCcpO1xuICBsZXQgcXVlcnk7XG4gIGxldCB2YXJpYWJsZXM7XG5cbiAgaWYgKGlzRW1haWwpIHtcbiAgICBxdWVyeSA9IGBcbiAgICAgIHF1ZXJ5IEdldFVzZXJCeUVtYWlsKCRlbWFpbDogU3RyaW5nISkge1xuICAgICAgICB1c2Vycyh3aGVyZToge2VtYWlsOiB7X2VxOiAkZW1haWx9fSwgbGltaXQ6IDEpIHtcbiAgICAgICAgICBpZFxuICAgICAgICAgIG5hbWVcbiAgICAgICAgICBlbWFpbFxuICAgICAgICB9XG4gICAgICB9XG4gICAgYDtcbiAgICB2YXJpYWJsZXMgPSB7IGVtYWlsOiBpZGVudGlmaWVyIH07XG4gIH0gZWxzZSB7XG4gICAgLy8gQXNzdW1pbmcgJ25hbWUnIGZpZWxkIGV4aXN0cyBhbmQgaXMgcXVlcnlhYmxlLiBUaGlzIG1pZ2h0IG5lZWQgdG8gYmUgc3BsaXQgaW50byBmaXJzdC9sYXN0IG5hbWUuXG4gICAgcXVlcnkgPSBgXG4gICAgICBxdWVyeSBHZXRVc2VyQnlOYW1lKCRuYW1lOiBTdHJpbmchKSB7XG4gICAgICAgIHVzZXJzKHdoZXJlOiB7bmFtZToge19pbGlrZTogJG5hbWV9fSwgbGltaXQ6IDEpIHsgIyBVc2luZyBpbGlrZSBmb3IgY2FzZS1pbnNlbnNpdGl2ZSBwYXJ0aWFsIG1hdGNoXG4gICAgICAgICAgaWRcbiAgICAgICAgICBuYW1lXG4gICAgICAgICAgZW1haWxcbiAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG4gICAgdmFyaWFibGVzID0geyBuYW1lOiBgJSR7aWRlbnRpZmllcn0lYCB9O1xuICB9XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGV4ZWN1dGVHcmFwaFFMUXVlcnk8e1xuICAgICAgdXNlcnM6IEFycmF5PHsgaWQ6IHN0cmluZzsgbmFtZT86IHN0cmluZzsgZW1haWw6IHN0cmluZyB9PjtcbiAgICB9PihcbiAgICAgIHF1ZXJ5LFxuICAgICAgdmFyaWFibGVzLFxuICAgICAgaXNFbWFpbCA/ICdHZXRVc2VyQnlFbWFpbCcgOiAnR2V0VXNlckJ5TmFtZSdcbiAgICAgIC8vIE5vIHVzZXJJZCBuZWVkZWQgaGVyZSwgYXMgd2UncmUgc2VhcmNoaW5nIGdsb2JhbGx5IGZvciB1c2VycyAoYWRtaW4gb3BlcmF0aW9uKVxuICAgICk7XG5cbiAgICBpZiAocmVzcG9uc2UgJiYgcmVzcG9uc2UudXNlcnMgJiYgcmVzcG9uc2UudXNlcnMubGVuZ3RoID4gMCkge1xuICAgICAgY29uc3QgdXNlciA9IHJlc3BvbnNlLnVzZXJzWzBdO1xuICAgICAgY29uc29sZS5sb2coYFtfZmluZEF0b21Vc2VyXSBGb3VuZCBBdG9tIHVzZXI6YCwgdXNlcik7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBlbWFpbDogdXNlci5lbWFpbCxcbiAgICAgICAgbmFtZTogdXNlci5uYW1lIHx8IGlkZW50aWZpZXIsXG4gICAgICAgIHVzZXJJZDogdXNlci5pZCxcbiAgICAgICAgc291cmNlOiAnYXRvbV91c2VyJyxcbiAgICAgICAgc3RhdHVzOiAnZm91bmQnLFxuICAgICAgfTtcbiAgICB9XG4gICAgY29uc29sZS5sb2coXG4gICAgICBgW19maW5kQXRvbVVzZXJdIE5vIEF0b20gdXNlciBmb3VuZCBmb3IgaWRlbnRpZmllcjogJHtpZGVudGlmaWVyfWBcbiAgICApO1xuICAgIHJldHVybiBudWxsO1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcihcbiAgICAgIGBbX2ZpbmRBdG9tVXNlcl0gRXJyb3Igc2VhcmNoaW5nIGZvciBBdG9tIHVzZXIgJHtpZGVudGlmaWVyfTpgLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIHJldHVybiBudWxsOyAvLyBPciByZXR1cm4gYW4gZXJyb3Igc3RhdHVzIHdpdGhpbiBSZXNvbHZlZEF0dGVuZGVlXG4gIH1cbn1cblxuYXN5bmMgZnVuY3Rpb24gX2ZpbmRHb29nbGVDb250YWN0KFxuICBuYW1lT3JFbWFpbDogc3RyaW5nLFxuICByZXF1ZXN0ZXJJZDogc3RyaW5nXG4pOiBQcm9taXNlPFJlc29sdmVkQXR0ZW5kZWUgfCBudWxsPiB7XG4gIGNvbnNvbGUubG9nKFxuICAgIGBbX2ZpbmRHb29nbGVDb250YWN0XSBTZWFyY2hpbmcgR29vZ2xlIENvbnRhY3RzIGZvcjogXCIke25hbWVPckVtYWlsfVwiIGZvciByZXF1ZXN0ZXIgJHtyZXF1ZXN0ZXJJZH1gXG4gICk7XG4gIGNvbnN0IHsgY2xpZW50OiBwZW9wbGVDbGllbnQsIGVycm9yOiBjbGllbnRFcnJvciB9ID1cbiAgICBhd2FpdCBnZXRHb29nbGVQZW9wbGVDbGllbnQocmVxdWVzdGVySWQpO1xuICBpZiAoY2xpZW50RXJyb3IgfHwgIXBlb3BsZUNsaWVudCkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICBgW19maW5kR29vZ2xlQ29udGFjdF0gRXJyb3IgZ2V0dGluZyBQZW9wbGUgQVBJIGNsaWVudDpgLFxuICAgICAgY2xpZW50RXJyb3JcbiAgICApO1xuICAgIHJldHVybiB7XG4gICAgICBlbWFpbDogbmFtZU9yRW1haWwsXG4gICAgICBzb3VyY2U6ICdnb29nbGVfY29udGFjdCcsXG4gICAgICBzdGF0dXM6ICdlcnJvcl9yZXNvbHZpbmcnLFxuICAgICAgZXJyb3JNZXNzYWdlOiBjbGllbnRFcnJvcj8ubWVzc2FnZSB8fCAnRmFpbGVkIHRvIGdldCBQZW9wbGUgQVBJIGNsaWVudCcsXG4gICAgfSBhcyBSZXNvbHZlZEF0dGVuZGVlO1xuICB9XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IHBlb3BsZUNsaWVudC5wZW9wbGUuY29ubmVjdGlvbnMubGlzdCh7XG4gICAgICByZXNvdXJjZU5hbWU6ICdwZW9wbGUvbWUnLFxuICAgICAgcGVyc29uRmllbGRzOiAnbmFtZXMsZW1haWxBZGRyZXNzZXMnLFxuICAgICAgcXVlcnk6IG5hbWVPckVtYWlsLCAvLyBVc2UgdGhlIHF1ZXJ5IHBhcmFtZXRlciBmb3Igc2VhcmNoaW5nXG4gICAgICBwYWdlU2l6ZTogNSwgLy8gTGltaXQgcmVzdWx0c1xuICAgIH0pO1xuXG4gICAgY29uc3QgY29ubmVjdGlvbnMgPSByZXNwb25zZS5kYXRhLmNvbm5lY3Rpb25zO1xuICAgIGlmIChjb25uZWN0aW9ucyAmJiBjb25uZWN0aW9ucy5sZW5ndGggPiAwKSB7XG4gICAgICAvLyBQcmlvcml0aXplIGV4YWN0IG1hdGNoZXMgb3IgbWFrZSBhIGJlc3QgZ3Vlc3MuIEZvciBzaW1wbGljaXR5LCB0YWtlIHRoZSBmaXJzdCBvbmUuXG4gICAgICBjb25zdCBjb250YWN0ID0gY29ubmVjdGlvbnNbMF07XG4gICAgICBjb25zdCBwcmltYXJ5TmFtZSA9XG4gICAgICAgIGNvbnRhY3QubmFtZXM/LmZpbmQoKG4pID0+IG4ubWV0YWRhdGE/LnByaW1hcnkpPy5kaXNwbGF5TmFtZSB8fFxuICAgICAgICBjb250YWN0Lm5hbWVzPy5bMF0/LmRpc3BsYXlOYW1lO1xuICAgICAgY29uc3QgcHJpbWFyeUVtYWlsID1cbiAgICAgICAgY29udGFjdC5lbWFpbEFkZHJlc3Nlcz8uZmluZCgoZSkgPT4gZS5tZXRhZGF0YT8ucHJpbWFyeSk/LnZhbHVlIHx8XG4gICAgICAgIGNvbnRhY3QuZW1haWxBZGRyZXNzZXM/LlswXT8udmFsdWU7XG5cbiAgICAgIGlmIChwcmltYXJ5RW1haWwpIHtcbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgYFtfZmluZEdvb2dsZUNvbnRhY3RdIEZvdW5kIEdvb2dsZSBDb250YWN0OiBOYW1lOiAke3ByaW1hcnlOYW1lfSwgRW1haWw6ICR7cHJpbWFyeUVtYWlsfWBcbiAgICAgICAgKTtcbiAgICAgICAgLy8gQ2hlY2sgaWYgdGhpcyBHb29nbGUgQ29udGFjdCBlbWFpbCBhbHNvIGNvcnJlc3BvbmRzIHRvIGFuIEF0b20gdXNlclxuICAgICAgICBjb25zdCBhdG9tVXNlck1hdGNoID0gYXdhaXQgX2ZpbmRBdG9tVXNlcihwcmltYXJ5RW1haWwpO1xuICAgICAgICBpZiAoYXRvbVVzZXJNYXRjaCAmJiBhdG9tVXNlck1hdGNoLnVzZXJJZCkge1xuICAgICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICAuLi5hdG9tVXNlck1hdGNoLFxuICAgICAgICAgICAgc291cmNlOiAnZ29vZ2xlX2NvbnRhY3QnLFxuICAgICAgICAgICAgbmFtZTogcHJpbWFyeU5hbWUgfHwgYXRvbVVzZXJNYXRjaC5uYW1lLFxuICAgICAgICAgIH07XG4gICAgICAgIH1cbiAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICBlbWFpbDogcHJpbWFyeUVtYWlsLFxuICAgICAgICAgIG5hbWU6IHByaW1hcnlOYW1lIHx8IG5hbWVPckVtYWlsLFxuICAgICAgICAgIHNvdXJjZTogJ2dvb2dsZV9jb250YWN0JyxcbiAgICAgICAgICBzdGF0dXM6ICdmb3VuZCcsXG4gICAgICAgIH07XG4gICAgICB9XG4gICAgfVxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYFtfZmluZEdvb2dsZUNvbnRhY3RdIE5vIEdvb2dsZSBDb250YWN0IGZvdW5kIGZvcjogXCIke25hbWVPckVtYWlsfVwiYFxuICAgICk7XG4gICAgcmV0dXJuIG51bGw7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgYFtfZmluZEdvb2dsZUNvbnRhY3RdIEVycm9yIHNlYXJjaGluZyBHb29nbGUgQ29udGFjdHMgZm9yICR7bmFtZU9yRW1haWx9OmAsXG4gICAgICBlcnJvclxuICAgICk7XG4gICAgcmV0dXJuIHtcbiAgICAgIGVtYWlsOiBuYW1lT3JFbWFpbCxcbiAgICAgIHNvdXJjZTogJ2dvb2dsZV9jb250YWN0JyxcbiAgICAgIHN0YXR1czogJ2Vycm9yX3Jlc29sdmluZycsXG4gICAgICBlcnJvck1lc3NhZ2U6IGVycm9yLm1lc3NhZ2UsXG4gICAgfSBhcyBSZXNvbHZlZEF0dGVuZGVlO1xuICB9XG59XG5cbmFzeW5jIGZ1bmN0aW9uIF9maW5kSHVic3BvdENvbnRhY3QoXG4gIG5hbWVPckVtYWlsOiBzdHJpbmcsXG4gIHJlcXVlc3RlcklkOiBzdHJpbmdcbik6IFByb21pc2U8UmVzb2x2ZWRBdHRlbmRlZSB8IG51bGw+IHtcbiAgY29uc29sZS5sb2coXG4gICAgYFtfZmluZEh1YnNwb3RDb250YWN0XSBTZWFyY2hpbmcgSHViU3BvdCBmb3I6IFwiJHtuYW1lT3JFbWFpbH1cIiBmb3IgcmVxdWVzdGVyICR7cmVxdWVzdGVySWR9YFxuICApO1xuICBjb25zdCBodWJzcG90Q2xpZW50ID0gZ2V0SHViU3BvdEFwaUNsaWVudCgpOyAvLyBUaGlzIGlzIHN5bmNocm9ub3VzXG4gIGlmICghaHVic3BvdENsaWVudCkge1xuICAgIHJldHVybiB7XG4gICAgICBlbWFpbDogbmFtZU9yRW1haWwsXG4gICAgICBzb3VyY2U6ICdodWJzcG90X2NvbnRhY3QnLFxuICAgICAgc3RhdHVzOiAnZXJyb3JfcmVzb2x2aW5nJyxcbiAgICAgIGVycm9yTWVzc2FnZTogJ0h1YlNwb3QgY2xpZW50IG5vdCBjb25maWd1cmVkLicsXG4gICAgfSBhcyBSZXNvbHZlZEF0dGVuZGVlO1xuICB9XG5cbiAgdHJ5IHtcbiAgICBjb25zdCBzZWFyY2hSZXF1ZXN0ID0ge1xuICAgICAgcXVlcnk6IG5hbWVPckVtYWlsLCAvLyBHZW5lcmFsIHNlYXJjaCBxdWVyeVxuICAgICAgcHJvcGVydGllczogWydlbWFpbCcsICdmaXJzdG5hbWUnLCAnbGFzdG5hbWUnLCAnaHNfb2JqZWN0X2lkJ10sXG4gICAgICBsaW1pdDogNSxcbiAgICAgIGZpbHRlckdyb3VwczogW1xuICAgICAgICB7XG4gICAgICAgICAgZmlsdGVyczogW1xuICAgICAgICAgICAgLy8gQXR0ZW1wdCB0byBzZWFyY2ggYnkgZW1haWwgZmlyc3QgaWYgaXQgbG9va3MgbGlrZSBvbmVcbiAgICAgICAgICAgIG5hbWVPckVtYWlsLmluY2x1ZGVzKCdAJylcbiAgICAgICAgICAgICAgPyB7IHByb3BlcnR5TmFtZTogJ2VtYWlsJywgb3BlcmF0b3I6ICdFUScsIHZhbHVlOiBuYW1lT3JFbWFpbCB9XG4gICAgICAgICAgICAgIDogLy8gT3RoZXJ3aXNlLCB0cnkgdG8gc2VhcmNoIGJ5IG5hbWUgcGFydHMgKHRoaXMgaXMgc2ltcGxpZmllZClcbiAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICBwcm9wZXJ0eU5hbWU6ICdmaXJzdG5hbWUnLFxuICAgICAgICAgICAgICAgICAgb3BlcmF0b3I6ICdDT05UQUlOU19UT0tFTicsXG4gICAgICAgICAgICAgICAgICB2YWx1ZTogbmFtZU9yRW1haWwuc3BsaXQoJyAnKVswXSxcbiAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgLy8gTW9yZSBzb3BoaXN0aWNhdGVkIG5hbWUgc2VhcmNoaW5nIHdvdWxkIGludm9sdmUgbXVsdGlwbGUgZmlsdGVycyBvciBiZXR0ZXIgcXVlcnkgY29uc3RydWN0aW9uXG4gICAgICAgICAgXSxcbiAgICAgICAgfSxcbiAgICAgIF0sXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlID1cbiAgICAgIGF3YWl0IGh1YnNwb3RDbGllbnQuY3JtLmNvbnRhY3RzLnNlYXJjaEFwaS5kb1NlYXJjaChzZWFyY2hSZXF1ZXN0KTtcblxuICAgIGlmIChyZXNwb25zZS5yZXN1bHRzICYmIHJlc3BvbnNlLnJlc3VsdHMubGVuZ3RoID4gMCkge1xuICAgICAgY29uc3QgY29udGFjdCA9IHJlc3BvbnNlLnJlc3VsdHNbMF07IC8vIFRha2UgdGhlIGZpcnN0IHJlc3VsdCBmb3Igc2ltcGxpY2l0eVxuICAgICAgY29uc3QgY29udGFjdEVtYWlsID0gY29udGFjdC5wcm9wZXJ0aWVzLmVtYWlsO1xuICAgICAgY29uc3QgY29udGFjdE5hbWUgPVxuICAgICAgICBgJHtjb250YWN0LnByb3BlcnRpZXMuZmlyc3RuYW1lIHx8ICcnfSAke2NvbnRhY3QucHJvcGVydGllcy5sYXN0bmFtZSB8fCAnJ31gLnRyaW0oKTtcblxuICAgICAgaWYgKGNvbnRhY3RFbWFpbCkge1xuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICBgW19maW5kSHVic3BvdENvbnRhY3RdIEZvdW5kIEh1YlNwb3QgQ29udGFjdDogTmFtZTogJHtjb250YWN0TmFtZX0sIEVtYWlsOiAke2NvbnRhY3RFbWFpbH1gXG4gICAgICAgICk7XG4gICAgICAgIC8vIENoZWNrIGlmIHRoaXMgSHViU3BvdCBDb250YWN0IGVtYWlsIGFsc28gY29ycmVzcG9uZHMgdG8gYW4gQXRvbSB1c2VyXG4gICAgICAgIGNvbnN0IGF0b21Vc2VyTWF0Y2ggPSBhd2FpdCBfZmluZEF0b21Vc2VyKGNvbnRhY3RFbWFpbCk7XG4gICAgICAgIGlmIChhdG9tVXNlck1hdGNoICYmIGF0b21Vc2VyTWF0Y2gudXNlcklkKSB7XG4gICAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICAgIC4uLmF0b21Vc2VyTWF0Y2gsXG4gICAgICAgICAgICBzb3VyY2U6ICdodWJzcG90X2NvbnRhY3QnLFxuICAgICAgICAgICAgbmFtZTogY29udGFjdE5hbWUgfHwgYXRvbVVzZXJNYXRjaC5uYW1lLFxuICAgICAgICAgIH07XG4gICAgICAgIH1cbiAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICBlbWFpbDogY29udGFjdEVtYWlsLFxuICAgICAgICAgIG5hbWU6IGNvbnRhY3ROYW1lIHx8IG5hbWVPckVtYWlsLFxuICAgICAgICAgIHNvdXJjZTogJ2h1YnNwb3RfY29udGFjdCcsXG4gICAgICAgICAgc3RhdHVzOiAnZm91bmQnLFxuICAgICAgICB9O1xuICAgICAgfVxuICAgIH1cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBbX2ZpbmRIdWJzcG90Q29udGFjdF0gTm8gSHViU3BvdCBjb250YWN0IGZvdW5kIGZvcjogXCIke25hbWVPckVtYWlsfVwiYFxuICAgICk7XG4gICAgcmV0dXJuIG51bGw7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgYFtfZmluZEh1YnNwb3RDb250YWN0XSBFcnJvciBzZWFyY2hpbmcgSHViU3BvdCBjb250YWN0cyBmb3IgJHtuYW1lT3JFbWFpbH06YCxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgZW1haWw6IG5hbWVPckVtYWlsLFxuICAgICAgc291cmNlOiAnaHVic3BvdF9jb250YWN0JyxcbiAgICAgIHN0YXR1czogJ2Vycm9yX3Jlc29sdmluZycsXG4gICAgICBlcnJvck1lc3NhZ2U6IGVycm9yLm1lc3NhZ2UsXG4gICAgfSBhcyBSZXNvbHZlZEF0dGVuZGVlO1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiByZXNvbHZlQXR0ZW5kZWVzKFxuICBhdHRlbmRlZVN0cmluZ3M6IHN0cmluZ1tdLFxuICByZXF1ZXN0ZXJJZDogc3RyaW5nXG4pOiBQcm9taXNlPENvbnRhY3RTa2lsbFJlc3BvbnNlPFJlc29sdmVkQXR0ZW5kZWVbXT4+IHtcbiAgY29uc29sZS5sb2coXG4gICAgYFtjb250YWN0U2tpbGxzXSBSZXNvbHZpbmcgYXR0ZW5kZWVzOiAke2F0dGVuZGVlU3RyaW5ncy5qb2luKCcsICcpfSBmb3IgcmVxdWVzdGVyICR7cmVxdWVzdGVySWR9YFxuICApO1xuICBjb25zdCByZXNvbHZlZEF0dGVuZGVlczogUmVzb2x2ZWRBdHRlbmRlZVtdID0gW107XG5cbiAgZm9yIChjb25zdCBhdHRlbmRlZVN0ciBvZiBhdHRlbmRlZVN0cmluZ3MpIHtcbiAgICBsZXQgcmVzb2x2ZWQ6IFJlc29sdmVkQXR0ZW5kZWUgfCBudWxsID0gbnVsbDtcblxuICAgIGlmIChhdHRlbmRlZVN0ci5pbmNsdWRlcygnQCcpKSB7XG4gICAgICAvLyBTaW1wbGUgY2hlY2sgZm9yIGVtYWlsXG4gICAgICByZXNvbHZlZCA9IGF3YWl0IF9maW5kQXRvbVVzZXIoYXR0ZW5kZWVTdHIpOyAvLyBDaGVjayBpZiBpdCdzIGFuIEF0b20gdXNlciBmaXJzdFxuICAgICAgaWYgKHJlc29sdmVkKSB7XG4gICAgICAgIHJlc29sdmVkLnNvdXJjZSA9ICdhdG9tX3VzZXInOyAvLyBDb3JyZWN0IHNvdXJjZSBpZiBmb3VuZCBhcyBBdG9tIHVzZXIgYnkgZW1haWxcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHJlc29sdmVkID0ge1xuICAgICAgICAgIGVtYWlsOiBhdHRlbmRlZVN0cixcbiAgICAgICAgICBzb3VyY2U6ICdlbWFpbF9kaXJlY3QnLFxuICAgICAgICAgIHN0YXR1czogJ2ZvdW5kJyxcbiAgICAgICAgICBuYW1lOiBhdHRlbmRlZVN0ci5zcGxpdCgnQCcpWzBdLFxuICAgICAgICB9OyAvLyBBc3N1bWUgaXQncyBhIHZhbGlkIGV4dGVybmFsIGVtYWlsXG4gICAgICB9XG4gICAgfSBlbHNlIHtcbiAgICAgIC8vIEl0J3MgbGlrZWx5IGEgbmFtZSwgdHJ5IHJlc29sdmluZyB0aHJvdWdoIGRpZmZlcmVudCBzb3VyY2VzXG4gICAgICByZXNvbHZlZCA9IGF3YWl0IF9maW5kQXRvbVVzZXIoYXR0ZW5kZWVTdHIpO1xuXG4gICAgICBpZiAoIXJlc29sdmVkKSB7XG4gICAgICAgIHJlc29sdmVkID0gYXdhaXQgX2ZpbmRHb29nbGVDb250YWN0KGF0dGVuZGVlU3RyLCByZXF1ZXN0ZXJJZCk7XG4gICAgICB9XG5cbiAgICAgIGlmICghcmVzb2x2ZWQpIHtcbiAgICAgICAgcmVzb2x2ZWQgPSBhd2FpdCBfZmluZEh1YnNwb3RDb250YWN0KGF0dGVuZGVlU3RyLCByZXF1ZXN0ZXJJZCk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgaWYgKHJlc29sdmVkKSB7XG4gICAgICByZXNvbHZlZEF0dGVuZGVlcy5wdXNoKHJlc29sdmVkKTtcbiAgICB9IGVsc2Uge1xuICAgICAgLy8gQ291bGQgbm90IHJlc29sdmUgYnkgbmFtZSwgYW5kIGl0IHdhc24ndCBhbiBlbWFpbFxuICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICBgW2NvbnRhY3RTa2lsbHNdIENvdWxkIG5vdCByZXNvbHZlIGF0dGVuZGVlOiBcIiR7YXR0ZW5kZWVTdHJ9XCJgXG4gICAgICApO1xuICAgICAgcmVzb2x2ZWRBdHRlbmRlZXMucHVzaCh7XG4gICAgICAgIGVtYWlsOiBhdHRlbmRlZVN0ciwgLy8gS2VlcCBvcmlnaW5hbCBzdHJpbmcgaWYgY2Fubm90IHJlc29sdmUgdG8gYWN0dWFsIGVtYWlsXG4gICAgICAgIG5hbWU6IGF0dGVuZGVlU3RyLFxuICAgICAgICBzb3VyY2U6ICd1bnJlc29sdmVkJyxcbiAgICAgICAgc3RhdHVzOiAnbm90X2ZvdW5kJyxcbiAgICAgIH0pO1xuICAgIH1cbiAgfVxuXG4gIC8vIEZpbHRlciBvdXQgYW55IG51bGxzIGp1c3QgaW4gY2FzZSwgdGhvdWdoIGxvZ2ljIGFib3ZlIHRyaWVzIHRvIHB1c2ggYSBwbGFjZWhvbGRlclxuICBjb25zdCBmaW5hbEF0dGVuZGVlcyA9IHJlc29sdmVkQXR0ZW5kZWVzLmZpbHRlcihcbiAgICBCb29sZWFuXG4gICkgYXMgUmVzb2x2ZWRBdHRlbmRlZVtdO1xuICBjb25zb2xlLmxvZygnW2NvbnRhY3RTa2lsbHNdIEZpbmFsIHJlc29sdmVkIGF0dGVuZGVlczonLCBmaW5hbEF0dGVuZGVlcyk7XG5cbiAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IGZpbmFsQXR0ZW5kZWVzIH07XG59XG5cbi8vIFBsYWNlaG9sZGVyIGZvciBmZXRjaGluZyB1c2VyIGF2YWlsYWJpbGl0eSAod29yayB0aW1lcyBhbmQgY2FsZW5kYXIgZXZlbnRzKVxuLy8gVGhpcyB3b3VsZCB0eXBpY2FsbHkgbGl2ZSBpbiBzY2hlZHVsaW5nU2tpbGxzLnRzIG9yIGNhbGVuZGFyU2tpbGxzLnRzXG4vLyBhbmQgaW52b2x2ZSBEQiBxdWVyaWVzIGZvciB3b3JrIHByZWZlcmVuY2VzIGFuZCBjYWxlbmRhciBBUEkgY2FsbHMuXG4vLyBGb3Igbm93LCB0aGlzIGlzIGEgY29uY2VwdHVhbCBwbGFjZWhvbGRlciB3aXRoaW4gdGhpcyBmaWxlLlxuLypcbmltcG9ydCB7IFVzZXJBdmFpbGFiaWxpdHksIFVzZXJXb3JrVGltZSwgQ2FsZW5kYXJFdmVudCB9IGZyb20gJy4uL3R5cGVzJztcbmltcG9ydCB7IGxpc3RVcGNvbWluZ0V2ZW50cyB9IGZyb20gJy4vY2FsZW5kYXJTa2lsbHMnO1xuXG5hc3luYyBmdW5jdGlvbiBfZmV0Y2hVc2VyV29ya1RpbWVzKHVzZXJJZDogc3RyaW5nKTogUHJvbWlzZTxVc2VyV29ya1RpbWVbXT4ge1xuICAgIC8vIFBsYWNlaG9sZGVyOiBRdWVyeSB5b3VyIGRhdGFiYXNlIGZvciB1c2VyX3dvcmtfcHJlZmVyZW5jZXMgYnkgdXNlcklkXG4gICAgY29uc29sZS5sb2coYFtfZmV0Y2hVc2VyV29ya1RpbWVzXSBGZXRjaGluZyB3b3JrIHRpbWVzIGZvciB1c2VyICR7dXNlcklkfSAoUGxhY2Vob2xkZXIpYCk7XG4gICAgLy8gRXhhbXBsZTpcbiAgICAvLyBjb25zdCBxdWVyeSA9IGBxdWVyeSBHZXRVc2VyV29ya1RpbWVzKCR1c2VySWQ6IFN0cmluZyEpIHsgdXNlcl93b3JrX3ByZWZlcmVuY2VzKHdoZXJlOiB7dXNlcl9pZDoge19lcTogJHVzZXJJZH19KSB7IGRheV9vZl93ZWVrIHN0YXJ0X3RpbWUgZW5kX3RpbWUgfSB9YDtcbiAgICAvLyBjb25zdCByZXNwb25zZSA9IGF3YWl0IGV4ZWN1dGVHcmFwaFFMUXVlcnkocXVlcnksIHsgdXNlcklkIH0sICdHZXRVc2VyV29ya1RpbWVzJywgdXNlcklkKTtcbiAgICAvLyByZXR1cm4gcmVzcG9uc2UudXNlcl93b3JrX3ByZWZlcmVuY2VzLm1hcChwcmVmID0+ICh7IGRheU9mV2VlazogcHJlZi5kYXlfb2Zfd2Vlaywgc3RhcnRUaW1lOiBwcmVmLnN0YXJ0X3RpbWUsIGVuZFRpbWU6IHByZWYuZW5kX3RpbWUgfSkpO1xuICAgIHJldHVybiBbIC8vIER1bW15IGRhdGFcbiAgICAgICAgeyBkYXlPZldlZWs6ICdNT05EQVknLCBzdGFydFRpbWU6ICcwOTowMCcsIGVuZFRpbWU6ICcxNzowMCcgfSxcbiAgICAgICAgeyBkYXlPZldlZWs6ICdUVUVTREFZJywgc3RhcnRUaW1lOiAnMDk6MDAnLCBlbmRUaW1lOiAnMTc6MDAnIH0sXG4gICAgICAgIHsgZGF5T2ZXZWVrOiAnV0VETkVTREFZJywgc3RhcnRUaW1lOiAnMDk6MDAnLCBlbmRUaW1lOiAnMTc6MDAnIH0sXG4gICAgICAgIHsgZGF5T2ZXZWVrOiAnVEhVUlNEQVknLCBzdGFydFRpbWU6ICcwOTowMCcsIGVuZFRpbWU6ICcxNzowMCcgfSxcbiAgICAgICAgeyBkYXlPZldlZWs6ICdGUklEQVknLCBzdGFydFRpbWU6ICcwOTowMCcsIGVuZFRpbWU6ICcxNzowMCcgfSxcbiAgICBdO1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0VXNlckF2YWlsYWJpbGl0eShcbiAgICB1c2VySWRzOiBzdHJpbmdbXSxcbiAgICB3aW5kb3dTdGFydDogc3RyaW5nLCAvLyBJU08gc3RyaW5nXG4gICAgd2luZG93RW5kOiBzdHJpbmcgICAvLyBJU08gc3RyaW5nXG4pOiBQcm9taXNlPENvbnRhY3RTa2lsbFJlc3BvbnNlPFVzZXJBdmFpbGFiaWxpdHlbXT4+IHtcbiAgICBjb25zb2xlLmxvZyhgW2NvbnRhY3RTa2lsbHNdIEdldHRpbmcgYXZhaWxhYmlsaXR5IGZvciB1c2VyczogJHt1c2VySWRzLmpvaW4oJywgJyl9IHdpdGhpbiB3aW5kb3c6ICR7d2luZG93U3RhcnR9IHRvICR7d2luZG93RW5kfWApO1xuICAgIGNvbnN0IGFsbFVzZXJzQXZhaWxhYmlsaXR5OiBVc2VyQXZhaWxhYmlsaXR5W10gPSBbXTtcblxuICAgIGZvciAoY29uc3QgdXNlcklkIG9mIHVzZXJJZHMpIHtcbiAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgIGNvbnN0IHdvcmtUaW1lcyA9IGF3YWl0IF9mZXRjaFVzZXJXb3JrVGltZXModXNlcklkKTtcblxuICAgICAgICAgICAgLy8gRmV0Y2ggY2FsZW5kYXIgZXZlbnRzIGZvciB0aGlzIHVzZXIgd2l0aGluIHRoZSB3aW5kb3dcbiAgICAgICAgICAgIC8vIE5vdGU6IGxpc3RVcGNvbWluZ0V2ZW50cyBmZXRjaGVzIGZyb20gJ25vdycuIFdlIG5lZWQgYSB2ZXJzaW9uIHRoYXQgdGFrZXMgYSB0aW1lIHdpbmRvdy5cbiAgICAgICAgICAgIC8vIEZvciBub3csIHRoaXMgaXMgYSBjb25jZXB0dWFsIGFkYXB0YXRpb24uXG4gICAgICAgICAgICAvLyBBIG1vcmUgcHJlY2lzZSBsaXN0VXBjb21pbmdFdmVudHNJbldpbmRvdyh1c2VySWQsIHRpbWVNaW4sIHRpbWVNYXgsIGxpbWl0KSB3b3VsZCBiZSBuZWVkZWQuXG4gICAgICAgICAgICBjb25zdCBldmVudHNSZXNwb25zZSA9IGF3YWl0IGxpc3RVcGNvbWluZ0V2ZW50cyh1c2VySWQsIDUwKTsgLy8gRmV0Y2ggYSBkZWNlbnQgbnVtYmVyXG4gICAgICAgICAgICBsZXQgcmVsZXZhbnRFdmVudHM6IENhbGVuZGFyRXZlbnRbXSA9IFtdO1xuICAgICAgICAgICAgaWYgKGV2ZW50c1Jlc3BvbnNlLm9rICYmIGV2ZW50c1Jlc3BvbnNlLmRhdGEpIHtcbiAgICAgICAgICAgICAgICAgcmVsZXZhbnRFdmVudHMgPSBldmVudHNSZXNwb25zZS5kYXRhLmZpbHRlcihldmVudCA9PiB7XG4gICAgICAgICAgICAgICAgICAgIGNvbnN0IGV2ZW50U3RhcnQgPSBuZXcgRGF0ZShldmVudC5zdGFydFRpbWUpLmdldFRpbWUoKTtcbiAgICAgICAgICAgICAgICAgICAgY29uc3QgZXZlbnRFbmQgPSBuZXcgRGF0ZShldmVudC5lbmRUaW1lKS5nZXRUaW1lKCk7XG4gICAgICAgICAgICAgICAgICAgIGNvbnN0IHdpbmRvd1N0YXJ0VGltZSA9IG5ldyBEYXRlKHdpbmRvd1N0YXJ0KS5nZXRUaW1lKCk7XG4gICAgICAgICAgICAgICAgICAgIGNvbnN0IHdpbmRvd0VuZFRpbWUgPSBuZXcgRGF0ZSh3aW5kb3dFbmQpLmdldFRpbWUoKTtcbiAgICAgICAgICAgICAgICAgICAgLy8gQ2hlY2sgZm9yIG92ZXJsYXBcbiAgICAgICAgICAgICAgICAgICAgcmV0dXJuIE1hdGgubWF4KGV2ZW50U3RhcnQsIHdpbmRvd1N0YXJ0VGltZSkgPCBNYXRoLm1pbihldmVudEVuZCwgd2luZG93RW5kVGltZSk7XG4gICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgIGNvbnNvbGUud2FybihgW2NvbnRhY3RTa2lsbHNdIENvdWxkIG5vdCBmZXRjaCBjYWxlbmRhciBldmVudHMgZm9yIHVzZXIgJHt1c2VySWR9OiAke2V2ZW50c1Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWApO1xuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBhbGxVc2Vyc0F2YWlsYWJpbGl0eS5wdXNoKHtcbiAgICAgICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICAgICAgd29ya1RpbWVzLFxuICAgICAgICAgICAgICAgIGNhbGVuZGFyRXZlbnRzOiByZWxldmFudEV2ZW50cyxcbiAgICAgICAgICAgIH0pO1xuICAgICAgICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgICAgICAgICBjb25zb2xlLmVycm9yKGBbY29udGFjdFNraWxsc10gRXJyb3IgZ2V0dGluZyBhdmFpbGFiaWxpdHkgZm9yIHVzZXIgJHt1c2VySWR9OiAke2Vycm9yLm1lc3NhZ2V9YCk7XG4gICAgICAgICAgICAvLyBPcHRpb25hbGx5IGFkZCBlcnJvciBzdGF0ZSBmb3IgdGhpcyB1c2VyIG9yIHNraXAgdGhlbVxuICAgICAgICB9XG4gICAgfVxuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiBhbGxVc2Vyc0F2YWlsYWJpbGl0eSB9O1xufVxuKi9cbiJdfQ==