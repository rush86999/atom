import { google, calendar_v3 } from 'googleapis';
import { Credentials as OAuth2Token } from 'google-auth-library'; // Use the official type
import {
    CalendarEvent,
    CreateEventResponse,
    // ListGoogleMeetEventsResponse, // Not directly returned by a public skill function
    // GetGoogleMeetEventDetailsResponse, // Not directly returned by a public skill function
    ConferenceData,
    ConferenceSolution,
    ConferenceEntryPoint,
    SlackMessageResponse,
    CalendarSkillResponse,
    SkillError, // Make sure SkillError is imported
} from '../types';
import {
  ATOM_GOOGLE_CALENDAR_CLIENT_ID,
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET,
  ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA,
  HASURA_GRAPHQL_URL, // For checking if client can be used
  HASURA_ADMIN_SECRET, // For checking if client can be used
} from '../_libs/constants';
import { executeGraphQLQuery, executeGraphQLMutation } from '../_libs/graphqlClient'; // Real GraphQL client
import { sendSlackMessage } from './slackSkills';

const GOOGLE_CALENDAR_SERVICE_NAME = 'google_calendar';

interface UserTokenRecord {
  access_token: string;
  refresh_token?: string | null;
  expiry_date?: string | null; // ISO String from DB
  scope?: string | null;
  token_type?: string | null;
  // other_data?: Record<string, any> | null; // If needed in future
}

// Fetches stored Google Calendar tokens for a user from the database
async function getStoredUserTokens(userId: string): Promise<CalendarSkillResponse<OAuth2Token>> {
  console.log(`Retrieving tokens for userId: ${userId}, service: ${GOOGLE_CALENDAR_SERVICE_NAME}`);

  if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'GraphQL client is not configured.' } };
  }

  const query = `
    query GetUserToken($userId: String!, $serviceName: String!) {
      user_tokens(
        where: { user_id: { _eq: $userId }, service_name: { _eq: $serviceName } },
        order_by: { created_at: desc },
        limit: 1
      ) {
        access_token
        refresh_token
        expiry_date
        scope
        token_type
      }
    }
  `;
  const variables = { userId, serviceName: GOOGLE_CALENDAR_SERVICE_NAME };
  const operationName = 'GetUserToken';

  try {
    const response = await executeGraphQLQuery<{ user_tokens: UserTokenRecord[] }>(query, variables, operationName, userId);

    if (!response || !response.user_tokens || response.user_tokens.length === 0) {
      const errorMsg = 'No Google Calendar tokens found for the user.';
      console.warn(errorMsg + ` (User: ${userId})`);
      return { ok: false, error: { code: 'AUTH_NO_TOKENS_FOUND', message: errorMsg } };
    }

    const tokenRecord = response.user_tokens[0];

    // Transform to OAuth2Token format expected by googleapis
    const oauth2Token: OAuth2Token = {
      access_token: tokenRecord.access_token,
      refresh_token: tokenRecord.refresh_token || null, // Ensure null if undefined/null from DB
      expiry_date: tokenRecord.expiry_date ? new Date(tokenRecord.expiry_date).getTime() : null,
      scope: tokenRecord.scope || undefined, // Ensure undefined if null from DB for consistency with googleapis type
      token_type: tokenRecord.token_type || null, // Ensure null if undefined/null from DB
    };

    if (!oauth2Token.access_token) {
        const errorMsg = 'Fetched token data is invalid (missing access_token).';
        console.error(errorMsg + ` (User: ${userId})`, tokenRecord);
        return { ok: false, error: { code: 'TOKEN_INVALID_STRUCTURE', message: errorMsg }};
    }

    return { ok: true, data: oauth2Token };

  } catch (error: any) {
    console.error(`Exception during getStoredUserTokens for userId ${userId}:`, error);
    const skillError: SkillError = {
      code: 'TOKEN_FETCH_FAILED',
      message: `Failed to retrieve Google Calendar tokens for user ${userId}.`,
      details: error.message,
    };
    if (error.code) { // If it's a GraphQLError with a code
        skillError.details = `${error.code}: ${error.message}`;
        if (error.code === 'CONFIG_ERROR') skillError.code = 'CONFIG_ERROR';
    }
    return { ok: false, error: skillError };
  }
}

