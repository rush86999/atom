import {
  listMicrosoftTeamsMeetings,
  getMicrosoftTeamsMeetingDetails,
  resetMSGraphTokenCache,
} from './msTeamsSkills';
import axios from 'axios';
import * as constants from '../_libs/constants';
import {
  ConfidentialClientApplication,
  AuthenticationResult,
  LogLevel,
} from '@azure/msal-node';
import { MSGraphEvent } from '../types'; // Assuming types are correctly defined

// Mock external dependencies
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock MSAL ConfidentialClientApplication
const mockAcquireTokenByClientCredential = jest.fn();
jest.mock('@azure/msal-node', () => ({
  ...jest.requireActual('@azure/msal-node'), // Import and retain actual LogLevel, etc.
  ConfidentialClientApplication: jest.fn().mockImplementation(() => ({
    acquireTokenByClientCredential: mockAcquireTokenByClientCredential,
  })),
}));

jest.mock('../_libs/constants', () => ({
  ATOM_MSGRAPH_CLIENT_ID: 'test-client-id',
  ATOM_MSGRAPH_CLIENT_SECRET: 'test-client-secret',
  ATOM_MSGRAPH_TENANT_ID: 'test-tenant-id',
  ATOM_MSGRAPH_AUTHORITY: 'https://login.microsoftonline.com/test-tenant-id',
  ATOM_MSGRAPH_SCOPES: ['https://graph.microsoft.com/.default'],
}));

// Spy on console.error and console.log
let consoleErrorSpy: jest.SpyInstance;
let consoleLogSpy: jest.SpyInstance;

