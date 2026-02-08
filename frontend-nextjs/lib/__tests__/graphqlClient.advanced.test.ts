/**
 * Advanced Tests for GraphQL Client
 *
 * Additional tests to improve coverage from 56% to 80%+
 */

import {
  executeGraphQLQuery,
  executeGraphQLMutation,
  executeGraphQLSubscription,
  createGraphQLClient,
} from '../graphqlClient';

// Mock fetch
global.fetch = jest.fn();

// Mock constants
jest.mock('../constants', () => ({
  HASURA_ADMIN_SECRET: 'test-secret',
  HASURA_GRAPHQL_URL: 'https://graphql.hasura.app/v1/graphql',
}));

describe('GraphQL Client - Advanced Coverage Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('executeGraphQLQuery - Success Paths', () => {
    it('should return data on successful query', async () => {
      const mockData = { user: { id: '1', name: 'Test User' } };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockData }),
      });

      const result = await executeGraphQLQuery('query { user { id name } }');

      expect(result).toEqual(mockData);
      expect(global.fetch).toHaveBeenCalledWith(
        'https://graphql.hasura.app/v1/graphql',
        expect.objectContaining({
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'x-hasura-admin-secret': 'test-secret',
          },
        })
      );
    });

    it('should pass variables in request body', async () => {
      const mockData = { user: { id: '1' } };
      const variables = { userId: '1' };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockData }),
      });

      await executeGraphQLQuery('query GetUser($userId: ID!) { user(id: $userId) { id } }', variables);

      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);

      expect(body.variables).toEqual(variables);
    });

    it('should pass operationName in request body', async () => {
      const mockData = { user: { id: '1' } };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockData }),
      });

      await executeGraphQLQuery('query GetUser { user { id } }', undefined, 'GetUser');

      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);

      expect(body.operationName).toBe('GetUser');
    });

    it('should pass userId parameter (for logging)', async () => {
      const mockData = { user: { id: '1' } };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockData }),
      });

      const result = await executeGraphQLQuery('query { user { id } }', undefined, undefined, 'user-123');

      expect(result).toEqual(mockData);
    });

    it('should handle empty data response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: null }),
      });

      const result = await executeGraphQLQuery('query { user { id } }');

      expect(result).toBeNull();
    });

    it('should handle missing data field', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      const result = await executeGraphQLQuery('query { user { id } }');

      expect(result).toBeUndefined();
    });
  });

  describe('executeGraphQLQuery - Error Handling', () => {
    it('should throw error on single GraphQL error', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          errors: [{ message: 'Syntax error' }],
        }),
      });

      await expect(executeGraphQLQuery('invalid query')).rejects.toThrow('Syntax error');
    });

    it('should throw combined error on multiple GraphQL errors', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          errors: [
            { message: 'Field error' },
            { message: 'Argument error' },
            { message: 'Type error' },
          ],
        }),
      });

      await expect(executeGraphQLQuery('bad query')).rejects.toThrow('Field error, Argument error, Type error');
    });

    it('should not throw when errors array is empty', async () => {
      const mockData = { user: { id: '1' } };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockData, errors: [] }),
      });

      const result = await executeGraphQLQuery('query { user { id } }');

      expect(result).toEqual(mockData);
    });

    it('should log error to console on failure', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network failure'));

      await expect(executeGraphQLQuery('query { user { id } }')).rejects.toThrow();

      expect(consoleSpy).toHaveBeenCalledWith('GraphQL query error:', expect.any(Error));

      consoleSpy.mockRestore();
    });

    it('should handle 500 Internal Server Error', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      });

      await expect(executeGraphQLQuery('query { user { id } }')).rejects.toThrow(
        'GraphQL request failed: 500 Internal Server Error'
      );
    });

    it('should handle 401 Unauthorized', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
      });

      await expect(executeGraphQLQuery('query { user { id } }')).rejects.toThrow(
        'GraphQL request failed: 401 Unauthorized'
      );
    });

    it('should handle 403 Forbidden', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 403,
        statusText: 'Forbidden',
      });

      await expect(executeGraphQLQuery('query { user { id } }')).rejects.toThrow(
        'GraphQL request failed: 403 Forbidden'
      );
    });
  });

  describe('executeGraphQLMutation', () => {
    it('should execute mutation successfully', async () => {
      const mockData = { createUser: { id: '123', name: 'New User' } };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockData }),
      });

      const result = await executeGraphQLMutation(
        'mutation CreateUser($name: String!) { createUser(name: $name) { id name } }',
        { name: 'New User' }
      );

      expect(result).toEqual(mockData);
    });

    it('should pass variables to mutation', async () => {
      const mockData = { updateUser: { id: '1', name: 'Updated' } };
      const variables = { id: '1', name: 'Updated' };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockData }),
      });

      await executeGraphQLMutation('mutation UpdateUser($id: ID!, $name: String!) { updateUser(id: $id, name: $name) { id name } }', variables);

      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);

      expect(body.variables).toEqual(variables);
    });

    it('should pass operationName to mutation', async () => {
      const mockData = { deleteUser: { id: '1' } };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockData }),
      });

      await executeGraphQLMutation('mutation DeleteUser { deleteUser { id } }', undefined, 'DeleteUser');

      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);

      expect(body.operationName).toBe('DeleteUser');
    });

    it('should pass userId parameter to mutation', async () => {
      const mockData = { createUser: { id: '1' } };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockData }),
      });

      await executeGraphQLMutation('mutation CreateUser { createUser { id } }', undefined, undefined, 'user-456');

      expect(global.fetch).toHaveBeenCalled();
    });

    it('should handle mutation errors', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          errors: [{ message: 'Validation error' }],
        }),
      });

      await expect(executeGraphQLMutation('mutation BadMutation { badMutation }')).rejects.toThrow('Validation error');
    });

    it('should handle mutation HTTP errors', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 400,
        statusText: 'Bad Request',
      });

      await expect(executeGraphQLMutation('mutation { bad }')).rejects.toThrow('GraphQL request failed: 400 Bad Request');
    });
  });

  describe('createGraphQLClient - Query Method', () => {
    it('should execute query through client', async () => {
      const mockData = { user: { id: '1', name: 'Test' } };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockData }),
      });

      const client = createGraphQLClient();
      const result = await client.query('query { user { id name } }');

      expect(result).toEqual(mockData);
    });

    it('should pass variables through client query', async () => {
      const mockData = { user: { id: '1' } };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockData }),
      });

      const client = createGraphQLClient();
      await client.query('query GetUser($id: ID!) { user(id: $id) { id } }', { id: '1' });

      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);

      expect(body.variables).toEqual({ id: '1' });
    });

    it('should pass operationName through client query', async () => {
      const mockData = { user: { id: '1' } };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockData }),
      });

      const client = createGraphQLClient();
      await client.query('query GetUser { user { id } }', undefined, 'GetUser');

      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);

      expect(body.operationName).toBe('GetUser');
    });

    it('should handle client query errors', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          errors: [{ message: 'Query error' }],
        }),
      });

      const client = createGraphQLClient();

      await expect(client.query('query { bad }')).rejects.toThrow('Query error');
    });

    it('should handle client query HTTP errors', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Server Error',
      });

      const client = createGraphQLClient();

      await expect(client.query('query { user }')).rejects.toThrow('GraphQL query failed: 500 Server Error');
    });
  });

  describe('createGraphQLClient - Mutate Method', () => {
    it('should execute mutation through client', async () => {
      const mockData = { createUser: { id: '123', name: 'New' } };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockData }),
      });

      const client = createGraphQLClient();
      const result = await client.mutate('mutation CreateUser { createUser { id name } }');

      expect(result).toEqual(mockData);
    });

    it('should pass variables through client mutate', async () => {
      const mockData = { updateUser: { id: '1', name: 'Updated' } };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockData }),
      });

      const client = createGraphQLClient();
      await client.mutate('mutation UpdateUser($name: String!) { updateUser(name: $name) { id name } }', { name: 'Updated' });

      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);

      expect(body.variables).toEqual({ name: 'Updated' });
    });

    it('should pass operationName through client mutate', async () => {
      const mockData = { deleteUser: { id: '1' } };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: mockData }),
      });

      const client = createGraphQLClient();
      await client.mutate('mutation DeleteUser { deleteUser { id } }', undefined, 'DeleteUser');

      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);

      expect(body.operationName).toBe('DeleteUser');
    });

    it('should handle client mutate errors', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          errors: [{ message: 'Mutation error' }],
        }),
      });

      const client = createGraphQLClient();

      await expect(client.mutate('mutation { badMutation }')).rejects.toThrow('Mutation error');
    });

    it('should handle client mutate HTTP errors', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 400,
        statusText: 'Bad Request',
      });

      const client = createGraphQLClient();

      await expect(client.mutate('mutation { bad }')).rejects.toThrow('GraphQL request failed: 400 Bad Request');
    });
  });

  describe('createGraphQLClient - Custom Headers', () => {
    it('should merge custom headers with defaults', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: {} }),
      });

      const customHeaders = {
        'Authorization': 'Bearer token123',
        'X-Custom-Header': 'custom-value',
      };

      const client = createGraphQLClient({ headers: customHeaders });
      await client.query('query { user { id } }');

      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];

      expect(fetchCall[1].headers).toEqual({
        'Content-Type': 'application/json',
        'x-hasura-admin-secret': 'test-secret',
        'Authorization': 'Bearer token123',
        'X-Custom-Header': 'custom-value',
      });
    });

    it('should allow overriding default headers', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: {} }),
      });

      const client = createGraphQLClient({
        headers: {
          'x-hasura-admin-secret': 'different-secret',
        },
      });

      await client.query('query { user { id } }');

      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];

      expect(fetchCall[1].headers['x-hasura-admin-secret']).toBe('different-secret');
    });

    it('should use custom headers for query but mutate uses defaults (known limitation)', async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: {} }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: {} }),
        });

      const client = createGraphQLClient({
        headers: { 'X-Request-ID': 'req-123' },
      });

      await client.query('query { user }');
      await client.mutate('mutation { createUser }');

      const queryCall = (global.fetch as jest.Mock).mock.calls[0];
      const mutateCall = (global.fetch as jest.Mock).mock.calls[1];

      // Query uses custom headers
      expect(queryCall[1].headers['X-Request-ID']).toBe('req-123');
      // Mutate calls executeGraphQLMutation which uses default headers (known behavior)
      expect(mutateCall[1].headers['X-Request-ID']).toBeUndefined();
    });
  });

  describe('executeGraphQLSubscription', () => {
    it('should throw not implemented error', async () => {
      await expect(
        executeGraphQLSubscription('subscription { userAdded { id name } }')
      ).rejects.toThrow('GraphQL subscriptions not implemented');
    });

    it('should throw regardless of parameters', async () => {
      await expect(
        executeGraphQLSubscription('subscription { test }', { var: 'value' }, 'TestSub')
      ).rejects.toThrow('GraphQL subscriptions not implemented');
    });
  });
});
