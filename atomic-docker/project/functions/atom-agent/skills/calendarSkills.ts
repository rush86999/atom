import { google, calendar_v3 } from 'googleapis';
import {
    CalendarEvent,
    CreateEventResponse,
    ListGoogleMeetEventsResponse,
    GetGoogleMeetEventDetailsResponse,
    ConferenceData, // Assuming this and related types are in ../types
    ConferenceSolution,
    ConferenceEntryPoint
} from '../types';
import {
  ATOM_GOOGLE_CALENDAR_CLIENT_ID,
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET,
  // ATOM_GOOGLE_CALENDAR_REDIRECT_URI, // Not directly used in skill functions after auth
} from '../_libs/constants';

// Placeholder for fetching stored Google Calendar tokens for a user
async function getStoredUserTokens(userId: string): Promise<any | null> {
    console.log(`TODO: Implement actual retrieval of tokens for userId: ${userId} from secure storage.`);
    // For now, return mock tokens if userId is 'mock_user_id' (or similar consistent mock ID)
    if (userId && userId.startsWith('mock_user_id')) {
        return {
            access_token: 'mock_access_token_from_storage', // This will cause API calls to fail
            refresh_token: 'mock_refresh_token_from_storage',
            expiry_date: Date.now() + 3600 * 1000, // Mock as valid for 1 hour
            scope: 'https://www.googleapis.com/auth/calendar'
        };
    }
    return null;
}

// Placeholder for updating/saving tokens (e.g., after a refresh)
async function saveUserTokens(userId: string, tokens: any): Promise<void> {
    console.log(`TODO: Implement actual saving of tokens for userId: ${userId}`, tokens);
}


export async function listUpcomingEvents(userId: string, limit: number = 10): Promise<CalendarEvent[]> {
  console.log(`Attempting to fetch up to ${limit} upcoming events for userId: ${userId}...`);

  const retrievedTokens = await getStoredUserTokens(userId);
  if (!retrievedTokens || !retrievedTokens.access_token) {
    console.error(`No stored tokens found for userId: ${userId}. Cannot fetch calendar events.`);
    // In a real app, you might throw an error or return a specific structure indicating auth is needed.
    // For now, returning an empty array and logging is consistent with mock behavior for "no events".
    return [];
  }

  if (!ATOM_GOOGLE_CALENDAR_CLIENT_ID || !ATOM_GOOGLE_CALENDAR_CLIENT_SECRET) {
    console.error('Atom Agent Google Calendar client ID or secret not configured.');
    return []; // Or throw an error
  }

  const oauth2Client = new google.auth.OAuth2(
    ATOM_GOOGLE_CALENDAR_CLIENT_ID,
    ATOM_GOOGLE_CALENDAR_CLIENT_SECRET
    // ATOM_GOOGLE_CALENDAR_REDIRECT_URI // Not needed for API calls after tokens are obtained
  );

  oauth2Client.setCredentials(retrievedTokens);

  // TODO: Listen for 'tokens' event on oauth2Client to automatically save new tokens if refreshed.
  // oauth2Client.on('tokens', (newTokens) => {
  //   if (newTokens.refresh_token) {
  //     // new access token and potentially new refresh token received
  //     console.log('Tokens refreshed:', newTokens);
  //     saveUserTokens(userId, { ...retrievedTokens, ...newTokens });
  //   } else {
  //     // only new access token received
  //     console.log('Access token refreshed:', newTokens);
  //     saveUserTokens(userId, { ...retrievedTokens, access_token: newTokens.access_token, expiry_date: newTokens.expiry_date });
  //   }
  // });

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
      return [];
    }

    return events.map(event => ({
      id: event.id || `generated_${Math.random()}`, // Ensure ID is always present
      summary: event.summary || 'No Title',
      description: event.description || undefined,
      startTime: event.start?.dateTime || event.start?.date || new Date().toISOString(),
      endTime: event.end?.dateTime || event.end?.date || new Date().toISOString(),
      location: event.location || undefined,
      htmlLink: event.htmlLink || undefined,
      // Ensure conferenceData is mapped if present
      conferenceData: event.conferenceData ? mapConferenceData(event.conferenceData) : undefined,
    }));

  } catch (error: any) {
    console.error('Error fetching Google Calendar events for Atom Agent:', error.message);
    if (error.response?.data?.error === 'invalid_grant') {
        console.error('Token error (invalid_grant). User might need to re-authenticate.');
        // TODO: Potentially trigger a re-authentication flow or clear stored tokens.
        // await saveUserTokens(userId, null); // Example: clear bad tokens
    }
    // For now, return empty or a specific error structure if desired by the handler
    return [];
  }
}