describe('msTeamsSkills', () => {
  const userPrincipalNameOrId = 'user@example.com';

  beforeEach(() => {
    mockedAxios.get.mockReset();
    mockAcquireTokenByClientCredential.mockReset();
    resetMSGraphTokenCache(); // Reset the in-memory token cache

    // Set default mock values for constants for each test
    // These can be overridden using jest.spyOn within specific tests if needed
    Object.defineProperty(constants, 'ATOM_MSGRAPH_CLIENT_ID', {
      value: 'test-client-id',
      configurable: true,
    });
    Object.defineProperty(constants, 'ATOM_MSGRAPH_CLIENT_SECRET', {
      value: 'test-client-secret',
      configurable: true,
    });
    Object.defineProperty(constants, 'ATOM_MSGRAPH_TENANT_ID', {
      value: 'test-tenant-id',
      configurable: true,
    });
    Object.defineProperty(constants, 'ATOM_MSGRAPH_AUTHORITY', {
      value: `https://login.microsoftonline.com/test-tenant-id`,
      configurable: true,
    });
    Object.defineProperty(constants, 'ATOM_MSGRAPH_SCOPES', {
      value: ['https://graph.microsoft.com/.default'],
      configurable: true,
    });

    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.clearAllMocks();
    consoleErrorSpy.mockRestore();
    consoleLogSpy.mockRestore();
  });

  describe('MSAL Token Logic (implicitly via skill calls)', () => {
    it('should fetch and cache a new MSAL token', async () => {
      mockAcquireTokenByClientCredential.mockResolvedValueOnce({
        accessToken: 'new_token_123',
        expiresOn: new Date(Date.now() + 3600 * 1000), // Expires in 1 hour
      } as AuthenticationResult);
      mockedAxios.get.mockResolvedValueOnce({ data: { value: [] } }); // For listMicrosoftTeamsMeetings

      await listMicrosoftTeamsMeetings(userPrincipalNameOrId); // First call
      expect(mockAcquireTokenByClientCredential).toHaveBeenCalledTimes(1);
      expect(ConfidentialClientApplication).toHaveBeenCalledTimes(1); // Client app initialized once

      mockedAxios.get.mockResolvedValueOnce({ data: { value: [] } }); // For second call
      await listMicrosoftTeamsMeetings(userPrincipalNameOrId); // Second call
      expect(mockAcquireTokenByClientCredential).toHaveBeenCalledTimes(1); // Token reused from cache
    });

    it('should refresh MSAL token if expired', async () => {
      mockAcquireTokenByClientCredential.mockResolvedValueOnce({
        accessToken: 'initial_token',
        expiresOn: new Date(Date.now() + 500), // Expires in 0.5 seconds
      } as AuthenticationResult);
      mockAcquireTokenByClientCredential.mockResolvedValueOnce({
        // For the refresh
        accessToken: 'refreshed_token',
        expiresOn: new Date(Date.now() + 3600 * 1000),
      } as AuthenticationResult);
      mockedAxios.get.mockResolvedValue({ data: { value: [] } }); // Mock for all GET calls

      await listMicrosoftTeamsMeetings(userPrincipalNameOrId); // Initial call
      expect(mockAcquireTokenByClientCredential).toHaveBeenCalledTimes(1);

      jest.useFakeTimers();
      jest.advanceTimersByTime(1000); // Advance time by 1 second (token expires)
      jest.useRealTimers();

      await listMicrosoftTeamsMeetings(userPrincipalNameOrId); // Second call, should refresh
      expect(mockAcquireTokenByClientCredential).toHaveBeenCalledTimes(2);
      expect(mockedAxOS.get.mock.calls[1][1]?.headers?.Authorization).toBe(
        'Bearer refreshed_token'
      );
    });

    it('should return error if MSAL constants are missing for token fetch', async () => {
      Object.defineProperty(constants, 'ATOM_MSGRAPH_CLIENT_ID', { value: '' }); // Simulate missing client ID
      const result = await listMicrosoftTeamsMeetings(userPrincipalNameOrId);
      expect(result.ok).toBe(false);
      expect(result.error).toContain('Failed to obtain MS Graph access token.');
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'MS Graph API client credentials (Client ID, Authority, Client Secret) not configured.'
      );
    });

    it('should return error if acquireTokenByClientCredential fails', async () => {
      mockAcquireTokenByClientCredential.mockRejectedValueOnce(
        new Error('MSAL Auth Error')
      );
      const result = await listMicrosoftTeamsMeetings(userPrincipalNameOrId);
      expect(result.ok).toBe(false);
      expect(result.error).toContain('Failed to obtain MS Graph access token.');
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Error acquiring MS Graph token by client credential:',
        expect.any(Error)
      );
    });
  });

  describe('listMicrosoftTeamsMeetings', () => {
    beforeEach(() => {
      // Ensure a valid token for these specific tests
      mockAcquireTokenByClientCredential.mockResolvedValue({
        accessToken: 'valid_graph_token',
        expiresOn: new Date(Date.now() + 3600 * 1000),
      } as AuthenticationResult);
    });

    it('should list Teams meetings successfully with default filter', async () => {
      const mockEvents: Partial<MSGraphEvent>[] = [
        { subject: 'Teams Meeting 1', id: 'evt1' },
      ];
      mockedAxios.get.mockResolvedValueOnce({
        data: { value: mockEvents, '@odata.nextLink': 'nextLink123' },
      });

      const result = await listMicrosoftTeamsMeetings(userPrincipalNameOrId, {
        limit: 5,
      });
      expect(result.ok).toBe(true);
      expect(result.events).toEqual(mockEvents);
      expect(result.nextLink).toBe('nextLink123');
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining(
          `/users/${userPrincipalNameOrId}/calendar/events`
        ),
        expect.objectContaining({
          headers: { Authorization: 'Bearer valid_graph_token' },
        })
      );
      const calledUrl = mockedAxios.get.mock.calls[0][0];
      expect(calledUrl).toContain(
        '$select=id,subject,start,end,isOnlineMeeting,onlineMeeting,webLink,bodyPreview'
      );
      expect(calledUrl).toContain('$orderby=start/dateTime ASC');
      expect(calledUrl).toContain('$top=5');
      expect(calledUrl).toContain(
        `$filter=isOnlineMeeting eq true and onlineMeeting/onlineMeetingProvider eq 'teamsForBusiness'`
      );
    });

    it('should list meetings without Teams filter if options.filterForTeams is false', async () => {
      mockedAxios.get.mockResolvedValueOnce({ data: { value: [] } });
      await listMicrosoftTeamsMeetings(userPrincipalNameOrId, {
        filterForTeams: false,
      });
      const calledUrl = mockedAxios.get.mock.calls[0][0];
      expect(calledUrl).not.toContain('$filter=');
    });

    it('should use nextLink for pagination if provided', async () => {
      const mockNextLink =
        'https://graph.microsoft.com/v1.0/users/someuser/calendar/events?$skipToken=abc';
      mockedAxios.get.mockResolvedValueOnce({
        data: { value: [{ id: 'evt2' }] },
      });
      await listMicrosoftTeamsMeetings(userPrincipalNameOrId, {
        nextLink: mockNextLink,
      });
      expect(mockedAxios.get).toHaveBeenCalledWith(
        mockNextLink, // Directly uses the nextLink
        expect.objectContaining({
          headers: { Authorization: 'Bearer valid_graph_token' },
        })
      );
    });

    it('should handle API error when listing meetings', async () => {
      const graphError = {
        isAxiosError: true,
        response: { data: { error: { message: 'Graph API Error' } } },
        message: 'Request failed',
      } as AxiosError;
      mockedAxios.get.mockRejectedValueOnce(graphError);
      const result = await listMicrosoftTeamsMeetings(userPrincipalNameOrId);
      expect(result.ok).toBe(false);
      expect(result.error).toBe('Graph API Error');
    });
  });

  describe('getMicrosoftTeamsMeetingDetails', () => {
    beforeEach(() => {
      mockAcquireTokenByClientCredential.mockResolvedValue({
        accessToken: 'valid_graph_token_for_details',
        expiresOn: new Date(Date.now() + 3600 * 1000),
      } as AuthenticationResult);
    });

    it('should get meeting details successfully with specific select fields', async () => {
      const mockEventDetail: Partial<MSGraphEvent> = {
        id: 'evtDetail1',
        subject: 'Detailed Teams Meeting',
      };
      mockedAxios.get.mockResolvedValueOnce({ data: mockEventDetail });
      const eventId = 'evtDetail1';
      const result = await getMicrosoftTeamsMeetingDetails(
        userPrincipalNameOrId,
        eventId
      );

      expect(result.ok).toBe(true);
      expect(result.event).toEqual(mockEventDetail);
      const expectedUrl = `https://graph.microsoft.com/v1.0/users/${userPrincipalNameOrId}/events/${eventId}?$select=id,subject,start,end,isOnlineMeeting,onlineMeeting,webLink,bodyPreview,body,attendees,location,locations,organizer`;
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expectedUrl,
        expect.objectContaining({
          headers: { Authorization: 'Bearer valid_graph_token_for_details' },
        })
      );
    });

    it('should handle meeting not found (404 error)', async () => {
      const eventId = 'nonExistentEventId';
      const graphError = {
        isAxiosError: true,
        response: {
          status: 404,
          data: { error: { message: 'Resource not found' } },
        },
        message: 'Request failed',
      } as AxiosError;
      mockedAxios.get.mockRejectedValueOnce(graphError);
      const result = await getMicrosoftTeamsMeetingDetails(
        userPrincipalNameOrId,
        eventId
      );

      expect(result.ok).toBe(false);
      expect(result.error).toContain(
        `Meeting event not found (ID: ${eventId}). Resource not found`
      );
    });

    it('should handle other API errors when getting details', async () => {
      const eventId = 'errorEventId';
      const graphError = {
        isAxiosError: true,
        response: {
          data: { error: { message: 'Some other Graph API Error' } },
        },
        message: 'Request failed',
      } as AxiosError;
      mockedAxios.get.mockRejectedValueOnce(graphError);
      const result = await getMicrosoftTeamsMeetingDetails(
        userPrincipalNameOrId,
        eventId
      );
      expect(result.ok).toBe(false);
      expect(result.error).toBe('Some other Graph API Error');
    });
  });
});
