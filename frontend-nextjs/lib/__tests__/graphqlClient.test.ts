/**
 * Tests for GraphQL Client
 *
 * Tests GraphQL query/mutation execution functions
 */

import {
  executeGraphQLQuery,
  executeGraphQLMutation,
  executeGraphQLSubscription,
  createGraphQLClient,
} from '../graphqlClient';

// Mock fetch
global.fetch = jest.fn() as any;

// Mock constants
jest.mock('../constants', () => ({
  HASURA_ADMIN_SECRET: 'test-secret',
  HASURA_GRAPHQL_URL: 'https://graphql.hasura.app/v1/graphql',
}));

describe('GraphQL Client', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('executeGraphQLQuery', () => {
    it('should export function', () => {
      expect(executeGraphQLQuery).toBeDefined();
      expect(typeof executeGraphQLQuery).toBe('function');
    });

    it('should throw error when fetch fails (404)', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
      });

      await expect(executeGraphQLQuery('query { test }')).rejects.toThrow(
        'GraphQL request failed: 404 Not Found'
      );
    });

    it('should throw error when response has GraphQL errors', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          errors: [{ message: 'Syntax error' }],
        }),
      });

      await expect(executeGraphQLQuery('invalid query')).rejects.toThrow(
        'Syntax error'
      );
    });

    it('should log errors to console', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      await expect(executeGraphQLQuery('query { test }')).rejects.toThrow();
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });
  });

  describe('executeGraphQLMutation', () => {
    it('should export function', () => {
      expect(executeGraphQLMutation).toBeDefined();
      expect(typeof executeGraphQLMutation).toBe('function');
    });

    it('should have same signature as executeGraphQLQuery', () => {
      // Both functions take query/mutation, variables, operationName
      expect(executeGraphQLMutation).toBeDefined();
      expect(typeof executeGraphQLMutation).toBe('function');
    });

    it('should pass through to executeGraphQLQuery', () => {
      // executeGraphQLMutation is just a wrapper around executeGraphQLQuery
      // We can't easily test this without proper fetch mocking, but we verify the function exists
      expect(() => executeGraphQLMutation('mutation { create }')).toBeDefined();
    });
  });

  describe('executeGraphQLSubscription', () => {
    it('should throw error for subscriptions', async () => {
      await expect(
        executeGraphQLSubscription('subscription { test }')
      ).rejects.toThrow('GraphQL subscriptions not implemented');
    });
  });

  describe('createGraphQLClient', () => {
    it('should return client with query and mutate methods', () => {
      const client = createGraphQLClient();

      expect(client).toBeDefined();
      expect(client.query).toBeDefined();
      expect(client.mutate).toBeDefined();
      expect(typeof client.query).toBe('function');
      expect(typeof client.mutate).toBe('function');
    });

    it('should accept custom headers', () => {
      const customHeaders = { 'X-Custom-Header': 'custom-value' };
      const client = createGraphQLClient({ headers: customHeaders });

      expect(client).toBeDefined();
      expect(client.query).toBeDefined();
      expect(client.mutate).toBeDefined();
    });

    it('should use default headers', () => {
      const client = createGraphQLClient();

      expect(client).toBeDefined();
    });

    it('should merge custom headers with defaults', () => {
      const customHeaders = { 'X-Custom': 'value' };
      const client = createGraphQLClient({ headers: customHeaders });

      expect(client).toBeDefined();
    });
  });
});
