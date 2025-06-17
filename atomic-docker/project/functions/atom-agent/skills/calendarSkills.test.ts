import { listUpcomingEvents, createCalendarEvent, CalendarEvent, CreateEventResponse } from './calendarSkills'; // Adjust import if types are from '../types'

// If types are indeed from '../types', the import would look like:
// import { listUpcomingEvents, createCalendarEvent } from './calendarSkills';
import * as calendarSkills from './calendarSkills';
import { CalendarEvent, CreateEventResponse } from '../types';
import { google } from 'googleapis';
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
  },
}));


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
      expect(events[0]).toEqual({
        id: 'g_event1',
        summary: 'Google Event 1',
        description: 'Desc 1',
        startTime: '2024-04-01T10:00:00Z',
        endTime: '2024-04-01T11:00:00Z',
        location: 'Location 1',
        htmlLink: 'link1',
      });
      expect(events[1].summary).toBe('Google Event 2');
      expect(events[1].startTime).toBe('2024-04-02'); // All-day start
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
