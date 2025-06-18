import { listCalendlyEventTypes, listCalendlyScheduledEvents } from './calendlySkills';
import * as constants from '../_libs/constants';
import { Calendly } from '@calendly/api-client';
import { CalendlyEventType, CalendlyScheduledEvent, CalendlyPagination } from '../types'; // Using our types for expected results

// Mock the Calendly SDK and constants
jest.mock('@calendly/api-client');
jest.mock('../_libs/constants', () => ({
    ATOM_CALENDLY_PERSONAL_ACCESS_TOKEN: 'test-pat-token', // Default mock value
}));

// Declare mock functions for Calendly client methods
let mockGetCurrentUser: jest.Mock;
let mockListEventTypes: jest.Mock;
let mockListScheduledEvents: jest.Mock;

// Spy on console.error and console.log
let consoleErrorSpy: jest.SpyInstance;
let consoleLogSpy: jest.SpyInstance;

describe('calendlySkills', () => {
  const callingUserId = 'test-user-123';
  const mockUserUri = 'https://api.calendly.com/users/mockuseruri';

  beforeEach(() => {
    // It's important to be able to change ATOM_CALENDLY_PERSONAL_ACCESS_TOKEN for specific tests.
    // The jest.mock above sets a default. To change it per test, we can spyOn the getter or re-mock.
    // For simplicity, we'll ensure tests that need an empty token set it directly via the spy.
    // The default 'test-pat-token' will be used unless a test overrides it.
     jest.spyOn(constants, 'ATOM_CALENDLY_PERSONAL_ACCESS_TOKEN', 'get').mockReturnValue('test-pat-token');

    mockGetCurrentUser = jest.fn();
    mockListEventTypes = jest.fn();
    mockListScheduledEvents = jest.fn();

    (Calendly as jest.Mock).mockImplementation(() => ({
      users: { getCurrent: mockGetCurrentUser },
      eventTypes: { list: mockListEventTypes },
      scheduledEvents: { list: mockListScheduledEvents },
    }));

    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.clearAllMocks();
    consoleErrorSpy.mockRestore();
    consoleLogSpy.mockRestore();
  });

  describe('listCalendlyEventTypes', () => {
    it('should list event types successfully', async () => {
      mockGetCurrentUser.mockResolvedValueOnce({ resource: { uri: mockUserUri } });
      const mockEventTypes: Partial<CalendlyEventType>[] = [{ name: 'Test Event Type', uri: 'event_type_uri_1' }];
      const mockPagination: Partial<CalendlyPagination> = { count: 1, next_page_token: null };
      mockListEventTypes.mockResolvedValueOnce({ collection: mockEventTypes, pagination: mockPagination });

      const result = await listCalendlyEventTypes(callingUserId);

      expect(result.ok).toBe(true);
      expect(result.collection).toEqual(mockEventTypes);
      expect(result.pagination).toEqual(mockPagination);
      expect(mockGetCurrentUser).toHaveBeenCalledTimes(1);
      expect(mockListEventTypes).toHaveBeenCalledWith({ user: mockUserUri, active: true, count: 100 });
      expect(consoleLogSpy).toHaveBeenCalledWith(`listCalendlyEventTypes called by userId: ${callingUserId}`);
    });

    it('should return error if token is missing', async () => {
      jest.spyOn(constants, 'ATOM_CALENDLY_PERSONAL_ACCESS_TOKEN', 'get').mockReturnValue('');
      const result = await listCalendlyEventTypes(callingUserId);
      expect(result).toEqual({ ok: false, error: 'Calendly Personal Access Token not configured.' });
      expect(mockGetCurrentUser).not.toHaveBeenCalled();
      expect(mockListEventTypes).not.toHaveBeenCalled();
      expect(consoleErrorSpy).toHaveBeenCalledWith('Calendly Personal Access Token not configured.');
    });

    it('should return error if getCurrentUser fails to return URI', async () => {
        mockGetCurrentUser.mockResolvedValueOnce({ resource: {} }); // Missing URI
        const result = await listCalendlyEventTypes(callingUserId);
        expect(result.ok).toBe(false);
        expect(result.error).toBe('Failed to retrieve current user URI from Calendly.');
    });


    it('should handle API error from getCurrentUser', async () => {
      const apiError = new Error('User API Error');
      mockGetCurrentUser.mockRejectedValueOnce(apiError);
      const result = await listCalendlyEventTypes(callingUserId);
      expect(result.ok).toBe(false);
      expect(result.error).toContain('User API Error');
      expect(consoleErrorSpy).toHaveBeenCalledWith(`Error listing Calendly event types for userId ${callingUserId}:`, apiError.message);
    });

    it('should handle API error from listEventTypes', async () => {
      mockGetCurrentUser.mockResolvedValueOnce({ resource: { uri: mockUserUri } });
      const apiError = new Error('Event Type API Error');
      mockListEventTypes.mockRejectedValueOnce(apiError);
      const result = await listCalendlyEventTypes(callingUserId);
      expect(result.ok).toBe(false);
      expect(result.error).toContain('Event Type API Error');
    });
  });

  describe('listCalendlyScheduledEvents', () => {
    it('should list scheduled events successfully (no options)', async () => {
      mockGetCurrentUser.mockResolvedValueOnce({ resource: { uri: mockUserUri } });
      const mockEvents: Partial<CalendlyScheduledEvent>[] = [{ name: 'Scheduled Meeting', uri: 'scheduled_event_uri_1' }];
      const mockPagination: Partial<CalendlyPagination> = { count: 1, next_page_token: null };
      mockListScheduledEvents.mockResolvedValueOnce({ collection: mockEvents, pagination: mockPagination });

      const result = await listCalendlyScheduledEvents(callingUserId);

      expect(result.ok).toBe(true);
      expect(result.collection).toEqual(mockEvents);
      expect(result.pagination).toEqual(mockPagination);
      expect(mockGetCurrentUser).toHaveBeenCalledTimes(1);
      expect(mockListScheduledEvents).toHaveBeenCalledWith(expect.objectContaining({ user: mockUserUri }));
      expect(consoleLogSpy).toHaveBeenCalledWith(`listCalendlyScheduledEvents called by userId: ${callingUserId} with options:`, undefined);
    });

    it('should list scheduled events with options correctly passed', async () => {
      mockGetCurrentUser.mockResolvedValueOnce({ resource: { uri: mockUserUri } });
      mockListScheduledEvents.mockResolvedValueOnce({ collection: [], pagination: {} });
      const options = {
        count: 5,
        status: 'active' as const,
        sort: 'start_time:desc',
        pageToken: 'next_token', // Changed from page_token to pageToken to match skill
        min_start_time: '2024-01-01T00:00:00Z',
        max_start_time: '2024-01-31T23:59:59Z',
      };

      // What the SDK call should receive based on the skill's mapping
      const expectedApiOptions = {
        user: mockUserUri,
        count: 5,
        status: 'active',
        sort: 'start_time:desc',
        page_token: 'next_token', // Skill maps pageToken to page_token
        min_start_time: '2024-01-01T00:00:00Z',
        max_start_time: '2024-01-31T23:59:59Z',
      };

      await listCalendlyScheduledEvents(callingUserId, options);
      expect(mockListScheduledEvents).toHaveBeenCalledWith(expectedApiOptions);
      expect(consoleLogSpy).toHaveBeenCalledWith(`listCalendlyScheduledEvents called by userId: ${callingUserId} with options:`, options);
    });

    it('should return error if token is missing', async () => {
      jest.spyOn(constants, 'ATOM_CALENDLY_PERSONAL_ACCESS_TOKEN', 'get').mockReturnValue('');
      const result = await listCalendlyScheduledEvents(callingUserId);
      expect(result).toEqual({ ok: false, error: 'Calendly Personal Access Token not configured.' });
      expect(mockGetCurrentUser).not.toHaveBeenCalled();
    });

    it('should return error if getCurrentUser fails to return URI', async () => {
        mockGetCurrentUser.mockResolvedValueOnce({ resource: {} }); // Missing URI
        const result = await listCalendlyScheduledEvents(callingUserId);
        expect(result.ok).toBe(false);
        expect(result.error).toBe('Failed to retrieve current user URI from Calendly.');
    });

    it('should handle API error from getCurrentUser', async () => {
      const apiError = new Error('User API Error for Scheduled Events');
      mockGetCurrentUser.mockRejectedValueOnce(apiError);
      const result = await listCalendlyScheduledEvents(callingUserId);
      expect(result.ok).toBe(false);
      expect(result.error).toContain('User API Error for Scheduled Events');
      expect(consoleErrorSpy).toHaveBeenCalledWith(`Error listing Calendly scheduled events for userId ${callingUserId}:`, apiError.message);
    });

    it('should handle API error from listScheduledEvents', async () => {
      mockGetCurrentUser.mockResolvedValueOnce({ resource: { uri: mockUserUri } });
      const apiError = new Error('Scheduled Events API Error');
      mockListScheduledEvents.mockRejectedValueOnce(apiError);
      const result = await listCalendlyScheduledEvents(callingUserId);
      expect(result.ok).toBe(false);
      expect(result.error).toContain('Scheduled Events API Error');
    });
  });
});
