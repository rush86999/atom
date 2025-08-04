import axios from 'axios';
import { HASURA_GRAPHQL_URL, HASURA_ADMIN_SECRET } from './constants';
/**
 * Represents a generic error from the GraphQL client.
 */
class GraphQLError extends Error {
    code;
    details;
    constructor(message, code, details) {
        super(message);
        this.code = code;
        this.details = details;
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
export async function executeGraphQLQuery(query, variables, operationName, userId) {
    if (!HASURA_GRAPHQL_URL || !HASURA_ADMIN_SECRET) {
        throw new GraphQLError('Hasura GraphQL URL or Admin Secret is not configured. Please set HASURA_GRAPHQL_URL and HASURA_ADMIN_SECRET environment variables.', 'CONFIG_ERROR');
    }
    const headers = {
        'Content-Type': 'application/json',
        'X-Hasura-Admin-Secret': HASURA_ADMIN_SECRET,
    };
    if (userId) {
        headers['X-Hasura-Role'] = 'user';
        headers['X-Hasura-User-Id'] = userId;
    }
    else {
        headers['X-Hasura-Role'] = 'admin';
    }
    const MAX_RETRIES = 3;
    const INITIAL_TIMEOUT_MS = 15000; // 15 seconds
    let attempt = 0;
    let lastError = null;
    while (attempt < MAX_RETRIES) {
        try {
            // console.log(`GraphQL attempt ${attempt + 1} for ${operationName}`); // For debugging
            const response = await axios.post(HASURA_GRAPHQL_URL, {
                query,
                variables,
                operationName,
            }, {
                headers,
                timeout: INITIAL_TIMEOUT_MS, // Timeout for each attempt
            });
            if (response.data.errors) {
                // console.error(`GraphQL errors for ${operationName} (attempt ${attempt + 1}):`, JSON.stringify(response.data.errors, null, 2));
                // Consider some GraphQL errors as non-retryable immediately
                // For now, let's assume most GraphQL operational errors might be transient if the service is overloaded.
                // However, validation errors (e.g., bad query) should not be retried.
                // This simple check doesn't distinguish well. A more robust solution would inspect error codes/types.
                lastError = new GraphQLError(`GraphQL error executing operation '${operationName}'.`, 'GRAPHQL_EXECUTION_ERROR', response.data.errors);
                // Example: if (response.data.errors[0]?.extensions?.code === 'validation-failed') break; // Non-retryable
                throw lastError; // Throw to trigger retry for now, or break if non-retryable
            }
            // console.log(`GraphQL attempt ${attempt + 1} for ${operationName} successful.`); // For debugging
            return response.data.data;
        }
        catch (error) {
            lastError = error; // Store the last error
            // console.warn(`GraphQL attempt ${attempt + 1} for ${operationName} failed:`, error.message); // For debugging
            if (axios.isAxiosError(error)) {
                const axiosError = error;
                if (axiosError.response) {
                    // HTTP error (e.g., 4xx, 5xx)
                    const status = axiosError.response.status;
                    // console.warn(
                    //   `HTTP error ${status} for GraphQL operation '${operationName}' (attempt ${attempt + 1}):`,
                    //   JSON.stringify(axiosError.response.data, null, 2)
                    // );
                    if (status >= 500 || status === 429) {
                        // Retry on 5xx or 429 (Too Many Requests)
                        // Fall through to retry logic
                    }
                    else {
                        // Non-retryable client HTTP error (400, 401, 403, etc.)
                        lastError = new GraphQLError(`HTTP error ${status} executing operation '${operationName}'. Not retrying.`, `HTTP_${status}`, axiosError.response.data);
                        break; // Exit retry loop for non-retryable HTTP errors
                    }
                }
                else if (axiosError.request) {
                    // Network error or timeout (axiosError.code === 'ECONNABORTED' for timeout)
                    // console.warn(`Network error or timeout for GraphQL operation '${operationName}' (attempt ${attempt + 1}):`, axiosError.message);
                    if (axiosError.code === 'ECONNABORTED') {
                        lastError = new GraphQLError(`GraphQL operation '${operationName}' timed out after ${INITIAL_TIMEOUT_MS}ms.`, 'TIMEOUT_ERROR', axiosError.config);
                    }
                    // Fall through to retry logic
                }
                else {
                    // Other Axios error (e.g. config issue before request was made) - likely non-retryable
                    lastError = new GraphQLError(`Axios setup error for operation '${operationName}': ${axiosError.message}. Not retrying.`, 'AXIOS_SETUP_ERROR', axiosError.config);
                    break;
                }
            }
            else if (error instanceof GraphQLError &&
                error.code === 'GRAPHQL_EXECUTION_ERROR') {
                // This was thrown from the `response.data.errors` block above.
                // This simple retry logic will retry all GraphQL errors.
                // For a more robust system, inspect error.details[0].extensions.code
                // to decide if it's a 'validation-error', 'permission-error', etc., and break if non-retryable.
                // console.warn(`GraphQL execution error for ${operationName} (attempt ${attempt + 1}), retrying. Error:`, error.details);
            }
            else {
                // Unexpected non-Axios error
                // console.error(`Unexpected error during GraphQL operation '${operationName}' (attempt ${attempt + 1}):`, error);
                // Consider this non-retryable
                break;
            }
        } // end catch
        attempt++;
        if (attempt < MAX_RETRIES) {
            const delay = Math.pow(2, attempt - 1) * 1000; // Exponential backoff: 1s, 2s
            // console.log(`Waiting ${delay}ms before GraphQL retry ${attempt + 1} for ${operationName}`); // For debugging
            await new Promise((resolve) => setTimeout(resolve, delay));
        }
    } // end while
    // All retries failed or a non-retryable error occurred
    const finalMessage = `Failed GraphQL operation '${operationName}' after ${attempt} attempts.`;
    console.error(finalMessage, {
        code: lastError?.code,
        message: lastError?.message,
        details: lastError?.details || lastError,
    });
    if (lastError instanceof GraphQLError) {
        // Re-throw the specific GraphQLError if it was set (e.g. for non-retryable HTTP or GraphQL specific errors)
        throw lastError;
    }
    // Otherwise, throw a new generic one for retry exhaustion
    throw new GraphQLError(`${finalMessage}: ${lastError?.message || 'Unknown error'}`, lastError?.code || 'ALL_RETRIES_FAILED', // Use a more specific code if possible
    lastError?.details || lastError);
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
export async function executeGraphQLMutation(mutation, variables, operationName, userId) {
    // The implementation is identical to executeGraphQLQuery,
    // as Hasura uses the same endpoint and request structure for queries and mutations.
    return executeGraphQLQuery(mutation, variables, operationName, userId);
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ3JhcGhxbENsaWVudC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImdyYXBocWxDbGllbnQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxLQUFxQixNQUFNLE9BQU8sQ0FBQztBQUMxQyxPQUFPLEVBQUUsa0JBQWtCLEVBQUUsbUJBQW1CLEVBQUUsTUFBTSxhQUFhLENBQUM7QUFFdEU7O0dBRUc7QUFDSCxNQUFNLFlBQWEsU0FBUSxLQUFLO0lBR3JCO0lBQ0E7SUFIVCxZQUNFLE9BQWUsRUFDUixJQUFhLEVBQ2IsT0FBYTtRQUVwQixLQUFLLENBQUMsT0FBTyxDQUFDLENBQUM7UUFIUixTQUFJLEdBQUosSUFBSSxDQUFTO1FBQ2IsWUFBTyxHQUFQLE9BQU8sQ0FBTTtRQUdwQixJQUFJLENBQUMsSUFBSSxHQUFHLGNBQWMsQ0FBQztJQUM3QixDQUFDO0NBQ0Y7QUFFRDs7Ozs7Ozs7O0dBU0c7QUFDSCxNQUFNLENBQUMsS0FBSyxVQUFVLG1CQUFtQixDQUN2QyxLQUFhLEVBQ2IsU0FBOEIsRUFDOUIsYUFBcUIsRUFDckIsTUFBZTtJQUVmLElBQUksQ0FBQyxrQkFBa0IsSUFBSSxDQUFDLG1CQUFtQixFQUFFLENBQUM7UUFDaEQsTUFBTSxJQUFJLFlBQVksQ0FDcEIsb0lBQW9JLEVBQ3BJLGNBQWMsQ0FDZixDQUFDO0lBQ0osQ0FBQztJQUVELE1BQU0sT0FBTyxHQUEyQjtRQUN0QyxjQUFjLEVBQUUsa0JBQWtCO1FBQ2xDLHVCQUF1QixFQUFFLG1CQUFtQjtLQUM3QyxDQUFDO0lBRUYsSUFBSSxNQUFNLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxlQUFlLENBQUMsR0FBRyxNQUFNLENBQUM7UUFDbEMsT0FBTyxDQUFDLGtCQUFrQixDQUFDLEdBQUcsTUFBTSxDQUFDO0lBQ3ZDLENBQUM7U0FBTSxDQUFDO1FBQ04sT0FBTyxDQUFDLGVBQWUsQ0FBQyxHQUFHLE9BQU8sQ0FBQztJQUNyQyxDQUFDO0lBRUQsTUFBTSxXQUFXLEdBQUcs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RSxPQUFPLElBQUksU0FBUyxDQUN6QyxDQUFDO0FBQ0osQ0FBQztBQUVEOzs7Ozs7Ozs7R0FTRztBQUNILE1BQU0sQ0FBQyxLQUFLLFVBQVUsc0JBQXNCLENBQzFDLFFBQWdCLEVBQ2hCLFNBQThCLEVBQzlCLGFBQXFCLEVBQ3JCLE1BQWU7SUFFZiwwREFBMEQ7SUFDMUQsb0ZBQW9GO0lBQ3BGLE9BQU8sbUJBQW1CLENBQUksUUFBUSxFQUFFLFNBQVMsRUFBRSxhQUFhLEVBQUUsTUFBTSxDQUFDLENBQUM7QUFDNUUsQ0FBQztBQUVELHlFQUF5RTtBQUN6RTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7RUFrREUiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgYXhpb3MsIHsgQXhpb3NFcnJvciB9IGZyb20gJ2F4aW9zJztcbmltcG9ydCB7IEhBU1VSQV9HUkFQSFFMX1VSTCwgSEFTVVJBX0FETUlOX1NFQ1JFVCB9IGZyb20gJy4vY29uc3RhbnRzJztcblxuLyoqXG4gKiBSZXByZXNlbnRzIGEgZ2VuZXJpYyBlcnJvciBmcm9tIHRoZSBHcmFwaFFMIGNsaWVudC5cbiAqL1xuY2xhc3MgR3JhcGhRTEVycm9yIGV4dGVuZHMgRXJyb3Ige1xuICBjb25zdHJ1Y3RvcihcbiAgICBtZXNzYWdlOiBzdHJpbmcsXG4gICAgcHVibGljIGNvZGU/OiBzdHJpbmcsXG4gICAgcHVibGljIGRldGFpbHM/OiBhbnlcbiAgKSB7XG4gICAgc3VwZXIobWVzc2FnZSk7XG4gICAgdGhpcy5uYW1lID0gJ0dyYXBoUUxFcnJvcic7XG4gIH1cbn1cblxuLyoqXG4gKiBFeGVjdXRlcyBhIEdyYXBoUUwgcXVlcnkuXG4gKlxuICogQHBhcmFtIHF1ZXJ5IFRoZSBHcmFwaFFMIHF1ZXJ5IHN0cmluZy5cbiAqIEBwYXJhbSB2YXJpYWJsZXMgQW4gb2JqZWN0IGNvbnRhaW5pbmcgdmFyaWFibGVzIGZvciB0aGUgcXVlcnkuXG4gKiBAcGFyYW0gb3BlcmF0aW9uTmFtZSBUaGUgbmFtZSBvZiB0aGUgR3JhcGhRTCBvcGVyYXRpb24uXG4gKiBAcGFyYW0gdXNlcklkIE9wdGlvbmFsIHVzZXIgSUQuIElmIHByb3ZpZGVkLCB0aGUgcmVxdWVzdCBpcyBtYWRlIHdpdGggJ3VzZXInIHJvbGUgYW5kICdYLUhhc3VyYS1Vc2VyLUlkJyBoZWFkZXIuIE90aGVyd2lzZSwgJ2FkbWluJyByb2xlIGlzIHVzZWQuXG4gKiBAcmV0dXJucyBBIFByb21pc2UgdGhhdCByZXNvbHZlcyB3aXRoIHRoZSBgZGF0YWAgcGFydCBvZiB0aGUgR3JhcGhRTCByZXNwb25zZS5cbiAqIEB0aHJvd3Mge0dyYXBoUUxFcnJvcn0gSWYgdGhlcmUncyBhIG5ldHdvcmsgZXJyb3IsIEhUVFAgZXJyb3IsIG9yIEdyYXBoUUwgZXJyb3JzIGFyZSBwcmVzZW50IGluIHRoZSByZXNwb25zZS5cbiAqL1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGV4ZWN1dGVHcmFwaFFMUXVlcnk8VCA9IGFueT4oXG4gIHF1ZXJ5OiBzdHJpbmcsXG4gIHZhcmlhYmxlczogUmVjb3JkPHN0cmluZywgYW55PixcbiAgb3BlcmF0aW9uTmFtZTogc3RyaW5nLFxuICB1c2VySWQ/OiBzdHJpbmdcbik6IFByb21pc2U8VD4ge1xuICBpZiAoIUhBU1VSQV9HUkFQSFFMX1VSTCB8fCAhSEFTVVJBX0FETUlOX1NFQ1JFVCkge1xuICAgIHRocm93IG5ldyBHcmFwaFFMRXJyb3IoXG4gICAgICAnSGFzdXJhIEdyYXBoUUwgVVJMIG9yIEFkbWluIFNlY3JldCBpcyBub3QgY29uZmlndXJlZC4gUGxlYXNlIHNldCBIQVNVUkFfR1JBUEhRTF9VUkwgYW5kIEhBU1VSQV9BRE1JTl9TRUNSRVQgZW52aXJvbm1lbnQgdmFyaWFibGVzLicsXG4gICAgICAnQ09ORklHX0VSUk9SJ1xuICAgICk7XG4gIH1cblxuICBjb25zdCBoZWFkZXJzOiBSZWNvcmQ8c3RyaW5nLCBzdHJpbmc+ID0ge1xuICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IEhBU1VSQV9BRE1JTl9TRUNSRVQsXG4gIH07XG5cbiAgaWYgKHVzZXJJZCkge1xuICAgIGhlYWRlcnNbJ1gtSGFzdXJhLVJvbGUnXSA9ICd1c2VyJztcbiAgICBoZWFkZXJzWydYLUhhc3VyYS1Vc2VyLUlkJ10gPSB1c2VySWQ7XG4gIH0gZWxzZSB7XG4gICAgaGVhZGVyc1snWC1IYXN1cmEtUm9sZSddID0gJ2FkbWluJztcbiAgfVxuXG4gIGNvbnN0IE1BWF9SRVRSSUVTID0gMztcbiAgY29uc3QgSU5JVElBTF9USU1FT1VUX01TID0gMTUwMDA7IC8vIDE1IHNlY29uZHNcbiAgbGV0IGF0dGVtcHQgPSAwO1xuICBsZXQgbGFzdEVycm9yOiBhbnkgPSBudWxsO1xuXG4gIHdoaWxlIChhdHRlbXB0IDwgTUFYX1JFVFJJRVMpIHtcbiAgICB0cnkge1xuICAgICAgLy8gY29uc29sZS5sb2coYEdyYXBoUUwgYXR0ZW1wdCAke2F0dGVtcHQgKyAxfSBmb3IgJHtvcGVyYXRpb25OYW1lfWApOyAvLyBGb3IgZGVidWdnaW5nXG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGF4aW9zLnBvc3QoXG4gICAgICAgIEhBU1VSQV9HUkFQSFFMX1VSTCxcbiAgICAgICAge1xuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICB9LFxuICAgICAgICB7XG4gICAgICAgICAgaGVhZGVycyxcbiAgICAgICAgICB0aW1lb3V0OiBJTklUSUFMX1RJTUVPVVRfTVMsIC8vIFRpbWVvdXQgZm9yIGVhY2ggYXR0ZW1wdFxuICAgICAgICB9XG4gICAgICApO1xuXG4gICAgICBpZiAocmVzcG9uc2UuZGF0YS5lcnJvcnMpIHtcbiAgICAgICAgLy8gY29uc29sZS5lcnJvcihgR3JhcGhRTCBlcnJvcnMgZm9yICR7b3BlcmF0aW9uTmFtZX0gKGF0dGVtcHQgJHthdHRlbXB0ICsgMX0pOmAsIEpTT04uc3RyaW5naWZ5KHJlc3BvbnNlLmRhdGEuZXJyb3JzLCBudWxsLCAyKSk7XG4gICAgICAgIC8vIENvbnNpZGVyIHNvbWUgR3JhcGhRTCBlcnJvcnMgYXMgbm9uLXJldHJ5YWJsZSBpbW1lZGlhdGVseVxuICAgICAgICAvLyBGb3Igbm93LCBsZXQncyBhc3N1bWUgbW9zdCBHcmFwaFFMIG9wZXJhdGlvbmFsIGVycm9ycyBtaWdodCBiZSB0cmFuc2llbnQgaWYgdGhlIHNlcnZpY2UgaXMgb3ZlcmxvYWRlZC5cbiAgICAgICAgLy8gSG93ZXZlciwgdmFsaWRhdGlvbiBlcnJvcnMgKGUuZy4sIGJhZCBxdWVyeSkgc2hvdWxkIG5vdCBiZSByZXRyaWVkLlxuICAgICAgICAvLyBUaGlzIHNpbXBsZSBjaGVjayBkb2Vzbid0IGRpc3Rpbmd1aXNoIHdlbGwuIEEgbW9yZSByb2J1c3Qgc29sdXRpb24gd291bGQgaW5zcGVjdCBlcnJvciBjb2Rlcy90eXBlcy5cbiAgICAgICAgbGFzdEVycm9yID0gbmV3IEdyYXBoUUxFcnJvcihcbiAgICAgICAgICBgR3JhcGhRTCBlcnJvciBleGVjdXRpbmcgb3BlcmF0aW9uICcke29wZXJhdGlvbk5hbWV9Jy5gLFxuICAgICAgICAgICdHUkFQSFFMX0VYRUNVVElPTl9FUlJPUicsXG4gICAgICAgICAgcmVzcG9uc2UuZGF0YS5lcnJvcnNcbiAgICAgICAgKTtcbiAgICAgICAgLy8gRXhhbXBsZTogaWYgKHJlc3BvbnNlLmRhdGEuZXJyb3JzWzBdPy5leHRlbnNpb25zPy5jb2RlID09PSAndmFsaWRhdGlvbi1mYWlsZWQnKSBicmVhazsgLy8gTm9uLXJldHJ5YWJsZVxuICAgICAgICB0aHJvdyBsYXN0RXJyb3I7IC8vIFRocm93IHRvIHRyaWdnZXIgcmV0cnkgZm9yIG5vdywgb3IgYnJlYWsgaWYgbm9uLXJldHJ5YWJsZVxuICAgICAgfVxuICAgICAgLy8gY29uc29sZS5sb2coYEdyYXBoUUwgYXR0ZW1wdCAke2F0dGVtcHQgKyAxfSBmb3IgJHtvcGVyYXRpb25OYW1lfSBzdWNjZXNzZnVsLmApOyAvLyBGb3IgZGVidWdnaW5nXG4gICAgICByZXR1cm4gcmVzcG9uc2UuZGF0YS5kYXRhIGFzIFQ7XG4gICAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICAgIGxhc3RFcnJvciA9IGVycm9yOyAvLyBTdG9yZSB0aGUgbGFzdCBlcnJvclxuICAgICAgLy8gY29uc29sZS53YXJuKGBHcmFwaFFMIGF0dGVtcHQgJHthdHRlbXB0ICsgMX0gZm9yICR7b3BlcmF0aW9uTmFtZX0gZmFpbGVkOmAsIGVycm9yLm1lc3NhZ2UpOyAvLyBGb3IgZGVidWdnaW5nXG5cbiAgICAgIGlmIChheGlvcy5pc0F4aW9zRXJyb3IoZXJyb3IpKSB7XG4gICAgICAgIGNvbnN0IGF4aW9zRXJyb3IgPSBlcnJvciBhcyBBeGlvc0Vycm9yPGFueT47XG4gICAgICAgIGlmIChheGlvc0Vycm9yLnJlc3BvbnNlKSB7XG4gICAgICAgICAgLy8gSFRUUCBlcnJvciAoZS5nLiwgNHh4LCA1eHgpXG4gICAgICAgICAgY29uc3Qgc3RhdHVzID0gYXhpb3NFcnJvci5yZXNwb25zZS5zdGF0dXM7XG4gICAgICAgICAgLy8gY29uc29sZS53YXJuKFxuICAgICAgICAgIC8vICAgYEhUVFAgZXJyb3IgJHtzdGF0dXN9IGZvciBHcmFwaFFMIG9wZXJhdGlvbiAnJHtvcGVyYXRpb25OYW1lfScgKGF0dGVtcHQgJHthdHRlbXB0ICsgMX0pOmAsXG4gICAgICAgICAgLy8gICBKU09OLnN0cmluZ2lmeShheGlvc0Vycm9yLnJlc3BvbnNlLmRhdGEsIG51bGwsIDIpXG4gICAgICAgICAgLy8gKTtcbiAgICAgICAgICBpZiAoc3RhdHVzID49IDUwMCB8fCBzdGF0dXMgPT09IDQyOSkge1xuICAgICAgICAgICAgLy8gUmV0cnkgb24gNXh4IG9yIDQyOSAoVG9vIE1hbnkgUmVxdWVzdHMpXG4gICAgICAgICAgICAvLyBGYWxsIHRocm91Z2ggdG8gcmV0cnkgbG9naWNcbiAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgLy8gTm9uLXJldHJ5YWJsZSBjbGllbnQgSFRUUCBlcnJvciAoNDAwLCA0MDEsIDQwMywgZXRjLilcbiAgICAgICAgICAgIGxhc3RFcnJvciA9IG5ldyBHcmFwaFFMRXJyb3IoXG4gICAgICAgICAgICAgIGBIVFRQIGVycm9yICR7c3RhdHVzfSBleGVjdXRpbmcgb3BlcmF0aW9uICcke29wZXJhdGlvbk5hbWV9Jy4gTm90IHJldHJ5aW5nLmAsXG4gICAgICAgICAgICAgIGBIVFRQXyR7c3RhdHVzfWAsXG4gICAgICAgICAgICAgIGF4aW9zRXJyb3IucmVzcG9uc2UuZGF0YVxuICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIGJyZWFrOyAvLyBFeGl0IHJldHJ5IGxvb3AgZm9yIG5vbi1yZXRyeWFibGUgSFRUUCBlcnJvcnNcbiAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSBpZiAoYXhpb3NFcnJvci5yZXF1ZXN0KSB7XG4gICAgICAgICAgLy8gTmV0d29yayBlcnJvciBvciB0aW1lb3V0IChheGlvc0Vycm9yLmNvZGUgPT09ICdFQ09OTkFCT1JURUQnIGZvciB0aW1lb3V0KVxuICAgICAgICAgIC8vIGNvbnNvbGUud2FybihgTmV0d29yayBlcnJvciBvciB0aW1lb3V0IGZvciBHcmFwaFFMIG9wZXJhdGlvbiAnJHtvcGVyYXRpb25OYW1lfScgKGF0dGVtcHQgJHthdHRlbXB0ICsgMX0pOmAsIGF4aW9zRXJyb3IubWVzc2FnZSk7XG4gICAgICAgICAgaWYgKGF4aW9zRXJyb3IuY29kZSA9PT0gJ0VDT05OQUJPUlRFRCcpIHtcbiAgICAgICAgICAgIGxhc3RFcnJvciA9IG5ldyBHcmFwaFFMRXJyb3IoXG4gICAgICAgICAgICAgIGBHcmFwaFFMIG9wZXJhdGlvbiAnJHtvcGVyYXRpb25OYW1lfScgdGltZWQgb3V0IGFmdGVyICR7SU5JVElBTF9USU1FT1VUX01TfW1zLmAsXG4gICAgICAgICAgICAgICdUSU1FT1VUX0VSUk9SJyxcbiAgICAgICAgICAgICAgYXhpb3NFcnJvci5jb25maWdcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgfVxuICAgICAgICAgIC8vIEZhbGwgdGhyb3VnaCB0byByZXRyeSBsb2dpY1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIC8vIE90aGVyIEF4aW9zIGVycm9yIChlLmcuIGNvbmZpZyBpc3N1ZSBiZWZvcmUgcmVxdWVzdCB3YXMgbWFkZSkgLSBsaWtlbHkgbm9uLXJldHJ5YWJsZVxuICAgICAgICAgIGxhc3RFcnJvciA9IG5ldyBHcmFwaFFMRXJyb3IoXG4gICAgICAgICAgICBgQXhpb3Mgc2V0dXAgZXJyb3IgZm9yIG9wZXJhdGlvbiAnJHtvcGVyYXRpb25OYW1lfSc6ICR7YXhpb3NFcnJvci5tZXNzYWdlfS4gTm90IHJldHJ5aW5nLmAsXG4gICAgICAgICAgICAnQVhJT1NfU0VUVVBfRVJST1InLFxuICAgICAgICAgICAgYXhpb3NFcnJvci5jb25maWdcbiAgICAgICAgICApO1xuICAgICAgICAgIGJyZWFrO1xuICAgICAgICB9XG4gICAgICB9IGVsc2UgaWYgKFxuICAgICAgICBlcnJvciBpbnN0YW5jZW9mIEdyYXBoUUxFcnJvciAmJlxuICAgICAgICBlcnJvci5jb2RlID09PSAnR1JBUEhRTF9FWEVDVVRJT05fRVJST1InXG4gICAgICApIHtcbiAgICAgICAgLy8gVGhpcyB3YXMgdGhyb3duIGZyb20gdGhlIGByZXNwb25zZS5kYXRhLmVycm9yc2AgYmxvY2sgYWJvdmUuXG4gICAgICAgIC8vIFRoaXMgc2ltcGxlIHJldHJ5IGxvZ2ljIHdpbGwgcmV0cnkgYWxsIEdyYXBoUUwgZXJyb3JzLlxuICAgICAgICAvLyBGb3IgYSBtb3JlIHJvYnVzdCBzeXN0ZW0sIGluc3BlY3QgZXJyb3IuZGV0YWlsc1swXS5leHRlbnNpb25zLmNvZGVcbiAgICAgICAgLy8gdG8gZGVjaWRlIGlmIGl0J3MgYSAndmFsaWRhdGlvbi1lcnJvcicsICdwZXJtaXNzaW9uLWVycm9yJywgZXRjLiwgYW5kIGJyZWFrIGlmIG5vbi1yZXRyeWFibGUuXG4gICAgICAgIC8vIGNvbnNvbGUud2FybihgR3JhcGhRTCBleGVjdXRpb24gZXJyb3IgZm9yICR7b3BlcmF0aW9uTmFtZX0gKGF0dGVtcHQgJHthdHRlbXB0ICsgMX0pLCByZXRyeWluZy4gRXJyb3I6YCwgZXJyb3IuZGV0YWlscyk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICAvLyBVbmV4cGVjdGVkIG5vbi1BeGlvcyBlcnJvclxuICAgICAgICAvLyBjb25zb2xlLmVycm9yKGBVbmV4cGVjdGVkIGVycm9yIGR1cmluZyBHcmFwaFFMIG9wZXJhdGlvbiAnJHtvcGVyYXRpb25OYW1lfScgKGF0dGVtcHQgJHthdHRlbXB0ICsgMX0pOmAsIGVycm9yKTtcbiAgICAgICAgLy8gQ29uc2lkZXIgdGhpcyBub24tcmV0cnlhYmxlXG4gICAgICAgIGJyZWFrO1xuICAgICAgfVxuICAgIH0gLy8gZW5kIGNhdGNoXG5cbiAgICBhdHRlbXB0Kys7XG4gICAgaWYgKGF0dGVtcHQgPCBNQVhfUkVUUklFUykge1xuICAgICAgY29uc3QgZGVsYXkgPSBNYXRoLnBvdygyLCBhdHRlbXB0IC0gMSkgKiAxMDAwOyAvLyBFeHBvbmVudGlhbCBiYWNrb2ZmOiAxcywgMnNcbiAgICAgIC8vIGNvbnNvbGUubG9nKGBXYWl0aW5nICR7ZGVsYXl9bXMgYmVmb3JlIEdyYXBoUUwgcmV0cnkgJHthdHRlbXB0ICsgMX0gZm9yICR7b3BlcmF0aW9uTmFtZX1gKTsgLy8gRm9yIGRlYnVnZ2luZ1xuICAgICAgYXdhaXQgbmV3IFByb21pc2UoKHJlc29sdmUpID0+IHNldFRpbWVvdXQocmVzb2x2ZSwgZGVsYXkpKTtcbiAgICB9XG4gIH0gLy8gZW5kIHdoaWxlXG5cbiAgLy8gQWxsIHJldHJpZXMgZmFpbGVkIG9yIGEgbm9uLXJldHJ5YWJsZSBlcnJvciBvY2N1cnJlZFxuICBjb25zdCBmaW5hbE1lc3NhZ2UgPSBgRmFpbGVkIEdyYXBoUUwgb3BlcmF0aW9uICcke29wZXJhdGlvbk5hbWV9JyBhZnRlciAke2F0dGVtcHR9IGF0dGVtcHRzLmA7XG4gIGNvbnNvbGUuZXJyb3IoZmluYWxNZXNzYWdlLCB7XG4gICAgY29kZTogKGxhc3RFcnJvciBhcyBhbnkpPy5jb2RlLFxuICAgIG1lc3NhZ2U6IGxhc3RFcnJvcj8ubWVzc2FnZSxcbiAgICBkZXRhaWxzOiAobGFzdEVycm9yIGFzIGFueSk/LmRldGFpbHMgfHwgbGFzdEVycm9yLFxuICB9KTtcblxuICBpZiAobGFzdEVycm9yIGluc3RhbmNlb2YgR3JhcGhRTEVycm9yKSB7XG4gICAgLy8gUmUtdGhyb3cgdGhlIHNwZWNpZmljIEdyYXBoUUxFcnJvciBpZiBpdCB3YXMgc2V0IChlLmcuIGZvciBub24tcmV0cnlhYmxlIEhUVFAgb3IgR3JhcGhRTCBzcGVjaWZpYyBlcnJvcnMpXG4gICAgdGhyb3cgbGFzdEVycm9yO1xuICB9XG4gIC8vIE90aGVyd2lzZSwgdGhyb3cgYSBuZXcgZ2VuZXJpYyBvbmUgZm9yIHJldHJ5IGV4aGF1c3Rpb25cbiAgdGhyb3cgbmV3IEdyYXBoUUxFcnJvcihcbiAgICBgJHtmaW5hbE1lc3NhZ2V9OiAkeyhsYXN0RXJyb3IgYXMgRXJyb3IpPy5tZXNzYWdlIHx8ICdVbmtub3duIGVycm9yJ31gLFxuICAgIChsYXN0RXJyb3IgYXMgYW55KT8uY29kZSB8fCAnQUxMX1JFVFJJRVNfRkFJTEVEJywgLy8gVXNlIGEgbW9yZSBzcGVjaWZpYyBjb2RlIGlmIHBvc3NpYmxlXG4gICAgKGxhc3RFcnJvciBhcyBhbnkpPy5kZXRhaWxzIHx8IGxhc3RFcnJvclxuICApO1xufVxuXG4vKipcbiAqIEV4ZWN1dGVzIGEgR3JhcGhRTCBtdXRhdGlvbi5cbiAqXG4gKiBAcGFyYW0gbXV0YXRpb24gVGhlIEdyYXBoUUwgbXV0YXRpb24gc3RyaW5nLlxuICogQHBhcmFtIHZhcmlhYmxlcyBBbiBvYmplY3QgY29udGFpbmluZyB2YXJpYWJsZXMgZm9yIHRoZSBtdXRhdGlvbi5cbiAqIEBwYXJhbSBvcGVyYXRpb25OYW1lIFRoZSBuYW1lIG9mIHRoZSBHcmFwaFFMIG9wZXJhdGlvbi5cbiAqIEBwYXJhbSB1c2VySWQgT3B0aW9uYWwgdXNlciBJRC4gSWYgcHJvdmlkZWQsIHRoZSByZXF1ZXN0IGlzIG1hZGUgd2l0aCAndXNlcicgcm9sZSBhbmQgJ1gtSGFzdXJhLVVzZXItSWQnIGhlYWRlci4gT3RoZXJ3aXNlLCAnYWRtaW4nIHJvbGUgaXMgdXNlZC5cbiAqIEByZXR1cm5zIEEgUHJvbWlzZSB0aGF0IHJlc29sdmVzIHdpdGggdGhlIGBkYXRhYCBwYXJ0IG9mIHRoZSBHcmFwaFFMIHJlc3BvbnNlLlxuICogQHRocm93cyB7R3JhcGhRTEVycm9yfSBJZiB0aGVyZSdzIGEgbmV0d29yayBlcnJvciwgSFRUUCBlcnJvciwgb3IgR3JhcGhRTCBlcnJvcnMgYXJlIHByZXNlbnQgaW4gdGhlIHJlc3BvbnNlLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZXhlY3V0ZUdyYXBoUUxNdXRhdGlvbjxUID0gYW55PihcbiAgbXV0YXRpb246IHN0cmluZyxcbiAgdmFyaWFibGVzOiBSZWNvcmQ8c3RyaW5nLCBhbnk+LFxuICBvcGVyYXRpb25OYW1lOiBzdHJpbmcsXG4gIHVzZXJJZD86IHN0cmluZ1xuKTogUHJvbWlzZTxUPiB7XG4gIC8vIFRoZSBpbXBsZW1lbnRhdGlvbiBpcyBpZGVudGljYWwgdG8gZXhlY3V0ZUdyYXBoUUxRdWVyeSxcbiAgLy8gYXMgSGFzdXJhIHVzZXMgdGhlIHNhbWUgZW5kcG9pbnQgYW5kIHJlcXVlc3Qgc3RydWN0dXJlIGZvciBxdWVyaWVzIGFuZCBtdXRhdGlvbnMuXG4gIHJldHVybiBleGVjdXRlR3JhcGhRTFF1ZXJ5PFQ+KG11dGF0aW9uLCB2YXJpYWJsZXMsIG9wZXJhdGlvbk5hbWUsIHVzZXJJZCk7XG59XG5cbi8vIEV4YW1wbGUgVXNhZ2UgKGZvciB0ZXN0aW5nIHB1cnBvc2VzLCBjYW4gYmUgcmVtb3ZlZCBvciBjb21tZW50ZWQgb3V0KTpcbi8qXG5hc3luYyBmdW5jdGlvbiB0ZXN0R3JhcGhRTCgpIHtcbiAgLy8gRXhhbXBsZTogRmV0Y2hpbmcgYSB1c2VyIGJ5IElEIChhc3N1bWluZyB5b3UgaGF2ZSBhICd1c2VycycgdGFibGUgYW5kICd1c2Vyc19ieV9waycgcXVlcnkpXG4gIGNvbnN0IGdldFVzZXJRdWVyeSA9IGBcbiAgICBxdWVyeSBHZXRVc2VyQnlJZCgkaWQ6IHV1aWQhKSB7XG4gICAgICB1c2Vyc19ieV9wayhpZDogJGlkKSB7XG4gICAgICAgIGlkXG4gICAgICAgIG5hbWVcbiAgICAgICAgZW1haWxcbiAgICAgIH1cbiAgICB9XG4gIGA7XG4gIHRyeSB7XG4gICAgLy8gUmVwbGFjZSAnc29tZS11c2VyLWlkJyB3aXRoIGFuIGFjdHVhbCBVVUlEIGZyb20geW91ciB1c2VycyB0YWJsZSBmb3IgdGhpcyB0byB3b3JrXG4gICAgLy8gY29uc3QgdXNlckRhdGEgPSBhd2FpdCBleGVjdXRlR3JhcGhRTFF1ZXJ5PHsgdXNlcnNfYnlfcGs6IHsgaWQ6IHN0cmluZzsgbmFtZTogc3RyaW5nOyBlbWFpbDogc3RyaW5nIH0gfT4oXG4gICAgLy8gICBnZXRVc2VyUXVlcnksXG4gICAgLy8gICB7IGlkOiAnc29tZS11c2VyLWlkJyB9LCAvLyBQcm92aWRlIGEgdmFsaWQgVVVJRFxuICAgIC8vICAgJ0dldFVzZXJCeUlkJyxcbiAgICAvLyAgICdzb21lLXVzZXItaWQnIC8vIE9wdGlvbmFsOiBpZiB5b3Ugd2FudCB0byB0ZXN0IHVzZXItc3BlY2lmaWMgcm9sZXNcbiAgICAvLyApO1xuICAgIC8vIGNvbnNvbGUubG9nKCdVc2VyIGRhdGE6JywgdXNlckRhdGEudXNlcnNfYnlfcGspO1xuXG4gICAgLy8gRXhhbXBsZTogSW5zZXJ0aW5nIGEgbmV3IHVzZXIgKGFzc3VtaW5nIHlvdSBoYXZlIGFuICdpbnNlcnRfdXNlcnNfb25lJyBtdXRhdGlvbilcbiAgICBjb25zdCBpbnNlcnRVc2VyTXV0YXRpb24gPSBgXG4gICAgICBtdXRhdGlvbiBJbnNlcnRVc2VyKCRuYW1lOiBTdHJpbmchLCAkZW1haWw6IFN0cmluZyEpIHtcbiAgICAgICAgaW5zZXJ0X3VzZXJzX29uZShvYmplY3Q6IHsgbmFtZTogJG5hbWUsIGVtYWlsOiAkZW1haWwgfSkge1xuICAgICAgICAgIGlkXG4gICAgICAgICAgbmFtZVxuICAgICAgICAgIGVtYWlsXG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgO1xuICAgIC8vIGNvbnN0IG5ld1VzZXIgPSBhd2FpdCBleGVjdXRlR3JhcGhRTE11dGF0aW9uPHsgaW5zZXJ0X3VzZXJzX29uZTogeyBpZDogc3RyaW5nOyBuYW1lOiBzdHJpbmc7IGVtYWlsOiBzdHJpbmcgfSB9PihcbiAgICAvLyAgIGluc2VydFVzZXJNdXRhdGlvbixcbiAgICAvLyAgIHsgbmFtZTogJ1Rlc3QgVXNlcicsIGVtYWlsOiAndGVzdEBleGFtcGxlLmNvbScgfSxcbiAgICAvLyAgICdJbnNlcnRVc2VyJ1xuICAgIC8vICAgLy8gJ3NvbWUtdXNlci1pZCcgLy8gT3B0aW9uYWw6IGlmIHlvdSB3YW50IHRvIHRlc3QgdXNlci1zcGVjaWZpYyByb2xlcyBmb3IgbXV0YXRpb25zXG4gICAgLy8gKTtcbiAgICAvLyBjb25zb2xlLmxvZygnTmV3IHVzZXI6JywgbmV3VXNlci5pbnNlcnRfdXNlcnNfb25lKTtcblxuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGlmIChlcnJvciBpbnN0YW5jZW9mIEdyYXBoUUxFcnJvcikge1xuICAgICAgY29uc29sZS5lcnJvcihgR3JhcGhRTCBDbGllbnQgVGVzdCBFcnJvciAoJHtlcnJvci5jb2RlfSk6ICR7ZXJyb3IubWVzc2FnZX1gLCBlcnJvci5kZXRhaWxzKTtcbiAgICB9IGVsc2Uge1xuICAgICAgY29uc29sZS5lcnJvcignR3JhcGhRTCBDbGllbnQgVGVzdCBFcnJvciAoVW5rbm93bik6JywgZXJyb3IpO1xuICAgIH1cbiAgfVxufVxuXG4vLyB0ZXN0R3JhcGhRTCgpOyAvLyBVbmNvbW1lbnQgdG8gcnVuIHRoZSB0ZXN0IGZ1bmN0aW9uXG4qL1xuIl19