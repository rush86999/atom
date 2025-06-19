import { google, calendar_v3 } from 'googleapis';
import {
    CalendarEvent,
    CreateEventResponse,
    ListGoogleMeetEventsResponse,
    GetGoogleMeetEventDetailsResponse,
    ConferenceData, // Assuming this and related types are in ../types
    ConferenceSolution,
    ConferenceEntryPoint,
    OAuth2Token, // Make sure this type is defined in ../types if it's specific
    SlackMessageResponse, // For the return type of sendSlackMessage
    CalendarSkillResponse // A generic response type for calendar skills
} from '../types';
import {
  ATOM_GOOGLE_CALENDAR_CLIENT_ID,
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET,
  ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA, // For fallback Slack channel
  // ATOM_GOOGLE_CALENDAR_REDIRECT_URI, // Not directly used in skill functions after auth
} from '../_libs/constants';
import { executeGraphQLQuery, executeGraphQLMutation } from '../_libs/graphqlClient'; // Import GraphQL helpers
import { sendSlackMessage } from './slackSkills'; // Import from slackSkills

const GOOGLE_CALENDAR_SERVICE_NAME = 'google_calendar';

// Fetches stored Google Calendar tokens for a user from the database
async function getStoredUserTokens(userId: string): Promise<CalendarSkillResponse<OAuth2Token>> {
  console.log(`Retrieving tokens for userId: ${userId}, service: ${GOOGLE_CALENDAR_SERVICE_NAME}`);
  const query = `
    query GetUserTokens($userId: String!, $serviceName: String!) {
      user_tokens(where: {user_id: {_eq: $userId}, service_name: {_eq: $serviceName}}, order_by: {created_at: desc}, limit: 1) {
        access_token
        refresh_token
        expiry_date
        scope
      }
    }
  `;
  const variables = { userId, serviceName: GOOGLE_CALENDAR_SERVICE_NAME };

  try {
    const response = await executeGraphQLQuery<{ user_tokens: OAuth2Token[] }>(query, variables);
    if (response.errors || !response.data || response.data.user_tokens.length === 0) {
      const errorMsg = 'No tokens found in database or GraphQL error.';
      console.warn(errorMsg, response.errors);
      return { ok: false, error: { code: 'AUTH_NO_TOKENS_FOUND', message: errorMsg, details: response.errors } };
    }
    const tokenData = response.data.user_tokens[0];
    return {
      ok: true,
      data: {
        ...tokenData,
        expiry_date: tokenData.expiry_date ? new Date(tokenData.expiry_date).getTime() : undefined,
      }
    };
  } catch (error: any) {
    console.error('Exception during getStoredUserTokens:', error);
    return { ok: false, error: { code: 'INTERNAL_ERROR', message: 'Failed to retrieve tokens due to an internal error.', details: error.message } };
  }
}

// Saves or updates Google Calendar tokens for a user in the database
async function saveUserTokens(userId: string, tokens: OAuth2Token): Promise<void> {
  console.log(`Saving tokens for userId: ${userId}, service: ${GOOGLE_CALENDAR_SERVICE_NAME}`);
  const mutation = `
    mutation UpsertUserToken($tokenData: user_tokens_insert_input!) {
      insert_user_tokens_one(
        object: $tokenData,
        on_conflict: {
          constraint: user_tokens_user_id_service_name_key, # Assuming this constraint exists: UNIQUE (user_id, service_name)
          update_columns: [access_token, refresh_token, expiry_date, scope, updated_at]
        }
      ) {
        id # Or any other field to confirm success
      }
    }
  `;
  const tokenData = {
    user_id: userId,
    service_name: GOOGLE_CALENDAR_SERVICE_NAME,
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
    expiry_date: tokens.expiry_date ? new Date(tokens.expiry_date).toISOString() : null, // Store as ISO string
    scope: tokens.scope,
    updated_at: new Date().toISOString(),
  };

  // For new tokens, also set created_at
  // The upsert logic should ideally handle this if `created_at` is not part of `update_columns`
  // and has a default value in the DB. For this example, we'll include `updated_at`.

  try {
    const response = await executeGraphQLMutation(mutation, { tokenData });
    if (response.errors) {
      console.error('Failed to save tokens to database:', response.errors);
    } else {
      console.log('Tokens saved successfully to database.');
    }
  } catch (error) {
    console.error('Exception during saveUserTokens:', error);
  }
}


