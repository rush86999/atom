// Google Calendar Operations Module
import { google } from 'googleapis';
import { EventType } from '../../types/EventType';
import crypto from 'crypto';
import { promisify } from 'util';
import { googleCalendarLogger } from './logger';

// OAuth2 Client configuration
const getOAuth2Client = (refreshToken: string) => {
  const oauth2Client = new google.auth.OAuth2(
    process.env.GOOGLE_CLIENT_ID_WEB || process.env.GOOGLE_CLIENT_ID_ATOMIC_WEB,
    process.env.GOOGLE_CLIENT_SECRET_WEB || process.env.GOOGLE_CLIENT_SECRET_ATOMIC_WEB,
    process.env.GOOGLE_REDIRECT_URL || 'http://localhost:3000/api/google/callback'
  );

  oauth2Client.setCredentials({ refresh_token: refreshToken });
  return oauth2Client;
};

// Convert our internal EventType to Google Calendar Event format
const convertToGoogleEvent = (event: EventType): any => {
  const googleEvent: any = {
    summary: event.title || 'Untitled Event',
    description: event.notes || '',
    location: event.location,
    start: {
      dateTime: event.startDateTime || new Date(event.startDate).toISOString(),
      timeZone: event.timezone || 'UTC',
    },
    end: {
      dateTime: event.endDateTime || new Date(event.endDate).toISOString(),
      timeZone: event.timezone || 'UTC',
    },
    attendees: [],
    reminders: {
      useDefault: event.useDefaultAlarms,
      overrides: [],
    },
    extendedProperties: {
      private: event.extendedProperties || {},
    },
  };

  // Handle all-day events
  if (event.allDay) {
    delete googleEvent.start;
    delete googleEvent.end;

    googleEvent.start = {
      date: new Date(event.startDate || event.startDateTime).toISOString().split('T')[0]
    };

    googleEvent.end = {
      date: new Date(event.endDate || event.endDateTime).toISOString().split('T')[0]
    };
  }

  // Add attendees
  if (event.attendees?.length > 0) {
    googleEvent.attendees = event.attendees.map(attendee => ({
      email: attendee.email,
      displayName: attendee.displayName,
      responseStatus: attendee.responseStatus || 'needsAction',
      organizer: attendee.organizer || false,
      additionalGuests: attendee.additionalGuests || 0,
      comment: attendee.comment,
    }));
  }

  return googleEvent;
};

// Convert Google Calendar Event back to our internal EventType
const convertFromGoogleEvent = (googleEvent: any): EventType => {
  const event: EventType = {
    id: googleEvent.id,
    title: googleEvent.summary,
    notes: googleEvent.description,
    location: googleEvent.location,

    startDate: googleEvent.start?.date || googleEvent.start?.dateTime,
    endDate: googleEvent.end?.date || googleEvent.end?.dateTime,
    startDateTime: googleEvent.start?.dateTime,
    endDateTime: googleEvent.end?.dateTime,

    timezone: googleEvent.start?.timeZone || googleEvent.end?.timeZone || 'UTC',
    allDay: !!(googleEvent.start?.date && googleEvent.end?.date),

    attendees: [],

    // Map other properties
    calendarId: 'primary',
    eventId: googleEvent.id,
    htmlLink: googleEvent.htmlLink,
    iCalUID: googleEvent.iCalUID,
    status: googleEvent.status,
    transparency: googleEvent.transparency,
    visibility: googleEvent.visibility,

    recurrence: googleEvent.recurrence,
    recurringEventId: googleEvent.recurringEventId,
    originalStartDateTime: googleEvent.originalStartDateTime,

    extendedProperties: googleEvent.extendedProperties?.private || {},
    useDefaultAlarms: googleEvent.reminders?.useDefault || false,

    createdDate: googleEvent.created,
    updatedAt: googleEvent.updated,
  };

  // Map Google attendees to our format
  if (googleEvent.attendees) {
    event.attendees = googleEvent.attendees.map((attendee: any) => ({
      email: attendee.email,
      displayName: attendee.displayName,
      responseStatus: attendee.responseStatus || 'needsAction',
      organizer: attendee.organizer || false,
      additionalGuests: attendee.additionalGuests || 0,
      comment: attendee.comment,
    }));
  }

  return event;
};

// Get valid Google API access token
export const getGoogleAPIToken = async (
  refreshToken: string,
  userId?: string
): Promise<string | null> => {
  try {
    if (!refreshToken) {
      googleCalendarLogger.error('No refresh token provided for Google API access');
      return null;
    }

    const oauth2Client = getOAuth2Client(refreshToken);
    const { credentials } = await oauth2Client.refreshAccessToken();

    googleCalendarLogger.info('Successfully refreshed Google API token');
    return credentials.access_token || null;
  } catch (error) {
    googleCalendarLogger.error('Error refreshing Google API access token:', error);
    return null;
  }
};

