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

  const MAX_RETRIES = 3;
  const INITIAL_TIMEOUT_MS = 15000; // 15 seconds
  let attempt = 0;
  let lastError: any = null;

  while (attempt < MAX_RETRIES) {
    try {
      // console.log(`GraphQL attempt ${attempt + 1} for ${operationName}`); // For debugging
      const response = await axios.post(
        HASURA_GRAPHQL_URL,
        {
          query,
          variables,
          operationName,
        },
        {
          headers,
          timeout: INITIAL_TIMEOUT_MS, // Timeout for each attempt
        }
      );

      if (response.data.errors) {
        // console.error(`GraphQL errors for ${operationName} (attempt ${attempt + 1}):`, JSON.stringify(response.data.errors, null, 2));
        // Consider some GraphQL errors as non-retryable immediately
        // For now, let's assume most GraphQL operational errors might be transient if the service is overloaded.
        // However, validation errors (e.g., bad query) should not be retried.
        // This simple check doesn't distinguish well. A more robust solution would inspect error codes/types.
        lastError = new GraphQLError(
          `GraphQL error executing operation '${operationName}'.`,
          'GRAPHQL_EXECUTION_ERROR',
          response.data.errors
        );
        // Example: if (response.data.errors[0]?.extensions?.code === 'validation-failed') break; // Non-retryable
        throw lastError; // Throw to trigger retry for now, or break if non-retryable
      }
      // console.log(`GraphQL attempt ${attempt + 1} for ${operationName} successful.`); // For debugging
      return response.data.data as T;

    } catch (error) {
      lastError = error; // Store the last error
      // console.warn(`GraphQL attempt ${attempt + 1} for ${operationName} failed:`, error.message); // For debugging

      if (axios.isAxiosError(error)) {
        const axiosError = error as AxiosError<any>;
        if (axiosError.response) {
          // HTTP error (e.g., 4xx, 5xx)
          const status = axiosError.response.status;
          // console.warn(
          //   `HTTP error ${status} for GraphQL operation '${operationName}' (attempt ${attempt + 1}):`,
          //   JSON.stringify(axiosError.response.data, null, 2)
          // );
          if (status >= 500 || status === 429) { // Retry on 5xx or 429 (Too Many Requests)
            // Fall through to retry logic
          } else { // Non-retryable client HTTP error (400, 401, 403, etc.)
            lastError = new GraphQLError(
              `HTTP error ${status} executing operation '${operationName}'. Not retrying.`,
              `HTTP_${status}`,
              axiosError.response.data
            );
            break; // Exit retry loop for non-retryable HTTP errors
          }
        } else if (axiosError.request) {
          // Network error or timeout (axiosError.code === 'ECONNABORTED' for timeout)
          // console.warn(`Network error or timeout for GraphQL operation '${operationName}' (attempt ${attempt + 1}):`, axiosError.message);
          if (axiosError.code === 'ECONNABORTED') {
            lastError = new GraphQLError(
              `GraphQL operation '${operationName}' timed out after ${INITIAL_TIMEOUT_MS}ms.`,
              'TIMEOUT_ERROR',
              axiosError.config
            );
          }
          // Fall through to retry logic
        } else {
          // Other Axios error (e.g. config issue before request was made) - likely non-retryable
           lastError = new GraphQLError(
              `Axios setup error for operation '${operationName}': ${axiosError.message}. Not retrying.`,
              'AXIOS_SETUP_ERROR',
              axiosError.config
            );
          break;
        }
      } else if (error instanceof GraphQLError && error.code === 'GRAPHQL_EXECUTION_ERROR') {
        // This was thrown from the `response.data.errors` block above.
        // This simple retry logic will retry all GraphQL errors.
        // For a more robust system, inspect error.details[0].extensions.code
        // to decide if it's a 'validation-error', 'permission-error', etc., and break if non-retryable.
        // console.warn(`GraphQL execution error for ${operationName} (attempt ${attempt + 1}), retrying. Error:`, error.details);
      } else {
        // Unexpected non-Axios error
        // console.error(`Unexpected error during GraphQL operation '${operationName}' (attempt ${attempt + 1}):`, error);
        // Consider this non-retryable
        break;
      }
    } // end catch

    attempt++;
    if (attempt < MAX_RETRIES) {
      const delay = Math.pow(2, attempt - 1 ) * 1000; // Exponential backoff: 1s, 2s
      // console.log(`Waiting ${delay}ms before GraphQL retry ${attempt + 1} for ${operationName}`); // For debugging
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  } // end while

  // All retries failed or a non-retryable error occurred
  const finalMessage = `Failed GraphQL operation '${operationName}' after ${attempt} attempts.`;
  console.error(finalMessage, { code: (lastError as any)?.code, message: lastError?.message, details: (lastError as any)?.details || lastError });

  if (lastError instanceof GraphQLError) {
    // Re-throw the specific GraphQLError if it was set (e.g. for non-retryable HTTP or GraphQL specific errors)
    throw lastError;
  }
  // Otherwise, throw a new generic one for retry exhaustion
  throw new GraphQLError(
    `${finalMessage}: ${(lastError as Error)?.message || 'Unknown error'}`,
    (lastError as any)?.code || 'ALL_RETRIES_FAILED', // Use a more specific code if possible
    (lastError as any)?.details || lastError
  );
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
