import { listUpcomingEvents, createCalendarEvent, CalendarEvent, CreateEventResponse } from './calendarSkills'; // Adjust import if types are from '../types'

// If types are indeed from '../types', the import would look like:
// import { listUpcomingEvents, createCalendarEvent, listUpcomingGoogleMeetEvents, getGoogleMeetEventDetails } from './calendarSkills';
import * as calendarSkills from './calendarSkills';
import {
    CalendarEvent,
    CreateEventResponse,
    ListGoogleMeetEventsResponse,
    GetGoogleMeetEventDetailsResponse,
    ConferenceData,
    ConferenceEntryPoint,
    ConferenceSolution
} from '../types';
import { google, calendar_v3 } from 'googleapis';
import * as constants from '../_libs/constants';

// Mock the entire googleapis module
jest.mock('googleapis');

// Mock our constants module
jest.mock('../_libs/constants', () => ({
  ATOM_GOOGLE_CALENDAR_CLIENT_ID: 'test_client_id',
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET: 'test_client_secret',
}));

// Typecast the mocked googleapis
const mockedGoogle = google as jest.Mocked<typeof google>;

// Mock implementation for OAuth2 client and calendar API
const mockEventsList = jest.fn();
const mockEventsInsert = jest.fn();
const mockEventsGet = jest.fn(); // For getCalendarEventById and getGoogleMeetEventDetails
const mockSetCredentials = jest.fn();

mockedGoogle.auth.OAuth2 = jest.fn().mockImplementation(() => ({
  setCredentials: mockSetCredentials,
  // Mock other OAuth2 methods if needed, e.g., for token refresh listener
  on: jest.fn(),
}));

mockedGoogle.calendar = jest.fn().mockImplementation(() => ({
  events: {
    list: mockEventsList,
    insert: mockEventsInsert,
    get: mockEventsGet, // Added mock for get
  },
}));

// Helper function to create mock Google API event data
const createMockGoogleApiEvent = (
    id: string,
    summary: string,
    startTime: string,
    endTime: string,
    conferenceData?: calendar_v3.Schema$ConferenceData,
    description?: string,
    location?: string,
    htmlLink?: string
): calendar_v3.Schema$Event => ({
    id,
    summary,
    start: { dateTime: startTime },
    end: { dateTime: endTime },
    conferenceData: conferenceData || undefined, // Ensure it's undefined if not provided, not null
    description: description || undefined,
    location: location || undefined,
    htmlLink: htmlLink || undefined,
});

const mockMeetConferenceData: calendar_v3.Schema$ConferenceData = {
    conferenceSolution: { key: { type: 'hangoutsMeet' }, name: 'Google Meet', iconUri: 'icon-meet' },
    entryPoints: [{ entryPointType: 'video', uri: 'https://meet.google.com/xyz-pdq-abc', label: 'meet.google.com/xyz-pdq-abc' }],
    conferenceId: 'xyz-pdq-abc',
};

const mockNonMeetConferenceData: calendar_v3.Schema$ConferenceData = {
    conferenceSolution: { key: { type: 'otherSolution' }, name: 'Other Conf', iconUri: 'icon-other' },
    entryPoints: [{ entryPointType: 'video', uri: 'https://otherservice.com/xyz' }],
    conferenceId: 'other-xyz',
};


// Helper to spy on getStoredUserTokens and saveUserTokens if they were not part of the module's export
// For this test, we will assume they are internal and their effect is tested via the exported functions.
// If they were exported, we could mock them:
// jest.mock('./calendarSkills', () => {
//   const originalModule = jest.requireActual('./calendarSkills');
//   return {
//     ...originalModule,
//     getStoredUserTokens: jest.fn(), // if it were exported
//   };
// });