export async function createCalendarEvent(userId: string, eventDetails: Partial<CalendarEvent>): Promise<CreateEventResponse> {
  console.log(`Attempting to create calendar event for userId: ${userId} with details:`, eventDetails);

  const retrievedTokens = await getStoredUserTokens(userId);
  if (!retrievedTokens || !retrievedTokens.access_token) {
    console.error(`No stored tokens for userId: ${userId}. Cannot create event.`);
    return { success: false, message: 'Authentication required. No tokens found.' };
  }

  if (!eventDetails.summary || !eventDetails.startTime || !eventDetails.endTime) {
    return { success: false, message: 'Missing required event details (summary, startTime, endTime).' };
  }

  if (!ATOM_GOOGLE_CALENDAR_CLIENT_ID || !ATOM_GOOGLE_CALENDAR_CLIENT_SECRET) {
    console.error('Atom Agent Google Calendar client ID or secret not configured.');
    return { success: false, message: 'Server configuration error for calendar service.' };
  }

  const oauth2Client = new google.auth.OAuth2(
    ATOM_GOOGLE_CALENDAR_CLIENT_ID,
    ATOM_GOOGLE_CALENDAR_CLIENT_SECRET
  );
  oauth2Client.setCredentials(retrievedTokens);

  // TODO: Listen for 'tokens' event on oauth2Client for token refresh as in listUpcomingEvents.

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
    return {
      success: true,
      eventId: createdEvent.id || undefined,
      message: 'Calendar event created successfully with Google Calendar.',
      htmlLink: createdEvent.htmlLink || undefined,
    };

  } catch (error: any) {
    console.error('Error creating Google Calendar event for Atom Agent:', error.message);
     if (error.response?.data?.error === 'invalid_grant') {
        console.error('Token error (invalid_grant). User might need to re-authenticate.');
        // TODO: Potentially trigger a re-authentication flow or clear stored tokens.
    }
    return { success: false, message: `Failed to create event with Google Calendar: ${error.message}` };
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


async function getCalendarEventById(userId: string, eventId: string): Promise<CalendarEvent | null> {
  console.log(`Fetching event by ID: ${eventId} for userId: ${userId}`);
  const retrievedTokens = await getStoredUserTokens(userId);
  if (!retrievedTokens || !retrievedTokens.access_token) {
    console.error(`No stored tokens for userId: ${userId}. Cannot fetch event.`);
    return null;
  }

  if (!ATOM_GOOGLE_CALENDAR_CLIENT_ID || !ATOM_GOOGLE_CALENDAR_CLIENT_SECRET) {
    console.error('Atom Agent Google Calendar client ID or secret not configured.');
    return null;
  }

  const oauth2Client = new google.auth.OAuth2(
    ATOM_GOOGLE_CALENDAR_CLIENT_ID,
    ATOM_GOOGLE_CALENDAR_CLIENT_SECRET
  );
  oauth2Client.setCredentials(retrievedTokens);
  // TODO: Add token refresh listener as in listUpcomingEvents

  const calendar = google.calendar({ version: 'v3', auth: oauth2Client });

  try {
    const response = await calendar.events.get({
      calendarId: 'primary',
      eventId: eventId,
    });

    const event = response.data;
    if (!event) {
      return null;
    }

    return {
      id: event.id || eventId,
      summary: event.summary || 'No Title',
      description: event.description || undefined,
      startTime: event.start?.dateTime || event.start?.date || new Date().toISOString(),
      endTime: event.end?.dateTime || event.end?.date || new Date().toISOString(),
      location: event.location || undefined,
      htmlLink: event.htmlLink || undefined,
      conferenceData: event.conferenceData ? mapConferenceData(event.conferenceData) : undefined,
    };
  } catch (error: any) {
    console.error(`Error fetching event ${eventId} from Google Calendar:`, error.message);
    if (error.response?.status === 404) {
        console.log(`Event ${eventId} not found.`);
    } else if (error.response?.data?.error === 'invalid_grant') {
        console.error('Token error (invalid_grant). User might need to re-authenticate.');
    }
    return null;
  }
}

export async function listUpcomingGoogleMeetEvents(userId: string, limit: number = 10): Promise<ListGoogleMeetEventsResponse> {
  console.log(`listUpcomingGoogleMeetEvents called for userId: ${userId}, limit: ${limit}`);
  try {
    // Fetch a larger number of events to ensure we can find enough Meet events up to the limit.
    // This is a simple approach; more sophisticated filtering might be done via API if available,
    // but Google Calendar API's direct filtering for Meet events is limited.
    const allEvents: CalendarEvent[] = await listUpcomingEvents(userId, (limit * 4) + 10);

    if (!allEvents || allEvents.length === 0) {
      // listUpcomingEvents already handles logging for no events or token errors.
      // It returns [] in those cases based on current implementation.
      return { ok: true, events: [] };
    }

    const meetEvents: CalendarEvent[] = allEvents.filter(event =>
        event.conferenceData?.conferenceSolution?.key?.type === 'hangoutsMeet' &&
        event.conferenceData?.entryPoints?.some(ep => ep.entryPointType === 'video' && ep.uri?.startsWith('https://meet.google.com/'))
    ).slice(0, limit);

    return { ok: true, events: meetEvents };
  } catch (error: any) {
    console.error('Error listing Google Meet events:', error.message);
    return { ok: false, error: 'Failed to list Google Meet events: ' + error.message };
  }
}

export async function getGoogleMeetEventDetails(userId: string, eventId: string): Promise<GetGoogleMeetEventDetailsResponse> {
  console.log(`getGoogleMeetEventDetails called for userId: ${userId}, eventId: ${eventId}`);
  try {
    const event: CalendarEvent | null = await getCalendarEventById(userId, eventId);

    if (!event) {
      return { ok: false, error: 'Event not found or access denied.' };
    }

    // Optionally, explicitly check if it's a Meet event again, though getCalendarEventById should provide conferenceData.
    if (!event.conferenceData?.conferenceSolution?.key?.type === 'hangoutsMeet') {
       console.log(`Event ${eventId} was found but does not appear to be a Google Meet event based on conferenceData.`);
       // Depending on strictness, either return it or an error/specific status.
       // For now, we'll return it as the user asked for this specific event ID.
       // The caller can then inspect conferenceData.
    }

    return { ok: true, event: event };
  } catch (error: any) { // This catch might be redundant if getCalendarEventById handles its errors well
    console.error('Error getting Google Meet event details:', error.message);
    return { ok: false, error: 'Failed to get Google Meet event details: ' + error.message };
  }
}
