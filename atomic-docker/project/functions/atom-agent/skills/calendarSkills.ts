import { google } from 'googleapis';
import { CalendarEvent, CreateEventResponse } from '../types';
import {
  ATOM_GOOGLE_CALENDAR_CLIENT_ID,
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET,
} from '../_libs/constants';
import { getAtomGoogleCalendarTokens, saveAtomGoogleCalendarTokens } from '../_libs/token-utils';


export async function listUpcomingEvents(userId: string, limit: number = 10): Promise<CalendarEvent[]> {
  console.log(`Attempting to fetch up to ${limit} upcoming events for userId: ${userId}...`);

  const retrievedTokens = await getAtomGoogleCalendarTokens(userId);
  if (!retrievedTokens || !retrievedTokens.access_token) {
    console.error(`No valid tokens found for userId: ${userId} via getAtomGoogleCalendarTokens. User may need to authenticate or re-authenticate.`);
    return [];
  }

  if (!ATOM_GOOGLE_CALENDAR_CLIENT_ID || !ATOM_GOOGLE_CALENDAR_CLIENT_SECRET) {
    console.error('Atom Agent Google Calendar client ID or secret not configured in constants.');
    return []; // Or throw an error indicating server misconfiguration
  }

  const oauth2Client = new google.auth.OAuth2(
    ATOM_GOOGLE_CALENDAR_CLIENT_ID,
    ATOM_GOOGLE_CALENDAR_CLIENT_SECRET
  );

  oauth2Client.setCredentials({
    access_token: retrievedTokens.access_token,
    refresh_token: retrievedTokens.refresh_token,
    expiry_date: retrievedTokens.expiry_date,
    scope: retrievedTokens.scope,
    token_type: retrievedTokens.token_type,
  });

  oauth2Client.on('tokens', async (newTokens) => {
    console.log('Google API tokens were refreshed for Atom Agent:', newTokens);
    let tokensToSave = { ...retrievedTokens, ...newTokens };
    if (newTokens.refresh_token) {
        console.log('Saving new refresh token from refresh event for Atom Agent.');
    } else {
        tokensToSave.refresh_token = retrievedTokens?.refresh_token || tokensToSave.refresh_token;
    }

    const googleTokenSet = {
        access_token: tokensToSave.access_token!, // Non-null assertion as it's core to the event
        refresh_token: tokensToSave.refresh_token,
        scope: tokensToSave.scope,
        token_type: tokensToSave.token_type,
        expiry_date: tokensToSave.expiry_date! // Non-null assertion
    };

    await saveAtomGoogleCalendarTokens(userId, googleTokenSet);
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
    }));

  } catch (error: any) {
    console.error('Error fetching Google Calendar events for Atom Agent:', error.message);
    if (error.response?.data?.error === 'invalid_grant' || error.message.toLowerCase().includes('token has been expired or revoked')) {
        console.error('Token error (invalid_grant or expired/revoked). User might need to re-authenticate for Atom Agent.');
        // TODO: Potentially clear stored tokens by calling deleteAtomGoogleCalendarTokens(userId) or similar
    }
    return [];
  }
}

export async function createCalendarEvent(userId: string, eventDetails: Partial<CalendarEvent>): Promise<CreateEventResponse> {
  console.log(`Attempting to create calendar event for userId: ${userId} with details:`, eventDetails);

  const retrievedTokens = await getAtomGoogleCalendarTokens(userId);
  if (!retrievedTokens || !retrievedTokens.access_token) {
    console.error(`No valid tokens found for userId: ${userId} via getAtomGoogleCalendarTokens. User may need to authenticate or re-authenticate.`);
    return { success: false, message: 'Authentication required. Please connect your Google Calendar in settings.' };
  }

  if (!eventDetails.summary || !eventDetails.startTime || !eventDetails.endTime) {
    return { success: false, message: 'Missing required event details (summary, startTime, endTime).' };
  }

  if (!ATOM_GOOGLE_CALENDAR_CLIENT_ID || !ATOM_GOOGLE_CALENDAR_CLIENT_SECRET) {
    console.error('Atom Agent Google Calendar client ID or secret not configured in constants.');
    return { success: false, message: 'Server configuration error for calendar service.' };
  }

  const oauth2Client = new google.auth.OAuth2(
    ATOM_GOOGLE_CALENDAR_CLIENT_ID,
    ATOM_GOOGLE_CALENDAR_CLIENT_SECRET
  );
  oauth2Client.setCredentials({
    access_token: retrievedTokens.access_token,
    refresh_token: retrievedTokens.refresh_token,
    expiry_date: retrievedTokens.expiry_date,
    scope: retrievedTokens.scope,
    token_type: retrievedTokens.token_type,
  });

  oauth2Client.on('tokens', async (newTokens) => {
    console.log('Google API tokens were refreshed during createEvent for Atom Agent:', newTokens);
    let tokensToSave = { ...retrievedTokens, ...newTokens };
    if (newTokens.refresh_token) {
        console.log('Saving new refresh token from refresh event during createEvent for Atom Agent.');
    } else {
        tokensToSave.refresh_token = retrievedTokens?.refresh_token || tokensToSave.refresh_token;
    }

    const googleTokenSet = {
        access_token: tokensToSave.access_token!,
        refresh_token: tokensToSave.refresh_token,
        scope: tokensToSave.scope,
        token_type: tokensToSave.token_type,
        expiry_date: tokensToSave.expiry_date!
    };
    await saveAtomGoogleCalendarTokens(userId, googleTokenSet);
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
    return {
      success: true,
      eventId: createdEvent.id || undefined,
      message: 'Calendar event created successfully with Google Calendar.',
      htmlLink: createdEvent.htmlLink || undefined,
    };

  } catch (error: any) {
    console.error('Error creating Google Calendar event for Atom Agent:', error.message);
    if (error.response?.data?.error === 'invalid_grant' || error.message.toLowerCase().includes('token has been expired or revoked')) {
        console.error('Token error (invalid_grant or expired/revoked). User might need to re-authenticate for Atom Agent.');
        // TODO: Potentially clear stored tokens
    }
    return { success: false, message: `Failed to create event with Google Calendar: ${error.message}` };
  }
}
