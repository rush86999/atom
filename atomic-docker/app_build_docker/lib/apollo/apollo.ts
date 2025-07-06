
// import { HttpLink } from 'apollo-link-http'
// import { ApolloClient } from 'apollo-client'
// import { InMemoryCache } from 'apollo-cache-inmemory'
import {
  ApolloClient,
  InMemoryCache,
  split, HttpLink, from
} from "@apollo/client"
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
      for (let err of graphQLErrors) {
        switch (err.extensions.code) {
          // Apollo Server sets code to UNAUTHENTICATED
          // when an AuthenticationError is thrown in a resolver
          case 'UNAUTHENTICATED':

            // Modify the operation context with a new token
            const oldHeaders = operation.getContext().headers;
            operation.setContext(async (_: any, { headers }: any) => {
              const accessToken = await Session.getAccessToken();
              return {
                headers: {
                  ...headers,
                  Authorization: accessToken ? `Bearer ${accessToken}` : ''
                }
              }
            })
            // Retry the request, returning the new observable
            return forward(operation);
        }
      }
    }

    // To retry on network errors, we recommend the RetryLink
    // instead of the onError link. This just logs the error.
    if (networkError) {
      console.log(`[Network error]: ${networkError}`);
    }
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
    from([errorLink, linkTokenHeader, httpLink]),
  )
  // create an inmemory cache instance for caching graphql data
  const cache = new InMemoryCache()

  // instantiate apollo client with apollo link instance and cache instance
  const client = new ApolloClient({
    link: splitLink,
    cache
  });

  return client;
}

export default makeApolloClient;
