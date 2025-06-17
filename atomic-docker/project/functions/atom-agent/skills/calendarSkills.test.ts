import * as calendarSkills from './calendarSkills';
import { CalendarEvent, CreateEventResponse } from '../types';
import { google } from 'googleapis';
import * as constants from '../_libs/constants';
import * as tokenUtils from '../_libs/token-utils';

// Mock the entire googleapis module
jest.mock('googleapis');

// Mock our constants module
jest.mock('../_libs/constants', () => ({
  ATOM_GOOGLE_CALENDAR_CLIENT_ID: 'test_client_id',
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET: 'test_client_secret',
}));

// Mock token-utils
jest.mock('../_libs/token-utils', () => ({
  getAtomGoogleCalendarTokens: jest.fn(),
  saveAtomGoogleCalendarTokens: jest.fn(),
}));

// Typecast the mocked modules
const mockedGoogle = google as jest.Mocked<typeof google>;
const mockedTokenUtils = tokenUtils as jest.Mocked<typeof tokenUtils>;

// Mock implementation for OAuth2 client and calendar API
const mockEventsList = jest.fn();
const mockEventsInsert = jest.fn();
const mockSetCredentials = jest.fn();
const mockOn = jest.fn(); // To mock the .on('tokens', ...) listener

// This will be the object returned by new google.auth.OAuth2()
const mockOAuth2ClientInstance = {
  setCredentials: mockSetCredentials,
  on: mockOn,
};

mockedGoogle.auth.OAuth2 = jest.fn().mockImplementation(() => mockOAuth2ClientInstance);

mockedGoogle.calendar = jest.fn().mockImplementation(() => ({
  events: {
    list: mockEventsList,
    insert: mockEventsInsert,
  },
}));

