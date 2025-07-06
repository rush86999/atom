
// import { HttpLink } from 'apollo-link-http'
// import { ApolloClient } from 'apollo-client'
// import { InMemoryCache } from 'apollo-cache-inmemory'
import {
  ApolloClient,
  InMemoryCache,
  split, HttpLink, from,
  ServerError, // For RetryLink
} from "@apollo/client"
import { RetryLink } from "@apollo/client/link/retry"; // Import RetryLink
import { setContext } from '@apollo/client/link/context'
import { getMainDefinition } from '@apollo/client/utilities'
import { GraphQLWsLink } from '@apollo/client/link/subscriptions'
import { createClient } from 'graphql-ws'
import { onError } from "@apollo/client/link/error"

// TODO: Update constants in @lib/constants to define postgraphileDbUrl and postgraphileWSUrl
// For now, we'll use placeholder names and assume they will be correctly defined.
import { postgraphileDbUrl, postgraphileWSUrl } from '@lib/constants'
import Session from "supertokens-web-js/recipe/session";
//endpointURL

const makeApolloClient = (token: String) => {
  if (!token) return
  
  const errorLink = onError(({ graphQLErrors, networkError, operation, forward }) => {
    if (graphQLErrors) {
      appServiceLogger.warn({ type: 'GraphQL Error', errors: graphQLErrors, operationName: operation?.operationName }, 'GraphQL errors occurred in Apollo operation.');
      for (let err of graphQLErrors) {
        // Existing UNAUTHENTICATED handling
        if (err.extensions?.code === 'UNAUTHENTICATED') {
            appServiceLogger.info({ operationName: operation.operationName, msg: 'GraphQL Error: UNAUTHENTICATED. Attempting token refresh and retry.' });
            // Modify the operation context with a new token
            operation.setContext(async (_: any, { headers }: any) => {
              const accessToken = await Session.getAccessToken();
              appServiceLogger.debug({ operationName: operation.operationName, msg: `Retrying with new token: ${accessToken ? 'present' : 'absent'}` });
              return {
                headers: {
                  ...headers,
                  Authorization: accessToken ? `Bearer ${accessToken}` : ''
                }
              }
            });
            return forward(operation);
        }
        // Log other GraphQL errors
        // appServiceLogger.error({ err, type: 'GraphQLErrorDetail', operationName: operation?.operationName }, `GraphQL Error Detail: ${err.message}`);
      }
    }

    if (networkError) {
      appServiceLogger.error({ err: networkError, type: 'NetworkError', operationName: operation?.operationName }, `[ApolloLinkNetworkError]: ${networkError.message}`);
    }
  });

  const retryLink = new RetryLink({
    delay: {
      initial: 300, // Initial delay
      max: Infinity,
      jitter: true, // Add jitter to avoid thundering herd problem
    },
    attempts: {
      max: 3, // Max number of retries (total 4 attempts)
      retryIf: (error, _operation) => {
        // Retry on network errors
        if (error && (error as ServerError).statusCode && (error as ServerError).statusCode >= 500) {
            appServiceLogger.warn({ operationName: _operation.operationName, error: error.message, statusCode: (error as ServerError).statusCode }, 'RetryLink: Retrying due to server error.');
            return true;
        }
        if (error && !(error as ServerError).statusCode) { // This typically means a network error without an HTTP response
            appServiceLogger.warn({ operationName: _operation.operationName, error: error.message }, 'RetryLink: Retrying due to network error.');
            return true;
        }
        // Potentially retry on specific GraphQL errors if needed, though errorLink handles UNAUTHENTICATED
        // Example: if (graphQLErrors) { graphQLErrors.some(e => e.extensions?.code === 'SOME_RETRYABLE_GQL_ERROR') }
        appServiceLogger.debug({ operationName: _operation.operationName, error: error?.message, statusCode: (error as ServerError)?.statusCode }, 'RetryLink: Not retrying this error.');
        return false;
      },
    },
  });


  // IMPORTANT: PostGraphile V4 subscriptions require server-side setup
  // with plugins like @graphile/pg-pubsub. The endpoint path might also differ (e.g., /graphql/subscriptions).
  // This wsLink setup ASSUMES such an endpoint is available and uses a similar auth pattern.
  // This will likely NOT work without further PostGraphile server-side configuration.
  const wsLink = new GraphQLWsLink(createClient({
    url: postgraphileWSUrl, // Use the new PostGraphile WebSocket URL
    connectionParams: () => { // connectionParams can be a function to dynamically get the token
      return {
        // PostGraphile's default JWT handling via `pgSettings` might pick up the role from the token.
        // Explicitly sending Authorization header might be needed depending on PostGraphile server setup.
        // Check PostGraphile's documentation for WebSocket authentication.
        // Authorization: `Bearer ${token}`, // Original token passed to makeApolloClient
        // headers: { // Headers might not be standard for graphql-ws connectionParams, often it's a flat object
        //   Authorization: `Bearer ${token}`
        // }
        // It's often better to rely on the JWT containing necessary claims (like role)
        // that PostGraphile can interpret via pgSettings.
        // If a token is needed for the initial WS connection itself:
        token: token // Or however the PostGraphile WS auth is configured.
      };
    },
  }))

  const linkTokenHeader = setContext(async (_, { headers }) => {
    const accessToken = await Session.getAccessToken();
    return {
      headers: {
        ...headers,
        Authorization: accessToken ? `Bearer ${accessToken}` : ''
      }
    }
  })

  const httpLink = new HttpLink({
    uri: postgraphileDbUrl, // Use the new PostGraphile HTTP URL
    // headers: { // Headers are now set by linkTokenHeader via setContext
    //   Authorization: `Bearer ${}`
    // },
  })

  const splitLink = split(
    ({ query }) => {
      const definition = getMainDefinition(query);
      return (
        definition.kind === 'OperationDefinition' &&
        definition.operation === 'subscription'
      );
    },
    wsLink,
    from([retryLink, errorLink, linkTokenHeader, httpLink]), // Added retryLink before errorLink
  )
  // create an inmemory cache instance for caching graphql data
  const cache = new InMemoryCache({
    // Optional: Configure cache policies if needed, e.g., for specific types or queries
    // typePolicies: { ... }
  })

  // instantiate apollo client with apollo link instance and cache instance
  const client = new ApolloClient({
    link: splitLink,
    cache
  });

  return client;
}

export default makeApolloClient;
