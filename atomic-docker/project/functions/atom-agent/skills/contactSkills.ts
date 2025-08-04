import { google, people_v1 } from 'googleapis';
import { Client as HubSpotClient } from '@hubspot/api-client';
import {
  ATOM_GOOGLE_CALENDAR_CLIENT_ID, // Assuming similar setup for People API
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET, // Assuming similar setup for People API
  ATOM_HUBSPOT_API_KEY,
  HASURA_GRAPHQL_URL,
  HASURA_ADMIN_SECRET,
} from '../_libs/constants';
import { executeGraphQLQuery } from '../_libs/graphqlClient';
import { getStoredUserTokens as getGoogleUserTokens } from './calendarSkills'; // Re-use for token fetching logic
import { getHubspotClient as getHubSpotApiClient } from './hubspotSkills'; // Re-use for client
import {
  ResolvedAttendee,
  ContactSkillResponse,
  SkillError,
  OAuth2Token, // From types.ts
  HubSpotContact, // From types.ts
} from '../types';

const GOOGLE_PEOPLE_API_SCOPES = [
  'https://www.googleapis.com/auth/contacts.readonly',
];

// Helper to get an authenticated Google People API client
async function getGooglePeopleClient(
  userId: string
): Promise<{ client?: people_v1.People; error?: SkillError }> {
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
        message:
          'Google authentication tokens are missing or invalid for People API.',
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

  const oauth2Client = new google.auth.OAuth2(
    ATOM_GOOGLE_CALENDAR_CLIENT_ID,
    ATOM_GOOGLE_CALENDAR_CLIENT_SECRET
  );
  oauth2Client.setCredentials(currentTokens);

  // TODO: Add token refresh listener similar to calendarSkills if not already handled globally by getGoogleUserTokens
  // oauth2Client.on('tokens', ...);

  return { client: google.people({ version: 'v1', auth: oauth2Client }) };
}

async function _findAtomUser(
  identifier: string
): Promise<ResolvedAttendee | null> {
  console.log(
    `[_findAtomUser] Searching for Atom user with identifier: ${identifier}`
  );
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
  } else {
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
    const response = await executeGraphQLQuery<{
      users: Array<{ id: string; name?: string; email: string }>;
    }>(
      query,
      variables,
      isEmail ? 'GetUserByEmail' : 'GetUserByName'
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
    console.log(
      `[_findAtomUser] No Atom user found for identifier: ${identifier}`
    );
    return null;
  } catch (error: any) {
    console.error(
      `[_findAtomUser] Error searching for Atom user ${identifier}:`,
      error
    );
    return null; // Or return an error status within ResolvedAttendee
  }
}

async function _findGoogleContact(
  nameOrEmail: string,
  requesterId: string
): Promise<ResolvedAttendee | null> {
  console.log(
    `[_findGoogleContact] Searching Google Contacts for: "${nameOrEmail}" for requester ${requesterId}`
  );
  const { client: peopleClient, error: clientError } =
    await getGooglePeopleClient(requesterId);
  if (clientError || !peopleClient) {
    console.error(
      `[_findGoogleContact] Error getting People API client:`,
      clientError
    );
    return {
      email: nameOrEmail,
      source: 'google_contact',
      status: 'error_resolving',
      errorMessage: clientError?.message || 'Failed to get People API client',
    } as ResolvedAttendee;
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
      const primaryName =
        contact.names?.find((n) => n.metadata?.primary)?.displayName ||
        contact.names?.[0]?.displayName;
      const primaryEmail =
        contact.emailAddresses?.find((e) => e.metadata?.primary)?.value ||
        contact.emailAddresses?.[0]?.value;

      if (primaryEmail) {
        console.log(
          `[_findGoogleContact] Found Google Contact: Name: ${primaryName}, Email: ${primaryEmail}`
        );
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
    console.log(
      `[_findGoogleContact] No Google Contact found for: "${nameOrEmail}"`
    );
    return null;
  } catch (error: any) {
    console.error(
      `[_findGoogleContact] Error searching Google Contacts for ${nameOrEmail}:`,
      error
    );
    return {
      email: nameOrEmail,
      source: 'google_contact',
      status: 'error_resolving',
      errorMessage: error.message,
    } as ResolvedAttendee;
  }
}

async function _findHubspotContact(
  nameOrEmail: string,
  requesterId: string
): Promise<ResolvedAttendee | null> {
  console.log(
    `[_findHubspotContact] Searching HubSpot for: "${nameOrEmail}" for requester ${requesterId}`
  );
  const hubspotClient = getHubSpotApiClient(); // This is synchronous
  if (!hubspotClient) {
    return {
      email: nameOrEmail,
      source: 'hubspot_contact',
      status: 'error_resolving',
      errorMessage: 'HubSpot client not configured.',
    } as ResolvedAttendee;
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

    const response =
      await hubspotClient.crm.contacts.searchApi.doSearch(searchRequest);

    if (response.results && response.results.length > 0) {
      const contact = response.results[0]; // Take the first result for simplicity
      const contactEmail = contact.properties.email;
      const contactName =
        `${contact.properties.firstname || ''} ${contact.properties.lastname || ''}`.trim();

      if (contactEmail) {
        console.log(
          `[_findHubspotContact] Found HubSpot Contact: Name: ${contactName}, Email: ${contactEmail}`
        );
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
    console.log(
      `[_findHubspotContact] No HubSpot contact found for: "${nameOrEmail}"`
    );
    return null;
  } catch (error: any) {
    console.error(
      `[_findHubspotContact] Error searching HubSpot contacts for ${nameOrEmail}:`,
      error
    );
    return {
      email: nameOrEmail,
      source: 'hubspot_contact',
      status: 'error_resolving',
      errorMessage: error.message,
    } as ResolvedAttendee;
  }
}

export async function resolveAttendees(
  attendeeStrings: string[],
  requesterId: string
): Promise<ContactSkillResponse<ResolvedAttendee[]>> {
  console.log(
    `[contactSkills] Resolving attendees: ${attendeeStrings.join(', ')} for requester ${requesterId}`
  );
  const resolvedAttendees: ResolvedAttendee[] = [];

  for (const attendeeStr of attendeeStrings) {
    let resolved: ResolvedAttendee | null = null;

    if (attendeeStr.includes('@')) {
      // Simple check for email
      resolved = await _findAtomUser(attendeeStr); // Check if it's an Atom user first
      if (resolved) {
        resolved.source = 'atom_user'; // Correct source if found as Atom user by email
      } else {
        resolved = {
          email: attendeeStr,
          source: 'email_direct',
          status: 'found',
          name: attendeeStr.split('@')[0],
        }; // Assume it's a valid external email
      }
    } else {
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
    } else {
      // Could not resolve by name, and it wasn't an email
      console.warn(
        `[contactSkills] Could not resolve attendee: "${attendeeStr}"`
      );
      resolvedAttendees.push({
        email: attendeeStr, // Keep original string if cannot resolve to actual email
        name: attendeeStr,
        source: 'unresolved',
        status: 'not_found',
      });
    }
  }

  // Filter out any nulls just in case, though logic above tries to push a placeholder
  const finalAttendees = resolvedAttendees.filter(
    Boolean
  ) as ResolvedAttendee[];
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