describe('Calendar Skills with Google API Mocks', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset ATOM_GOOGLE_CALENDAR_CLIENT_ID and ATOM_GOOGLE_CALENDAR_CLIENT_SECRET to valid values for most tests
    Object.defineProperty(constants, 'ATOM_GOOGLE_CALENDAR_CLIENT_ID', { value: 'test_client_id', configurable: true });
    Object.defineProperty(constants, 'ATOM_GOOGLE_CALENDAR_CLIENT_SECRET', { value: 'test_client_secret', configurable: true });
  });

  describe('listUpcomingEvents', () => {
    it('should return empty array if no tokens are found for user', async () => {
      // getStoredUserTokens is internal, so we test its behavior by providing a userId that won't return mock tokens
      const events = await calendarSkills.listUpcomingEvents('unknown_user_id');
      expect(events).toEqual([]);
      expect(google.auth.OAuth2).not.toHaveBeenCalled(); // OAuth client shouldn't even be created
    });

    it('should return empty array if client ID or secret is missing', async () => {
      Object.defineProperty(constants, 'ATOM_GOOGLE_CALENDAR_CLIENT_ID', { value: undefined, configurable: true });
      const events = await calendarSkills.listUpcomingEvents('mock_user_id');
      expect(events).toEqual([]);
      expect(google.auth.OAuth2).not.toHaveBeenCalled();

      Object.defineProperty(constants, 'ATOM_GOOGLE_CALENDAR_CLIENT_ID', { value: 'test_client_id', configurable: true }); // restore
      Object.defineProperty(constants, 'ATOM_GOOGLE_CALENDAR_CLIENT_SECRET', { value: undefined, configurable: true });
      const events2 = await calendarSkills.listUpcomingEvents('mock_user_id');
      expect(events2).toEqual([]);
      expect(google.auth.OAuth2).not.toHaveBeenCalled();
    });

    it('should call Google API and map events correctly on success', async () => {
      const mockGoogleEvents = {
        data: {
          items: [
            { id: 'g_event1', summary: 'Google Event 1', description: 'Desc 1', start: { dateTime: '2024-04-01T10:00:00Z' }, end: { dateTime: '2024-04-01T11:00:00Z' }, location: 'Location 1', htmlLink: 'link1' },
            { id: 'g_event2', summary: 'Google Event 2', start: { date: '2024-04-02' }, end: { date: '2024-04-03' } }, // All-day event
          ],
        },
      };
      mockEventsList.mockResolvedValue(mockGoogleEvents);

      const events = await calendarSkills.listUpcomingEvents('mock_user_id_for_list');

      expect(google.auth.OAuth2).toHaveBeenCalledWith('test_client_id', 'test_client_secret');
      expect(mockSetCredentials).toHaveBeenCalledWith(expect.objectContaining({ access_token: 'mock_access_token_from_storage' }));
      expect(mockEventsList).toHaveBeenCalledWith(expect.objectContaining({ calendarId: 'primary', maxResults: 10 }));

      expect(events.length).toBe(2);
      expect(events[0]).toEqual(expect.objectContaining({ // Use objectContaining for partial match if conferenceData is complex
        id: 'g_event1',
        summary: 'Google Event 1',
        description: 'Desc 1',
        startTime: '2024-04-01T10:00:00Z',
        endTime: '2024-04-01T11:00:00Z',
        location: 'Location 1',
        htmlLink: 'link1',
        conferenceData: undefined, // Explicitly check if not present
      }));
      expect(events[1].summary).toBe('Google Event 2');
      expect(events[1].startTime).toBe('2024-04-02'); // All-day start
    });

    it('should correctly map conferenceData when present in listUpcomingEvents', async () => {
        const eventWithMeet = createMockGoogleApiEvent('evt1', 'Meet Event', '2024-01-01T10:00:00Z', '2024-01-01T11:00:00Z', mockMeetConferenceData);
        mockEventsList.mockResolvedValue({ data: { items: [eventWithMeet] } });

        const events = await calendarSkills.listUpcomingEvents('mock_user_id_for_meet_list');
        expect(events.length).toBe(1);
        expect(events[0].conferenceData).toBeDefined();
        expect(events[0].conferenceData?.conferenceSolution?.key?.type).toBe('hangoutsMeet');
        expect(events[0].conferenceData?.entryPoints?.[0]?.uri).toBe('https://meet.google.com/xyz-pdq-abc');
    });


    it('should return empty array and log error if Google API call fails for list', async () => {
      mockEventsList.mockRejectedValue(new Error('Google API List Error'));
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {}); // Suppress console.error during test

      const events = await calendarSkills.listUpcomingEvents('mock_user_id_for_list_fail');

      expect(events).toEqual([]);
      expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining('Error fetching Google Calendar events'), 'Google API List Error');
      consoleErrorSpy.mockRestore();
    });

    it('should handle "invalid_grant" error specifically for list', async () => {
      const apiError = new Error('Token error') as any;
      apiError.response = { data: { error: 'invalid_grant' } };
      mockEventsList.mockRejectedValue(apiError);
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      await calendarSkills.listUpcomingEvents('mock_user_id_for_invalid_grant');
      expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining('Token error (invalid_grant)'));
      consoleErrorSpy.mockRestore();
    });
  });

  // Note: getCalendarEventById is not directly exported, so it's tested via getGoogleMeetEventDetails.
  // If it were exported, its tests would be similar to getGoogleMeetEventDetails' successful/not found cases.

  describe('getGoogleMeetEventDetails', () => {
    it('should fetch and map a single event with Google Meet data', async () => {
        const mockEventId = 'eventWithMeetDetails';
        const apiEvent = createMockGoogleApiEvent(mockEventId, 'Detailed Meet Event', '2024-01-01T14:00:00Z', '2024-01-01T15:00:00Z', mockMeetConferenceData);
        mockEventsGet.mockResolvedValue({ data: apiEvent }); // calendar.events.get returns { data: event }

        const result = await calendarSkills.getGoogleMeetEventDetails('mock_user_id', mockEventId);

        expect(result.ok).toBe(true);
        expect(result.event).toBeDefined();
        expect(result.event?.id).toBe(mockEventId);
        expect(result.event?.summary).toBe('Detailed Meet Event');
        expect(result.event?.conferenceData).toBeDefined();
        expect(result.event?.conferenceData?.conferenceSolution?.key?.type).toBe('hangoutsMeet');
        expect(result.event?.conferenceData?.entryPoints?.[0]?.uri).toBe('https://meet.google.com/xyz-pdq-abc');
        expect(mockEventsGet).toHaveBeenCalledWith({ calendarId: 'primary', eventId: mockEventId });
    });

    it('should return error if event not found (API returns 404)', async () => {
        const mockEventId = 'nonExistentEvent';
        const apiError = new Error('Not Found') as any;
        apiError.response = { status: 404, data: { error: { message: 'Event not found' } } }; // Mimic Google API error structure
        mockEventsGet.mockRejectedValue(apiError);
        const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});


        const result = await calendarSkills.getGoogleMeetEventDetails('mock_user_id', mockEventId);

        expect(result.ok).toBe(false);
        expect(result.error).toBe('Event not found or access denied.'); // This is the message from getGoogleMeetEventDetails
        expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining(`Error fetching event ${mockEventId}`), 'Not Found');
        expect(consoleLogSpy).toHaveBeenCalledWith(`Event ${mockEventId} not found.`);
        consoleErrorSpy.mockRestore();
    });

    it('should return the event even if it is not a Google Meet event', async () => {
        const mockEventId = 'eventWithoutMeet';
        const apiEvent = createMockGoogleApiEvent(mockEventId, 'Non-Meet Event', '2024-01-01T14:00:00Z', '2024-01-01T15:00:00Z', mockNonMeetConferenceData);
        mockEventsGet.mockResolvedValue({ data: apiEvent });

        const result = await calendarSkills.getGoogleMeetEventDetails('mock_user_id', mockEventId);
        expect(result.ok).toBe(true);
        expect(result.event).toBeDefined();
        expect(result.event?.id).toBe(mockEventId);
        expect(result.event?.conferenceData?.conferenceSolution?.key?.type).toBe('otherSolution');
        expect(consoleLogSpy).toHaveBeenCalledWith(`Event ${mockEventId} was found but does not appear to be a Google Meet event based on conferenceData.`);
    });

     it('should return error if getCalendarEventById returns null due to token issue', async () => {
        // Simulate getStoredUserTokens returning null for this user
        // This requires the ability to mock getStoredUserTokens or test this path another way.
        // For now, we assume getCalendarEventById itself would log and return null.
        // If getCalendarEventById is not exported, this tests the path where it returns null internally.
        mockEventsGet.mockImplementation(async () => { // Simulate internal failure of getCalendarEventById
            (calendarSkills as any).getStoredUserTokens = jest.fn().mockResolvedValueOnce(null); // Temporarily mock internal
            return Promise.resolve(null); // This mock needs to be more sophisticated for a real internal mock
        });
        // A simpler way: mock get to throw an error that getCalendarEventById would turn into null
        mockEventsGet.mockRejectedValue(new Error("Simulated token failure for getCalendarEventById"));


        const result = await calendarSkills.getGoogleMeetEventDetails('user_with_no_tokens', 'anyEventId');
        expect(result.ok).toBe(false);
        // The exact error message depends on how getCalendarEventById propagates the error or returns null.
        // Based on current getCalendarEventById, it would return null, leading to "Event not found or access denied."
        expect(result.error).toBe('Event not found or access denied.');
    });

  });

  describe('listUpcomingGoogleMeetEvents', () => {
    it('should return only events with valid Google Meet links', async () => {
        const event1Meet = createMockGoogleApiEvent('ev1', 'Meet Event 1', '2024-01-01T10:00:00Z', '2024-01-01T11:00:00Z', mockMeetConferenceData);
        const event2NonMeet = createMockGoogleApiEvent('ev2', 'Non-Meet Event', '2024-01-01T12:00:00Z', '2024-01-01T13:00:00Z', mockNonMeetConferenceData);
        const event3NoConf = createMockGoogleApiEvent('ev3', 'No Conference', '2024-01-01T14:00:00Z', '2024-01-01T15:00:00Z', undefined);
        const event4MeetNoVideoUri = createMockGoogleApiEvent('ev4', 'Meet No Video URI', '2024-01-01T16:00:00Z', '2024-01-01T17:00:00Z',
            { conferenceSolution: { key: { type: 'hangoutsMeet' } }, entryPoints: [{ entryPointType: 'phone', uri: 'tel:123' }] });

        mockEventsList.mockResolvedValue({ data: { items: [event1Meet, event2NonMeet, event3NoConf, event4MeetNoVideoUri] } });

        const result = await calendarSkills.listUpcomingGoogleMeetEvents('mock_user_id');
        expect(result.ok).toBe(true);
        expect(result.events).toBeDefined();
        expect(result.events?.length).toBe(1);
        expect(result.events?.[0].id).toBe('ev1');
        expect(result.events?.[0].conferenceData?.conferenceSolution?.key?.type).toBe('hangoutsMeet');
    });

    it('should respect the limit after filtering Meet events', async () => {
        const meetEventsData = [
            createMockGoogleApiEvent('m1', 'Meet 1', '2024-01-01T10:00:00Z', '2024-01-01T11:00:00Z', mockMeetConferenceData),
            createMockGoogleApiEvent('m2', 'Meet 2', '2024-01-02T10:00:00Z', '2024-01-02T11:00:00Z', mockMeetConferenceData),
            createMockGoogleApiEvent('m3', 'Meet 3', '2024-01-03T10:00:00Z', '2024-01-03T11:00:00Z', mockMeetConferenceData),
        ];
        mockEventsList.mockResolvedValue({ data: { items: meetEventsData } });

        const result = await calendarSkills.listUpcomingGoogleMeetEvents('mock_user_id', 2);
        expect(result.ok).toBe(true);
        expect(result.events?.length).toBe(2);
        expect(result.events?.[0].id).toBe('m1');
        expect(result.events?.[1].id).toBe('m2');
    });

    it('should return empty array if listUpcomingEvents returns no events', async () => {
        mockEventsList.mockResolvedValue({ data: { items: [] } });
        const result = await calendarSkills.listUpcomingGoogleMeetEvents('mock_user_id');
        expect(result.ok).toBe(true);
        expect(result.events).toEqual([]);
    });

    it('should return empty array if no events are Google Meet events', async () => {
        const nonMeetEvents = [
            createMockGoogleApiEvent('nm1', 'Non-Meet 1', '2024-01-01T10:00:00Z', '2024-01-01T11:00:00Z', mockNonMeetConferenceData),
            createMockGoogleApiEvent('nm2', 'No Conf 1', '2024-01-02T10:00:00Z', '2024-01-02T11:00:00Z', undefined),
        ];
        mockEventsList.mockResolvedValue({ data: { items: nonMeetEvents } });
        const result = await calendarSkills.listUpcomingGoogleMeetEvents('mock_user_id');
        expect(result.ok).toBe(true);
        expect(result.events).toEqual([]);
    });

    it('should handle errors from listUpcomingEvents', async () => {
        mockEventsList.mockRejectedValue(new Error("Failed to fetch from Google API"));
        const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
        const result = await calendarSkills.listUpcomingGoogleMeetEvents('mock_user_id');
        expect(result.ok).toBe(false);
        expect(result.error).toContain('Failed to list Google Meet events: Failed to fetch from Google API');
        expect(consoleErrorSpy).toHaveBeenCalledWith('Error listing Google Meet events:', 'Failed to fetch from Google API');
        consoleErrorSpy.mockRestore();
    });

  });

  describe('createCalendarEvent', () => {
    const eventDetails: Partial<CalendarEvent> = {
      summary: 'New Test Event',
      startTime: '2024-04-25T10:00:00Z',
      endTime: '2024-04-25T11:00:00Z',
      description: 'A test event.',
      location: 'Test Location'
    };

    it('should return auth error if no tokens are found', async () => {
      const response = await calendarSkills.createCalendarEvent('unknown_user_id', eventDetails);
      expect(response.success).toBe(false);
      expect(response.message).toBe('Authentication required. No tokens found.');
      expect(google.auth.OAuth2).not.toHaveBeenCalled();
    });

    it('should return config error if client ID or secret is missing', async () => {
      Object.defineProperty(constants, 'ATOM_GOOGLE_CALENDAR_CLIENT_ID', { value: undefined, configurable: true });
      let response = await calendarSkills.createCalendarEvent('mock_user_id', eventDetails);
      expect(response.success).toBe(false);
      expect(response.message).toBe('Server configuration error for calendar service.');

      Object.defineProperty(constants, 'ATOM_GOOGLE_CALENDAR_CLIENT_ID', { value: 'test_client_id', configurable: true });
      Object.defineProperty(constants, 'ATOM_GOOGLE_CALENDAR_CLIENT_SECRET', { value: undefined, configurable: true });
      response = await calendarSkills.createCalendarEvent('mock_user_id', eventDetails);
      expect(response.success).toBe(false);
      expect(response.message).toBe('Server configuration error for calendar service.');
    });

    it('should return error if required event details are missing', async () => {
      const response = await calendarSkills.createCalendarEvent('mock_user_id', { summary: 'Only summary' });
      expect(response.success).toBe(false);
      expect(response.message).toContain('Missing required event details');
    });

    it('should call Google API and return success on event creation', async () => {
      const mockGoogleCreatedEvent = {
        data: {
          id: 'created_g_event1',
          summary: eventDetails.summary,
          htmlLink: 'created_link1',
        },
      };
      mockEventsInsert.mockResolvedValue(mockGoogleCreatedEvent);

      const response = await calendarSkills.createCalendarEvent('mock_user_id_for_create', eventDetails);

      expect(google.auth.OAuth2).toHaveBeenCalledWith('test_client_id', 'test_client_secret');
      expect(mockSetCredentials).toHaveBeenCalledWith(expect.objectContaining({ access_token: 'mock_access_token_from_storage' }));
      expect(mockEventsInsert).toHaveBeenCalledWith(expect.objectContaining({
        calendarId: 'primary',
        requestBody: expect.objectContaining({
          summary: eventDetails.summary,
          description: eventDetails.description,
          location: eventDetails.location,
          start: { dateTime: eventDetails.startTime },
          end: { dateTime: eventDetails.endTime },
        }),
      }));

      expect(response.success).toBe(true);
      expect(response.eventId).toBe('created_g_event1');
      expect(response.htmlLink).toBe('created_link1');
      expect(response.message).toContain('Calendar event created successfully with Google Calendar.');
    });

    it('should return failure and log error if Google API call fails for insert', async () => {
      mockEventsInsert.mockRejectedValue(new Error('Google API Insert Error'));
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      const response = await calendarSkills.createCalendarEvent('mock_user_id_for_create_fail', eventDetails);

      expect(response.success).toBe(false);
      expect(response.message).toContain('Failed to create event with Google Calendar: Google API Insert Error');
      expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining('Error creating Google Calendar event'), 'Google API Insert Error');
      consoleErrorSpy.mockRestore();
    });

    it('should handle "invalid_grant" error specifically for insert', async () => {
      const apiError = new Error('Token error') as any;
      apiError.response = { data: { error: 'invalid_grant' } };
      mockEventsInsert.mockRejectedValue(apiError);
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      await calendarSkills.createCalendarEvent('mock_user_id_for_invalid_grant_insert', eventDetails);
      expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining('Token error (invalid_grant)'));
      consoleErrorSpy.mockRestore();
    });
  });
});
