import axios from 'axios';
import { executeGraphQLQuery, executeGraphQLMutation } from './graphqlClient';
import { HASURA_GRAPHQL_URL, HASURA_ADMIN_SECRET } from './constants';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock constants
jest.mock('./constants', () => ({
  HASURA_GRAPHQL_URL: 'http://test-hasura.com/v1/graphql',
  HASURA_ADMIN_SECRET: 'test-admin-secret',
}));

describe('graphqlClient', () => {
  const query = 'query TestQuery { test { id } }';
  const variables = { id: '123' };
  const operationName = 'TestQuery';
  const userId = 'test-user';

  const mockSuccessData = { test: { id: '123', name: 'Test Data' } };
  const mockGraphQLErrors = [{ message: 'Some GraphQL error' }];

  beforeEach(() => {
    mockedAxios.post.mockReset();
    // jest.resetModules() // Not strictly needed here if constants are properly mocked via jest.mock factory
    // Spy on console.error and console.warn to check logging
    jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('executeGraphQLQuery', () => {
    it('should execute query successfully on first attempt', async () => {
      mockedAxios.post.mockResolvedValueOnce({
        data: { data: mockSuccessData },
      });
      const result = await executeGraphQLQuery(
        query,
        variables,
        operationName,
        userId
      );
      expect(result).toEqual(mockSuccessData);
      expect(mockedAxios.post).toHaveBeenCalledTimes(1);
      expect(mockedAxios.post).toHaveBeenCalledWith(
        HASURA_GRAPHQL_URL,
        { query, variables, operationName },
        {
          headers: {
            'Content-Type': 'application/json',
            'X-Hasura-Admin-Secret': HASURA_ADMIN_SECRET,
            'X-Hasura-Role': 'user',
            'X-Hasura-User-Id': userId,
          },
          timeout: 15000,
        }
      );
    });

    it('should use admin role if userId is not provided', async () => {
      mockedAxios.post.mockResolvedValueOnce({
        data: { data: mockSuccessData },
      });
      await executeGraphQLQuery(query, variables, operationName);
      expect(mockedAxios.post).toHaveBeenCalledWith(
        HASURA_GRAPHQL_URL,
        expect.anything(),
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-Hasura-Role': 'admin',
            'X-Hasura-User-Id': undefined,
          }),
        })
      );
    });

    it('should succeed on the second attempt after a 503 error', async () => {
      mockedAxios.post
        .mockRejectedValueOnce({
          isAxiosError: true,
          response: { status: 503, data: 'Service Unavailable' },
          request: {},
          config: {},
        })
        .mockResolvedValueOnce({ data: { data: mockSuccessData } });

      const result = await executeGraphQLQuery(
        query,
        variables,
        operationName,
        userId
      );
      expect(result).toEqual(mockSuccessData);
      expect(mockedAxios.post).toHaveBeenCalledTimes(2);
      expect(console.error).toHaveBeenCalledWith(
        expect.stringContaining('HTTP error 503'),
        expect.any(String)
      );
    });

    it('should succeed on the second attempt after a timeout (ECONNABORTED)', async () => {
      mockedAxios.post
        .mockRejectedValueOnce({
          isAxiosError: true,
          code: 'ECONNABORTED',
          message: 'timeout exceeded',
          request: {},
          config: {},
        })
        .mockResolvedValueOnce({ data: { data: mockSuccessData } });

      const result = await executeGraphQLQuery(
        query,
        variables,
        operationName,
        userId
      );
      expect(result).toEqual(mockSuccessData);
      expect(mockedAxios.post).toHaveBeenCalledTimes(2);
      // Check console.warn for timeout log
      expect(console.warn).toHaveBeenCalledWith(
        expect.stringContaining(
          `Network error or timeout for GraphQL operation '${operationName}'`
        ),
        expect.any(String)
      );
    });

    it('should fail after all retries for persistent 500 errors', async () => {
      mockedAxios.post
        .mockRejectedValueOnce({
          isAxiosError: true,
          response: { status: 500, data: 'Server Error 1' },
          request: {},
          config: {},
        })
        .mockRejectedValueOnce({
          isAxiosError: true,
          response: { status: 500, data: 'Server Error 2' },
          request: {},
          config: {},
        })
        .mockRejectedValueOnce({
          isAxiosError: true,
          response: { status: 500, data: 'Server Error 3' },
          request: {},
          config: {},
        });

      await expect(
        executeGraphQLQuery(query, variables, operationName, userId)
      ).rejects.toThrow(
        expect.objectContaining({
          message: `HTTP error 500 executing operation '${operationName}'. Not retrying.`,
        }) // The last error thrown before retry logic gives up
      );
      expect(mockedAxios.post).toHaveBeenCalledTimes(3);
      expect(console.error).toHaveBeenCalledWith(
        expect.stringContaining('Failed GraphQL operation'),
        expect.anything()
      );
    });

    it('should fail immediately on a non-retryable 400 error', async () => {
      mockedAxios.post.mockRejectedValueOnce({
        isAxiosError: true,
        response: { status: 400, data: 'Bad Request' },
        request: {},
        config: {},
      });

      await expect(
        executeGraphQLQuery(query, variables, operationName, userId)
      ).rejects.toThrow(
        expect.objectContaining({
          message: `HTTP error 400 executing operation '${operationName}'. Not retrying.`,
        })
      );
      expect(mockedAxios.post).toHaveBeenCalledTimes(1);
      expect(console.error).toHaveBeenCalledWith(
        expect.stringContaining('HTTP error 400'),
        expect.any(String)
      );
      expect(console.error).toHaveBeenCalledWith(
        expect.stringContaining('Failed GraphQL operation'),
        expect.anything()
      );
    });

    it('should retry on GraphQL execution errors then succeed', async () => {
      mockedAxios.post
        .mockResolvedValueOnce({ data: { errors: mockGraphQLErrors } })
        .mockResolvedValueOnce({ data: { data: mockSuccessData } });

      const result = await executeGraphQLQuery(
        query,
        variables,
        operationName,
        userId
      );
      expect(result).toEqual(mockSuccessData);
      expect(mockedAxios.post).toHaveBeenCalledTimes(2);
      expect(console.error).toHaveBeenCalledWith(
        'GraphQL errors:',
        JSON.stringify(mockGraphQLErrors, null, 2)
      );
    });

    it('should fail after all retries for persistent GraphQL errors', async () => {
      mockedAxios.post.mockResolvedValue({
        data: { errors: mockGraphQLErrors },
      }); // Fails all 3 times

      await expect(
        executeGraphQLQuery(query, variables, operationName, userId)
      ).rejects.toThrow(
        expect.objectContaining({
          message: `GraphQL error executing operation '${operationName}'.`,
        })
      );
      expect(mockedAxios.post).toHaveBeenCalledTimes(3);
      expect(console.error).toHaveBeenCalledTimes(3 + 1); // 3 for each attempt's GraphQL error log, 1 for final failure
    });

    it('should throw config error if HASURA_GRAPHQL_URL is not set', async () => {
      const originalUrl = (constants as any).HASURA_GRAPHQL_URL;
      (constants as any).HASURA_GRAPHQL_URL = undefined;

      await expect(
        executeGraphQLQuery(query, variables, operationName, userId)
      ).rejects.toThrow(
        'Hasura GraphQL URL or Admin Secret is not configured.'
      );
      (constants as any).HASURA_GRAPHQL_URL = originalUrl; // Restore
    });
  });

  describe('executeGraphQLMutation', () => {
    // Since executeGraphQLMutation just calls executeGraphQLQuery, we only need a basic test
    // to ensure it's wired up correctly. The retry/timeout logic is tested via executeGraphQLQuery.
    it('should execute mutation successfully', async () => {
      const mutation = 'mutation TestMutation { testMutate { id } }';
      mockedAxios.post.mockResolvedValueOnce({
        data: { data: mockSuccessData },
      });
      const result = await executeGraphQLMutation(
        mutation,
        variables,
        'TestMutation',
        userId
      );
      expect(result).toEqual(mockSuccessData);
      expect(mockedAxios.post).toHaveBeenCalledTimes(1);
      expect(mockedAxios.post).toHaveBeenCalledWith(
        HASURA_GRAPHQL_URL,
        { query: mutation, variables, operationName: 'TestMutation' },
        expect.anything()
      );
    });
  });
});
