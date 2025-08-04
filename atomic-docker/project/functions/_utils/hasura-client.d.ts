import { GraphQLClient } from 'graphql-request';
/**
 * Initializes and returns a GraphQLClient instance configured for Hasura.
 * It uses environment variables for the endpoint and admin secret.
 * The client is cached for subsequent calls within the same Lambda invocation.
 *
 * @returns {GraphQLClient} An instance of GraphQLClient.
 * @throws {Error} If Hasura endpoint or admin secret environment variables are not set.
 */
export declare const getGraphQLClient: () => GraphQLClient;
/**
 * Clears the cached GraphQLClient instance.
 * Useful for testing or if credentials need to be re-evaluated in a long-running process.
 */
export declare const clearCachedClient: () => void;
