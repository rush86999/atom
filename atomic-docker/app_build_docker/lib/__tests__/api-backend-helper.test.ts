import { scheduleMeeting } from '../api-backend-helper';
import { ScheduleMeetingRequestType } from '../dataTypes/ScheduleMeetingRequestType';
import { SCHEDULER_API_URL } from '../constants';
import got from 'got';
import { appServiceLogger } from '../logger'; // Import the actual logger

// Mock 'got'
jest.mock('got');
// Spy on the logger methods
jest.mock('../logger', () => ({
  appServiceLogger: {
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
    debug: jest.fn(),
    fatal: jest.fn(), // Ensure all used methods are mocked
  },
}));

const mockedGot = got as jest.Mocked<typeof got>;
const mockedLogger = appServiceLogger as jest.Mocked<typeof appServiceLogger>;

describe('api-backend-helper', () => {
  // Reset mocks before each test in the suite
  beforeEach(() => {
    mockedGot.post.mockReset();
    mockedGot.get.mockReset(); // If other methods are used by resilientGot
    // Reset all logger spies
    Object.values(mockedLogger).forEach((mockFn) => mockFn.mockReset());
  });

  describe('scheduleMeeting (testing resilientGot indirectly)', () => {
    const mockPayload: ScheduleMeetingRequestType = {
      participantNames: ['Alice', 'Bob'],
      durationMinutes: 30,
      preferredDate: '2024-07-25',
      preferredStartTimeFrom: '10:00:00',
      preferredStartTimeTo: '11:00:00',
    };
    const expectedUrl = `${SCHEDULER_API_URL}/timeTable/user/scheduleMeeting`;
    const operationName = 'scheduleMeeting'; // As used in the main code

    // No longer need beforeEach for mockGot.post.mockClear() as it's in the global beforeEach

    it('should succeed on the first attempt, calling resilientGot correctly', async () => {
      const mockApiResponse = { meetingId: '123', status: 'SCHEDULED' };
      mockedGot.post.mockResolvedValueOnce({ body: mockApiResponse } as any); // resilientGot expects response.body

      const result = await scheduleMeeting(mockPayload);

      expect(result).toEqual(mockApiResponse);
      expect(mockedGot.post).toHaveBeenCalledTimes(1);
      expect(mockedGot.post).toHaveBeenCalledWith(
        expectedUrl,
        expect.objectContaining({
          json: mockPayload,
          timeout: { request: 15000 }, // Default from resilientGot
          retry: { limit: 0 }, // resilientGot handles retries
          responseType: 'json',
          headers: { 'Content-Type': 'application/json' },
        })
      );
      expect(mockedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(`[${operationName}] Called.`),
        expect.anything()
      );
      expect(mockedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(
          `[${operationName}] Attempt 1/3 - POST ${expectedUrl}`
        ),
        expect.anything()
      );
      expect(mockedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(`[${operationName}] Attempt 1 successful.`),
        expect.anything()
      );
      expect(mockedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(
          `[${operationName}] Successfully scheduled meeting.`
        ),
        expect.anything()
      );
    });

    it('should succeed on the second attempt after a 503 error', async () => {
      const mockApiResponse = { meetingId: '123', status: 'SCHEDULED' };
      mockedGot.post
        .mockRejectedValueOnce({
          response: { statusCode: 503 },
          message: 'Service Unavailable',
          isGotError: true,
        })
        .mockResolvedValueOnce({ body: mockApiResponse } as any);

      const result = await scheduleMeeting(mockPayload);
      expect(result).toEqual(mockApiResponse);
      expect(mockedGot.post).toHaveBeenCalledTimes(2);
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        expect.stringContaining(
          `[${operationName}_SchedulerAPI] Attempt 1/3 failed.`
        ),
        expect.anything()
      ); // resilientGot's internal opName
      expect(mockedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(
          `[${operationName}_SchedulerAPI] Waiting 1000ms before retry 2/3.`
        ),
        expect.anything()
      );
      expect(mockedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(
          `[${operationName}] Successfully scheduled meeting.`
        ),
        expect.anything()
      );
    });

    it('should fail after all retries for persistent 500 errors', async () => {
      mockedGot.post.mockRejectedValue({
        response: { statusCode: 500 },
        message: 'Internal Server Error',
        isGotError: true,
      });

      await expect(scheduleMeeting(mockPayload)).rejects.toThrow(
        'Internal Server Error'
      );
      expect(mockedGot.post).toHaveBeenCalledTimes(3);
      expect(mockedLogger.error).toHaveBeenCalledWith(
        expect.stringContaining(
          `[${operationName}_SchedulerAPI] Failed after 3 attempts.`
        ),
        expect.anything()
      ); // resilientGot log
      expect(mockedLogger.error).toHaveBeenCalledWith(
        expect.stringContaining(
          `[${operationName}] Error calling scheduleMeeting API.`
        ),
        expect.anything()
      ); // scheduleMeeting log
    });

    it('should fail immediately on a non-retryable 400 error from resilientGot', async () => {
      const apiError = {
        response: {
          statusCode: 400,
          body: JSON.stringify({ message: 'Invalid participants' }),
        },
        message: 'Bad Request',
        isGotError: true,
      };
      mockedGot.post.mockRejectedValueOnce(apiError);

      await expect(scheduleMeeting(mockPayload)).rejects.toThrow(
        'API Error from scheduleMeeting_SchedulerAPI: Invalid participants'
      );
      expect(mockedGot.post).toHaveBeenCalledTimes(1);
      expect(mockedLogger.error).toHaveBeenCalledWith(
        expect.stringContaining(
          `[${operationName}_SchedulerAPI] Non-retryable error encountered. Aborting retries.`
        ),
        expect.anything()
      );
      expect(mockedLogger.error).toHaveBeenCalledWith(
        expect.stringContaining(
          `[${operationName}] Error calling scheduleMeeting API.`
        ),
        expect.anything()
      );
    });

    it('should handle timeout from resilientGot (ETIMEDOUT)', async () => {
      const mockApiResponse = { meetingId: '123', status: 'SCHEDULED' };
      mockedGot.post
        .mockRejectedValueOnce({
          code: 'ETIMEDOUT',
          message: 'Connection timed out',
          isGotError: true,
        })
        .mockResolvedValueOnce({ body: mockApiResponse } as any);

      const result = await scheduleMeeting(mockPayload);
      expect(result).toEqual(mockApiResponse);
      expect(mockedGot.post).toHaveBeenCalledTimes(2);
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        expect.stringContaining(
          `[${operationName}_SchedulerAPI] Attempt 1/3 failed.`
        ),
        expect.objectContaining({ errorCode: 'ETIMEDOUT' })
      );
    });

    // Test the specific error message construction in scheduleMeeting's catch block
    it('should throw correctly structured error when resilientGot rethrows a got error with JSON body', async () => {
      const errorBody = { message: 'Specific API error message' };
      const gotError = {
        response: {
          statusCode: 422,
          body: JSON.stringify(errorBody),
        },
        message: 'Request failed with status code 422',
        isGotError: true,
      };
      mockedGot.post.mockRejectedValueOnce(gotError);

      await expect(scheduleMeeting(mockPayload)).rejects.toThrow(
        `API Error from ${operationName}_SchedulerAPI: Specific API error message`
      );
    });

    it('should throw correctly structured error when resilientGot rethrows a got error with non-JSON body', async () => {
      const errorBodyText = 'A plain text error from server';
      const gotError = {
        response: {
          statusCode: 503,
          body: errorBodyText,
        },
        message: 'Service unavailable',
        isGotError: true,
      };
      // resilientGot will retry 503s, so make all attempts fail
      mockedGot.post.mockRejectedValue(gotError);

      await expect(scheduleMeeting(mockPayload)).rejects.toThrow(
        `API Error from ${operationName}_SchedulerAPI: ${errorBodyText}`
      );
    });
  });

  describe('exchangeCodeForTokens', () => {
    const mockCode = 'auth-code-123';
    const mockTokens = {
      access_token: 'acc_token',
      refresh_token: 'ref_token',
      expiry_date: Date.now() + 3600000,
    };

    // Mock the googleapis auth client
    const mockGetToken = jest.fn();
    // Original: const oauth2Client = new google.auth.OAuth2(...)
    // We need to mock the globally instantiated oauth2Client or google.auth.OAuth2 itself.
    // For simplicity, let's assume we can mock the instance's method used in the actual code.
    // This requires careful setup if the instance is created at module scope.
    // A common way is to mock the 'googleapis' module.

    let originalGoogleAuth: any;

    beforeAll(() => {
      originalGoogleAuth = jest.requireActual('googleapis').google.auth;
      const { google } = jest.requireActual('googleapis');
      google.auth = {
        OAuth2: jest.fn(() => ({
          getToken: mockGetToken,
          setCredentials: jest.fn(), // Mock this if it's called
          generateAuthUrl: jest.fn(), // Mock this if it's called by other tested funcs
        })),
      };
      // This re-imports with the google.auth mocked.
      // It's a bit tricky; ensure api-backend-helper uses this mocked version.
      // Alternative: Directly mock the oauth2Client instance if it's exported or accessible.
    });

    afterAll(() => {
      // Restore original googleapis auth
      const { google } = jest.requireActual('googleapis');
      google.auth = originalGoogleAuth;
    });

    beforeEach(() => {
      mockGetToken.mockReset();
    });

    it('should exchange code for tokens successfully and log info', async () => {
      mockGetToken.mockResolvedValueOnce({ tokens: mockTokens });
      const {
        exchangeCodeForTokens: exchangeCodeFunc,
      } = require('../api-backend-helper'); // Re-require to get potentially mocked version

      const result = await exchangeCodeFunc(mockCode);

      expect(result).toEqual(mockTokens);
      expect(mockGetToken).toHaveBeenCalledWith(mockCode);
      expect(mockedLogger.info).toHaveBeenCalledWith(
        '[exchangeCodeForTokens] Successfully exchanged code for tokens.',
        expect.objectContaining({ codePrefix: mockCode.substring(0, 10) })
      );
    });

    it('should log error and re-throw if token exchange fails', async () => {
      const error = new Error('Exchange failed');
      mockGetToken.mockRejectedValueOnce(error);
      const {
        exchangeCodeForTokens: exchangeCodeFunc,
      } = require('../api-backend-helper');

      await expect(exchangeCodeFunc(mockCode)).rejects.toThrow(
        'Exchange failed'
      );
      expect(mockGetToken).toHaveBeenCalledWith(mockCode);
      expect(mockedLogger.error).toHaveBeenCalledWith(
        '[exchangeCodeForTokens] Unable to exchange code for tokens.',
        expect.objectContaining({ error: error.message })
      );
    });
  });

  // Add tests for getMinimalCalendarIntegrationByResource (as another resilientGot consumer)
  describe('getMinimalCalendarIntegrationByResource (testing resilientGot for Hasura)', () => {
    const userId = 'test-user-hasura';
    const resource = 'google_calendar';
    const operationName = 'getCalendarIntegration'; // Internal operation name
    const mockIntegration = {
      id: 'integ-1',
      resource: 'google_calendar',
      token: 'token',
    };

    it('should fetch integration successfully using resilientGot', async () => {
      mockedGot.post.mockResolvedValueOnce({
        body: { data: { Calendar_Integration: [mockIntegration] } },
      } as any);
      const {
        getMinimalCalendarIntegrationByResource: getIntegFunc,
      } = require('../api-backend-helper');

      const result = await getIntegFunc(userId, resource);
      expect(result).toEqual(mockIntegration);
      expect(mockedGot.post).toHaveBeenCalledTimes(1);
      expect(mockedGot.post).toHaveBeenCalledWith(
        hasuraGraphUrl,
        expect.objectContaining({
          json: expect.objectContaining({ operationName }),
        })
      );
      expect(mockedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(`[${operationName}] Attempt 1/3`),
        expect.anything()
      );
    });

    it('should return undefined and log info if no integration found', async () => {
      mockedGot.post.mockResolvedValueOnce({
        body: { data: { Calendar_Integration: [] } },
      } as any);
      const {
        getMinimalCalendarIntegrationByResource: getIntegFunc,
      } = require('../api-backend-helper');

      const result = await getIntegFunc(userId, resource);
      expect(result).toBeUndefined();
      expect(mockedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(`[${operationName}] No integration found`),
        expect.anything()
      );
    });

    it('should re-throw error from resilientGot if Hasura call fails after retries', async () => {
      mockedGot.post.mockRejectedValue(new Error('Hasura down')); // All attempts fail
      const {
        getMinimalCalendarIntegrationByResource: getIntegFunc,
      } = require('../api-backend-helper');

      await expect(getIntegFunc(userId, resource)).rejects.toThrow(
        'Hasura down'
      );
      expect(mockedLogger.error).toHaveBeenCalledWith(
        expect.stringContaining(`[${operationName}] Failed after 3 attempts`),
        expect.anything()
      ); // from resilientGot
      expect(mockedLogger.error).toHaveBeenCalledWith(
        expect.stringContaining(
          `[${operationName}] Unable to get calendar integration.`
        ),
        expect.anything()
      ); // from getMinimalCalendarIntegrationByResource
    });
  });

  describe('refreshGoogleToken (atomic-web path using resilientGot)', () => {
    const refreshToken = 'google-refresh-token';
    const clientType = 'atomic-web';
    const operationName = 'refreshGoogleToken'; // As used in the main code for this specific call path
    const mockGoogleSuccessResponse = {
      access_token: 'new_google_token',
      expires_in: 3599,
      scope: 'test_scope',
      token_type: 'Bearer',
    };
    const googleTokenUrl = 'https://oauth2.googleapis.com/token'; // from constants

    it('should refresh token successfully via resilientGot for atomic-web', async () => {
      mockedGot.post.mockResolvedValueOnce({
        body: mockGoogleSuccessResponse,
      } as any);
      const {
        refreshGoogleToken: refreshFunc,
      } = require('../api-backend-helper');

      const result = await refreshFunc(refreshToken, clientType);
      expect(result).toEqual(mockGoogleSuccessResponse);
      expect(mockedGot.post).toHaveBeenCalledTimes(1);
      expect(mockedGot.post).toHaveBeenCalledWith(
        googleTokenUrl,
        expect.objectContaining({
          form: expect.objectContaining({
            grant_type: 'refresh_token',
            refresh_token: refreshToken,
          }),
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          responseType: 'json',
        })
      );
      expect(mockedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(`[${operationName}] Called.`),
        { clientType }
      );
      expect(mockedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(`[${operationName}] Attempt 1/3`),
        expect.anything()
      ); // from resilientGot
      expect(mockedLogger.info).toHaveBeenCalledWith(
        expect.stringContaining(
          `[${operationName}] Token refresh successful for clientType: ${clientType}.`
        ),
        expect.anything()
      );
    });

    it('should retry and succeed for atomic-web if resilientGot handles retryable error', async () => {
      mockedGot.post
        .mockRejectedValueOnce({
          response: { statusCode: 500 },
          message: 'Server Error',
          isGotError: true,
        })
        .mockResolvedValueOnce({ body: mockGoogleSuccessResponse } as any);
      const {
        refreshGoogleToken: refreshFunc,
      } = require('../api-backend-helper');

      const result = await refreshFunc(refreshToken, clientType);
      expect(result).toEqual(mockGoogleSuccessResponse);
      expect(mockedGot.post).toHaveBeenCalledTimes(2);
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        expect.stringContaining(`[${operationName}] Attempt 1/3 failed.`),
        expect.anything()
      ); // from resilientGot
    });

    it('should throw error if resilientGot fails after all retries for atomic-web', async () => {
      mockedGot.post.mockRejectedValue(new Error('Token endpoint down'));
      const {
        refreshGoogleToken: refreshFunc,
      } = require('../api-backend-helper');

      await expect(refreshFunc(refreshToken, clientType)).rejects.toThrow(
        'Token endpoint down'
      );
      expect(mockedGot.post).toHaveBeenCalledTimes(3);
      expect(mockedLogger.error).toHaveBeenCalledWith(
        expect.stringContaining(`[${operationName}] Failed after 3 attempts`),
        expect.anything()
      ); // from resilientGot
      expect(mockedLogger.error).toHaveBeenCalledWith(
        expect.stringContaining(
          `[${operationName}] Unable to refresh Google token.`
        ),
        expect.anything()
      ); // from refreshGoogleToken
    });

    it('should return undefined if clientType is not atomic-web and not configured for got', async () => {
      const {
        refreshGoogleToken: refreshFunc,
      } = require('../api-backend-helper');
      const result = await refreshFunc(refreshToken, 'web'); // 'web' is not configured for direct got call in this func
      expect(result).toBeUndefined();
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        expect.stringContaining(
          `[${operationName}] Client type 'web' not configured for direct got-based token refresh in this function.`
        )
      );
    });
  });
});
