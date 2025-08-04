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
export declare function executeGraphQLQuery<T = any>(query: string, variables: Record<string, any>, operationName: string, userId?: string): Promise<T>;
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
export declare function executeGraphQLMutation<T = any>(mutation: string, variables: Record<string, any>, operationName: string, userId?: string): Promise<T>;