// Create new Google Calendar event
export const createGoogleEvent = async (
  refreshToken: string,
  event: EventType,
  sendUpdates?: string,
  calendarId: string = 'primary'
): Promise<EventType | null> => {
  try {
    const accessToken = await getGoogleAPIToken(refreshToken);
    if (!accessToken) {
      throw new Error('Unable to acquire valid access token');
    }

    const oauth2Client = getOAuth2Client(refreshToken);
    const googleCalendar = google.calendar({ version: 'v3', auth: oauth2Client });

    const googleEvent = convertToGoogleEvent(event);

    const response = await googleCalendar.events.insert({
      calendarId,
      requestBody: googleEvent,
      sendUpdates: sendUpdates as any || 'all',
    });

    googleCalendarLogger.info('Successfully created Google Calendar event', {
      eventId: response.data.id,
      title: response.data.summary,
      calendarId
    });

    return convertFromGoogleEvent(response.data);
  } catch (error) {
    googleCalendarLogger.error('Error creating Google Calendar event:', error);
    return null;
  }
};

// Patch/Update existing Google Calendar event
export const patchGoogleEvent = async (
  refreshToken: string,
  event: EventType,
  eventId: string,
  sendUpdates?: string,
  calendarId: string = 'primary'
): Promise<EventType | null> => {
  try {
    const accessToken = await getGoogleAPIToken(refreshToken);
    if (!accessToken) {
      throw new Error('Unable to acquire valid access token');
    }

    const oauth2Client = getOAuth2Client(refreshToken);
    const googleCalendar = google.calendar({ version: 'v3', auth: oauth2Client });

    // For patch, we only include fields that might have changed
    const patchableFields = [
      'summary', 'description', 'location', 'start', 'end', 'attendees'
    ];

    const googleEvent: any = {};
    patchableFields.forEach(field => {
      if (field === 'summary' && event.title) googleEvent.summary = event.title;
      else if (field === 'description' && event.notes) googleEvent.description = event.notes;
      else if (field === 'location' && event.location) googleEvent.location = event.location;
      else if (field === 'start') googleEvent.start = {
        dateTime: event.startDateTime || new Date(event.startDate).toISOString(),
        timeZone: event.timezone || 'UTC',
      };
      else if (field === 'end') googleEvent.end = {
        dateTime: event.endDateTime || new Date(event.endDate).toISOString(),
        timeZone: event.timezone || 'UTC',
      };
      else if (field === 'attendees' && event.attendees) {
        googleEvent.attendees = event.attendees.map(attendee => ({
          email: attendee.email,
          displayName: attendee.displayName,
          responseStatus: attendee.responseStatus || 'needsAction',
        }));
      }
    });

    const response = await googleCalendar.events.patch({
      calendarId,
      eventId,
      requestBody: googleEvent,
      sendUpdates: sendUpdates as any || 'all',
    });

    googleCalendarLogger.info('Successfully patched Google Calendar event', {
      eventId: response.data.id,
      title: response.data.summary,
      calendarId
    });

    return convertFromGoogleEvent(response.data);
  } catch (error) {
    googleCalendarLogger.error('Error patching Google Calendar event:', error);
    return null;
  }
};

// Delete Google Calendar event
export const deleteGoogleEvent = async (
  refreshToken: string,
  eventId: string,
  sendUpdates?: string,
  calendarId: string = 'primary'
): Promise<boolean> => {
  try {
    const accessToken = await getGoogleAPIToken(refreshToken);
    if (!accessToken) {
      throw new Error('Unable to acquire valid access token');
    }

    const oauth2Client = getOAuth2Client(refreshToken);
    const googleCalendar = google.calendar({ version: 'v3', auth: oauth2Client });

    await googleCalendar.events.delete({
      calendarId,
      eventId,
      sendUpdates: sendUpdates as any || 'all',
    });

    googleCalendarLogger.info('Successfully deleted Google Calendar event', { eventId, calendarId });
    return true;
  } catch (error) {
    googleCalendarLogger.error('Error deleting Google Calendar event:', error);
    return false;
  }
};

// List Google Calendar events
export const listGoogleEvents = async (
  refreshToken: string,
  timeMin: string,
  timeMax?: string,
  calendarId: string = 'primary',
  maxResults: number = 100
): Promise<EventType[]> => {
  try {
    const accessToken = await getGoogleAPIToken(refreshToken);
    if (!accessToken) {
      throw new Error('Unable to acquire valid access token');
    }

    const oauth2Client = getOAuth2Client(refreshToken);
    const googleCalendar = google.calendar({ version: 'v3', auth: oauth2Client });

    const params: any = {
      calendarId,
      timeMin,
      singleEvents: true,
      orderBy: 'startTime',
      maxResults,
    };

    if (timeMax) {
      params.timeMax = timeMax;
    }

    const response = await googleCalendar.events.list(params);

    const events = response.data.items || [];\    return events.map(convertFromGoogleEvent);
  } catch (error) {
    googleCalendarLogger.error('Error listing Google Calendar events:', error);
    return [];
  }
};

// Create a utility logger for this module
export const googleCalendarLogger = {
  info: console.log.bind(console, '[GoogleCalendar] INFO:'),\n  error: console.error.bind(console, '[GoogleCalendar] ERROR:'),\n  warn: console.warn.bind(console, '[GoogleCalendar] WARN:'),\n};"}
