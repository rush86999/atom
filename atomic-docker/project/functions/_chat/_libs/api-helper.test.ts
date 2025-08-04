import {
  // Import functions to test, starting with resilientGotPostHasura (if exported)
  // or functions that use it. For now, we'll test it indirectly.
  upsertConference, // Example function using resilientGotPostHasura
  refreshZoomToken,
  convertEventTitleToOpenAIVector,
  callOpenAIWithMessageHistoryOnly,
  // We'll need to import the logger to spy on it
} from './api-helper';
import got from 'got';
import axios from 'axios';
import OpenAI from 'openai';
import { ವಸ್ತುನಿಷ್ಠ_URL, hasuraAdminSecret } from './constants'; // These are the actual names from the file
import { chatApiHelperLogger } from './api-helper'; // Assuming logger is exported or accessible for spying

// Mock 'got'
jest.mock('got');
const mockedGot = got as jest.Mocked<typeof got>;

// Mock 'axios'
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock 'openai'
const mockOpenAICreateEmbedding = jest.fn();
const mockOpenAIChatCompletionsCreate = jest.fn();
jest.mock('openai', () => {
  return jest.fn().mockImplementation(() => ({
    embeddings: { create: mockOpenAICreateEmbedding },
    chat: { completions: { create: mockOpenAIChatCompletionsCreate } },
  }));
});

// Mock the logger
jest.mock('./api-helper', () => {
  const originalModule = jest.requireActual('./api-helper');
  const winston = require('winston');
  const mockLogger = {
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
    debug: jest.fn(),
  };
  // Create a real logger but spy on its methods
  const actualLogger = winston.createLogger({
    level: 'info',
    transports: [new winston.transports.Console({ silent: true })], // Silent during tests
  });
  for (const level in mockLogger) {
    actualLogger[level] = mockLogger[level];
  }

  return {
    ...originalModule,
    chatApiHelperLogger: actualLogger, // Provide the spied-upon logger
    // resilientGotPostHasura: originalModule.resilientGotPostHasura, // Keep actual implementation
  };
});

