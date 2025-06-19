import axios, { AxiosError } from 'axios';
import { HASURA_GRAPHQL_URL, HASURA_ADMIN_SECRET } from './constants';

/**
 * Represents a generic error from the GraphQL client.
 */
class GraphQLError extends Error {
  constructor(message: string, public code?: string, public details?: any) {
    super(message);
    this.name = 'GraphQLError';
  }
}

/**
 * Executes a GraphQL query.
 *
 * @param query The GraphQL query string.
 * @param variables An object containing variables for the query.
 * @param operationName The name of the GraphQL operation.
 * @param userId Optional user ID. If provided, the request is made with 'user' role and 'X-Hasura-User-Id' header. Otherwise, 'admin' role is used.
 * @returns A Promise that resolves with the `data` part of the GraphQL response.
 * @throws {GraphQLError} If there's a network error, HTTP error, or GraphQL errors are present in the response.
 */
export async function executeGraphQLQuery<T = any>(
  query: string,
  variables: Record<string, any>,
  operationName: string,
  userId?: string
): Promise<T> {
  if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
    throw new GraphQLError(
      'Hasura GraphQL URL or Admin Secret is not configured. Please set HASURA_GRAPHQL_URL and HASURA_ADMIN_SECRET environment variables.',
      'CONFIG_ERROR'
    );
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Hasura-Admin-Secret': HASURA_ADMIN_SECRET,
  };

  if (userId) {
    headers['X-Hasura-Role'] = 'user';
    headers['X-Hasura-User-Id'] = userId;
  } else {
    headers['X-Hasura-Role'] = 'admin';
  }

  try {
    const response = await axios.post(
      HASURA_GRAPHQL_URL,
      {
        query,
        variables,
        operationName,
      },
      {
        headers,
      }
    );

    if (response.data.errors) {
      console.error('GraphQL errors:', JSON.stringify(response.data.errors, null, 2));
      throw new GraphQLError(
        `GraphQL error executing operation '${operationName}'. Check server logs or GraphQL response for details.`,
        'GRAPHQL_EXECUTION_ERROR',
        response.data.errors
      );
    }

    return response.data.data as T;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError<any>;
      let errorCode = 'NETWORK_ERROR';
      if (axiosError.response) {
        // HTTP error (e.g., 4xx, 5xx)
        errorCode = `HTTP_${axiosError.response.status}`;
        console.error(
          `HTTP error ${axiosError.response.status} calling GraphQL endpoint for operation '${operationName}':`,
          JSON.stringify(axiosError.response.data, null, 2)
        );
        throw new GraphQLError(
          `HTTP error ${axiosError.response.status} executing operation '${operationName}'.`,
          errorCode,
          axiosError.response.data
        );
      } else if (axiosError.request) {
        // Network error (request made but no response received)
        console.error(`Network error calling GraphQL endpoint for operation '${operationName}':`, axiosError.message);
        throw new GraphQLError(
          `Network error executing operation '${operationName}': ${axiosError.message}`,
          errorCode,
          axiosError.request
        );
      }
    }
    // Rethrow if it's already a GraphQLError (e.g. from config check or GraphQL execution error)
    // or if it's an unexpected error
    if (error instanceof GraphQLError) {
        throw error;
    }
    console.error(`Unexpected error executing GraphQL operation '${operationName}':`, error);
    throw new GraphQLError(
        `Unexpected error executing operation '${operationName}': ${(error as Error).message || 'Unknown error'}`,
        'UNKNOWN_GRAPHQL_CLIENT_ERROR',
        error
    );
  }
}

/**
 * Executes a GraphQL mutation.
 *
 * @param mutation The GraphQL mutation string.
 * @param variables An object containing variables for the mutation.
 * @param operationName The name of the GraphQL operation.
 * @param userId Optional user ID. If provided, the request is made with 'user' role and 'X-Hasura-User-Id' header. Otherwise, 'admin' role is used.
 * @returns A Promise that resolves with the `data` part of the GraphQL response.
 * @throws {GraphQLError} If there's a network error, HTTP error, or GraphQL errors are present in the response.
 */
export async function executeGraphQLMutation<T = any>(
  mutation: string,
  variables: Record<string, any>,
  operationName: string,
  userId?: string
): Promise<T> {
  // The implementation is identical to executeGraphQLQuery,
  // as Hasura uses the same endpoint and request structure for queries and mutations.
  return executeGraphQLQuery<T>(mutation, variables, operationName, userId);
}

// Example Usage (for testing purposes, can be removed or commented out):
/*
async function testGraphQL() {
  // Example: Fetching a user by ID (assuming you have a 'users' table and 'users_by_pk' query)
  const getUserQuery = `
    query GetUserById($id: uuid!) {
      users_by_pk(id: $id) {
        id
        name
        email
      }
    }
  `;
  try {
    // Replace 'some-user-id' with an actual UUID from your users table for this to work
    // const userData = await executeGraphQLQuery<{ users_by_pk: { id: string; name: string; email: string } }>(
    //   getUserQuery,
    //   { id: 'some-user-id' }, // Provide a valid UUID
    //   'GetUserById',
    //   'some-user-id' // Optional: if you want to test user-specific roles
    // );
    // console.log('User data:', userData.users_by_pk);

    // Example: Inserting a new user (assuming you have an 'insert_users_one' mutation)
    const insertUserMutation = `
      mutation InsertUser($name: String!, $email: String!) {
        insert_users_one(object: { name: $name, email: $email }) {
          id
          name
          email
        }
      }
    `;
    // const newUser = await executeGraphQLMutation<{ insert_users_one: { id: string; name: string; email: string } }>(
    //   insertUserMutation,
    //   { name: 'Test User', email: 'test@example.com' },
    //   'InsertUser'
    //   // 'some-user-id' // Optional: if you want to test user-specific roles for mutations
    // );
    // console.log('New user:', newUser.insert_users_one);

  } catch (error) {
    if (error instanceof GraphQLError) {
      console.error(`GraphQL Client Test Error (${error.code}): ${error.message}`, error.details);
    } else {
      console.error('GraphQL Client Test Error (Unknown):', error);
    }
  }
}

// testGraphQL(); // Uncomment to run the test function
*/
