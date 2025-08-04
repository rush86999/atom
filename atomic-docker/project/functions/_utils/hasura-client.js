// File: atomic-docker/project/functions/_utils/hasura-client.ts
import { GraphQLClient } from 'graphql-request';
// Environment variables expected:
// - HASURA_GRAPHQL_ENDPOINT_URL: The HTTP(S) endpoint for your Hasura GraphQL API.
// - HASURA_GRAPHQL_ADMIN_SECRET: The admin secret for Hasura.
let clientInstance = null;
/**
 * Initializes and returns a GraphQLClient instance configured for Hasura.
 * It uses environment variables for the endpoint and admin secret.
 * The client is cached for subsequent calls within the same Lambda invocation.
 *
 * @returns {GraphQLClient} An instance of GraphQLClient.
 * @throws {Error} If Hasura endpoint or admin secret environment variables are not set.
 */
export const getGraphQLClient = () => {
    if (clientInstance) {
        return clientInstance;
    }
    const endpoint = process.env.HASURA_GRAPHQL_ENDPOINT_URL;
    const adminSecret = process.env.HASURA_GRAPHQL_ADMIN_SECRET;
    if (!endpoint) {
        console.error('[HasuraClient] HASURA_GRAPHQL_ENDPOINT_URL environment variable is not set.');
        throw new Error('Hasura GraphQL endpoint URL is not configured.');
    }
    if (!adminSecret) {
        console.error('[HasuraClient] HASURA_GRAPHQL_ADMIN_SECRET environment variable is not set.');
        throw new Error('Hasura admin secret is not configured.');
    }
    // Basic logging to confirm initialization, avoid logging full endpoint if too sensitive.
    const urlScheme = endpoint.startsWith('https://') ? 'https://' : 'http://';
    console.log(`[HasuraClient] Initializing GraphQL client for endpoint starting with: ${urlScheme}...`);
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
export const clearCachedClient = () => {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaGFzdXJhLWNsaWVudC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImhhc3VyYS1jbGllbnQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsZ0VBQWdFO0FBRWhFLE9BQU8sRUFBRSxhQUFhLEVBQUUsTUFBTSxpQkFBaUIsQ0FBQztBQUVoRCxrQ0FBa0M7QUFDbEMsbUZBQW1GO0FBQ25GLDhEQUE4RDtBQUU5RCxJQUFJLGNBQWMsR0FBeUIsSUFBSSxDQUFDO0FBRWhEOzs7Ozs7O0dBT0c7QUFDSCxNQUFNLENBQUMsTUFBTSxnQkFBZ0IsR0FBRyxHQUFrQixFQUFFO0lBQ2xELElBQUksY0FBYyxFQUFFLENBQUM7UUFDbkIsT0FBTyxjQUFjLENBQUM7SUFDeEIsQ0FBQztJQUVELE1BQU0sUUFBUSxHQUFHLE9BQU8sQ0FBQyxHQUFHLENBQUMsMkJBQTJCLENBQUM7SUFDekQsTUFBTSxXQUFXLEdBQUcsT0FBTyxDQUFDLEdBQUcsQ0FBQywyQkFBMkIsQ0FBQztJQUU1RCxJQUFJLENBQUMsUUFBUSxFQUFFLENBQUM7UUFDZCxPQUFPLENBQUMsS0FBSyxDQUNYLDZFQUE2RSxDQUM5RSxDQUFDO1FBQ0YsTUFBTSxJQUFJLEtBQUssQ0FBQyxnREFBZ0QsQ0FBQyxDQUFDO0lBQ3BFLENBQUM7SUFFRCxJQUFJLENBQUMsV0FBVyxFQUFFLENBQUM7UUFDakIsT0FBTyxDQUFDLEtBQUssQ0FDWCw2RUFBNkUsQ0FDOUUsQ0FBQztRQUNGLE1BQU0sSUFBSSxLQUFLLENBQUMsd0NBQXdDLENBQUMsQ0FBQztJQUM1RCxDQUFDO0lBRUQseUZBQXlGO0lBQ3pGLE1BQU0sU0FBUyxHQUFHLFFBQVEsQ0FBQyxVQUFVLENBQUMsVUFBVSxDQUFDLENBQUMsQ0FBQyxDQUFDLFVBQVUsQ0FBQyxDQUFDLENBQUMsU0FBUyxDQUFDO0lBQzNFLE9BQU8sQ0FBQyxHQUFHLENBQ1QsMEVBQTBFLFNBQVMsS0FBSyxDQUN6RixDQUFDO0lBRUYsY0FBYyxHQUFHLElBQUksYUFBYSxDQUFDLFFBQVEsRUFBRTtRQUMzQyxPQUFPLEVBQUU7WUFDUCx1QkFBdUIsRUFBRSxXQUFXO1lBQ3BDLGNBQWMsRUFBRSxrQkFBa0I7U0FDbkM7S0FDRixDQUFDLENBQUM7SUFFSCxPQUFPLGNBQWMsQ0FBQztBQUN4QixDQUFDLENBQUM7QUFFRjs7O0dBR0c7QUFDSCxNQUFNLENBQUMsTUFBTSxpQkFBaUIsR0FBRyxHQUFTLEVBQUU7SUFDMUMsY0FBYyxHQUFHLElBQUksQ0FBQztJQUN0QixPQUFPLENBQUMsR0FBRyxDQUFDLHdEQUF3RCxDQUFDLENBQUM7QUFDeEUsQ0FBQyxDQUFDO0FBRUYsd0NBQXdDO0FBQ3hDOzs7Ozs7Ozs7Ozs7Ozs7RUFlRSIsInNvdXJjZXNDb250ZW50IjpbIi8vIEZpbGU6IGF0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvX3V0aWxzL2hhc3VyYS1jbGllbnQudHNcblxuaW1wb3J0IHsgR3JhcGhRTENsaWVudCB9IGZyb20gJ2dyYXBocWwtcmVxdWVzdCc7XG5cbi8vIEVudmlyb25tZW50IHZhcmlhYmxlcyBleHBlY3RlZDpcbi8vIC0gSEFTVVJBX0dSQVBIUUxfRU5EUE9JTlRfVVJMOiBUaGUgSFRUUChTKSBlbmRwb2ludCBmb3IgeW91ciBIYXN1cmEgR3JhcGhRTCBBUEkuXG4vLyAtIEhBU1VSQV9HUkFQSFFMX0FETUlOX1NFQ1JFVDogVGhlIGFkbWluIHNlY3JldCBmb3IgSGFzdXJhLlxuXG5sZXQgY2xpZW50SW5zdGFuY2U6IEdyYXBoUUxDbGllbnQgfCBudWxsID0gbnVsbDtcblxuLyoqXG4gKiBJbml0aWFsaXplcyBhbmQgcmV0dXJucyBhIEdyYXBoUUxDbGllbnQgaW5zdGFuY2UgY29uZmlndXJlZCBmb3IgSGFzdXJhLlxuICogSXQgdXNlcyBlbnZpcm9ubWVudCB2YXJpYWJsZXMgZm9yIHRoZSBlbmRwb2ludCBhbmQgYWRtaW4gc2VjcmV0LlxuICogVGhlIGNsaWVudCBpcyBjYWNoZWQgZm9yIHN1YnNlcXVlbnQgY2FsbHMgd2l0aGluIHRoZSBzYW1lIExhbWJkYSBpbnZvY2F0aW9uLlxuICpcbiAqIEByZXR1cm5zIHtHcmFwaFFMQ2xpZW50fSBBbiBpbnN0YW5jZSBvZiBHcmFwaFFMQ2xpZW50LlxuICogQHRocm93cyB7RXJyb3J9IElmIEhhc3VyYSBlbmRwb2ludCBvciBhZG1pbiBzZWNyZXQgZW52aXJvbm1lbnQgdmFyaWFibGVzIGFyZSBub3Qgc2V0LlxuICovXG5leHBvcnQgY29uc3QgZ2V0R3JhcGhRTENsaWVudCA9ICgpOiBHcmFwaFFMQ2xpZW50ID0+IHtcbiAgaWYgKGNsaWVudEluc3RhbmNlKSB7XG4gICAgcmV0dXJuIGNsaWVudEluc3RhbmNlO1xuICB9XG5cbiAgY29uc3QgZW5kcG9pbnQgPSBwcm9jZXNzLmVudi5IQVNVUkFfR1JBUEhRTF9FTkRQT0lOVF9VUkw7XG4gIGNvbnN0IGFkbWluU2VjcmV0ID0gcHJvY2Vzcy5lbnYuSEFTVVJBX0dSQVBIUUxfQURNSU5fU0VDUkVUO1xuXG4gIGlmICghZW5kcG9pbnQpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgJ1tIYXN1cmFDbGllbnRdIEhBU1VSQV9HUkFQSFFMX0VORFBPSU5UX1VSTCBlbnZpcm9ubWVudCB2YXJpYWJsZSBpcyBub3Qgc2V0LidcbiAgICApO1xuICAgIHRocm93IG5ldyBFcnJvcignSGFzdXJhIEdyYXBoUUwgZW5kcG9pbnQgVVJMIGlzIG5vdCBjb25maWd1cmVkLicpO1xuICB9XG5cbiAgaWYgKCFhZG1pblNlY3JldCkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAnW0hhc3VyYUNsaWVudF0gSEFTVVJBX0dSQVBIUUxfQURNSU5fU0VDUkVUIGVudmlyb25tZW50IHZhcmlhYmxlIGlzIG5vdCBzZXQuJ1xuICAgICk7XG4gICAgdGhyb3cgbmV3IEVycm9yKCdIYXN1cmEgYWRtaW4gc2VjcmV0IGlzIG5vdCBjb25maWd1cmVkLicpO1xuICB9XG5cbiAgLy8gQmFzaWMgbG9nZ2luZyB0byBjb25maXJtIGluaXRpYWxpemF0aW9uLCBhdm9pZCBsb2dnaW5nIGZ1bGwgZW5kcG9pbnQgaWYgdG9vIHNlbnNpdGl2ZS5cbiAgY29uc3QgdXJsU2NoZW1lID0gZW5kcG9pbnQuc3RhcnRzV2l0aCgnaHR0cHM6Ly8nKSA/ICdodHRwczovLycgOiAnaHR0cDovLyc7XG4gIGNvbnNvbGUubG9nKFxuICAgIGBbSGFzdXJhQ2xpZW50XSBJbml0aWFsaXppbmcgR3JhcGhRTCBjbGllbnQgZm9yIGVuZHBvaW50IHN0YXJ0aW5nIHdpdGg6ICR7dXJsU2NoZW1lfS4uLmBcbiAgKTtcblxuICBjbGllbnRJbnN0YW5jZSA9IG5ldyBHcmFwaFFMQ2xpZW50KGVuZHBvaW50LCB7XG4gICAgaGVhZGVyczoge1xuICAgICAgJ3gtaGFzdXJhLWFkbWluLXNlY3JldCc6IGFkbWluU2VjcmV0LFxuICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICB9LFxuICB9KTtcblxuICByZXR1cm4gY2xpZW50SW5zdGFuY2U7XG59O1xuXG4vKipcbiAqIENsZWFycyB0aGUgY2FjaGVkIEdyYXBoUUxDbGllbnQgaW5zdGFuY2UuXG4gKiBVc2VmdWwgZm9yIHRlc3Rpbmcgb3IgaWYgY3JlZGVudGlhbHMgbmVlZCB0byBiZSByZS1ldmFsdWF0ZWQgaW4gYSBsb25nLXJ1bm5pbmcgcHJvY2Vzcy5cbiAqL1xuZXhwb3J0IGNvbnN0IGNsZWFyQ2FjaGVkQ2xpZW50ID0gKCk6IHZvaWQgPT4ge1xuICBjbGllbnRJbnN0YW5jZSA9IG51bGw7XG4gIGNvbnNvbGUubG9nKCdbSGFzdXJhQ2xpZW50XSBDYWNoZWQgR3JhcGhRTCBjbGllbnQgaW5zdGFuY2UgY2xlYXJlZC4nKTtcbn07XG5cbi8vIEV4YW1wbGUgb2YgaG93IGEgTGFtYmRhIG1pZ2h0IHVzZSBpdDpcbi8qXG5pbXBvcnQgeyBnZXRHcmFwaFFMQ2xpZW50IH0gZnJvbSAnLi9oYXN1cmEtY2xpZW50JzsgLy8gQWRqdXN0IHBhdGggYXMgbmVlZGVkXG5pbXBvcnQgeyBncWwgfSBmcm9tICdncmFwaHFsLXJlcXVlc3QnO1xuXG5leHBvcnQgY29uc3Qgc29tZUxhbWJkYUhhbmRsZXIgPSBhc3luYyAoZXZlbnQ6IGFueSkgPT4ge1xuICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IGNsaWVudCA9IGdldEdyYXBoUUxDbGllbnQoKTtcbiAgICAgICAgY29uc3QgcXVlcnkgPSBncWxgcXVlcnkgTXlRdWVyeSB7IHlvdXJfdGFibGUgeyBpZCB9IH1gO1xuICAgICAgICBjb25zdCBkYXRhID0gYXdhaXQgY2xpZW50LnJlcXVlc3QocXVlcnkpO1xuICAgICAgICBjb25zb2xlLmxvZyhkYXRhKTtcbiAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgICBjb25zb2xlLmVycm9yKFwiRXJyb3IgaW4gc29tZUxhbWJkYUhhbmRsZXI6XCIsIGVycm9yKTtcbiAgICAgICAgLy8gaGFuZGxlIGVycm9yXG4gICAgfVxufTtcbiovXG4iXX0=