export async function listUpcomingEvents(userId: string, limit: number = 10): Promise<CalendarSkillResponse<CalendarEvent[]>> {
  console.log(`Attempting to fetch up to ${limit} upcoming events for userId: ${userId}...`);

  if (!ATOM_GOOGLE_CALENDAR_CLIENT_ID || !ATOM_GOOGLE_CALENDAR_CLIENT_SECRET) {
    const errorMsg = 'Google Calendar client ID or secret not configured.';
    console.error(errorMsg);
    return { ok: false, error: { code: 'CONFIG_ERROR', message: errorMsg } };
  }

  const tokenResponse = await getStoredUserTokens(userId);
  if (!tokenResponse.ok || !tokenResponse.data?.access_token) {
    console.error(`Authentication tokens not available for userId: ${userId}.`);
    // Propagate the error from getStoredUserTokens or a more specific one
    return tokenResponse.ok === false ? tokenResponse : { ok: false, error: { code: 'AUTH_REQUIRED', message: 'Authentication tokens are missing or invalid.'} };
  }
  const currentTokens = tokenResponse.data;

  const oauth2Client = new google.auth.OAuth2(
    ATOM_GOOGLE_CALENDAR_CLIENT_ID,
    ATOM_GOOGLE_CALENDAR_CLIENT_SECRET
    // ATOM_GOOGLE_CALENDAR_REDIRECT_URI // Not needed for API calls after tokens are obtained
  );

  oauth2Client.setCredentials(currentTokens);

  // Listen for 'tokens' event on oauth2Client to automatically save new tokens if refreshed.
  oauth2Client.on('tokens', (newTokens) => {
    console.log('Google API tokens event received for user:', userId);
    let tokensToSave: OAuth2Token = { ...currentTokens, ...newTokens };

    if (!newTokens.refresh_token) {
      tokensToSave.refresh_token = currentTokens.refresh_token;
    }

    if (newTokens.access_token && newTokens.expiry_date) {
         console.log('Access token refreshed. New expiry:', new Date(newTokens.expiry_date).toISOString());
    }
    if (newTokens.refresh_token) {
        console.log('Refresh token was also updated.');
    }

    saveUserTokens(userId, tokensToSave).catch(err => { // saveUserTokens is void, so no explicit error propagation here beyond logging
        console.error("Error saving refreshed tokens:", err);
    });
  });

  const calendar = google.calendar({ version: 'v3', auth: oauth2Client });

  try {
    const response = await calendar.events.list({
      calendarId: 'primary',
      timeMin: (new Date()).toISOString(),
      maxResults: limit,
      singleEvents: true,
      orderBy: 'startTime',
    });

    const events = response.data.items;
    if (!events || events.length === 0) {
      console.log('No upcoming events found on Google Calendar.');
      return { ok: true, data: [] };
    }

    const mappedEvents = events.map(event => ({
      id: event.id || `generated_${Math.random()}`, // Ensure ID is always present
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
    console.error('Error fetching Google Calendar events for Atom Agent:', error.message, error.response?.data);
    if (error.response?.data?.error === 'invalid_grant' || error.code === 401) {
      return { ok: false, error: { code: 'AUTH_TOKEN_INVALID', message: 'Google Calendar token is invalid or expired. Re-authentication required.', details: error.response?.data?.error_description } };
    }
    // Check for network errors (e.g., if error.code is ENOTFOUND, ECONNREFUSED)
    if (error.code && ['ENOTFOUND', 'ECONNREFUSED', 'ETIMEDOUT'].includes(error.code)) {
        return { ok: false, error: { code: 'NETWORK_ERROR', message: `Network error communicating with Google Calendar: ${error.code}`, details: error.message } };
    }
    return { ok: false, error: { code: 'GOOGLE_API_ERROR', message: 'Failed to fetch Google Calendar events due to an API error.', details: error.response?.data || error.message } };
  }
}

export async function createCalendarEvent(userId: string, eventDetails: Partial<CalendarEvent>): Promise<CalendarSkillResponse<CreateEventResponse>> {
  console.log(`Attempting to create calendar event for userId: ${userId} with details:`, eventDetails);

  if (!ATOM_GOOGLE_CALENDAR_CLIENT_ID || !ATOM_GOOGLE_CALENDAR_CLIENT_SECRET) {
    const errorMsg = 'Google Calendar client ID or secret not configured for event creation.';
    console.error(errorMsg);
    return { ok: false, error: { code: 'CONFIG_ERROR', message: errorMsg } };
  }

  if (!eventDetails.summary || !eventDetails.startTime || !eventDetails.endTime) {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Missing required event details (summary, startTime, endTime).' } };
  }

  const tokenResponse = await getStoredUserTokens(userId);
   if (!tokenResponse.ok || !tokenResponse.data?.access_token) {
    console.error(`Authentication tokens not available for userId ${userId} for event creation.`);
    return tokenResponse.ok === false ? tokenResponse : { ok: false, error: { code: 'AUTH_REQUIRED', message: 'Authentication tokens are missing or invalid for event creation.'} };
  }
  const currentTokens = tokenResponse.data;

  const oauth2Client = new google.auth.OAuth2(
    ATOM_GOOGLE_CALENDAR_CLIENT_ID,
    ATOM_GOOGLE_CALENDAR_CLIENT_SECRET
  );
  oauth2Client.setCredentials(currentTokens);

  // Listen for 'tokens' event on oauth2Client for token refresh
  oauth2Client.on('tokens', (newTokens) => {
    console.log('Google API tokens event received during createCalendarEvent for user:', userId);
    let tokensToSave: OAuth2Token = { ...currentTokens, ...newTokens };
    if (!newTokens.refresh_token) {
      tokensToSave.refresh_token = currentTokens.refresh_token;
    }
    saveUserTokens(userId, tokensToSave).catch(err => {
        console.error("Error saving refreshed tokens during createCalendarEvent:", err);
    });
  });

  const calendar = google.calendar({ version: 'v3', auth: oauth2Client });

  const googleEventResource: any = { // Use 'any' for flexibility or define a proper Google Event Resource type
    summary: eventDetails.summary,
    description: eventDetails.description,
    start: {
      dateTime: eventDetails.startTime, // Assuming startTime is a full ISO string
      // timeZone: 'America/Los_Angeles', // Optional: Google typically infers or uses calendar's default
    },
    end: {
      dateTime: eventDetails.endTime, // Assuming endTime is a full ISO string
      // timeZone: 'America/Los_Angeles',
    },
    location: eventDetails.location,
    // attendees: [], // Add if needed
    // reminders: {} // Add if needed
  };

  try {
    const response = await calendar.events.insert({
      calendarId: 'primary',
      requestBody: googleEventResource,
    });

    const createdEvent = response.data;
    console.log('Google Calendar event created successfully for Atom Agent:', createdEvent.id);
    // Note: The original CreateEventResponse type is not under 'data' property.
    // To align with CalendarSkillResponse<T>, we wrap it.
    return {
      ok: true,
      data: {
        success: true,
        eventId: createdEvent.id || undefined,
        message: 'Calendar event created successfully with Google Calendar.',
        htmlLink: createdEvent.htmlLink || undefined,
      }
    };

  } catch (error: any) {
    console.error('Error creating Google Calendar event for Atom Agent:', error.message, error.response?.data);
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


// Helper to map Google API's conferenceData to our ConferenceData type
// This is important because the structure might differ slightly or have more fields than we need.
function mapConferenceData(googleConferenceData: calendar_v3.Schema$ConferenceData): ConferenceData {
    // Basic mapping, can be expanded
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
        key: googleConferenceData.conferenceSolution.key as ConferenceSolution['key'],
        name: googleConferenceData.conferenceSolution.name || undefined,
        iconUri: googleConferenceData.conferenceSolution.iconUri || undefined,
    } : undefined;

    return {
        createRequest: googleConferenceData.createRequest ? {
            requestId: googleConferenceData.createRequest.requestId || undefined,
            conferenceSolutionKey: googleConferenceData.createRequest.conferenceSolutionKey as ConferenceSolution['key'],
            status: googleConferenceData.createRequest.status as any, // Cast or map status correctly
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

  if (!ATOM_GOOGLE_CALENDAR_CLIENT_ID || !ATOM_GOOGLE_CALENDAR_CLIENT_SECRET) {
    const errorMsg = 'Google Calendar client ID or secret not configured for getEventById.';
    console.error(errorMsg);
    return { ok: false, error: { code: 'CONFIG_ERROR', message: errorMsg } };
  }

  const tokenResponse = await getStoredUserTokens(userId);
  if (!tokenResponse.ok || !tokenResponse.data?.access_token) {
    console.error(`Authentication tokens not available for userId ${userId} for getEventById.`);
    return tokenResponse.ok === false ? tokenResponse : { ok: false, error: { code: 'AUTH_REQUIRED', message: 'Authentication tokens are missing or invalid for getEventById.'} };
  }
  const currentTokens = tokenResponse.data;

  const oauth2Client = new google.auth.OAuth2(
    ATOM_GOOGLE_CALENDAR_CLIENT_ID,
    ATOM_GOOGLE_CALENDAR_CLIENT_SECRET
  );
  oauth2Client.setCredentials(currentTokens);

  // Listen for 'tokens' event on oauth2Client for token refresh
  oauth2Client.on('tokens', (newTokens) => {
    console.log('Google API tokens event received during getCalendarEventById for user:', userId);
    let tokensToSave: OAuth2Token = { ...currentTokens, ...newTokens };
    if (!newTokens.refresh_token) {
      tokensToSave.refresh_token = currentTokens.refresh_token;
    }
    saveUserTokens(userId, tokensToSave).catch(err => {
        console.error("Error saving refreshed tokens during getCalendarEventById:", err);
    });
  });

  const calendar = google.calendar({ version: 'v3', auth: oauth2Client });

  try {
    const response = await calendar.events.get({
      calendarId: 'primary',
      eventId: eventId,
    });

    const event = response.data;
    if (!event) { // Should not happen if API call is successful and no error thrown
      return { ok: false, error: { code: 'UNEXPECTED_RESPONSE', message: 'Event data unexpectedly null.' } };
    }

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
    console.error(`Error fetching event ${eventId} from Google Calendar:`, error.message, error.response?.data);
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

  // Fetch a larger number of events to ensure we can find enough Meet events up to the limit.
  const allEventsResponse = await listUpcomingEvents(userId, (limit * 4) + 10);

  if (!allEventsResponse.ok) {
    // Propagate the error from listUpcomingEvents
    return allEventsResponse;
  }

  const allEvents = allEventsResponse.data || [];
  if (allEvents.length === 0) {
    return { ok: true, data: [] }; // No events found, which is a valid success case
  }

  try {
    const meetEvents: CalendarEvent[] = allEvents.filter(event =>
      event.conferenceData?.conferenceSolution?.key?.type === 'hangoutsMeet' &&
      event.conferenceData?.entryPoints?.some(ep => ep.entryPointType === 'video' && ep.uri?.startsWith('https://meet.google.com/'))
    ).slice(0, limit);
    return { ok: true, data: meetEvents };
  } catch (error: any) { // Catch errors from filter/slice or unexpected issues
    console.error('Error processing events for listUpcomingGoogleMeetEvents:', error.message);
    return { ok: false, error: { code: 'INTERNAL_ERROR', message: 'Failed to process events for Google Meet listing.', details: error.message } };
  }
}

export async function getGoogleMeetEventDetails(userId: string, eventId: string): Promise<CalendarSkillResponse<CalendarEvent>> {
  console.log(`getGoogleMeetEventDetails called for userId: ${userId}, eventId: ${eventId}`);

  const eventResponse = await getCalendarEventById(userId, eventId);

  if (!eventResponse.ok) {
    // Propagate error from getCalendarEventById
    return eventResponse;
  }

  const event = eventResponse.data;
  if (!event) { // Should be caught by getCalendarEventById, but as a safeguard
      return { ok: false, error: { code: 'EVENT_NOT_FOUND', message: `Event with ID ${eventId} not found after retrieval attempt.` } };
  }

  // Optionally, explicitly check if it's a Meet event again.
  if (event.conferenceData?.conferenceSolution?.key?.type !== 'hangoutsMeet') {
     console.log(`Event ${eventId} was found but does not appear to be a Google Meet event based on conferenceData.`);
     // Depending on strictness, one might return an error here or a specific status.
     // For now, returning the event as is, the caller can inspect conferenceData.
     // If it MUST be a Meet event, one could return:
     // return { ok: false, error: { code: 'NOT_A_MEET_EVENT', message: `Event ${eventId} is not a Google Meet event.` } };
  }

  return { ok: true, data: event };
}


export async function slackMyAgenda(userId: string, limit: number = 5): Promise<SlackMessageResponse> {
  console.log(`slackMyAgenda called for userId: ${userId} with limit: ${limit}`);

  // 1. Fetch upcoming events
  const eventsResponse = await listUpcomingEvents(userId, limit);

  if (!eventsResponse.ok) {
    console.error(`Error fetching upcoming events for agenda for userId ${userId}:`, eventsResponse.error);
    const slackChannelId = userId || ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA;
    if (!slackChannelId) {
        return { ok: false, error: `Failed to fetch calendar events and no Slack channel to report to: ${eventsResponse.error.message}` };
    }
    // Try to send the error message to Slack
    await sendSlackMessage(userId, slackChannelId, `Sorry, I couldn't fetch your agenda. Error: ${eventsResponse.error.message}`);
    return { ok: false, error: `Failed to fetch calendar events: ${eventsResponse.error.message}` };
  }

  const events = eventsResponse.data || [];
  if (events.length === 0) {
    const noEventsMessage = "You have no upcoming events in your Google Calendar for the requested period.";
    const slackChannelId = userId || ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA;
    if (!slackChannelId) {
      console.warn('No Slack channel ID could be determined. Cannot send "no events" message.');
      return { ok: true, error: 'No events found, and no Slack channel to report to.' }; // Not strictly an error of slackMyAgenda itself
    }
    return await sendSlackMessage(userId, slackChannelId, noEventsMessage);
  }

  // 2. Format the events
  let formattedAgenda = `Here's your upcoming agenda:\n`;
  try {
    for (const event of events) {
      const startTime = new Date(event.startTime).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true });
      const endTime = new Date(event.endTime).toLocaleString([], { hour: 'numeric', minute: '2-digit', hour12: true }); // Only time for end if same day
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


  // 3. Determine Slack Channel ID
  // Assumption: For "my agenda", the userId passed to this function IS the Slack User ID,
  // which can be used as a channel ID to send a direct message.
  // Fallback: If ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA is defined in constants, use that.
  const slackChannelId = userId || ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA;

  if (!slackChannelId) {
    const errorMsg = 'slackMyAgenda: Slack channel ID could not be determined. `userId` is null/empty and no default channel (ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA) is configured.';
    console.error(errorMsg);
    return { ok: false, error: errorMsg };
  }
  console.log(`Determined Slack channel ID for agenda: ${slackChannelId} (using userId or default)`);

  // 4. Send the formatted agenda to Slack
  try {
    const slackResponse = await sendSlackMessage(userId, slackChannelId, formattedAgenda);
    if (!slackResponse.ok) {
      console.error(`Failed to send Slack message for agenda for userId ${userId}: ${slackResponse.error}`);
    } else {
      console.log(`Agenda sent successfully to Slack channel ${slackChannelId} for userId ${userId}. Message ts: ${slackResponse.ts}`);
    }
    return slackResponse;
  } catch (slackError: any) {
    console.error(`Error sending agenda to Slack for userId ${userId}:`, slackError);
    return { ok: false, error: `Failed to send agenda to Slack: ${slackError.message}` };
  }
}
