import {
  ApolloClient,
  gql,
  HttpLink,
  InMemoryCache,
  ServerError,
  ServerParseError,
} from '@apollo/client';
import { RetryLink } from '@apollo/client/link/retry';
import { onError } from '@apollo/client/link/error';
import { setContext } from '@apollo/client/link/context';
import { appServiceLogger } from '../../logger'; // Actual logger
import makeApolloClient from '../apollo'; // The function we want to test (indirectly its RetryLink)

// Mock Session from supertokens-web-js
jest.mock('supertokens-web-js/recipe/session', () => ({
  __esModule: true,
  default: {
    getAccessToken: jest.fn().mockResolvedValue('mock-access-token'),
  },
}));

// Mock the logger for verification
jest.mock('../../logger', () => ({
  appServiceLogger: {
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
    debug: jest.fn(),
  },
}));
const mockedLogger = appServiceLogger as jest.Mocked<typeof appServiceLogger>;

// Mock 'got' which might be used by HttpLink under the hood, or node-fetch.
// For HttpLink, it typically uses `fetch`. We'll mock global fetch for these tests.
const mockFetch = jest.fn();
global.fetch = mockFetch as any;

describe('Apollo Client with RetryLink', () => {
  let client: ApolloClient<any>;

  const GET_TEST_DATA = gql`
    query GetTestData {
      testData {
        id
        value
      }
    }
  `;

  beforeEach(() => {
    mockFetch.mockReset();
    // Reset all logger spies
    Object.values(mockedLogger).forEach((mockFn) => mockFn.mockReset());

    // Create a new client for each test to ensure isolation
    // makeApolloClient expects a token, but it's for WebSocket, HttpLink uses setContext
    client = makeApolloClient('mock-ws-token');
  });

  it('should succeed on the first attempt if fetch is successful', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ data: { testData: { id: '1', value: 'success' } } }),
      text: async () =>
        JSON.stringify({ data: { testData: { id: '1', value: 'success' } } }),
      headers: new Headers({ 'Content-Type': 'application/json' }),
    });

    const { data } = await client.query({ query: GET_TEST_DATA });
    expect(data.testData.value).toBe('success');
    expect(mockFetch).toHaveBeenCalledTimes(1);
    // Logger for UNAUTHENTICATED might still be called if errorLink is processed even on success for some reason (unlikely for this path)
    // More specific logging checks would depend on what RetryLink logs on success (usually nothing)
  });

  it('should retry on a 503 server error and then succeed', async () => {
    mockFetch
      .mockResolvedValueOnce({
        // Attempt 1: Fails with 503
        ok: false,
        status: 503,
        statusText: 'Service Unavailable',
        json: async () => ({ errors: [{ message: 'Service Unavailable' }] }),
        text: async () =>
          JSON.stringify({ errors: [{ message: 'Service Unavailable' }] }),
        headers: new Headers({ 'Content-Type': 'application/json' }),
      })
      .mockResolvedValueOnce({
        // Attempt 2: Succeeds
        ok: true,
        json: async () => ({
          data: { testData: { id: '1', value: 'retry success' } },
        }),
        text: async () =>
          JSON.stringify({
            data: { testData: { id: '1', value: 'retry success' } },
          }),
        headers: new Headers({ 'Content-Type': 'application/json' }),
      });

    const { data } = await client.query({ query: GET_TEST_DATA });
    expect(data.testData.value).toBe('retry success');
    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(mockedLogger.warn).toHaveBeenCalledWith(
      expect.objectContaining({
        message: expect.stringContaining(
          'RetryLink: Retrying due to server error.'
        ),
      }),
      expect.anything() // This was the format in the RetryLink logger call
    );
  });

  it('should fail after max retries for persistent 500 errors', async () => {
    mockFetch.mockResolvedValue({
      // All attempts fail
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => ({ errors: [{ message: 'Internal Server Error' }] }),
      text: async () =>
        JSON.stringify({ errors: [{ message: 'Internal Server Error' }] }),
      headers: new Headers({ 'Content-Type': 'application/json' }),
    });

    await expect(client.query({ query: GET_TEST_DATA })).rejects.toThrow(); // Throws ApolloError
    expect(mockFetch).toHaveBeenCalledTimes(4); // 1 initial + 3 retries
    expect(mockedLogger.warn).toHaveBeenCalledTimes(3); // For each retry attempt
    expect(mockedLogger.warn).toHaveBeenLastCalledWith(
      expect.objectContaining({
        message: expect.stringContaining(
          'RetryLink: Retrying due to server error.'
        ),
      }),
      expect.anything()
    );
    // The onError link will also log the final networkError
    expect(mockedLogger.error).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'NetworkError' }),
      expect.stringContaining(
        '[ApolloLinkNetworkError]: Response not successful: Received status code 500'
      )
    );
  });

  it('should not retry on a 400 client error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: async () => ({ errors: [{ message: 'Bad Request' }] }),
      text: async () =>
        JSON.stringify({ errors: [{ message: 'Bad Request' }] }),
      headers: new Headers({ 'Content-Type': 'application/json' }),
    });

    await expect(client.query({ query: GET_TEST_DATA })).rejects.toThrow();
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockedLogger.warn).not.toHaveBeenCalledWith(
      expect.stringContaining('RetryLink: Retrying due to server error.'),
      expect.anything()
    );
    expect(mockedLogger.debug).toHaveBeenCalledWith(
      // RetryLink logs 'Not retrying' at debug
      expect.objectContaining({
        message: expect.stringContaining('RetryLink: Not retrying this error.'),
      }),
      expect.anything()
    );
    expect(mockedLogger.error).toHaveBeenCalledWith(
      // onError link logs the final error
      expect.objectContaining({ type: 'NetworkError' }),
      expect.stringContaining(
        '[ApolloLinkNetworkError]: Response not successful: Received status code 400'
      )
    );
  });

  it('should retry on a network error (fetch throws)', async () => {
    mockFetch
      .mockRejectedValueOnce(new TypeError('Network request failed')) // Attempt 1: Network error
      .mockResolvedValueOnce({
        // Attempt 2: Succeeds
        ok: true,
        json: async () => ({
          data: { testData: { id: '1', value: 'network retry success' } },
        }),
        text: async () =>
          JSON.stringify({
            data: { testData: { id: '1', value: 'network retry success' } },
          }),
        headers: new Headers({ 'Content-Type': 'application/json' }),
      });

    const { data } = await client.query({ query: GET_TEST_DATA });
    expect(data.testData.value).toBe('network retry success');
    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(mockedLogger.warn).toHaveBeenCalledWith(
      expect.objectContaining({
        message: expect.stringContaining(
          'RetryLink: Retrying due to network error.'
        ),
      }),
      expect.anything()
    );
  });
});
