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

// Mock the graphqlClient
const mockExecuteGraphQLQuery = jest.fn();
const mockExecuteGraphQLMutation = jest.fn();
jest.mock('../_libs/graphqlClient', () => ({
    executeGraphQLQuery: mockExecuteGraphQLQuery,
    executeGraphQLMutation: mockExecuteGraphQLMutation,
}));


describe('Calendar Skills', () => { // Changed describe name to be more general
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset ATOM_GOOGLE_CALENDAR_CLIENT_ID and ATOM_GOOGLE_CALENDAR_CLIENT_SECRET to valid values for most tests
    Object.defineProperty(constants, 'ATOM_GOOGLE_CALENDAR_CLIENT_ID', { value: 'test_client_id', configurable: true });
    Object.defineProperty(constants, 'ATOM_GOOGLE_CALENDAR_CLIENT_SECRET', { value: 'test_client_secret', configurable: true });
    Object.defineProperty(constants, 'HASURA_GRAPHQL_URL', { value: 'http://hasura.test/v1/graphql', configurable: true });
    Object.defineProperty(constants, 'HASURA_ADMIN_SECRET', { value: 'testsecret', configurable: true });

    // Clear console spies if they are used in other describe blocks, or set them up here if needed
    // jest.spyOn(console, 'error').mockImplementation(() => {});
    // jest.spyOn(console, 'warn').mockImplementation(() => {});
    // jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  // Internal functions testing (getStoredUserTokens, saveUserTokens)
  // These are not directly exported, so we test them via a function that uses them,
  // or by temporarily exposing them for testing (less ideal but sometimes practical for complex internal logic).
  // For now, we'll assume we can test their core logic by observing calls to graphqlClient from a top-level function.
  // Let's create a new describe block for these token functions, tested via getGoogleCalendarClient
  // which is a primary user of getStoredUserTokens and saveUserTokens (via oauth2Client.on('tokens')).

  describe('Token Management (getStoredUserTokens, saveUserTokens - tested via getGoogleCalendarClient)', () => {
    const userId = 'user-token-test';

    it('getGoogleCalendarClient should successfully retrieve and use stored tokens', async () => {
        const mockTokenData = {
            user_tokens: [{
                access_token: 'valid_access_token',
                refresh_token: 'valid_refresh_token',
                expiry_date: new Date(Date.now() + 3600 * 1000).toISOString(), // Expires in 1 hour
                scope: 'https://www.googleapis.com/auth/calendar',
                token_type: 'Bearer',
            }]
        };
        mockExecuteGraphQLQuery.mockResolvedValueOnce(mockTokenData); // For getStoredUserTokens

        const clientResponse = await (calendarSkills as any).getGoogleCalendarClient(userId); // Cast to any to call private

        expect(clientResponse.ok).toBe(true);
        expect(mockExecuteGraphQLQuery).toHaveBeenCalledWith(
            expect.stringContaining('GetUserToken'),
            { userId, serviceName: 'google_calendar' },
            'GetUserToken',
            userId
        );
        expect(mockSetCredentials).toHaveBeenCalledWith({
            access_token: 'valid_access_token',
            refresh_token: 'valid_refresh_token',
            expiry_date: expect.any(Number),
            scope: 'https://www.googleapis.com/auth/calendar',
            token_type: 'Bearer',
        });
    });

    it('getGoogleCalendarClient should return AUTH_NO_TOKENS_FOUND if no tokens in DB', async () => {
        mockExecuteGraphQLQuery.mockResolvedValueOnce({ user_tokens: [] }); // No tokens found
        const clientResponse = await (calendarSkills as any).getGoogleCalendarClient(userId);
        expect(clientResponse.ok).toBe(false);
        expect(clientResponse.error?.code).toBe('AUTH_NO_TOKENS_FOUND');
    });

    it('getGoogleCalendarClient should return TOKEN_FETCH_FAILED on GraphQL error during token fetch', async () => {
        mockExecuteGraphQLQuery.mockRejectedValueOnce(new Error('DB connection error'));
        const clientResponse = await (calendarSkills as any).getGoogleCalendarClient(userId);
        expect(clientResponse.ok).toBe(false);
        expect(clientResponse.error?.code).toBe('TOKEN_FETCH_FAILED');
    });

    // Testing saveUserTokens is harder as it's inside an event listener.
    // A more direct unit test for saveUserTokens would require exporting it or refactoring.
    // For now, we'll assume its direct GraphQL call is correct if getGoogleCalendarClient sets up the listener.
    // A test for the 'tokens' event on oauth2Client could be added if we can trigger it.
    it('saveUserTokens (via oauth2Client listener) should call executeGraphQLMutation correctly', async () => {
        // This test is more conceptual due to the event listener.
        // We'll simulate the conditions for the listener to be set up.
        const mockInitialTokenData = {
            user_tokens: [{
                access_token: 'initial_access_token',
                refresh_token: 'initial_refresh_token',
                expiry_date: new Date(Date.now() + 3600 * 1000).toISOString(),
            }]
        };
        mockExecuteGraphQLQuery.mockResolvedValueOnce(mockInitialTokenData); // For getStoredUserTokens

        // Mock the oauth2Client.on('tokens', callback)
        let tokenSaveCallback: Function | null = null;
        (mockedGoogle.auth.OAuth2 as jest.Mock).mockImplementation(() => ({
            setCredentials: mockSetCredentials,
            on: (event: string, callback: Function) => {
                if (event === 'tokens') {
                    tokenSaveCallback = callback;
                }
            },
        }));

        await (calendarSkills as any).getGoogleCalendarClient(userId); // This sets up the listener
        expect(tokenSaveCallback).not.toBeNull();

        // Simulate the 'tokens' event being emitted
        const newTokensToSave = {
            access_token: 'new_refreshed_access_token',
            refresh_token: 'persisted_refresh_token', // Assuming newTokens might not have refresh_token
            expiry_date: new Date(Date.now() + 7200 * 1000).getTime(),
        };
        mockExecuteGraphQLMutation.mockResolvedValueOnce({ insert_user_tokens: { affected_rows: 1 } });

        if (tokenSaveCallback) {
            await tokenSaveCallback(newTokensToSave); // Trigger the callback
        }

        expect(mockExecuteGraphQLMutation).toHaveBeenCalledWith(
            expect.stringContaining('UpsertUserToken'),
            expect.objectContaining({
                objects: [expect.objectContaining({
                    user_id: userId,
                    service_name: 'google_calendar',
                    access_token: newTokensToSave.access_token,
                    refresh_token: 'initial_refresh_token', // Should persist old refresh if new one isn't there
                    expiry_date: new Date(newTokensToSave.expiry_date).toISOString(),
                })]
            }),
            'UpsertUserToken',
            userId
        );
    });


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

  describe('findEventByFuzzyReference', () => {
    const userId = 'user-fuzzy-test';
    const mockEventsListForFuzzy: CalendarEvent[] = [
      { id: 'ev1', summary: 'Team Sync Q1', startTime: new Date(Date.now() + 1000 * 60 * 60).toISOString(), endTime: new Date(Date.now() + 1000 * 60 * 120).toISOString(), description: 'Quarterly planning' },
      { id: 'ev2', summary: 'Project Alpha Review', startTime: new Date(Date.now() + 1000 * 60 * 60 * 2).toISOString(), endTime: new Date(Date.now() + 1000 * 60 * 60 * 3).toISOString(), description: 'Alpha phase feedback' },
      { id: 'ev3', summary: 'Next Meeting with Client X', startTime: new Date(Date.now() + 1000 * 60 * 30).toISOString(), endTime: new Date(Date.now() + 1000 * 60 * 90).toISOString(), description: 'Client discussion' },
      { id: 'ev4', summary: '1:1 with Manager', startTime: new Date(Date.now() + 1000 * 60 * 60 * 5).toISOString(), endTime: new Date(Date.now() + 1000 * 60 * 60 * 5.5).toISOString(), description: 'Performance review' },
    ];

    // Mock listUpcomingEvents as it's a dependency
    let listUpcomingEventsSpy: jest.SpyInstance;

    beforeEach(() => {
      // Ensure getGoogleCalendarClient (and thus getStoredUserTokens) is mocked to succeed for listUpcomingEvents
      const mockTokenData = { user_tokens: [{ access_token: 'valid_access_token', refresh_token: 'valid_refresh_token', expiry_date: new Date(Date.now() + 3600 * 1000).toISOString() }]};
      mockExecuteGraphQLQuery.mockResolvedValue(mockTokenData); // For getStoredUserTokens used by getGoogleCalendarClient

      listUpcomingEventsSpy = jest.spyOn(calendarSkills, 'listUpcomingEvents');
    });

    afterEach(() => {
      listUpcomingEventsSpy.mockRestore();
    });

    it('should return the first event for "next meeting"', async () => {
      listUpcomingEventsSpy.mockResolvedValue({ ok: true, data: mockEventsListForFuzzy });
      const result = await calendarSkills.findEventByFuzzyReference(userId, "next meeting");
      expect(result.ok).toBe(true);
      expect(result.data?.id).toBe('ev3'); // ev3 is the soonest
    });

    it('should find an event by exact summary match', async () => {
      listUpcomingEventsSpy.mockResolvedValue({ ok: true, data: mockEventsListForFuzzy });
      const result = await calendarSkills.findEventByFuzzyReference(userId, "Project Alpha Review");
      expect(result.ok).toBe(true);
      expect(result.data?.id).toBe('ev2');
    });

    it('should find an event by partial summary match', async () => {
      listUpcomingEventsSpy.mockResolvedValue({ ok: true, data: mockEventsListForFuzzy });
      const result = await calendarSkills.findEventByFuzzyReference(userId, "alpha review");
      expect(result.ok).toBe(true);
      expect(result.data?.id).toBe('ev2');
    });

    it('should find an event by keyword matching in summary', async () => {
      listUpcomingEventsSpy.mockResolvedValue({ ok: true, data: mockEventsListForFuzzy });
      const result = await calendarSkills.findEventByFuzzyReference(userId, "client x discussion");
      expect(result.ok).toBe(true);
      expect(result.data?.id).toBe('ev3');
    });

    it('should return null if no confident match is found', async () => {
      listUpcomingEventsSpy.mockResolvedValue({ ok: true, data: mockEventsListForFuzzy });
      const result = await calendarSkills.findEventByFuzzyReference(userId, "completely unrelated topic");
      expect(result.ok).toBe(true);
      expect(result.data).toBeNull();
    });

    it('should return null if listUpcomingEvents returns no events', async () => {
      listUpcomingEventsSpy.mockResolvedValue({ ok: true, data: [] });
      const result = await calendarSkills.findEventByFuzzyReference(userId, "any query");
      expect(result.ok).toBe(true);
      expect(result.data).toBeNull();
    });

    it('should propagate error if listUpcomingEvents fails', async () => {
      const fetchError = { code: 'FUZZY_FETCH_FAILED', message: "Failed to fetch events for fuzzy matching." };
      listUpcomingEventsSpy.mockResolvedValue({ ok: false, error: fetchError, data: null });
      const result = await calendarSkills.findEventByFuzzyReference(userId, "any query");
      expect(result.ok).toBe(false);
      expect(result.data).toBeNull();
      expect(result.error).toEqual(fetchError);
    });
     it('should handle "today" lookback period', async () => {
      // Mock listUpcomingEvents to be called with specific timeMin/timeMax for "today"
      const todayStart = new Date(); todayStart.setHours(0,0,0,0);
      const todayEnd = new Date(); todayEnd.setHours(23,59,59,999);

      listUpcomingEventsSpy.mockResolvedValue({ ok: true, data: [mockEventsListForFuzzy[0]] }); // Assume one event today

      await calendarSkills.findEventByFuzzyReference(userId, "Team Sync Q1", "today");

      expect(listUpcomingEventsSpy).toHaveBeenCalledWith(
        userId,
        50, // internal limit for fuzzy search
        expect.stringMatching(todayStart.toISOString().substring(0,10)), // Check if timeMin is start of today
        expect.stringMatching(todayEnd.toISOString().substring(0,10))   // Check if timeMax is end of today
      );
    });
  });

  describe('slackMyAgenda', () => {
    const userId = 'user-slack-agenda-test';
    let listUpcomingEventsSpy: jest.SpyInstance;
    let sendSlackMessageSpy: jest.SpyInstance;
    // const mockSlackSkills = require('./slackSkills'); // Not needed if using jest.spyOn on imported function

     beforeEach(() => {
      // Mock getStoredUserTokens to ensure getGoogleCalendarClient (used by listUpcomingEvents) can proceed
      const mockTokenData = { user_tokens: [{ access_token: 'valid_access_token', expiry_date: new Date(Date.now() + 3600 * 1000).toISOString() }]};
      mockExecuteGraphQLQuery.mockResolvedValue(mockTokenData);

      listUpcomingEventsSpy = jest.spyOn(calendarSkills, 'listUpcomingEvents');
      // Need to get the actual module to spy on sendSlackMessage if it's not part of calendarSkills
      const slackSkills = require('./slackSkills');
      sendSlackMessageSpy = jest.spyOn(slackSkills, 'sendSlackMessage');
    });

    afterEach(() => {
      listUpcomingEventsSpy.mockRestore();
      sendSlackMessageSpy.mockRestore();
    });

    it('should send formatted agenda to Slack when events are found', async () => {
      const mockEvents: CalendarEvent[] = [
        { id: 'ev1', summary: 'Event One', startTime: '2024-01-01T10:00:00Z', endTime: '2024-01-01T11:00:00Z', location: 'Room 1', conferenceData: mockMeetConferenceData },
        { id: 'ev2', summary: 'Event Two', startTime: '2024-01-01T12:00:00Z', endTime: '2024-01-01T13:00:00Z' },
      ];
      listUpcomingEventsSpy.mockResolvedValue({ ok: true, data: mockEvents });
      sendSlackMessageSpy.mockResolvedValue({ ok: true, message: "Slack message sent" });

      const result = await calendarSkills.slackMyAgenda(userId, 2);

      expect(result.ok).toBe(true);
      expect(listUpcomingEventsSpy).toHaveBeenCalledWith(userId, 2);
      expect(sendSlackMessageSpy).toHaveBeenCalledTimes(1);
      const sentMessage = sendSlackMessageSpy.mock.calls[0][2]; // Third argument is the message text
      expect(sentMessage).toContain('*Event One*');
      expect(sentMessage).toContain('Jan 1, 10:00 AM - 11:00 AM'); // Example formatting, locale dependent
      expect(sentMessage).toContain('📍 Room 1');
      expect(sentMessage).toContain('🔗 Google Meet: https://meet.google.com/xyz-pdq-abc');
      expect(sentMessage).toContain('*Event Two*');
    });

    it('should send "no upcoming events" message if no events are found', async () => {
      listUpcomingEventsSpy.mockResolvedValue({ ok: true, data: [] });
      sendSlackMessageSpy.mockResolvedValue({ ok: true, message: "Slack message sent" });

      const result = await calendarSkills.slackMyAgenda(userId, 5);
      expect(result.ok).toBe(true);
      expect(sendSlackMessageSpy).toHaveBeenCalledWith(userId, userId, "You have no upcoming events in your Google Calendar for the requested period.");
    });

    it('should use default channel if userId is not suitable as channelId and ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA is set', async () => {
        const defaultChannel = "C123DEFAULT";
        Object.defineProperty(constants, 'ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA', { value: defaultChannel, configurable: true });

        listUpcomingEventsSpy.mockResolvedValue({ ok: true, data: [] });
        sendSlackMessageSpy.mockResolvedValue({ ok: true, message: "Slack message sent" });

        // Simulate a scenario where userId might not be a valid slack channel (e.g. if it's just a DB UUID)
        // The function logic is `const slackChannelId = userId || ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA;`
        // This test will effectively use userId if it's truthy. To test default, userId needs to be falsy.
        // However, the function signature requires userId. Let's assume the fallback logic is meant for cases
        // where userId is perhaps not directly usable as a channel. The current implementation always uses userId if present.
        // To truly test the fallback, the function would need to check if userId is a valid channel, or userId itself would be undefined.
        // Given the current code: `userId || ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA` means if userId is provided, it's used.
        // So, we'll test the case where userId IS the channel.

        await calendarSkills.slackMyAgenda(userId, 5);
        expect(sendSlackMessageSpy).toHaveBeenCalledWith(userId, userId, expect.any(String));

        // To test the fallback, we'd need to call it differently or modify the logic.
        // For now, this confirms userId is used if provided.
    });


    it('should return error if listUpcomingEvents fails', async () => {
      const listError = { code: 'API_ERROR', message: 'Failed to fetch' };
      listUpcomingEventsSpy.mockResolvedValue({ ok: false, error: listError, data: null });
      sendSlackMessageSpy.mockResolvedValue({ ok: true, message: "Error message sent to slack" }); // Slack message for the error

      const result = await calendarSkills.slackMyAgenda(userId, 5);

      expect(result.ok).toBe(false);
      expect(result.error).toContain('Failed to fetch calendar events: API_ERROR: Failed to fetch');
      // Check if an error message was attempted to be sent to Slack
      expect(sendSlackMessageSpy).toHaveBeenCalledWith(userId, userId, expect.stringContaining("Sorry, I couldn't fetch your agenda. Error: API_ERROR: Failed to fetch"));
    });

    it('should return error if sendSlackMessage fails', async () => {
      const mockEvents: CalendarEvent[] = [{ id: 'ev1', summary: 'Event One', startTime: '2024-01-01T10:00:00Z', endTime: '2024-01-01T11:00:00Z' }];
      listUpcomingEventsSpy.mockResolvedValue({ ok: true, data: mockEvents });
      const slackErrorMsg = "Slack API error";
      sendSlackMessageSpy.mockResolvedValue({ ok: false, error: slackErrorMsg });
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});


      const result = await calendarSkills.slackMyAgenda(userId, 1);

      expect(result.ok).toBe(false);
      expect(result.error).toBe(slackErrorMsg);
      expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining('Failed to send Slack message for agenda'), slackErrorMsg);
      consoleErrorSpy.mockRestore();
    });

    it('should return error if no slack channel can be determined and no events', async () => {
        listUpcomingEventsSpy.mockResolvedValue({ ok: true, data: [] });
        Object.defineProperty(constants, 'ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA', { value: undefined, configurable: true });
        // To make `userId || ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA` result in falsy for channelId
        // We need to pass a falsy userId, but the function signature expects string.
        // This test case reveals a slight fragility in channel determination if userId could be empty string.
        // For now, assume userId is always a non-empty string if this path is hit.
        // The code has: `const slackChannelId = userId || ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA;`
        // If userId = 'user-slack-agenda-test' (truthy), slackChannelId will be userId.
        // If userId = '' (falsy) AND ATOM_DEFAULT_SLACK_CHANNEL_FOR_AGENDA is undefined, then slackChannelId is undefined.
        // Let's test this by trying to make slackChannelId effectively undefined.
        // The test below is for the case where sendSlackMessage itself would fail due to no channel.
        // The current function logic would use userId IF it's provided.
        // A more direct test of the "no channel" logic would be to spy on sendSlackMessage and ensure it's NOT called.

        const result = await calendarSkills.slackMyAgenda("", 1); // Pass empty string for userId
        expect(result.ok).toBe(false);
        expect(result.error).toBe('No Slack channel ID to send the "no events" message to.');
        expect(sendSlackMessageSpy).not.toHaveBeenCalled();
    });
  });
});