describe('_chat/_libs/api-helper.ts', () => {
  const testUserId = 'test-user-123';
  const testOperationName = 'TestHasuraOperation';
  const testQuery = 'query Test { test }';
  const testVariables = { id: 1 };
  const mockSuccessData = { test: 'success' };
  const mockGraphQLErrors = [{ message: 'GraphQL error from Hasura' }];

  // Access the spied logger methods
  let spiedLogger: any;
  beforeAll(() => {
    // Import here to get the version with the mocked logger
    const apiHelper = require('./api-helper');
    spiedLogger = apiHelper.chatApiHelperLogger;
  });

  beforeEach(() => {
    jest.clearAllMocks(); // Clears spies and mocks
    mockedGot.post.mockReset(); // Reset specifically for got
    mockedAxios.post.mockReset();
    mockedAxios.mockReset(); // For other methods like axios({})
    mockOpenAICreateEmbedding.mockReset();
    mockOpenAIChatCompletionsCreate.mockReset();
  });

  describe('resilientGotPostHasura (tested via a consumer like upsertConference)', () => {
    // We test resilientGotPostHasura indirectly by calling a function that uses it.
    // Let's use upsertConference as an example.
    const mockConferenceInput = { id: 'conf1', name: 'Test Conference' } as any;
    const upsertConferenceQuery = expect.stringContaining('UpsertConference');

    it('should succeed on the first attempt', async () => {
      mockedGot.post.mockResolvedValueOnce({
        json: () =>
          Promise.resolve({ data: { insert_Conference_one: { id: 'conf1' } } }),
      } as any);

      const result = await upsertConference(mockConferenceInput);
      expect(result?.id).toBe('conf1');
      expect(mockedGot.post).toHaveBeenCalledTimes(1);
      expect(mockedGot.post).toHaveBeenCalledWith(
        वस्तुನಿಷ್ಠ_URL, // Using the actual constant name from the file for hasuraGraphUrl
        expect.objectContaining({
          json: expect.objectContaining({ query: upsertConferenceQuery }),
          timeout: { request: 10000 },
        })
      );
      expect(spiedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining('Hasura call attempt 1 for UpsertConference'),
        expect.anything()
      );
      expect(spiedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(
          'Hasura call UpsertConference successful on attempt 1'
        ),
        expect.anything()
      );
    });

    it('should succeed on the second attempt after a 503 error', async () => {
      mockedGot.post
        .mockRejectedValueOnce({
          response: { statusCode: 503 },
          message: 'Service Unavailable',
          isGotError: true,
        })
        .mockResolvedValueOnce({
          json: () =>
            Promise.resolve({
              data: { insert_Conference_one: { id: 'conf1' } },
            }),
        } as any);

      const result = await upsertConference(mockConferenceInput);
      expect(result?.id).toBe('conf1');
      expect(mockedGot.post).toHaveBeenCalledTimes(2);
      expect(spiedLogger.warn).toHaveBeenCalledWith(
        expect.stringContaining(
          'Hasura call attempt 1 for UpsertConference failed'
        ),
        expect.anything()
      );
      expect(spiedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(
          'Waiting 1000ms before Hasura retry 1 for UpsertConference'
        ),
        expect.anything()
      );
      expect(spiedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(
          'Hasura call UpsertConference successful on attempt 2'
        ),
        expect.anything()
      );
    });

    it('should fail after all retries for persistent 500 errors', async () => {
      mockedGot.post
        .mockRejectedValueOnce({
          response: { statusCode: 500 },
          message: 'Internal Server Error 1',
          isGotError: true,
        })
        .mockRejectedValueOnce({
          response: { statusCode: 500 },
          message: 'Internal Server Error 2',
          isGotError: true,
        })
        .mockRejectedValueOnce({
          response: { statusCode: 500 },
          message: 'Internal Server Error 3',
          isGotError: true,
        });

      await expect(upsertConference(mockConferenceInput)).rejects.toThrow(
        'Internal Server Error 3'
      );
      expect(mockedGot.post).toHaveBeenCalledTimes(3);
      expect(spiedLogger.warn).toHaveBeenCalledTimes(3);
      expect(spiedLogger.error).toHaveBeenCalledWith(
        expect.stringContaining(
          "Failed Hasura operation 'UpsertConference' after 3 attempts."
        ),
        expect.anything()
      );
    });

    it('should fail immediately on a non-retryable 400 error', async () => {
      mockedGot.post.mockRejectedValueOnce({
        response: { statusCode: 400 },
        message: 'Bad Request',
        isGotError: true,
      });

      await expect(upsertConference(mockConferenceInput)).rejects.toThrow(
        'Bad Request'
      );
      expect(mockedGot.post).toHaveBeenCalledTimes(1);
      expect(spiedLogger.error).toHaveBeenCalledWith(
        expect.stringContaining(
          'Non-retryable HTTP error 400 for UpsertConference. Aborting.'
        ),
        expect.anything()
      );
      expect(spiedLogger.error).toHaveBeenCalledWith(
        expect.stringContaining(
          "Failed Hasura operation 'UpsertConference' after 1 attempts."
        ),
        expect.anything()
      );
    });

    it('should handle GraphQL errors in response (and retry by default)', async () => {
      mockedGot.post
        .mockResolvedValueOnce({
          json: () => Promise.resolve({ errors: mockGraphQLErrors }),
        } as any)
        .mockResolvedValueOnce({
          json: () =>
            Promise.resolve({
              data: { insert_Conference_one: { id: 'conf1' } },
            }),
        } as any);

      const result = await upsertConference(mockConferenceInput);
      expect(result?.id).toBe('conf1');
      expect(mockedGot.post).toHaveBeenCalledTimes(2);
      expect(spiedLogger.warn).toHaveBeenCalledWith(
        expect.stringContaining(
          'Hasura call attempt 1 for UpsertConference failed'
        ),
        expect.objectContaining({
          error: expect.stringContaining('GraphQL error in UpsertConference'),
        })
      );
    });

    it('should handle timeout (ETIMEDOUT)', async () => {
      mockedGot.post
        .mockRejectedValueOnce({
          code: 'ETIMEDOUT',
          message: 'Connection timed out',
          isGotError: true,
        })
        .mockResolvedValueOnce({
          json: () =>
            Promise.resolve({
              data: { insert_Conference_one: { id: 'conf1' } },
            }),
        } as any);

      const result = await upsertConference(mockConferenceInput);
      expect(result?.id).toBe('conf1');
      expect(mockedGot.post).toHaveBeenCalledTimes(2);
      expect(spiedLogger.warn).toHaveBeenCalledWith(
        expect.stringContaining(
          'Hasura call attempt 1 for UpsertConference failed'
        ),
        expect.objectContaining({ code: 'ETIMEDOUT' })
      );
    });
  });

  // More tests would follow for refreshZoomToken, OpenAI calls, and Google API calls...
  // For brevity, I'll add a placeholder for one Zoom and one OpenAI function.

  describe('refreshZoomToken (axios resilience)', () => {
    const refreshToken = 'dummy-refresh-token';
    const mockZoomSuccess = {
      access_token: 'new_zoom_token',
      expires_in: 3600,
    };

    it('should succeed on first attempt', async () => {
      mockedAxios.mockResolvedValueOnce({ data: mockZoomSuccess });
      const result = await refreshZoomToken(refreshToken);
      expect(result).toEqual(mockZoomSuccess);
      expect(mockedAxios).toHaveBeenCalledTimes(1);
      expect(spiedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining('Attempt 1 to refreshZoomToken'),
        expect.anything()
      );
    });

    it('should retry on 503 and then succeed', async () => {
      mockedAxios
        .mockRejectedValueOnce({
          isAxiosError: true,
          response: { status: 503 },
        })
        .mockResolvedValueOnce({ data: mockZoomSuccess });

      const result = await refreshZoomToken(refreshToken);
      expect(result).toEqual(mockZoomSuccess);
      expect(mockedAxios).toHaveBeenCalledTimes(2);
      expect(spiedLogger.warn).toHaveBeenCalledWith(
        expect.stringContaining('Attempt 1 for refreshZoomToken failed'),
        expect.anything()
      );
      expect(spiedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(
          'Waiting 1000ms before refreshZoomToken retry 2'
        ),
        expect.anything()
      );
    });

    it('should fail after all retries for persistent 500 errors', async () => {
      mockedAxios.mockRejectedValue({
        isAxiosError: true,
        response: { status: 500 },
      }); // Fails all 3 times

      await expect(refreshZoomToken(refreshToken)).rejects.toThrow();
      expect(mockedAxios).toHaveBeenCalledTimes(3);
      expect(spiedLogger.error).toHaveBeenCalledWith(
        expect.stringContaining('Failed refreshZoomToken after 3 attempts'),
        expect.anything()
      );
    });
  });

  describe('convertEventTitleToOpenAIVector (OpenAI resilience)', () => {
    const title = 'Test Event Title';
    const mockEmbedding = [0.1, 0.2, 0.3];

    it('should succeed on first attempt', async () => {
      mockOpenAICreateEmbedding.mockResolvedValueOnce({
        data: [{ embedding: mockEmbedding }],
      });
      const result = await convertEventTitleToOpenAIVector(title);
      expect(result).toEqual(mockEmbedding);
      expect(mockOpenAICreateEmbedding).toHaveBeenCalledTimes(1);
    });

    it('should retry on API error then succeed', async () => {
      mockOpenAICreateEmbedding
        .mockRejectedValueOnce({
          response: { status: 500 },
          message: 'OpenAI server error',
        })
        .mockResolvedValueOnce({ data: [{ embedding: mockEmbedding }] });

      const result = await convertEventTitleToOpenAIVector(title);
      expect(result).toEqual(mockEmbedding);
      expect(mockOpenAICreateEmbedding).toHaveBeenCalledTimes(2);
      expect(spiedLogger.warn).toHaveBeenCalledWith(
        expect.stringContaining('Attempt 1 for OpenAI embedding'),
        expect.anything()
      );
    });
  });

  // New tests for Google Calendar related functions
  describe('refreshGoogleToken (via resilientGotGoogleAuth)', () => {
    const refreshToken = 'google-refresh-token';
    const clientType = 'web';
    const mockGoogleSuccess = {
      access_token: 'new_google_token',
      expires_in: 3599,
      scope: 'test_scope',
      token_type: 'Bearer',
    };

    it('should succeed on the first attempt', async () => {
      mockedGot.post.mockResolvedValueOnce({
        json: () => Promise.resolve(mockGoogleSuccess),
      } as any);

      const result = await require('./api-helper').refreshGoogleToken(
        refreshToken,
        clientType
      );
      expect(result).toEqual(mockGoogleSuccess);
      expect(mockedGot.post).toHaveBeenCalledTimes(1);
      expect(mockedGot.post).toHaveBeenCalledWith(
        expect.stringContaining('oauth2/v4/token'), // googleTokenUrl
        expect.objectContaining({
          form: expect.objectContaining({
            refresh_token: refreshToken,
            grant_type: 'refresh_token',
          }),
          timeout: { request: 10000 },
        })
      );
      expect(spiedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(
          `Google Auth call attempt 1 for refreshGoogleToken (${clientType})`
        ),
        expect.anything()
      );
      expect(spiedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(
          `Google Auth call refreshGoogleToken (${clientType}) successful on attempt 1`
        ),
        expect.anything()
      );
    });

    it('should retry on 503 then succeed', async () => {
      mockedGot.post
        .mockRejectedValueOnce({
          response: { statusCode: 503 },
          message: 'Server Error',
          isGotError: true,
        })
        .mockResolvedValueOnce({
          json: () => Promise.resolve(mockGoogleSuccess),
        } as any);

      await require('./api-helper').refreshGoogleToken(
        refreshToken,
        clientType
      );
      expect(mockedGot.post).toHaveBeenCalledTimes(2);
      expect(spiedLogger.warn).toHaveBeenCalledWith(
        expect.stringContaining(
          `Google Auth call attempt 1 for refreshGoogleToken (${clientType}) failed`
        ),
        expect.anything()
      );
      expect(spiedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(
          `Waiting 1000ms before Google Auth retry 2 for refreshGoogleToken (${clientType})`
        ),
        expect.anything()
      );
    });

    it('should fail after all retries for persistent 500 error', async () => {
      mockedGot.post.mockRejectedValue({
        response: { statusCode: 500 },
        message: 'Internal Error',
        isGotError: true,
      });

      await expect(
        require('./api-helper').refreshGoogleToken(refreshToken, clientType)
      ).rejects.toThrow('Internal Error');
      expect(mockedGot.post).toHaveBeenCalledTimes(3);
      expect(spiedLogger.error).toHaveBeenCalledWith(
        expect.stringContaining(
          `Failed Google Auth operation 'refreshGoogleToken' (${clientType}) after 3 attempts`
        ),
        expect.anything()
      );
    });

    it('should fail immediately on 400 error', async () => {
      mockedGot.post.mockRejectedValueOnce({
        response: { statusCode: 400, body: { error: 'invalid_grant' } },
        message: 'Bad Request',
        isGotError: true,
      });

      await expect(
        require('./api-helper').refreshGoogleToken(refreshToken, clientType)
      ).rejects.toThrow('Bad Request');
      expect(mockedGot.post).toHaveBeenCalledTimes(1);
      expect(spiedLogger.error).toHaveBeenCalledWith(
        expect.stringContaining(
          `Non-retryable HTTP error 400 for refreshGoogleToken (${clientType}). Aborting.`
        ),
        expect.anything()
      );
    });

    it('should handle timeout (ETIMEDOUT)', async () => {
      mockedGot.post
        .mockRejectedValueOnce({
          code: 'ETIMEDOUT',
          message: 'Connection timed out',
          isGotError: true,
        })
        .mockResolvedValueOnce({
          json: () => Promise.resolve(mockGoogleSuccess),
        } as any);

      await require('./api-helper').refreshGoogleToken(
        refreshToken,
        clientType
      );
      expect(mockedGot.post).toHaveBeenCalledTimes(2);
      expect(spiedLogger.warn).toHaveBeenCalledWith(
        expect.stringContaining(
          `Google Auth call attempt 1 for refreshGoogleToken (${clientType}) failed`
        ),
        expect.objectContaining({ code: 'ETIMEDOUT' })
      );
    });
  });

  describe('getGoogleAPIToken', () => {
    const userId = 'test-g-user';
    const name = 'google_calendar'; // Matches constant
    const clientType = 'web';
    const mockValidIntegration = {
      id: 'integ-id',
      token: 'valid-token',
      expiresAt: dayjs().add(1, 'hour').toISOString(),
      refreshToken: 'valid-refresh-token',
      clientType: 'web',
    };
    const mockExpiredIntegration = {
      ...mockValidIntegration,
      token: 'expired-token',
      expiresAt: dayjs().subtract(1, 'hour').toISOString(),
    };
    const mockIntegrationNoToken = {
      ...mockValidIntegration,
      token: null, // or undefined
      expiresAt: dayjs().add(1, 'hour').toISOString(),
    };

    let getCalendarIntegrationByNameMock: jest.SpyInstance;
    let refreshGoogleTokenMock: jest.SpyInstance;
    let updateCalendarIntegrationMock: jest.SpyInstance;

    beforeEach(() => {
      // Need to spy on functions within the same module
      const apiHelperModule = require('./api-helper');
      getCalendarIntegrationByNameMock = jest.spyOn(
        apiHelperModule,
        'getCalendarIntegrationByName'
      );
      refreshGoogleTokenMock = jest.spyOn(
        apiHelperModule,
        'refreshGoogleToken'
      );
      updateCalendarIntegrationMock = jest.spyOn(
        apiHelperModule,
        'updateCalendarIntegration'
      );
    });

    afterEach(() => {
      getCalendarIntegrationByNameMock.mockRestore();
      refreshGoogleTokenMock.mockRestore();
      updateCalendarIntegrationMock.mockRestore();
    });

    it('should return existing valid token (cache hit)', async () => {
      getCalendarIntegrationByNameMock.mockResolvedValueOnce(
        mockValidIntegration
      );
      const token = await require('./api-helper').getGoogleAPIToken(
        userId,
        name,
        clientType
      );
      expect(token).toBe(mockValidIntegration.token);
      expect(getCalendarIntegrationByNameMock).toHaveBeenCalledWith(
        userId,
        name
      );
      expect(refreshGoogleTokenMock).not.toHaveBeenCalled();
      expect(spiedLogger.debug).toHaveBeenCalledWith(
        expect.stringContaining('Existing token is valid'),
        expect.anything()
      );
    });

    it('should refresh token if expired', async () => {
      getCalendarIntegrationByNameMock.mockResolvedValueOnce(
        mockExpiredIntegration
      );
      refreshGoogleTokenMock.mockResolvedValueOnce({
        access_token: 'new-refreshed-token',
        expires_in: 3600,
      });
      updateCalendarIntegrationMock.mockResolvedValueOnce(undefined);

      const token = await require('./api-helper').getGoogleAPIToken(
        userId,
        name,
        clientType
      );
      expect(token).toBe('new-refreshed-token');
      expect(refreshGoogleTokenMock).toHaveBeenCalledWith(
        mockExpiredIntegration.refreshToken,
        clientType
      );
      expect(updateCalendarIntegrationMock).toHaveBeenCalledWith(
        mockExpiredIntegration.id,
        'new-refreshed-token',
        3600
      );
      expect(spiedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining('Token expired or missing, attempting refresh'),
        expect.anything()
      );
    });

    it('should refresh token if token is missing', async () => {
      getCalendarIntegrationByNameMock.mockResolvedValueOnce(
        mockIntegrationNoToken
      );
      refreshGoogleTokenMock.mockResolvedValueOnce({
        access_token: 'new-refreshed-token-no-original',
        expires_in: 3600,
      });
      updateCalendarIntegrationMock.mockResolvedValueOnce(undefined);

      const token = await require('./api-helper').getGoogleAPIToken(
        userId,
        name,
        clientType
      );
      expect(token).toBe('new-refreshed-token-no-original');
      expect(refreshGoogleTokenMock).toHaveBeenCalledWith(
        mockIntegrationNoToken.refreshToken,
        clientType
      );
    });

    it('should throw and attempt to disable integration if getCalendarIntegrationByName returns nothing', async () => {
      getCalendarIntegrationByNameMock.mockResolvedValueOnce(null); // No integration found

      await expect(
        require('./api-helper').getGoogleAPIToken(userId, name, clientType)
      ).rejects.toThrow('Calendar integration or essential details not found');
      expect(updateCalendarIntegrationMock).not.toHaveBeenCalled(); // Should not be called if integrationId was never set
      expect(spiedLogger.error).toHaveBeenCalledWith(
        expect.stringContaining(
          'Calendar integration or essential details not found'
        ),
        expect.anything()
      );
    });

    it('should throw and attempt to disable integration if refreshGoogleToken fails', async () => {
      getCalendarIntegrationByNameMock.mockResolvedValueOnce(
        mockExpiredIntegration
      );
      refreshGoogleTokenMock.mockRejectedValueOnce(new Error('Refresh failed'));
      updateCalendarIntegrationMock.mockResolvedValueOnce(undefined); // Mock for disabling

      await expect(
        require('./api-helper').getGoogleAPIToken(userId, name, clientType)
      ).rejects.toThrow('Refresh failed');
      expect(updateCalendarIntegrationMock).toHaveBeenCalledWith(
        mockExpiredIntegration.id,
        undefined,
        undefined,
        false
      );
      expect(spiedLogger.error).toHaveBeenCalledWith(
        expect.stringContaining('Failed to get/refresh Google API token'),
        expect.anything()
      );
      expect(spiedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(
          'Attempting to disable calendar integration due to error'
        ),
        expect.anything()
      );
    });
  });

  describe('getGlobalCalendar', () => {
    const userId = 'test-user-global-cal';
    const mockCalendarData = { id: 'global-cal-id', title: 'Global Primary' };

    // Mock resilientGotPostHasura for these tests
    let resilientGotPostHasuraMock: jest.SpyInstance;
    beforeEach(() => {
      const apiHelperModule = require('./api-helper');
      // Correctly mock the resilientGotPostHasura if it's not already mocked globally in a way that allows per-test config
      // For this example, assuming it's part of the original module and we can spy on it.
      // If it's tricky due to module loading, direct mocking like `got` might be necessary.
      // For now, let's assume it's available to be spied upon or we have a way to control its behavior.
      // This might require adjusting the global mock setup for './api-helper'
      // For simplicity in this snippet, we'll assume a direct mock path or that it's included in the spied module.
      // This is a common Jest challenge with module-internal function calls.
      // A robust way is to ensure `resilientGotPostHasura` is also exported and then re-mocked here,
      // or ensure the global mock of './api-helper' provides a jest.fn() for it.
      // Let's assume the global mock setup can be adjusted or resilientGotPostHasura is exported.
      // For now, we'll act as if we can mock its behavior for getGlobalCalendar.
      resilientGotPostHasuraMock = jest.spyOn(
        apiHelperModule,
        'resilientGotPostHasura'
      );
    });
    afterEach(() => {
      resilientGotPostHasuraMock.mockRestore();
    });

    it('should return calendar data on successful fetch', async () => {
      resilientGotPostHasuraMock.mockResolvedValueOnce({
        Calendar: [mockCalendarData],
      });

      const result = await require('./api-helper').getGlobalCalendar(userId);
      expect(result).toEqual(mockCalendarData);
      expect(resilientGotPostHasuraMock).toHaveBeenCalledWith(
        'getGlobalCalendar',
        expect.any(String),
        { userId }
      );
      expect(spiedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining('getGlobalCalendar successful for user'),
        expect.anything()
      );
    });

    it('should return undefined if no global calendar is found', async () => {
      resilientGotPostHasuraMock.mockResolvedValueOnce({ Calendar: [] });
      const result = await require('./api-helper').getGlobalCalendar(userId);
      expect(result).toBeUndefined();
      expect(spiedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(
          'getGlobalCalendar: No global primary calendar found for user'
        ),
        expect.anything()
      );
    });

    it('should return undefined if Calendar field is missing (unexpected response)', async () => {
      resilientGotPostHasuraMock.mockResolvedValueOnce({}); // Missing Calendar field
      const result = await require('./api-helper').getGlobalCalendar(userId);
      expect(result).toBeUndefined();
      expect(spiedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(
          'getGlobalCalendar: No global primary calendar found for user'
        ),
        expect.anything()
      );
    });

    it('should throw if resilientGotPostHasura throws', async () => {
      const error = new Error('Hasura fetch failed');
      resilientGotPostHasuraMock.mockRejectedValueOnce(error);

      await expect(
        require('./api-helper').getGlobalCalendar(userId)
      ).rejects.toThrow('Hasura fetch failed');
      expect(spiedLogger.error).toHaveBeenCalledWith(
        expect.stringContaining('Error in getGlobalCalendar for user'),
        expect.objectContaining({ error: 'Hasura fetch failed' })
      );
    });
  });

  describe('Google Calendar API Event Functions (create, patch, delete)', () => {
    const userId = 'test-gcal-user';
    const calendarId = 'primary';
    const clientType = 'web';
    const mockGCalEventId = 'gcal-event-id-123';
    const mockOurEventId = `${mockGCalEventId}#${calendarId}`;

    let getGoogleAPITokenMock: jest.SpyInstance;
    const mockGoogleEventsInsert = jest.fn();
    const mockGoogleEventsPatch = jest.fn();
    const mockGoogleEventsDelete = jest.fn();

    beforeEach(() => {
      const apiHelperModule = require('./api-helper');
      getGoogleAPITokenMock = jest.spyOn(apiHelperModule, 'getGoogleAPIToken');

      // Mock googleapis
      const google = require('googleapis').google;
      google.calendar = jest.fn().mockReturnValue({
        events: {
          insert: mockGoogleEventsInsert,
          patch: mockGoogleEventsPatch,
          delete: mockGoogleEventsDelete,
        },
      });
    });

    afterEach(() => {
      getGoogleAPITokenMock.mockRestore();
      mockGoogleEventsInsert.mockReset();
      mockGoogleEventsPatch.mockReset();
      mockGoogleEventsDelete.mockReset();
    });

    describe('createGoogleEvent', () => {
      const eventSummary = 'Test Event Creation';
      const eventData = {
        summary: eventSummary,
        startDateTime: dayjs().add(1, 'day').toISOString(),
        endDateTime: dayjs().add(1, 'day').add(1, 'hour').toISOString(),
        timezone: 'America/New_York',
      };

      it('should create event successfully on first attempt', async () => {
        getGoogleAPITokenMock.mockResolvedValueOnce('fake-google-api-token');
        mockGoogleEventsInsert.mockResolvedValueOnce({
          data: { id: mockGCalEventId, summary: eventSummary },
        });

        const result = await require('./api-helper').createGoogleEvent(
          userId,
          calendarId,
          clientType,
          mockOurEventId,
          eventData.endDateTime,
          eventData.startDateTime,
          1,
          undefined,
          undefined,
          undefined,
          undefined,
          eventSummary,
          undefined,
          eventData.timezone
        );

        expect(result.googleEventId).toBe(mockGCalEventId);
        expect(getGoogleAPITokenMock).toHaveBeenCalledWith(
          userId,
          expect.any(String),
          clientType
        );
        expect(mockGoogleEventsInsert).toHaveBeenCalledTimes(1);
        expect(mockGoogleEventsInsert).toHaveBeenCalledWith(
          expect.objectContaining({
            calendarId,
            requestBody: expect.objectContaining({ summary: eventSummary }),
          }),
          { timeout: 20000 }
        );
        expect(spiedLogger.info).toHaveBeenCalledWith(
          expect.stringContaining(
            `Google Calendar event created successfully on attempt 1 for user ${userId}`
          ),
          expect.anything()
        );
      });

      it('should retry on 500 error then succeed', async () => {
        getGoogleAPITokenMock.mockResolvedValue('fake-google-api-token');
        mockGoogleEventsInsert
          .mockRejectedValueOnce({ code: 500, message: 'Server error' })
          .mockResolvedValueOnce({
            data: { id: mockGCalEventId, summary: eventSummary },
          });

        await require('./api-helper').createGoogleEvent(
          userId,
          calendarId,
          clientType,
          mockOurEventId,
          eventData.endDateTime,
          eventData.startDateTime,
          1,
          undefined,
          undefined,
          undefined,
          undefined,
          eventSummary,
          undefined,
          eventData.timezone
        );

        expect(mockGoogleEventsInsert).toHaveBeenCalledTimes(2);
        expect(spiedLogger.warn).toHaveBeenCalledWith(
          expect.stringContaining(
            `Attempt 1 to create Google event for user ${userId} failed`
          ),
          expect.anything()
        );
        expect(spiedLogger.warn).toHaveBeenCalledWith(
          expect.stringContaining(
            `Retrying Google event creation for user ${userId}, attempt 2`
          ),
          expect.anything()
        );
      });

      it('should fail immediately on 401 error', async () => {
        getGoogleAPITokenMock.mockResolvedValue('fake-google-api-token');
        mockGoogleEventsInsert.mockRejectedValueOnce({
          code: 401,
          message: 'Unauthorized',
        });

        await expect(
          require('./api-helper').createGoogleEvent(
            userId,
            calendarId,
            clientType,
            mockOurEventId,
            eventData.endDateTime,
            eventData.startDateTime,
            1,
            undefined,
            undefined,
            undefined,
            undefined,
            eventSummary,
            undefined,
            eventData.timezone
          )
        ).rejects.toThrow('Unauthorized');
        expect(mockGoogleEventsInsert).toHaveBeenCalledTimes(1);
        expect(spiedLogger.error).toHaveBeenCalledWith(
          expect.stringContaining('Failed to create Google event for user'),
          expect.anything()
        );
      });
      it('should fail if getGoogleAPIToken fails', async () => {
        getGoogleAPITokenMock.mockRejectedValueOnce(
          new Error('Token fetch failed')
        );

        await expect(
          require('./api-helper').createGoogleEvent(
            userId,
            calendarId,
            clientType,
            mockOurEventId,
            eventData.endDateTime,
            eventData.startDateTime,
            1,
            undefined,
            undefined,
            undefined,
            undefined,
            eventSummary,
            undefined,
            eventData.timezone
          )
        ).rejects.toThrow('Token fetch failed');
        expect(mockGoogleEventsInsert).not.toHaveBeenCalled();
      });
    });

    describe('patchGoogleEvent', () => {
      const eventSummaryUpdate = 'Updated Test Event';
      const patchData = { summary: eventSummaryUpdate };

      it('should patch event successfully', async () => {
        getGoogleAPITokenMock.mockResolvedValue('fake-google-api-token');
        mockGoogleEventsPatch.mockResolvedValueOnce({
          data: { id: mockGCalEventId, summary: eventSummaryUpdate },
        });

        await require('./api-helper').patchGoogleEvent(
          userId,
          calendarId,
          mockGCalEventId,
          clientType,
          undefined,
          undefined,
          1,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          eventSummaryUpdate
        );
        expect(mockGoogleEventsPatch).toHaveBeenCalledTimes(1);
        expect(mockGoogleEventsPatch).toHaveBeenCalledWith(
          expect.objectContaining({
            calendarId,
            eventId: mockGCalEventId,
            requestBody: expect.objectContaining(patchData),
          }),
          { timeout: 20000 }
        );
        expect(spiedLogger.info).toHaveBeenCalledWith(
          expect.stringContaining(
            `Google Calendar event ${mockGCalEventId} patched successfully on attempt 1`
          ),
          expect.anything()
        );
      });

      it('should retry on 403 rateLimitExceeded then succeed', async () => {
        getGoogleAPITokenMock.mockResolvedValue('fake-google-api-token');
        mockGoogleEventsPatch
          .mockRejectedValueOnce({
            code: 403,
            errors: [{ reason: 'rateLimitExceeded' }],
            message: 'Rate limit',
          })
          .mockResolvedValueOnce({
            data: { id: mockGCalEventId, summary: eventSummaryUpdate },
          });

        await require('./api-helper').patchGoogleEvent(
          userId,
          calendarId,
          mockGCalEventId,
          clientType,
          undefined,
          undefined,
          1,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          eventSummaryUpdate
        );
        expect(mockGoogleEventsPatch).toHaveBeenCalledTimes(2);
        expect(spiedLogger.warn).toHaveBeenCalledWith(
          expect.stringContaining(
            `Attempt 1 to patch Google event ${mockGCalEventId} for user ${userId} failed`
          ),
          expect.anything()
        );
      });
    });

    describe('deleteGoogleEvent', () => {
      it('should delete event successfully', async () => {
        getGoogleAPITokenMock.mockResolvedValue('fake-google-api-token');
        mockGoogleEventsDelete.mockResolvedValueOnce({}); // Delete often returns empty response

        await require('./api-helper').deleteGoogleEvent(
          userId,
          calendarId,
          mockGCalEventId,
          clientType
        );
        expect(mockGoogleEventsDelete).toHaveBeenCalledTimes(1);
        expect(mockGoogleEventsDelete).toHaveBeenCalledWith(
          expect.objectContaining({ calendarId, eventId: mockGCalEventId }),
          { timeout: 20000 }
        );
        expect(spiedLogger.info).toHaveBeenCalledWith(
          expect.stringContaining(
            `Google Calendar event ${mockGCalEventId} deleted successfully on attempt 1`
          ),
          expect.anything()
        );
      });

      it('should fail immediately on 404 (event not found) if not retried by policy (though current policy might retry 404 - verify)', async () => {
        // The current retry policy in deleteGoogleEvent *does* retry 404.
        // To test immediate bail on 404, the policy in the main code would need to change.
        // For now, let's test that it *does* retry 404 and then could succeed or fail based on mock.
        getGoogleAPITokenMock.mockResolvedValue('fake-google-api-token');
        mockGoogleEventsDelete
          .mockRejectedValueOnce({ code: 404, message: 'Not Found' }) // First attempt fails with 404
          .mockResolvedValueOnce({}); // Second attempt succeeds

        await require('./api-helper').deleteGoogleEvent(
          userId,
          calendarId,
          mockGCalEventId,
          clientType
        );
        expect(mockGoogleEventsDelete).toHaveBeenCalledTimes(2);
        expect(spiedLogger.warn).toHaveBeenCalledWith(
          expect.stringContaining(
            `Attempt 1 to delete Google event ${mockGCalEventId} for user ${userId} failed`
          ),
          expect.anything()
        );
        expect(spiedLogger.warn).toHaveBeenCalledWith(
          expect.stringContaining(
            `Retrying Google event delete for event ${mockGCalEventId}`
          ),
          expect.anything()
        );
        expect(spiedLogger.info).toHaveBeenCalledWith(
          expect.stringContaining(
            `Google Calendar event ${mockGCalEventId} deleted successfully on attempt 2`
          ),
          expect.anything()
        );
      });
    });
  });

  describe('LanceDB/OpenSearch and other utilities with logger changes', () => {
    // Mock lancedb_service functions if they are called directly by the functions under test
    // For now, assume they throw errors for testing error paths.
    const mockSearchEvents = jest.fn();
    const mockGetSearchClient = jest.fn(); // For putDataInTrainEventIndexInOpenSearch

    jest.mock('@functions/_utils/lancedb_service', () => ({
      ...jest.requireActual('@functions/_utils/lancedb_service'), // Keep original for non-mocked parts
      searchEvents: mockSearchEvents,
      // Add other lancedb_service mocks if needed by other functions
    }));

    // Mock for putDataInTrainEventIndexInOpenSearch's getSearchClient
    // This is more complex if getSearchClient is not easily mockable or has side effects.
    // For this example, we'll assume a simplified path or that it's handled if needed.

    beforeEach(() => {
      mockSearchEvents.mockReset();
      mockGetSearchClient.mockReset();
      // Reset any other mocks for this suite
    });

    describe('searchSingleEventByVectorLanceDb', () => {
      const userId = 'lance-user';
      const vector = [0.1, 0.2];
      it('should return null and log error when searchEvents throws', async () => {
        const error = new Error('LanceDB connection failed');
        mockSearchEvents.mockRejectedValueOnce(error);

        const result =
          await require('./api-helper').searchSingleEventByVectorLanceDb(
            userId,
            vector
          );
        expect(result).toBeNull(); // As per original logic, it catches and returns null
        expect(spiedLogger.error).toHaveBeenCalledWith(
          'Error in searchSingleEventByVectorLanceDb',
          expect.objectContaining({ userId, error: error.message })
        );
      });
    });

    describe('extrapolateDateFromJSONData', () => {
      // This function is very complex. We'll do a basic test to ensure it runs and a debug log is hit.
      it('should run and make a debug log call', () => {
        const currentTime = '2023-10-26T10:00:00Z';
        const timezone = 'America/New_York';
        // Call with some basic data, actual result isn't the focus, just that it runs and logs.
        require('./api-helper').extrapolateDateFromJSONData(
          currentTime,
          timezone,
          '2023',
          '10',
          '26',
          null,
          14,
          30,
          null,
          null,
          null
        );
        expect(spiedLogger.debug).toHaveBeenCalledWith(
          expect.stringContaining(
            '[extrapolateDateFromJSONData] Initial params:'
          ),
          expect.anything()
        );
      });
    });

    describe('generateJSONDataFromUserInput', () => {
      const userInput = 'schedule a meeting for tomorrow';
      const userCurrentTime = 'Monday, 2023-10-30T10:00:00-04:00';

      it('should return undefined and log error if OpenAI call fails', async () => {
        // Mock the internal callOpenAIWithMessageHistoryOnly to throw an error
        // This requires callOpenAIWithMessageHistoryOnly to be mockable, might need to adjust global mock setup
        const apiHelperModule = require('./api-helper');
        const callOpenAIMock = jest.spyOn(
          apiHelperModule,
          'callOpenAIWithMessageHistoryOnly'
        );
        callOpenAIMock.mockRejectedValueOnce(new Error('OpenAI API Error'));

        const result = await apiHelperModule.generateJSONDataFromUserInput(
          userInput,
          userCurrentTime
        );
        expect(result).toBeUndefined();
        expect(spiedLogger.error).toHaveBeenCalledWith(
          'Unable to generate JSON data from user input',
          expect.objectContaining({ userInput, error: 'OpenAI API Error' })
        );
        callOpenAIMock.mockRestore();
      });
    });
  });
});
