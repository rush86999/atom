// File: atomic-docker/project/functions/_utils/hasura-client.ts

import { GraphQLClient } from 'graphql-request';

// Environment variables expected:
// - HASURA_GRAPHQL_ENDPOINT_URL: The HTTP(S) endpoint for your Hasura GraphQL API.
// - HASURA_GRAPHQL_ADMIN_SECRET: The admin secret for Hasura.

let clientInstance: GraphQLClient | null = null;

/**
 * Initializes and returns a GraphQLClient instance configured for Hasura.
 * It uses environment variables for the endpoint and admin secret.
 * The client is cached for subsequent calls within the same Lambda invocation.
 *
 * @returns {GraphQLClient} An instance of GraphQLClient.
 * @throws {Error} If Hasura endpoint or admin secret environment variables are not set.
 */
export const getGraphQLClient = (): GraphQLClient => {
  if (clientInstance) {
    return clientInstance;
  }

  const endpoint = process.env.HASURA_GRAPHQL_ENDPOINT_URL;
  const adminSecret = process.env.HASURA_GRAPHQL_ADMIN_SECRET;

  if (!endpoint) {
    console.error(
      '[HasuraClient] HASURA_GRAPHQL_ENDPOINT_URL environment variable is not set.'
    );
    throw new Error('Hasura GraphQL endpoint URL is not configured.');
  }

  if (!adminSecret) {
    console.error(
      '[HasuraClient] HASURA_GRAPHQL_ADMIN_SECRET environment variable is not set.'
    );
    throw new Error('Hasura admin secret is not configured.');
  }

  // Basic logging to confirm initialization, avoid logging full endpoint if too sensitive.
  const urlScheme = endpoint.startsWith('https://') ? 'https://' : 'http://';
  console.log(
    `[HasuraClient] Initializing GraphQL client for endpoint starting with: ${urlScheme}...`
  );

  clientInstance = new GraphQLClient(endpoint, {
    headers: {
      'x-hasura-admin-secret': adminSecret,
      'Content-Type': 'application/json',
    },
  });

  return clientInstance;
};

/**
 * Clears the cached GraphQLClient instance.
 * Useful for testing or if credentials need to be re-evaluated in a long-running process.
 */
export const clearCachedClient = (): void => {
  clientInstance = null;
  console.log('[HasuraClient] Cached GraphQL client instance cleared.');
};

// Example of how a Lambda might use it:
/*
import { getGraphQLClient } from './hasura-client'; // Adjust path as needed
import { gql } from 'graphql-request';

export const someLambdaHandler = async (event: any) => {
    try {
        const client = getGraphQLClient();
        const query = gql`query MyQuery { your_table { id } }`;
        const data = await client.request(query);
        console.log(data);
    } catch (error) {
        console.error("Error in someLambdaHandler:", error);
        // handle error
    }
};
*/