// Saves or updates Google Calendar tokens for a user in the database
async function saveUserTokens(userId: string, tokens: OAuth2Token): Promise<CalendarSkillResponse<void>> {
  console.log(`Saving tokens for userId: ${userId}, service: ${GOOGLE_CALENDAR_SERVICE_NAME}`);

  if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'GraphQL client is not configured.' } };
  }

  const mutation = `
    mutation UpsertUserToken($objects: [user_tokens_insert_input!]!) {
      insert_user_tokens(
        objects: $objects,
        on_conflict: {
          constraint: user_tokens_user_id_service_name_key, # Assumed constraint: UNIQUE (user_id, service_name)
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
    expiry_date: tokens.expiry_date ? new Date(tokens.expiry_date).toISOString() : null,
    scope: tokens.scope,
    token_type: tokens.token_type,
    // other_data: tokens.id_token ? { id_token: tokens.id_token } : undefined, // Example if you need to store id_token
    updated_at: new Date().toISOString(),
  };

  const variables = { objects: [tokenDataForDb] };
  const operationName = 'UpsertUserToken';

  try {
    // Using userId for the mutation call as it pertains to this user's tokens
    const response = await executeGraphQLMutation<{ insert_user_tokens: { affected_rows: number } }>(mutation, variables, operationName, userId);

    if (!response || !response.insert_user_tokens || response.insert_user_tokens.affected_rows === 0) {
      // This might not be an error if the token was identical and thus not updated,
      // but for simplicity, we'll log a warning if no rows were affected by an upsert.
      // Hasura often returns affected_rows: 1 even if only updated, so 0 is unusual for an upsert.
      console.warn(`Token save operation for user ${userId} reported 0 affected_rows.`, response);
      // Not returning error, as it might be non-critical if tokens are effectively the same.
      // If this becomes an issue, a more specific error could be returned.
    } else {
      console.log(`Tokens saved successfully to database for user ${userId}. Affected rows: ${response.insert_user_tokens.affected_rows}`);
    }
    return { ok: true, data: undefined }; // data is void

  } catch (error: any) {
    console.error(`Exception during saveUserTokens for userId ${userId}:`, error);
    const skillError: SkillError = {
      code: 'TOKEN_SAVE_FAILED',
      message: `Failed to save Google Calendar tokens for user ${userId}.`,
      details: error.message,
    };
    if (error.code) { // If it's a GraphQLError with a code
      skillError.details = `${error.code}: ${error.message}`;
      if (error.code === 'CONFIG_ERROR') skillError.code = 'CONFIG_ERROR';
    }
    return { ok: false, error: skillError };
  }
}

// Helper to get an authenticated Google Calendar client
async function getGoogleCalendarClient(userId: string): Promise<CalendarSkillResponse<calendar_v3.Calendar>> {
  if (!ATOM_GOOGLE_CALENDAR_CLIENT_ID || !ATOM_GOOGLE_CALENDAR_CLIENT_SECRET) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Google Calendar client ID or secret not configured.' } };
  }

  const tokenResponse = await getStoredUserTokens(userId);
  if (!tokenResponse.ok || !tokenResponse.data) {
    return {
        ok: false,
        error: tokenResponse.error || { code: 'AUTH_REQUIRED', message: 'Authentication tokens are missing or invalid.' }
    };
  }
  const currentTokens = tokenResponse.data;

  if (!currentTokens.access_token) { // Should be caught by getStoredUserTokens, but double check
    return { ok: false, error: { code: 'AUTH_TOKEN_INVALID', message: 'Fetched token is invalid (missing access_token).'}};
  }

  const oauth2Client = new google.auth.OAuth2(
    ATOM_GOOGLE_CALENDAR_CLIENT_ID,
    ATOM_GOOGLE_CALENDAR_CLIENT_SECRET
  );
  oauth2Client.setCredentials(currentTokens);

  oauth2Client.on('tokens', async (newTokens) => {
    console.log(`Google API tokens event received for user: ${userId}. New expiry: ${newTokens.expiry_date ? new Date(newTokens.expiry_date).toISOString() : 'N/A'}`);
    let tokensToSave: OAuth2Token = { ...currentTokens, ...newTokens };
    if (!newTokens.refresh_token && currentTokens.refresh_token) {
      tokensToSave.refresh_token = currentTokens.refresh_token;
    }

    const saveResponse = await saveUserTokens(userId, tokensToSave);
    if (!saveResponse.ok) {
        console.error(`Error saving refreshed tokens for user ${userId}:`, saveResponse.error);
    } else {
        console.log(`Refreshed tokens saved successfully for user ${userId}.`);
    }
  });

  return { ok: true, data: google.calendar({ version: 'v3', auth: oauth2Client }) };
}

/**
 * Lists events from the user's primary Google Calendar.
 * Can fetch upcoming events or events within a specified time range (for past or future).
 *
 * @param userId The ID of the user.
 * @param limit Maximum number of events to return.
 * @param timeMin Optional ISO string for the minimum start time of events. If not provided and timeMax is also not provided, defaults to now (upcoming events).
 * @param timeMax Optional ISO string for the maximum end time of events. Used for querying specific ranges.
 * @returns A promise that resolves to a CalendarSkillResponse containing an array of CalendarEvent objects.
 */
export async function listUpcomingEvents(
  userId: string,
  limit: number = 10,
  timeMin?: string,
  timeMax?: string
): Promise<CalendarSkillResponse<CalendarEvent[]>> {
  console.log(`Fetching up to ${limit} events for userId: ${userId}. TimeMin: ${timeMin}, TimeMax: ${timeMax}`);

  const clientResponse = await getGoogleCalendarClient(userId);
  if (!clientResponse.ok || !clientResponse.data) {
    return clientResponse; // Propagate error
  }
  const calendar = clientResponse.data;

  try {
    const listOptions: calendar_v3.Params$Resource$Events$List = {
      calendarId: 'primary',
      maxResults: limit,
      singleEvents: true,
      orderBy: 'startTime',
    };

    if (timeMin) {
      listOptions.timeMin = timeMin;
    } else if (!timeMax) { // Only default to now if neither timeMin nor timeMax is set
      listOptions.timeMin = (new Date()).toISOString();
    }

    if (timeMax) {
      listOptions.timeMax = timeMax;
      // If timeMax is provided, orderBy should typically be 'startTime' (default).
      // If querying past events (timeMax is in the past), and you want the most recent first,
      // you might consider changing orderBy, but Google Calendar API orderBy is 'startTime' or 'updated'.
      // For simply listing events in a range, 'startTime' is usually appropriate.
    }

    // If timeMin is in the past and timeMax is not set, this will fetch events from timeMin until now/future.
    // If timeMin and timeMax define a past range, it fetches past events.

    const response = await calendar.events.list(listOptions);

    const events = response.data.items;
    if (!events || events.length === 0) {
      console.log(`No upcoming events found on Google Calendar for user ${userId}.`);
      return { ok: true, data: [] };
    }

    const mappedEvents = events.map(event => ({
      id: event.id || `generated_${Math.random().toString(36).substring(2, 15)}`,
      summary: event.summary || 'No Title',
      description: event.description || undefined,
      startTime: event.start?.dateTime || event.start?.date || new Date().toISOString(),
      endTime: event.end?.dateTime || event.end?.date || new Date().toISOString(),
      location: event.location || undefined,
      htmlLink: event.htmlLink || undefined,
      conferenceData: event.conferenceData ? mapConferenceData(event.conferenceData) : undefined,
    }));
    return { ok: true, data: mappedEvents };

  } catch (error: any) {
    console.error(`Error fetching Google Calendar events for user ${userId}:`, error.message, error.response?.data);
    if (error.response?.data?.error === 'invalid_grant' || error.code === 401) {
      return { ok: false, error: { code: 'AUTH_TOKEN_INVALID', message: 'Google Calendar token is invalid or expired. Re-authentication required.', details: error.response?.data?.error_description } };
    }
    if (error.code && ['ENOTFOUND', 'ECONNREFUSED', 'ETIMEDOUT'].includes(error.code)) {
        return { ok: false, error: { code: 'NETWORK_ERROR', message: `Network error communicating with Google Calendar: ${error.code}`, details: error.message } };
    }
    return { ok: false, error: { code: 'GOOGLE_API_ERROR', message: 'Failed to fetch Google Calendar events due to an API error.', details: error.response?.data || error.message } };
  }
}

export async function createCalendarEvent(userId: string, eventDetails: Partial<CalendarEvent>): Promise<CalendarSkillResponse<CreateEventResponse>> {
  console.log(`Attempting to create calendar event for userId: ${userId} with details:`, eventDetails);

  if (!eventDetails.summary || !eventDetails.startTime || !eventDetails.endTime) {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Missing required event details (summary, startTime, endTime).' } };
  }

  const clientResponse = await getGoogleCalendarClient(userId);
  if (!clientResponse.ok || !clientResponse.data) {
    return clientResponse; // Propagate error
  }
  const calendar = clientResponse.data;

  const googleEventResource: calendar_v3.Schema$Event = {
    summary: eventDetails.summary,
    description: eventDetails.description,
    start: {
      dateTime: eventDetails.startTime, // Assuming startTime is a full ISO string
    },
    end: {
      dateTime: eventDetails.endTime, // Assuming endTime is a full ISO string
    },
    location: eventDetails.location,
    conferenceData: eventDetails.conferenceData ? { createRequest: { requestId: `atom-${Date.now()}` } } : undefined, // Basic request for Meet
  };

  if (eventDetails.conferenceData?.createRequest?.conferenceSolutionKey?.type === 'hangoutsMeet') {
     googleEventResource.conferenceData = {
         createRequest: {
             requestId: `atom-${Date.now()}-${Math.random().toString(36).substring(2,9)}`, // unique request id
             conferenceSolutionKey: { type: 'hangoutsMeet' }
         }
     };
  }


  try {
    const response = await calendar.events.insert({
      calendarId: 'primary',
      requestBody: googleEventResource,
      conferenceDataVersion: 1, // Required if manipulating conferenceData
    });

    const createdEvent = response.data;
    console.log(`Google Calendar event created successfully for user ${userId}: ${createdEvent.id}`);
    return {
      ok: true,
      data: {
        success: true,
        eventId: createdEvent.id || undefined,
        message: 'Calendar event created successfully with Google Calendar.',
        htmlLink: createdEvent.htmlLink || undefined,
        conferenceData: createdEvent.conferenceData ? mapConferenceData(createdEvent.conferenceData) : undefined,
      }
    };

  } catch (error: any) {
    console.error(`Error creating Google Calendar event for user ${userId}:`, error.message, error.response?.data);
    if (error.response?.data?.error === 'invalid_grant' || error.code === 401) {
      return { ok: false, error: { code: 'AUTH_TOKEN_INVALID', message: 'Google Calendar token is invalid or expired. Re-authentication required.', details: error.response?.data?.error_description } };
    }
    if (error.code && ['ENOTFOUND', 'ECONNREFUSED', 'ETIMEDOUT'].includes(error.code)) {
        return { ok: false, error: { code: 'NETWORK_ERROR', message: `Network error during event creation: ${error.code}`, details: error.message } };
    }
    const message = error.response?.data?.error?.message || error.message || 'Failed to create event with Google Calendar.';
    return { ok: false, error: { code: 'GOOGLE_API_ERROR', message: message, details: error.response?.data || error.message } };
  }
}

function mapConferenceData(googleConferenceData: calendar_v3.Schema$ConferenceData): ConferenceData {
    const entryPoints = googleConferenceData.entryPoints?.map(ep => ({
        entryPointType: ep.entryPointType as ConferenceEntryPoint['entryPointType'],
        uri: ep.uri || undefined,
        label: ep.label || undefined,
        pin: ep.pin || undefined,
        accessCode: ep.accessCode || undefined,
        meetingCode: ep.meetingCode || undefined,
        passcode: ep.passcode || undefined,
        password: ep.password || undefined,
    })) || [];

    const conferenceSolution = googleConferenceData.conferenceSolution ? {
        key: googleConferenceData.conferenceSolution.key as ConferenceSolution['key'], // Might need more specific type assertion if 'type' is the only prop
        name: googleConferenceData.conferenceSolution.name || undefined,
        iconUri: googleConferenceData.conferenceSolution.iconUri || undefined,
    } : undefined;

    // Ensure key type is correctly mapped if it's just an object like { type: 'hangoutsMeet' }
    if (googleConferenceData.conferenceSolution?.key && typeof googleConferenceData.conferenceSolution.key.type === 'string') {
      conferenceSolution!.key = { type: googleConferenceData.conferenceSolution.key.type as 'hangoutsMeet' | 'addOn' }; // Example
    }


    return {
        createRequest: googleConferenceData.createRequest ? {
            requestId: googleConferenceData.createRequest.requestId || undefined,
            conferenceSolutionKey: googleConferenceData.createRequest.conferenceSolutionKey as ConferenceSolution['key'], // Same as above
            status: googleConferenceData.createRequest.status as any,
        } : undefined,
        entryPoints: entryPoints,
        conferenceSolution: conferenceSolution,
        conferenceId: googleConferenceData.conferenceId || undefined,
        signature: googleConferenceData.signature || undefined,
        notes: googleConferenceData.notes || undefined,
    };
}

async function getCalendarEventById(userId: string, eventId: string): Promise<CalendarSkillResponse<CalendarEvent>> {
  console.log(`Fetching event by ID: ${eventId} for userId: ${userId}`);

  const clientResponse = await getGoogleCalendarClient(userId);
  if (!clientResponse.ok || !clientResponse.data) {
    return clientResponse; // Propagate error
  }
  const calendar = clientResponse.data;

  try {
    const response = await calendar.events.get({
      calendarId: 'primary',
      eventId: eventId,
    });

    const event = response.data;
    return {
      ok: true,
      data: {
        id: event.id || eventId,
        summary: event.summary || 'No Title',
        description: event.description || undefined,
        startTime: event.start?.dateTime || event.start?.date || new Date().toISOString(),
        endTime: event.end?.dateTime || event.end?.date || new Date().toISOString(),
        location: event.location || undefined,
        htmlLink: event.htmlLink || undefined,
        conferenceData: event.conferenceData ? mapConferenceData(event.conferenceData) : undefined,
      }
    };
  } catch (error: any) {
    console.error(`Error fetching event ${eventId} from Google Calendar for user ${userId}:`, error.message, error.response?.data);
    if (error.response?.status === 404) {
      return { ok: false, error: { code: 'EVENT_NOT_FOUND', message: `Event with ID ${eventId} not found.`, details: error.response?.data } };
    } else if (error.response?.data?.error === 'invalid_grant' || error.code === 401) {
      return { ok: false, error: { code: 'AUTH_TOKEN_INVALID', message: 'Google Calendar token is invalid or expired. Re-authentication required.', details: error.response?.data?.error_description } };
    }
    if (error.code && ['ENOTFOUND', 'ECONNREFUSED', 'ETIMEDOUT'].includes(error.code)) {
        return { ok: false, error: { code: 'NETWORK_ERROR', message: `Network error fetching event by ID: ${error.code}`, details: error.message } };
    }
    return { ok: false, error: { code: 'GOOGLE_API_ERROR', message: `Failed to fetch event ${eventId} due to an API error.`, details: error.response?.data || error.message } };
  }
}

export async function listUpcomingGoogleMeetEvents(userId: string, limit: number = 10): Promise<CalendarSkillResponse<CalendarEvent[]>> {
  console.log(`listUpcomingGoogleMeetEvents called for userId: ${userId}, limit: ${limit}`);

  const allEventsResponse = await listUpcomingEvents(userId, (limit * 4) + 10); // Fetch more to filter

  if (!allEventsResponse.ok) {
    return allEventsResponse;
  }

  const allEvents = allEventsResponse.data || [];
  if (allEvents.length === 0) {
    return { ok: true, data: [] };
  }

  try {
    const meetEvents: CalendarEvent[] = allEvents.filter(event =>
      event.conferenceData?.conferenceSolution?.key?.type === 'hangoutsMeet' &&
      event.conferenceData?.entryPoints?.some(ep => ep.entryPointType === 'video' && ep.uri?.startsWith('https://meet.google.com/'))
    ).slice(0, limit);
    return { ok: true, data: meetEvents };
  } catch (error: any) {
    console.error('Error processing events for listUpcomingGoogleMeetEvents:', error.message);
    return { ok: false, error: { code: 'INTERNAL_ERROR', message: 'Failed to process events for Google Meet listing.', details: error.message } };
  }
}

export async function getGoogleMeetEventDetails(userId: string, eventId: string): Promise<CalendarSkillResponse<CalendarEvent>> {
  console.log(`getGoogleMeetEventDetails called for userId: ${userId}, eventId: ${eventId}`);

  const eventResponse = await getCalendarEventById(userId, eventId);

  if (!eventResponse.ok) {
    return eventResponse;
  }

  const event = eventResponse.data;
  if (!event) {
      return { ok: false, error: { code: 'EVENT_NOT_FOUND', message: `Event with ID ${eventId} not found after retrieval attempt.` } };
  }

  if (event.conferenceData?.conferenceSolution?.key?.type !== 'hangoutsMeet') {
     console.log(`Event ${eventId} was found but is not a Google Meet event.`);
     // return { ok: false, error: { code: 'EVENT_NOT_MEET_EVENT', message: `Event ${eventId} is not a Google Meet event.` } };
  }

  return { ok: true, data: event };
}

export async function slackMyAgenda(userId: string, limit: number = 5): Promise<SlackMessageResponse> {
  console.log(`slackMyAgenda called for userId: ${userId} with limit: ${limit}`);

  const eventsResponse = await listUpcomingEvents(userId, limit);

  if (!eventsResponse.ok || !eventsResponse.data) { // Check data as well
    const errorDetails = eventsResponse.error ? `${eventsResponse.error.code}: ${eventsResponse.error.message}` : 'Unknown error fetching agenda.';
    console.error(`Error fetching upcoming events for agenda (userId ${userId}):`, errorDetails);

    const slackChannelId = userId || ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA;
    if (!slackChannelId) {
        return { ok: false, error: `Failed to fetch calendar events and no Slack channel to report to: ${errorDetails}` };
    }
    await sendSlackMessage(userId, slackChannelId, `Sorry, I couldn't fetch your agenda. Error: ${errorDetails}`);
    return { ok: false, error: `Failed to fetch calendar events: ${errorDetails}` };
  }

  const events = eventsResponse.data;
  if (events.length === 0) {
    const noEventsMessage = "You have no upcoming events in your Google Calendar for the requested period.";
    const slackChannelId = userId || ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA;
     if (!slackChannelId) {
      console.warn('No Slack channel ID could be determined. Cannot send "no events" message.');
      return { ok: false, error: 'No Slack channel ID to send the "no events" message to.' };
    }
    return await sendSlackMessage(userId, slackChannelId, noEventsMessage);
  }

  let formattedAgenda = `Here's your upcoming agenda:\n`;
  try {
    for (const event of events) {
      const startTime = new Date(event.startTime).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true });
      const endTime = new Date(event.endTime).toLocaleString([], { hour: 'numeric', minute: '2-digit', hour12: true });
      formattedAgenda += `\n- *${event.summary}*\n  \`${startTime} - ${endTime}\``;
      if (event.location) {
        formattedAgenda += `\n  📍 ${event.location}`;
      }
      if (event.conferenceData?.entryPoints?.find(ep => ep.entryPointType === 'video' && ep.uri?.includes('meet.google.com'))) {
        const meetLink = event.conferenceData.entryPoints.find(ep => ep.entryPointType === 'video' && ep.uri?.includes('meet.google.com'))!.uri;
        formattedAgenda += `\n  🔗 Google Meet: ${meetLink}`;
      }
      formattedAgenda += `\n`;
    }
  } catch (formatError: any) {
    console.error(`Error formatting agenda for userId ${userId}:`, formatError);
    return { ok: false, error: `Failed to format agenda: ${formatError.message}` };
  }

  const slackChannelId = userId || ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA;
  if (!slackChannelId) {
    const errorMsg = 'slackMyAgenda: Slack channel ID could not be determined.';
    console.error(errorMsg);
    return { ok: false, error: errorMsg };
  }

  try {
    const slackResponse = await sendSlackMessage(userId, slackChannelId, formattedAgenda);
    if (!slackResponse.ok) {
      console.error(`Failed to send Slack message for agenda (userId ${userId}): ${slackResponse.error}`);
    }
    return slackResponse;
  } catch (slackError: any) {
    console.error(`Error sending agenda to Slack for userId ${userId}:`, slackError);
    return { ok: false, error: `Failed to send agenda to Slack: ${slackError.message}` };
  }
}
