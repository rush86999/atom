"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
// import { HttpLink } from 'apollo-link-http'
// import { ApolloClient } from 'apollo-client'
// import { InMemoryCache } from 'apollo-cache-inmemory'
const client_1 = require("@apollo/client");
const retry_1 = require("@apollo/client/link/retry"); // Import RetryLink
const context_1 = require("@apollo/client/link/context");
const utilities_1 = require("@apollo/client/utilities");
const subscriptions_1 = require("@apollo/client/link/subscriptions");
const graphql_ws_1 = require("graphql-ws");
const error_1 = require("@apollo/client/link/error");
// TODO: Update constants in @lib/constants to define postgraphileDbUrl and postgraphileWSUrl
// For now, we'll use placeholder names and assume they will be correctly defined.
const constants_1 = require("@lib/constants");
const session_1 = __importDefault(require("supertokens-web-js/recipe/session"));
//endpointURL
const makeApolloClient = (token) => {
    if (!token)
        return;
    const errorLink = (0, error_1.onError)(({ graphQLErrors, networkError, operation, forward }) => {
        if (graphQLErrors) {
            appServiceLogger.warn({
                type: 'GraphQL Error',
                errors: graphQLErrors,
                operationName: operation?.operationName,
            }, 'GraphQL errors occurred in Apollo operation.');
            for (let err of graphQLErrors) {
                // Existing UNAUTHENTICATED handling
                if (err.extensions?.code === 'UNAUTHENTICATED') {
                    appServiceLogger.info({
                        operationName: operation.operationName,
                        msg: 'GraphQL Error: UNAUTHENTICATED. Attempting token refresh and retry.',
                    });
                    // Modify the operation context with a new token
                    operation.setContext(async (_, { headers }) => {
                        const accessToken = await session_1.default.getAccessToken();
                        appServiceLogger.debug({
                            operationName: operation.operationName,
                            msg: `Retrying with new token: ${accessToken ? 'present' : 'absent'}`,
                        });
                        return {
                            headers: {
                                ...headers,
                                Authorization: accessToken ? `Bearer ${accessToken}` : '',
                            },
                        };
                    });
                    return forward(operation);
                }
                // Log other GraphQL errors
                // appServiceLogger.error({ err, type: 'GraphQLErrorDetail', operationName: operation?.operationName }, `GraphQL Error Detail: ${err.message}`);
            }
        }
        if (networkError) {
            appServiceLogger.error({
                err: networkError,
                type: 'NetworkError',
                operationName: operation?.operationName,
            }, `[ApolloLinkNetworkError]: ${networkError.message}`);
        }
    });
    const retryLink = new retry_1.RetryLink({
        delay: {
            initial: 300, // Initial delay
            max: Infinity,
            jitter: true, // Add jitter to avoid thundering herd problem
        },
        attempts: {
            max: 3, // Max number of retries (total 4 attempts)
            retryIf: (error, _operation) => {
                // Retry on network errors
                if (error &&
                    error.statusCode &&
                    error.statusCode >= 500) {
                    appServiceLogger.warn({
                        operationName: _operation.operationName,
                        error: error.message,
                        statusCode: error.statusCode,
                    }, 'RetryLink: Retrying due to server error.');
                    return true;
                }
                if (error && !error.statusCode) {
                    // This typically means a network error without an HTTP response
                    appServiceLogger.warn({ operationName: _operation.operationName, error: error.message }, 'RetryLink: Retrying due to network error.');
                    return true;
                }
                // Potentially retry on specific GraphQL errors if needed, though errorLink handles UNAUTHENTICATED
                // Example: if (graphQLErrors) { graphQLErrors.some(e => e.extensions?.code === 'SOME_RETRYABLE_GQL_ERROR') }
                appServiceLogger.debug({
                    operationName: _operation.operationName,
                    error: error?.message,
                    statusCode: error?.statusCode,
                }, 'RetryLink: Not retrying this error.');
                return false;
            },
        },
    });
    // IMPORTANT: PostGraphile V4 subscriptions require server-side setup
    // with plugins like @graphile/pg-pubsub. The endpoint path might also differ (e.g., /graphql/subscriptions).
    // This wsLink setup ASSUMES such an endpoint is available and uses a similar auth pattern.
    // This will likely NOT work without further PostGraphile server-side configuration.
    const wsLink = new subscriptions_1.GraphQLWsLink((0, graphql_ws_1.createClient)({
        url: constants_1.postgraphileWSUrl, // Use the new PostGraphile WebSocket URL
        connectionParams: () => {
            // connectionParams can be a function to dynamically get the token
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
                token: token, // Or however the PostGraphile WS auth is configured.
            };
        },
    }));
    const linkTokenHeader = (0, context_1.setContext)(async (_, { headers }) => {
        const accessToken = await session_1.default.getAccessToken();
        return {
            headers: {
                ...headers,
                Authorization: accessToken ? `Bearer ${accessToken}` : '',
            },
        };
    });
    const httpLink = new client_1.HttpLink({
        uri: constants_1.postgraphileDbUrl, // Use the new PostGraphile HTTP URL
        // headers: { // Headers are now set by linkTokenHeader via setContext
        //   Authorization: `Bearer ${}`
        // },
    });
    const splitLink = (0, client_1.split)(({ query }) => {
        const definition = (0, utilities_1.getMainDefinition)(query);
        return (definition.kind === 'OperationDefinition' &&
            definition.operation === 'subscription');
    }, wsLink, (0, client_1.from)([retryLink, errorLink, linkTokenHeader, httpLink]) // Added retryLink before errorLink
    );
    // create an inmemory cache instance for caching graphql data
    const cache = new client_1.InMemoryCache({
    // Optional: Configure cache policies if needed, e.g., for specific types or queries
    // typePolicies: { ... }
    });
    // instantiate apollo client with apollo link instance and cache instance
    const client = new client_1.ApolloClient({
        link: splitLink,
        cache,
    });
    return client;
};
exports.default = makeApolloClient;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBvbGxvLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiYXBvbGxvLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7O0FBQUEsOENBQThDO0FBQzlDLCtDQUErQztBQUMvQyx3REFBd0Q7QUFDeEQsMkNBT3dCO0FBQ3hCLHFEQUFzRCxDQUFDLG1CQUFtQjtBQUMxRSx5REFBeUQ7QUFDekQsd0RBQTZEO0FBQzdELHFFQUFrRTtBQUNsRSwyQ0FBMEM7QUFDMUMscURBQW9EO0FBRXBELDZGQUE2RjtBQUM3RixrRkFBa0Y7QUFDbEYsOENBQXNFO0FBQ3RFLGdGQUF3RDtBQUN4RCxhQUFhO0FBRWIsTUFBTSxnQkFBZ0IsR0FBRyxDQUFDLEtBQWEsRUFBRSxFQUFFO0lBQ3pDLElBQUksQ0FBQyxLQUFLO1FBQUUsT0FBTztJQUVuQixNQUFNLFNBQVMsR0FBRyxJQUFBLGVBQU8sRUFDdkIsQ0FBQyxFQUFFLGFBQWEsRUFBRSxZQUFZLEVBQUUsU0FBUyxFQUFFLE9BQU8sRUFBRSxFQUFFLEVBQUU7UUFDdEQsSUFBSSxhQUFhLEVBQUUsQ0FBQztZQUNsQixnQkFBZ0IsQ0FBQyxJQUFJLENBQ25CO2dCQUNFLElBQUksRUFBRSxlQUFlO2dCQUNyQixNQUFNLEVBQUUsYUFBYTtnQkFDckIsYUFBYSxFQUFFLFNBQVMsRUFBRSxhQUFhO2FBQ3hDLEVBQ0QsOENBQThDLENBQy9DLENBQUM7WUFDRixLQUFLLElBQUksR0FBRyxJQUFJLGFBQWEsRUFBRSxDQUFDO2dCQUM5QixvQ0FBb0M7Z0JBQ3BDLElBQUksR0FBRyxDQUFDLFVBQVUsRUFBRSxJQUFJLEtBQUssaUJBQWlCLEVBQUUsQ0FBQztvQkFDL0MsZ0JBQWdCLENBQUMsSUFBSSxDQUFDO3dCQUNwQixhQUFhLEVBQUUsU0FBUyxDQUFDLGFBQWE7d0JBQ3RDLEdBQUcsRUFBRSxxRUFBcUU7cUJBQzNFLENBQUMsQ0FBQztvQkFDSCxnREFBZ0Q7b0JBQ2hELFNBQVMsQ0FBQyxVQUFVLENBQUMsS0FBSyxFQUFFLENB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LElBQUEsYUFBSSxFQUFDLENBQUMsU0FBUyxFQUFFLFNBQVMsRUFBRSxlQUFlLEVBQUUsUUFBUSxDQUFDLENBQUMsQ0FBQyxtQ0FBbUM7S0FDNUYsQ0FBQztJQUNGLDZEQUE2RDtJQUM3RCxNQUFNLEtBQUssR0FBRyxJQUFJLHNCQUFhLENBQUM7SUFDOUIsb0ZBQW9GO0lBQ3BGLHdCQUF3QjtLQUN6QixDQUFDLENBQUM7SUFFSCx5RUFBeUU7SUFDekUsTUFBTSxNQUFNLEdBQUcsSUFBSSxxQkFBWSxDQUFDO1FBQzlCLElBQUksRUFBRSxTQUFTO1FBQ2YsS0FBSztLQUNOLENBQUMsQ0FBQztJQUVILE9BQU8sTUFBTSxDQUFDO0FBQ2hCLENBQUMsQ0FBQztBQUVGLGtCQUFlLGdCQUFnQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiLy8gaW1wb3J0IHsgSHR0cExpbmsgfSBmcm9tICdhcG9sbG8tbGluay1odHRwJ1xuLy8gaW1wb3J0IHsgQXBvbGxvQ2xpZW50IH0gZnJvbSAnYXBvbGxvLWNsaWVudCdcbi8vIGltcG9ydCB7IEluTWVtb3J5Q2FjaGUgfSBmcm9tICdhcG9sbG8tY2FjaGUtaW5tZW1vcnknXG5pbXBvcnQge1xuICBBcG9sbG9DbGllbnQsXG4gIEluTWVtb3J5Q2FjaGUsXG4gIHNwbGl0LFxuICBIdHRwTGluayxcbiAgZnJvbSxcbiAgU2VydmVyRXJyb3IsIC8vIEZvciBSZXRyeUxpbmtcbn0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuaW1wb3J0IHsgUmV0cnlMaW5rIH0gZnJvbSAnQGFwb2xsby9jbGllbnQvbGluay9yZXRyeSc7IC8vIEltcG9ydCBSZXRyeUxpbmtcbmltcG9ydCB7IHNldENvbnRleHQgfSBmcm9tICdAYXBvbGxvL2NsaWVudC9saW5rL2NvbnRleHQnO1xuaW1wb3J0IHsgZ2V0TWFpbkRlZmluaXRpb24gfSBmcm9tICdAYXBvbGxvL2NsaWVudC91dGlsaXRpZXMnO1xuaW1wb3J0IHsgR3JhcGhRTFdzTGluayB9IGZyb20gJ0BhcG9sbG8vY2xpZW50L2xpbmsvc3Vic2NyaXB0aW9ucyc7XG5pbXBvcnQgeyBjcmVhdGVDbGllbnQgfSBmcm9tICdncmFwaHFsLXdzJztcbmltcG9ydCB7IG9uRXJyb3IgfSBmcm9tICdAYXBvbGxvL2NsaWVudC9saW5rL2Vycm9yJztcblxuLy8gVE9ETzogVXBkYXRlIGNvbnN0YW50cyBpbiBAbGliL2NvbnN0YW50cyB0byBkZWZpbmUgcG9zdGdyYXBoaWxlRGJVcmwgYW5kIHBvc3RncmFwaGlsZVdTVXJsXG4vLyBGb3Igbm93LCB3ZSdsbCB1c2UgcGxhY2Vob2xkZXIgbmFtZXMgYW5kIGFzc3VtZSB0aGV5IHdpbGwgYmUgY29ycmVjdGx5IGRlZmluZWQuXG5pbXBvcnQgeyBwb3N0Z3JhcGhpbGVEYlVybCwgcG9zdGdyYXBoaWxlV1NVcmwgfSBmcm9tICdAbGliL2NvbnN0YW50cyc7XG5pbXBvcnQgU2Vzc2lvbiBmcm9tICdzdXBlcnRva2Vucy13ZWItanMvcmVjaXBlL3Nlc3Npb24nO1xuLy9lbmRwb2ludFVSTFxuXG5jb25zdCBtYWtlQXBvbGxvQ2xpZW50ID0gKHRva2VuOiBTdHJpbmcpID0+IHtcbiAgaWYgKCF0b2tlbikgcmV0dXJuO1xuXG4gIGNvbnN0IGVycm9yTGluayA9IG9uRXJyb3IoXG4gICAgKHsgZ3JhcGhRTEVycm9ycywgbmV0d29ya0Vycm9yLCBvcGVyYXRpb24sIGZvcndhcmQgfSkgPT4ge1xuICAgICAgaWYgKGdyYXBoUUxFcnJvcnMpIHtcbiAgICAgICAgYXBwU2VydmljZUxvZ2dlci53YXJuKFxuICAgICAgICAgIHtcbiAgICAgICAgICAgIHR5cGU6ICdHcmFwaFFMIEVycm9yJyxcbiAgICAgICAgICAgIGVycm9yczogZ3JhcGhRTEVycm9ycyxcbiAgICAgICAgICAgIG9wZXJhdGlvbk5hbWU6IG9wZXJhdGlvbj8ub3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICB9LFxuICAgICAgICAgICdHcmFwaFFMIGVycm9ycyBvY2N1cnJlZCBpbiBBcG9sbG8gb3BlcmF0aW9uLidcbiAgICAgICAgKTtcbiAgICAgICAgZm9yIChsZXQgZXJyIG9mIGdyYXBoUUxFcnJvcnMpIHtcbiAgICAgICAgICAvLyBFeGlzdGluZyBVTkFVVEhFTlRJQ0FURUQgaGFuZGxpbmdcbiAgICAgICAgICBpZiAoZXJyLmV4dGVuc2lvbnM/LmNvZGUgPT09ICdVTkFVVEhFTlRJQ0FURUQnKSB7XG4gICAgICAgICAgICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oe1xuICAgICAgICAgICAgICBvcGVyYXRpb25OYW1lOiBvcGVyYXRpb24ub3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICAgICAgbXNnOiAnR3JhcGhRTCBFcnJvcjogVU5BVVRIRU5USUNBVEVELiBBdHRlbXB0aW5nIHRva2VuIHJlZnJlc2ggYW5kIHJldHJ5LicsXG4gICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIC8vIE1vZGlmeSB0aGUgb3BlcmF0aW9uIGNvbnRleHQgd2l0aCBhIG5ldyB0b2tlblxuICAgICAgICAgICAgb3BlcmF0aW9uLnNldENvbnRleHQoYXN5bmMgKF86IGFueSwgeyBoZWFkZXJzIH06IGFueSkgPT4ge1xuICAgICAgICAgICAgICBjb25zdCBhY2Nlc3NUb2tlbiA9IGF3YWl0IFNlc3Npb24uZ2V0QWNjZXNzVG9rZW4oKTtcbiAgICAgICAgICAgICAgYXBwU2VydmljZUxvZ2dlci5kZWJ1Zyh7XG4gICAgICAgICAgICAgICAgb3BlcmF0aW9uTmFtZTogb3BlcmF0aW9uLm9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgICAgICAgbXNnOiBgUmV0cnlpbmcgd2l0aCBuZXcgdG9rZW46ICR7YWNjZXNzVG9rZW4gPyAncHJlc2VudCcgOiAnYWJzZW50J31gLFxuICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAgICAgICAuLi5oZWFkZXJzLFxuICAgICAgICAgICAgICAgICAgQXV0aG9yaXphdGlvbjogYWNjZXNzVG9rZW4gPyBgQmVhcmVyICR7YWNjZXNzVG9rZW59YCA6ICcnLFxuICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgIH07XG4gICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIHJldHVybiBmb3J3YXJkKG9wZXJhdGlvbik7XG4gICAgICAgICAgfVxuICAgICAgICAgIC8vIExvZyBvdGhlciBHcmFwaFFMIGVycm9yc1xuICAgICAgICAgIC8vIGFwcFNlcnZpY2VMb2dnZXIuZXJyb3IoeyBlcnIsIHR5cGU6ICdHcmFwaFFMRXJyb3JEZXRhaWwnLCBvcGVyYXRpb25OYW1lOiBvcGVyYXRpb24/Lm9wZXJhdGlvbk5hbWUgfSwgYEdyYXBoUUwgRXJyb3IgRGV0YWlsOiAke2Vyci5tZXNzYWdlfWApO1xuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIGlmIChuZXR3b3JrRXJyb3IpIHtcbiAgICAgICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihcbiAgICAgICAgICB7XG4gICAgICAgICAgICBlcnI6IG5ldHdvcmtFcnJvcixcbiAgICAgICAgICAgIHR5cGU6ICdOZXR3b3JrRXJyb3InLFxuICAgICAgICAgICAgb3BlcmF0aW9uTmFtZTogb3BlcmF0aW9uPy5vcGVyYXRpb25OYW1lLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgYFtBcG9sbG9MaW5rTmV0d29ya0Vycm9yXTogJHtuZXR3b3JrRXJyb3IubWVzc2FnZX1gXG4gICAgICAgICk7XG4gICAgICB9XG4gICAgfVxuICApO1xuXG4gIGNvbnN0IHJldHJ5TGluayA9IG5ldyBSZXRyeUxpbmsoe1xuICAgIGRlbGF5OiB7XG4gICAgICBpbml0aWFsOiAzMDAsIC8vIEluaXRpYWwgZGVsYXlcbiAgICAgIG1heDogSW5maW5pdHksXG4gICAgICBqaXR0ZXI6IHRydWUsIC8vIEFkZCBqaXR0ZXIgdG8gYXZvaWQgdGh1bmRlcmluZyBoZXJkIHByb2JsZW1cbiAgICB9LFxuICAgIGF0dGVtcHRzOiB7XG4gICAgICBtYXg6IDMsIC8vIE1heCBudW1iZXIgb2YgcmV0cmllcyAodG90YWwgNCBhdHRlbXB0cylcbiAgICAgIHJldHJ5SWY6IChlcnJvciwgX29wZXJhdGlvbikgPT4ge1xuICAgICAgICAvLyBSZXRyeSBvbiBuZXR3b3JrIGVycm9yc1xuICAgICAgICBpZiAoXG4gICAgICAgICAgZXJyb3IgJiZcbiAgICAgICAgICAoZXJyb3IgYXMgU2VydmVyRXJyb3IpLnN0YXR1c0NvZGUgJiZcbiAgICAgICAgICAoZXJyb3IgYXMgU2VydmVyRXJyb3IpLnN0YXR1c0NvZGUgPj0gNTAwXG4gICAgICAgICkge1xuICAgICAgICAgIGFwcFNlcnZpY2VMb2dnZXIud2FybihcbiAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgb3BlcmF0aW9uTmFtZTogX29wZXJhdGlvbi5vcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgICBlcnJvcjogZXJyb3IubWVzc2FnZSxcbiAgICAgICAgICAgICAgc3RhdHVzQ29kZTogKGVycm9yIGFzIFNlcnZlckVycm9yKS5zdGF0dXNDb2RlLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICdSZXRyeUxpbms6IFJldHJ5aW5nIGR1ZSB0byBzZXJ2ZXIgZXJyb3IuJ1xuICAgICAgICAgICk7XG4gICAgICAgICAgcmV0dXJuIHRydWU7XG4gICAgICAgIH1cbiAgICAgICAgaWYgKGVycm9yICYmICEoZXJyb3IgYXMgU2VydmVyRXJyb3IpLnN0YXR1c0NvZGUpIHtcbiAgICAgICAgICAvLyBUaGlzIHR5cGljYWxseSBtZWFucyBhIG5ldHdvcmsgZXJyb3Igd2l0aG91dCBhbiBIVFRQIHJlc3BvbnNlXG4gICAgICAgICAgYXBwU2VydmljZUxvZ2dlci53YXJuKFxuICAgICAgICAgICAgeyBvcGVyYXRpb25OYW1lOiBfb3BlcmF0aW9uLm9wZXJhdGlvbk5hbWUsIGVycm9yOiBlcnJvci5tZXNzYWdlIH0sXG4gICAgICAgICAgICAnUmV0cnlMaW5rOiBSZXRyeWluZyBkdWUgdG8gbmV0d29yayBlcnJvci4nXG4gICAgICAgICAgKTtcbiAgICAgICAgICByZXR1cm4gdHJ1ZTtcbiAgICAgICAgfVxuICAgICAgICAvLyBQb3RlbnRpYWxseSByZXRyeSBvbiBzcGVjaWZpYyBHcmFwaFFMIGVycm9ycyBpZiBuZWVkZWQsIHRob3VnaCBlcnJvckxpbmsgaGFuZGxlcyBVTkFVVEhFTlRJQ0FURURcbiAgICAgICAgLy8gRXhhbXBsZTogaWYgKGdyYXBoUUxFcnJvcnMpIHsgZ3JhcGhRTEVycm9ycy5zb21lKGUgPT4gZS5leHRlbnNpb25zPy5jb2RlID09PSAnU09NRV9SRVRSWUFCTEVfR1FMX0VSUk9SJykgfVxuICAgICAgICBhcHBTZXJ2aWNlTG9nZ2VyLmRlYnVnKFxuICAgICAgICAgIHtcbiAgICAgICAgICAgIG9wZXJhdGlvbk5hbWU6IF9vcGVyYXRpb24ub3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICAgIGVycm9yOiBlcnJvcj8ubWVzc2FnZSxcbiAgICAgICAgICAgIHN0YXR1c0NvZGU6IChlcnJvciBhcyBTZXJ2ZXJFcnJvcik/LnN0YXR1c0NvZGUsXG4gICAgICAgICAgfSxcbiAgICAgICAgICAnUmV0cnlMaW5rOiBOb3QgcmV0cnlpbmcgdGhpcyBlcnJvci4nXG4gICAgICAgICk7XG4gICAgICAgIHJldHVybiBmYWxzZTtcbiAgICAgIH0sXG4gICAgfSxcbiAgfSk7XG5cbiAgLy8gSU1QT1JUQU5UOiBQb3N0R3JhcGhpbGUgVjQgc3Vic2NyaXB0aW9ucyByZXF1aXJlIHNlcnZlci1zaWRlIHNldHVwXG4gIC8vIHdpdGggcGx1Z2lucyBsaWtlIEBncmFwaGlsZS9wZy1wdWJzdWIuIFRoZSBlbmRwb2ludCBwYXRoIG1pZ2h0IGFsc28gZGlmZmVyIChlLmcuLCAvZ3JhcGhxbC9zdWJzY3JpcHRpb25zKS5cbiAgLy8gVGhpcyB3c0xpbmsgc2V0dXAgQVNTVU1FUyBzdWNoIGFuIGVuZHBvaW50IGlzIGF2YWlsYWJsZSBhbmQgdXNlcyBhIHNpbWlsYXIgYXV0aCBwYXR0ZXJuLlxuICAvLyBUaGlzIHdpbGwgbGlrZWx5IE5PVCB3b3JrIHdpdGhvdXQgZnVydGhlciBQb3N0R3JhcGhpbGUgc2VydmVyLXNpZGUgY29uZmlndXJhdGlvbi5cbiAgY29uc3Qgd3NMaW5rID0gbmV3IEdyYXBoUUxXc0xpbmsoXG4gICAgY3JlYXRlQ2xpZW50KHtcbiAgICAgIHVybDogcG9zdGdyYXBoaWxlV1NVcmwsIC8vIFVzZSB0aGUgbmV3IFBvc3RHcmFwaGlsZSBXZWJTb2NrZXQgVVJMXG4gICAgICBjb25uZWN0aW9uUGFyYW1zOiAoKSA9PiB7XG4gICAgICAgIC8vIGNvbm5lY3Rpb25QYXJhbXMgY2FuIGJlIGEgZnVuY3Rpb24gdG8gZHluYW1pY2FsbHkgZ2V0IHRoZSB0b2tlblxuICAgICAgICByZXR1cm4ge1xuICAgICAgICAgIC8vIFBvc3RHcmFwaGlsZSdzIGRlZmF1bHQgSldUIGhhbmRsaW5nIHZpYSBgcGdTZXR0aW5nc2AgbWlnaHQgcGljayB1cCB0aGUgcm9sZSBmcm9tIHRoZSB0b2tlbi5cbiAgICAgICAgICAvLyBFeHBsaWNpdGx5IHNlbmRpbmcgQXV0aG9yaXphdGlvbiBoZWFkZXIgbWlnaHQgYmUgbmVlZGVkIGRlcGVuZGluZyBvbiBQb3N0R3JhcGhpbGUgc2VydmVyIHNldHVwLlxuICAgICAgICAgIC8vIENoZWNrIFBvc3RHcmFwaGlsZSdzIGRvY3VtZW50YXRpb24gZm9yIFdlYlNvY2tldCBhdXRoZW50aWNhdGlvbi5cbiAgICAgICAgICAvLyBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7dG9rZW59YCwgLy8gT3JpZ2luYWwgdG9rZW4gcGFzc2VkIHRvIG1ha2VBcG9sbG9DbGllbnRcbiAgICAgICAgICAvLyBoZWFkZXJzOiB7IC8vIEhlYWRlcnMgbWlnaHQgbm90IGJlIHN0YW5kYXJkIGZvciBncmFwaHFsLXdzIGNvbm5lY3Rpb25QYXJhbXMsIG9mdGVuIGl0J3MgYSBmbGF0IG9iamVjdFxuICAgICAgICAgIC8vICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3Rva2VufWBcbiAgICAgICAgICAvLyB9XG4gICAgICAgICAgLy8gSXQncyBvZnRlbiBiZXR0ZXIgdG8gcmVseSBvbiB0aGUgSldUIGNvbnRhaW5pbmcgbmVjZXNzYXJ5IGNsYWltcyAobGlrZSByb2xlKVxuICAgICAgICAgIC8vIHRoYXQgUG9zdEdyYXBoaWxlIGNhbiBpbnRlcnByZXQgdmlhIHBnU2V0dGluZ3MuXG4gICAgICAgICAgLy8gSWYgYSB0b2tlbiBpcyBuZWVkZWQgZm9yIHRoZSBpbml0aWFsIFdTIGNvbm5lY3Rpb24gaXRzZWxmOlxuICAgICAgICAgIHRva2VuOiB0b2tlbiwgLy8gT3IgaG93ZXZlciB0aGUgUG9zdEdyYXBoaWxlIFdTIGF1dGggaXMgY29uZmlndXJlZC5cbiAgICAgICAgfTtcbiAgICAgIH0sXG4gICAgfSlcbiAgKTtcblxuICBjb25zdCBsaW5rVG9rZW5IZWFkZXIgPSBzZXRDb250ZXh0KGFzeW5jIChfLCB7IGhlYWRlcnMgfSkgPT4ge1xuICAgIGNvbnN0IGFjY2Vzc1Rva2VuID0gYXdhaXQgU2Vzc2lvbi5nZXRBY2Nlc3NUb2tlbigpO1xuICAgIHJldHVybiB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIC4uLmhlYWRlcnMsXG4gICAgICAgIEF1dGhvcml6YXRpb246IGFjY2Vzc1Rva2VuID8gYEJlYXJlciAke2FjY2Vzc1Rva2VufWAgOiAnJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfSk7XG5cbiAgY29uc3QgaHR0cExpbmsgPSBuZXcgSHR0cExpbmsoe1xuICAgIHVyaTogcG9zdGdyYXBoaWxlRGJVcmwsIC8vIFVzZSB0aGUgbmV3IFBvc3RHcmFwaGlsZSBIVFRQIFVSTFxuICAgIC8vIGhlYWRlcnM6IHsgLy8gSGVhZGVycyBhcmUgbm93IHNldCBieSBsaW5rVG9rZW5IZWFkZXIgdmlhIHNldENvbnRleHRcbiAgICAvLyAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt9YFxuICAgIC8vIH0sXG4gIH0pO1xuXG4gIGNvbnN0IHNwbGl0TGluayA9IHNwbGl0KFxuICAgICh7IHF1ZXJ5IH0pID0+IHtcbiAgICAgIGNvbnN0IGRlZmluaXRpb24gPSBnZXRNYWluRGVmaW5pdGlvbihxdWVyeSk7XG4gICAgICByZXR1cm4gKFxuICAgICAgICBkZWZpbml0aW9uLmtpbmQgPT09ICdPcGVyYXRpb25EZWZpbml0aW9uJyAmJlxuICAgICAgICBkZWZpbml0aW9uLm9wZXJhdGlvbiA9PT0gJ3N1YnNjcmlwdGlvbidcbiAgICAgICk7XG4gICAgfSxcbiAgICB3c0xpbmssXG4gICAgZnJvbShbcmV0cnlMaW5rLCBlcnJvckxpbmssIGxpbmtUb2tlbkhlYWRlciwgaHR0cExpbmtdKSAvLyBBZGRlZCByZXRyeUxpbmsgYmVmb3JlIGVycm9yTGlua1xuICApO1xuICAvLyBjcmVhdGUgYW4gaW5tZW1vcnkgY2FjaGUgaW5zdGFuY2UgZm9yIGNhY2hpbmcgZ3JhcGhxbCBkYXRhXG4gIGNvbnN0IGNhY2hlID0gbmV3IEluTWVtb3J5Q2FjaGUoe1xuICAgIC8vIE9wdGlvbmFsOiBDb25maWd1cmUgY2FjaGUgcG9saWNpZXMgaWYgbmVlZGVkLCBlLmcuLCBmb3Igc3BlY2lmaWMgdHlwZXMgb3IgcXVlcmllc1xuICAgIC8vIHR5cGVQb2xpY2llczogeyAuLi4gfVxuICB9KTtcblxuICAvLyBpbnN0YW50aWF0ZSBhcG9sbG8gY2xpZW50IHdpdGggYXBvbGxvIGxpbmsgaW5zdGFuY2UgYW5kIGNhY2hlIGluc3RhbmNlXG4gIGNvbnN0IGNsaWVudCA9IG5ldyBBcG9sbG9DbGllbnQoe1xuICAgIGxpbms6IHNwbGl0TGluayxcbiAgICBjYWNoZSxcbiAgfSk7XG5cbiAgcmV0dXJuIGNsaWVudDtcbn07XG5cbmV4cG9ydCBkZWZhdWx0IG1ha2VBcG9sbG9DbGllbnQ7XG4iXX0=