describe('Calendar Skills with Real Token Utilities and Google API Mocks', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Ensure constants are set for each test if they can be modified by tests
    Object.defineProperty(constants, 'ATOM_GOOGLE_CALENDAR_CLIENT_ID', { value: 'test_client_id', configurable: true, writable: true });
    Object.defineProperty(constants, 'ATOM_GOOGLE_CALENDAR_CLIENT_SECRET', { value: 'test_client_secret', configurable: true, writable: true });
  });

  describe('listUpcomingEvents', () => {
    it('should return empty array if no tokens are found for user', async () => {
      mockedTokenUtils.getAtomGoogleCalendarTokens.mockResolvedValue(null);
      const events = await calendarSkills.listUpcomingEvents('unknown_user_id');
      expect(events).toEqual([]);
      expect(google.auth.OAuth2).not.toHaveBeenCalled();
      expect(mockedTokenUtils.getAtomGoogleCalendarTokens).toHaveBeenCalledWith('unknown_user_id');
    });

    it('should return empty array if client ID or secret is missing from constants', async () => {
      mockedTokenUtils.getAtomGoogleCalendarTokens.mockResolvedValue({ access_token: 'valid_mock_token', expiry_date: Date.now() + 3600000, refresh_token: 'mock_refresh' });

      // @ts-ignore
      constants.ATOM_GOOGLE_CALENDAR_CLIENT_ID = undefined;
      let events = await calendarSkills.listUpcomingEvents('mock_user_id');
      expect(events).toEqual([]);
      expect(google.auth.OAuth2).not.toHaveBeenCalled();

      // @ts-ignore
      constants.ATOM_GOOGLE_CALENDAR_CLIENT_ID = 'test_client_id'; // restore
      // @ts-ignore
      constants.ATOM_GOOGLE_CALENDAR_CLIENT_SECRET = undefined;
      events = await calendarSkills.listUpcomingEvents('mock_user_id');
      expect(events).toEqual([]);
      expect(google.auth.OAuth2).not.toHaveBeenCalled();
    });

    it('should call Google API and map events correctly on success', async () => {
      const mockStoredTokens = {
        access_token: 'valid_access_token',
        refresh_token: 'valid_refresh_token',
        expiry_date: Date.now() + 3600000,
        scope: 'https://www.googleapis.com/auth/calendar',
        token_type: 'Bearer'
      };
      mockedTokenUtils.getAtomGoogleCalendarTokens.mockResolvedValue(mockStoredTokens);

      const mockGoogleEvents = {
        data: {
          items: [
            { id: 'g_event1', summary: 'Google Event 1', description: 'Desc 1', start: { dateTime: '2024-04-01T10:00:00Z' }, end: { dateTime: '2024-04-01T11:00:00Z' }, location: 'Location 1', htmlLink: 'link1' },
            { id: 'g_event2', summary: 'Google Event 2', start: { date: '2024-04-02' }, end: { date: '2024-04-03' } },
          ],
        },
      };
      mockEventsList.mockResolvedValue(mockGoogleEvents);

      const events = await calendarSkills.listUpcomingEvents('mock_user_id_for_list', 5);

      expect(mockedTokenUtils.getAtomGoogleCalendarTokens).toHaveBeenCalledWith('mock_user_id_for_list');
      expect(google.auth.OAuth2).toHaveBeenCalledWith('test_client_id', 'test_client_secret');
      expect(mockSetCredentials).toHaveBeenCalledWith(mockStoredTokens);
      expect(mockEventsList).toHaveBeenCalledWith(expect.objectContaining({ calendarId: 'primary', maxResults: 5 }));

      expect(events.length).toBe(2);
      expect(events[0]).toEqual(expect.objectContaining({ id: 'g_event1', summary: 'Google Event 1' }));
      expect(events[1]).toEqual(expect.objectContaining({ id: 'g_event2', summary: 'Google Event 2' }));
    });

    it('should return empty array and log error if Google API call fails', async () => {
      mockedTokenUtils.getAtomGoogleCalendarTokens.mockResolvedValue({ access_token: 'valid_token', expiry_date: Date.now() + 3600000, refresh_token: 'refresh' });
      mockEventsList.mockRejectedValue(new Error('Google API List Error'));
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      const events = await calendarSkills.listUpcomingEvents('mock_user_id_for_list_fail');
      expect(events).toEqual([]);
      expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining('Error fetching Google Calendar events'), 'Google API List Error');
      consoleErrorSpy.mockRestore();
    });

    it('should save refreshed tokens if "tokens" event is emitted', async () => {
      const initialTokens = {
        access_token: 'initial_access_token',
        refresh_token: 'initial_refresh_token',
        expiry_date: Date.now() + 1000,
        scope: 'scope1',
        token_type: 'Bearer'
      };
      mockedTokenUtils.getAtomGoogleCalendarTokens.mockResolvedValue(initialTokens);

      const refreshedTokensFromEvent = {
        access_token: 'refreshed_access_token',
        expiry_date: Date.now() + 3600000,
        // No new refresh_token in this event from Google typically
      };

      let tokenListenerCallback: (tokens: any) => void = () => {};
      mockOn.mockImplementation((event, callback) => {
        if (event === 'tokens') {
          tokenListenerCallback = callback;
        }
        return mockOAuth2ClientInstance; // Return the client instance for chaining or other purposes
      });

      mockEventsList.mockResolvedValue({ data: { items: [] } });
      await calendarSkills.listUpcomingEvents('user_with_refresh_event');

      // Manually invoke the captured listener
      await tokenListenerCallback(refreshedTokensFromEvent);

      expect(mockedTokenUtils.saveAtomGoogleCalendarTokens).toHaveBeenCalledWith('user_with_refresh_event',
        expect.objectContaining({
          access_token: 'refreshed_access_token',
          refresh_token: 'initial_refresh_token', // Should reuse the old refresh token
          expiry_date: refreshedTokensFromEvent.expiry_date
        })
      );
    });
  });

  describe('createCalendarEvent', () => {
    const eventDetails: Partial<CalendarEvent> = {
      summary: 'New Test Event',
      startTime: '2024-04-25T10:00:00Z',
      endTime: '2024-04-25T11:00:00Z',
    };

    it('should return auth error if no tokens are found', async () => {
      mockedTokenUtils.getAtomGoogleCalendarTokens.mockResolvedValue(null);
      const response = await calendarSkills.createCalendarEvent('unknown_user_id', eventDetails);
      expect(response.success).toBe(false);
      expect(response.message).toBe('Authentication required. Please connect your Google Calendar in settings.');
    });

    it('should call Google API and return success on event creation', async () => {
      const mockStoredTokens = { access_token: 'valid_token_for_create', expiry_date: Date.now() + 3600000, refresh_token: 'refresh_create' };
      mockedTokenUtils.getAtomGoogleCalendarTokens.mockResolvedValue(mockStoredTokens);
      const mockGoogleCreatedEvent = { data: { id: 'newEventId', htmlLink: 'link_to_event' } };
      mockEventsInsert.mockResolvedValue(mockGoogleCreatedEvent);

      const response = await calendarSkills.createCalendarEvent('mock_user_id_for_create', eventDetails);

      expect(mockEventsInsert).toHaveBeenCalledWith(expect.objectContaining({
        calendarId: 'primary',
        requestBody: expect.objectContaining({ summary: eventDetails.summary }),
      }));
      expect(response.success).toBe(true);
      expect(response.eventId).toBe('newEventId');
      expect(response.htmlLink).toBe('link_to_event');
    });

    it('should return failure if Google API call fails for insert', async () => {
      mockedTokenUtils.getAtomGoogleCalendarTokens.mockResolvedValue({ access_token: 'valid_token', expiry_date: Date.now() + 3600000, refresh_token: 'refresh' });
      mockEventsInsert.mockRejectedValue(new Error('Google API Insert Error'));
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      const response = await calendarSkills.createCalendarEvent('mock_user_id_for_create_fail', eventDetails);
      expect(response.success).toBe(false);
      expect(response.message).toContain('Google API Insert Error');
      consoleErrorSpy.mockRestore();
    });
  });
});
