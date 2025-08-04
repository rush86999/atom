import { Calendly } from '@calendly/api-client';
import { decrypt } from '../_libs/crypto';
import { executeGraphQLQuery } from '../_libs/graphqlClient';
async function getCalendlyApiKey(userId) {
    const query = `
        query GetUserCredential($userId: String!, $serviceName: String!) {
            user_credentials(where: {user_id: {_eq: $userId}, service_name: {_eq: $serviceName}}) {
                encrypted_secret
            }
        }
    `;
    const variables = {
        userId,
        serviceName: 'calendly_api_key',
    };
    const response = await executeGraphQLQuery(query, variables, 'GetUserCredential', userId);
    if (response.user_credentials && response.user_credentials.length > 0) {
        return decrypt(response.user_credentials[0].encrypted_secret);
    }
    return null;
}
const getCalendlyClient = async (userId) => {
    const personalAccessToken = await getCalendlyApiKey(userId);
    if (!personalAccessToken) {
        console.error('Calendly Personal Access Token not configured for this user.');
        return null;
    }
    return new Calendly({
        auth: {
            personalAccessToken,
        },
    });
};
export async function listCalendlyEventTypes(callingUserId) {
    console.log(`listCalendlyEventTypes called by userId: ${callingUserId}`);
    const client = await getCalendlyClient(callingUserId);
    if (!client) {
        return {
            ok: false,
            error: 'Calendly Personal Access Token not configured.',
        };
    }
    try {
        // First, get the current user's URI, as event types are typically listed for a user.
        const meResponse = await client.users.getCurrent(); // SDK should provide a method like this.
        if (!meResponse || !meResponse.resource || !meResponse.resource.uri) {
            console.error('Failed to retrieve current user URI from Calendly.');
            return {
                ok: false,
                error: 'Failed to retrieve current user URI from Calendly.',
            };
        }
        const userUri = meResponse.resource.uri;
        // Now list event types for this user.
        // The SDK's list method might take slightly different parameters.
        // Common parameters are `user`, `active`, `count`.
        const eventTypesResponse = await client.eventTypes.list({
            user: userUri,
            active: true, // Typically, you want active event types.
            count: 100, // Adjust count as needed, or handle pagination more robustly.
            // sort: 'name:asc' // Optional: sorting
        });
        // Cast the SDK's collection and pagination to our defined types.
        // This assumes the structure is compatible. If not, mapping is needed.
        return {
            ok: true,
            collection: eventTypesResponse.collection,
            pagination: eventTypesResponse.pagination,
        };
    }
    catch (error) {
        console.error(`Error listing Calendly event types for userId ${callingUserId}:`, error.message);
        if (error.response && error.response.data) {
            // Calendly SDK might wrap error details in response.data
            console.error('Calendly API Error Details:', error.response.data);
            const details = error.response.data;
            return {
                ok: false,
                error: details.message ||
                    details.title ||
                    error.message ||
                    'Failed to list Calendly event types',
            };
        }
        return {
            ok: false,
            error: error.message || 'Failed to list Calendly event types',
        };
    }
}
export async function listCalendlyScheduledEvents(callingUserId, options) {
    console.log(`listCalendlyScheduledEvents called by userId: ${callingUserId} with options:`, options);
    const client = await getCalendlyClient(callingUserId);
    if (!client) {
        return {
            ok: false,
            error: 'Calendly Personal Access Token not configured.',
        };
    }
    try {
        const meResponse = await client.users.getCurrent();
        if (!meResponse || !meResponse.resource || !meResponse.resource.uri) {
            console.error('Failed to retrieve current user URI from Calendly.');
            return {
                ok: false,
                error: 'Failed to retrieve current user URI from Calendly.',
            };
        }
        const userUri = meResponse.resource.uri;
        // Prepare options for the SDK, mapping our options to what the SDK expects.
        // The Calendly SDK list methods usually take an object of query parameters.
        const apiOptions = {
            user: userUri, // Associate with the current user
            ...(options?.count && { count: options.count }),
            ...(options?.status && { status: options.status }),
            ...(options?.sort && { sort: options.sort }),
            ...(options?.pageToken && { page_token: options.pageToken }), // Note: SDK might use 'pageToken' or 'page_token'
            ...(options?.min_start_time && {
                min_start_time: options.min_start_time,
            }),
            ...(options?.max_start_time && {
                max_start_time: options.max_start_time,
            }),
        };
        const scheduledEventsResponse = await client.scheduledEvents.list(apiOptions);
        return {
            ok: true,
            collection: scheduledEventsResponse.collection,
            pagination: scheduledEventsResponse.pagination,
        };
    }
    catch (error) {
        console.error(`Error listing Calendly scheduled events for userId ${callingUserId}:`, error.message);
        if (error.response && error.response.data) {
            console.error('Calendly API Error Details:', error.response.data);
            const details = error.response.data;
            return {
                ok: false,
                error: details.message ||
                    details.title ||
                    error.message ||
                    'Failed to list Calendly scheduled events',
            };
        }
        return {
            ok: false,
            error: error.message || 'Failed to list Calendly scheduled events',
        };
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsZW5kbHlTa2lsbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjYWxlbmRseVNraWxscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEVBQUUsUUFBUSxFQUFFLE1BQU0sc0JBQXNCLENBQUM7QUFDaEQsT0FBTyxFQUFFLE9BQU8sRUFBRSxNQUFNLGlCQUFpQixDQUFDO0FBQzFDLE9BQU8sRUFBRSxtQkFBbUIsRUFBRSxNQUFNLHdCQUF3QixDQUFDO0FBUzdELEtBQUssVUFBVSxpQkFBaUIsQ0FBQyxNQUFjO0lBQzdDLE1BQU0sS0FBSyxHQUFHOzs7Ozs7S0FNWCxDQUFDO0lBQ0osTUFBTSxTQUFTLEdBQUc7UUFDaEIsTUFBTTtRQUNOLFdBQVcsRUFBRSxrQkFBa0I7S0FDaEMsQ0FBQztJQUNGLE1BQU0sUUFBUSxHQUFHLE1BQU0sbUJBQW1CLENBRXZDLEtBQUssRUFBRSxTQUFTLEVBQUUsbUJBQW1CLEVBQUUsTUFBTSxDQUFDLENBQUM7SUFDbEQsSUFBSSxRQUFRLENBQUMsZ0JBQWdCLElBQUksUUFBUSxDQUFDLGdCQUFnQixDQUFDLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztRQUN0RSxPQUFPLE9BQU8sQ0FBQyxRQUFRLENBQUMsZ0JBQWdCLENBQUMsQ0FBQyxDQUFDLENBQUMsZ0JBQWdCLENBQUMsQ0FBQztJQUNoRSxDQUFDO0lBQ0QsT0FBTyxJQUFJLENBQUM7QUFDZCxDQUFDO0FBRUQsTUFBTSxpQkFBaUIsR0FBRyxLQUFLLEVBQUUsTUFBYyxFQUFFLEVBQUU7SUFDakQsTUFBTSxtQkFBbUIsR0FBRyxNQUFNLGlCQUFpQixDQUFDLE1BQU0sQ0FBQyxDQUFDO0lBQzVELElBQUksQ0FBQyxtQkFBbUIsRUFBRSxDQUFDO1FBQ3pCLE9BQU8sQ0FBQyxLQUFLLENBQ1gsOERBQThELENBQy9ELENBQUM7UUFDRixPQUFPLElBQUksQ0FBQztJQUNkLENBQUM7SUFDRCxPQUFPLElBQUksUUFBUSxDQUFDO1FBQ2xCLElBQUks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RUFBRSxPQUFPLENBQUMsY0FBYzthQUN2QyxDQUFDO1NBQ0gsQ0FBQztRQUVGLE1BQU0sdUJBQXVCLEdBQzNCLE1BQU0sTUFBTSxDQUFDLGVBQWUsQ0FBQyxJQUFJLENBQUMsVUFBVSxDQUFDLENBQUM7UUFFaEQsT0FBTztZQUNMLEVBQUUsRUFBRSxJQUFJO1lBQ1IsVUFBVSxFQUNSLHVCQUF1QixDQUFDLFVBQXNDO1lBQ2hFLFVBQVUsRUFBRSx1QkFBdUIsQ0FBQyxVQUFnQztTQUNyRSxDQUFDO0lBQ0osQ0FBQztJQUFDLE9BQU8sS0FBVSxFQUFFLENBQUM7UUFDcEIsT0FBTyxDQUFDLEtBQUssQ0FDWCxzREFBc0QsYUFBYSxHQUFHLEVBQ3RFLEtBQUssQ0FBQyxPQUFPLENBQ2QsQ0FBQztRQUNGLElBQUksS0FBSyxDQUFDLFFBQVEsSUFBSSxLQUFLLENBQUMsUUFBUSxDQUFDLElBQUksRUFBRSxDQUFDO1lBQzFDLE9BQU8sQ0FBQyxLQUFLLENBQUMsNkJBQTZCLEVBQUUsS0FBSyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUMsQ0FBQztZQUNsRSxNQUFNLE9BQU8sR0FBRyxLQUFLLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQztZQUNwQyxPQUFPO2dCQUNMLEVBQUUsRUFBRSxLQUFLO2dCQUNULEtBQUssRUFDSCxPQUFPLENBQUMsT0FBTztvQkFDZixPQUFPLENBQUMsS0FBSztvQkFDYixLQUFLLENBQUMsT0FBTztvQkFDYiwwQ0FBMEM7YUFDN0MsQ0FBQztRQUNKLENBQUM7UUFDRCxPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUUsS0FBSyxDQUFDLE9BQU8sSUFBSSwwQ0FBMEM7U0FDbkUsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgQ2FsZW5kbHkgfSBmcm9tICdAY2FsZW5kbHkvYXBpLWNsaWVudCc7XG5pbXBvcnQgeyBkZWNyeXB0IH0gZnJvbSAnLi4vX2xpYnMvY3J5cHRvJztcbmltcG9ydCB7IGV4ZWN1dGVHcmFwaFFMUXVlcnkgfSBmcm9tICcuLi9fbGlicy9ncmFwaHFsQ2xpZW50JztcbmltcG9ydCB7XG4gIENhbGVuZGx5RXZlbnRUeXBlLFxuICBDYWxlbmRseVNjaGVkdWxlZEV2ZW50LFxuICBDYWxlbmRseVBhZ2luYXRpb24sXG4gIExpc3RDYWxlbmRseUV2ZW50VHlwZXNSZXNwb25zZSxcbiAgTGlzdENhbGVuZGx5U2NoZWR1bGVkRXZlbnRzUmVzcG9uc2UsXG59IGZyb20gJy4uL3R5cGVzJztcblxuYXN5bmMgZnVuY3Rpb24gZ2V0Q2FsZW5kbHlBcGlLZXkodXNlcklkOiBzdHJpbmcpOiBQcm9taXNlPHN0cmluZyB8IG51bGw+IHtcbiAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgIHF1ZXJ5IEdldFVzZXJDcmVkZW50aWFsKCR1c2VySWQ6IFN0cmluZyEsICRzZXJ2aWNlTmFtZTogU3RyaW5nISkge1xuICAgICAgICAgICAgdXNlcl9jcmVkZW50aWFscyh3aGVyZToge3VzZXJfaWQ6IHtfZXE6ICR1c2VySWR9LCBzZXJ2aWNlX25hbWU6IHtfZXE6ICRzZXJ2aWNlTmFtZX19KSB7XG4gICAgICAgICAgICAgICAgZW5jcnlwdGVkX3NlY3JldFxuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgYDtcbiAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgIHVzZXJJZCxcbiAgICBzZXJ2aWNlTmFtZTogJ2NhbGVuZGx5X2FwaV9rZXknLFxuICB9O1xuICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGV4ZWN1dGVHcmFwaFFMUXVlcnk8e1xuICAgIHVzZXJfY3JlZGVudGlhbHM6IHsgZW5jcnlwdGVkX3NlY3JldDogc3RyaW5nIH1bXTtcbiAgfT4ocXVlcnksIHZhcmlhYmxlcywgJ0dldFVzZXJDcmVkZW50aWFsJywgdXNlcklkKTtcbiAgaWYgKHJlc3BvbnNlLnVzZXJfY3JlZGVudGlhbHMgJiYgcmVzcG9uc2UudXNlcl9jcmVkZW50aWFscy5sZW5ndGggPiAwKSB7XG4gICAgcmV0dXJuIGRlY3J5cHQocmVzcG9uc2UudXNlcl9jcmVkZW50aWFsc1swXS5lbmNyeXB0ZWRfc2VjcmV0KTtcbiAgfVxuICByZXR1cm4gbnVsbDtcbn1cblxuY29uc3QgZ2V0Q2FsZW5kbHlDbGllbnQgPSBhc3luYyAodXNlcklkOiBzdHJpbmcpID0+IHtcbiAgY29uc3QgcGVyc29uYWxBY2Nlc3NUb2tlbiA9IGF3YWl0IGdldENhbGVuZGx5QXBpS2V5KHVzZXJJZCk7XG4gIGlmICghcGVyc29uYWxBY2Nlc3NUb2tlbikge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAnQ2FsZW5kbHkgUGVyc29uYWwgQWNjZXNzIFRva2VuIG5vdCBjb25maWd1cmVkIGZvciB0aGlzIHVzZXIuJ1xuICAgICk7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cbiAgcmV0dXJuIG5ldyBDYWxlbmRseSh7XG4gICAgYXV0aDoge1xuICAgICAgcGVyc29uYWxBY2Nlc3NUb2tlbixcbiAgICB9LFxuICB9KTtcbn07XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBsaXN0Q2FsZW5kbHlFdmVudFR5cGVzKFxuICBjYWxsaW5nVXNlcklkOiBzdHJpbmdcbik6IFByb21pc2U8TGlzdENhbGVuZGx5RXZlbnRUeXBlc1Jlc3BvbnNlPiB7XG4gIGNvbnNvbGUubG9nKGBsaXN0Q2FsZW5kbHlFdmVudFR5cGVzIGNhbGxlZCBieSB1c2VySWQ6ICR7Y2FsbGluZ1VzZXJJZH1gKTtcbiAgY29uc3QgY2xpZW50ID0gYXdhaXQgZ2V0Q2FsZW5kbHlDbGllbnQoY2FsbGluZ1VzZXJJZCk7XG4gIGlmICghY2xpZW50KSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiAnQ2FsZW5kbHkgUGVyc29uYWwgQWNjZXNzIFRva2VuIG5vdCBjb25maWd1cmVkLicsXG4gICAgfTtcbiAgfVxuXG4gIHRyeSB7XG4gICAgLy8gRmlyc3QsIGdldCB0aGUgY3VycmVudCB1c2VyJ3MgVVJJLCBhcyBldmVudCB0eXBlcyBhcmUgdHlwaWNhbGx5IGxpc3RlZCBmb3IgYSB1c2VyLlxuICAgIGNvbnN0IG1lUmVzcG9uc2UgPSBhd2FpdCBjbGllbnQudXNlcnMuZ2V0Q3VycmVudCgpOyAvLyBTREsgc2hvdWxkIHByb3ZpZGUgYSBtZXRob2QgbGlrZSB0aGlzLlxuICAgIGlmICghbWVSZXNwb25zZSB8fCAhbWVSZXNwb25zZS5yZXNvdXJjZSB8fCAhbWVSZXNwb25zZS5yZXNvdXJjZS51cmkpIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoJ0ZhaWxlZCB0byByZXRyaWV2ZSBjdXJyZW50IHVzZXIgVVJJIGZyb20gQ2FsZW5kbHkuJyk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiAnRmFpbGVkIHRvIHJldHJpZXZlIGN1cnJlbnQgdXNlciBVUkkgZnJvbSBDYWxlbmRseS4nLFxuICAgICAgfTtcbiAgICB9XG4gICAgY29uc3QgdXNlclVyaSA9IG1lUmVzcG9uc2UucmVzb3VyY2UudXJpO1xuXG4gICAgLy8gTm93IGxpc3QgZXZlbnQgdHlwZXMgZm9yIHRoaXMgdXNlci5cbiAgICAvLyBUaGUgU0RLJ3MgbGlzdCBtZXRob2QgbWlnaHQgdGFrZSBzbGlnaHRseSBkaWZmZXJlbnQgcGFyYW1ldGVycy5cbiAgICAvLyBDb21tb24gcGFyYW1ldGVycyBhcmUgYHVzZXJgLCBgYWN0aXZlYCwgYGNvdW50YC5cbiAgICBjb25zdCBldmVudFR5cGVzUmVzcG9uc2UgPSBhd2FpdCBjbGllbnQuZXZlbnRUeXBlcy5saXN0KHtcbiAgICAgIHVzZXI6IHVzZXJVcmksXG4gICAgICBhY3RpdmU6IHRydWUsIC8vIFR5cGljYWxseSwgeW91IHdhbnQgYWN0aXZlIGV2ZW50IHR5cGVzLlxuICAgICAgY291bnQ6IDEwMCwgLy8gQWRqdXN0IGNvdW50IGFzIG5lZWRlZCwgb3IgaGFuZGxlIHBhZ2luYXRpb24gbW9yZSByb2J1c3RseS5cbiAgICAgIC8vIHNvcnQ6ICduYW1lOmFzYycgLy8gT3B0aW9uYWw6IHNvcnRpbmdcbiAgICB9KTtcblxuICAgIC8vIENhc3QgdGhlIFNESydzIGNvbGxlY3Rpb24gYW5kIHBhZ2luYXRpb24gdG8gb3VyIGRlZmluZWQgdHlwZXMuXG4gICAgLy8gVGhpcyBhc3N1bWVzIHRoZSBzdHJ1Y3R1cmUgaXMgY29tcGF0aWJsZS4gSWYgbm90LCBtYXBwaW5nIGlzIG5lZWRlZC5cbiAgICByZXR1cm4ge1xuICAgICAgb2s6IHRydWUsXG4gICAgICBjb2xsZWN0aW9uOiBldmVudFR5cGVzUmVzcG9uc2UuY29sbGVjdGlvbiBhcyBDYWxlbmRseUV2ZW50VHlwZVtdLFxuICAgICAgcGFnaW5hdGlvbjogZXZlbnRUeXBlc1Jlc3BvbnNlLnBhZ2luYXRpb24gYXMgQ2FsZW5kbHlQYWdpbmF0aW9uLFxuICAgIH07XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgYEVycm9yIGxpc3RpbmcgQ2FsZW5kbHkgZXZlbnQgdHlwZXMgZm9yIHVzZXJJZCAke2NhbGxpbmdVc2VySWR9OmAsXG4gICAgICBlcnJvci5tZXNzYWdlXG4gICAgKTtcbiAgICBpZiAoZXJyb3IucmVzcG9uc2UgJiYgZXJyb3IucmVzcG9uc2UuZGF0YSkge1xuICAgICAgLy8gQ2FsZW5kbHkgU0RLIG1pZ2h0IHdyYXAgZXJyb3IgZGV0YWlscyBpbiByZXNwb25zZS5kYXRhXG4gICAgICBjb25zb2xlLmVycm9yKCdDYWxlbmRseSBBUEkgRXJyb3IgRGV0YWlsczonLCBlcnJvci5yZXNwb25zZS5kYXRhKTtcbiAgICAgIGNvbnN0IGRldGFpbHMgPSBlcnJvci5yZXNwb25zZS5kYXRhO1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICBlcnJvcjpcbiAgICAgICAgICBkZXRhaWxzLm1lc3NhZ2UgfHxcbiAgICAgICAgICBkZXRhaWxzLnRpdGxlIHx8XG4gICAgICAgICAgZXJyb3IubWVzc2FnZSB8fFxuICAgICAgICAgICdGYWlsZWQgdG8gbGlzdCBDYWxlbmRseSBldmVudCB0eXBlcycsXG4gICAgICB9O1xuICAgIH1cbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IGVycm9yLm1lc3NhZ2UgfHwgJ0ZhaWxlZCB0byBsaXN0IENhbGVuZGx5IGV2ZW50IHR5cGVzJyxcbiAgICB9O1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBsaXN0Q2FsZW5kbHlTY2hlZHVsZWRFdmVudHMoXG4gIGNhbGxpbmdVc2VySWQ6IHN0cmluZyxcbiAgb3B0aW9ucz86IHtcbiAgICBjb3VudD86IG51bWJlcjtcbiAgICBzdGF0dXM/OiAnYWN0aXZlJyB8ICdjYW5jZWxlZCc7XG4gICAgc29ydD86IHN0cmluZzsgLy8gZS5nLiwgXCJzdGFydF90aW1lOmRlc2NcIlxuICAgIHBhZ2VUb2tlbj86IHN0cmluZzsgLy8gRm9yIHRva2VuLWJhc2VkIHBhZ2luYXRpb25cbiAgICBtaW5fc3RhcnRfdGltZT86IHN0cmluZzsgLy8gSVNPIDg2MDEgZm9ybWF0XG4gICAgbWF4X3N0YXJ0X3RpbWU/OiBzdHJpbmc7IC8vIElTTyA4NjAxIGZvcm1hdFxuICAgIC8vIGludml0ZWVfZW1haWw/OiBzdHJpbmc7IC8vIElmIGZpbHRlcmluZyBieSBpbnZpdGVlXG4gIH1cbik6IFByb21pc2U8TGlzdENhbGVuZGx5U2NoZWR1bGVkRXZlbnRzUmVzcG9uc2U+IHtcbiAgY29uc29sZS5sb2coXG4gICAgYGxpc3RDYWxlbmRseVNjaGVkdWxlZEV2ZW50cyBjYWxsZWQgYnkgdXNlcklkOiAke2NhbGxpbmdVc2VySWR9IHdpdGggb3B0aW9uczpgLFxuICAgIG9wdGlvbnNcbiAgKTtcbiAgY29uc3QgY2xpZW50ID0gYXdhaXQgZ2V0Q2FsZW5kbHlDbGllbnQoY2FsbGluZ1VzZXJJZCk7XG4gIGlmICghY2xpZW50KSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiAnQ2FsZW5kbHkgUGVyc29uYWwgQWNjZXNzIFRva2VuIG5vdCBjb25maWd1cmVkLicsXG4gICAgfTtcbiAgfVxuXG4gIHRyeSB7XG4gICAgY29uc3QgbWVSZXNwb25zZSA9IGF3YWl0IGNsaWVudC51c2Vycy5nZXRDdXJyZW50KCk7XG4gICAgaWYgKCFtZVJlc3BvbnNlIHx8ICFtZVJlc3BvbnNlLnJlc291cmNlIHx8ICFtZVJlc3BvbnNlLnJlc291cmNlLnVyaSkge1xuICAgICAgY29uc29sZS5lcnJvcignRmFpbGVkIHRvIHJldHJpZXZlIGN1cnJlbnQgdXNlciBVUkkgZnJvbSBDYWxlbmRseS4nKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6ICdGYWlsZWQgdG8gcmV0cmlldmUgY3VycmVudCB1c2VyIFVSSSBmcm9tIENhbGVuZGx5LicsXG4gICAgICB9O1xuICAgIH1cbiAgICBjb25zdCB1c2VyVXJpID0gbWVSZXNwb25zZS5yZXNvdXJjZS51cmk7XG5cbiAgICAvLyBQcmVwYXJlIG9wdGlvbnMgZm9yIHRoZSBTREssIG1hcHBpbmcgb3VyIG9wdGlvbnMgdG8gd2hhdCB0aGUgU0RLIGV4cGVjdHMuXG4gICAgLy8gVGhlIENhbGVuZGx5IFNESyBsaXN0IG1ldGhvZHMgdXN1YWxseSB0YWtlIGFuIG9iamVjdCBvZiBxdWVyeSBwYXJhbWV0ZXJzLlxuICAgIGNvbnN0IGFwaU9wdGlvbnM6IFJlY29yZDxzdHJpbmcsIGFueT4gPSB7XG4gICAgICB1c2VyOiB1c2VyVXJpLCAvLyBBc3NvY2lhdGUgd2l0aCB0aGUgY3VycmVudCB1c2VyXG4gICAgICAuLi4ob3B0aW9ucz8uY291bnQgJiYgeyBjb3VudDogb3B0aW9ucy5jb3VudCB9KSxcbiAgICAgIC4uLihvcHRpb25zPy5zdGF0dXMgJiYgeyBzdGF0dXM6IG9wdGlvbnMuc3RhdHVzIH0pLFxuICAgICAgLi4uKG9wdGlvbnM/LnNvcnQgJiYgeyBzb3J0OiBvcHRpb25zLnNvcnQgfSksXG4gICAgICAuLi4ob3B0aW9ucz8ucGFnZVRva2VuICYmIHsgcGFnZV90b2tlbjogb3B0aW9ucy5wYWdlVG9rZW4gfSksIC8vIE5vdGU6IFNESyBtaWdodCB1c2UgJ3BhZ2VUb2tlbicgb3IgJ3BhZ2VfdG9rZW4nXG4gICAgICAuLi4ob3B0aW9ucz8ubWluX3N0YXJ0X3RpbWUgJiYge1xuICAgICAgICBtaW5fc3RhcnRfdGltZTogb3B0aW9ucy5taW5fc3RhcnRfdGltZSxcbiAgICAgIH0pLFxuICAgICAgLi4uKG9wdGlvbnM/Lm1heF9zdGFydF90aW1lICYmIHtcbiAgICAgICAgbWF4X3N0YXJ0X3RpbWU6IG9wdGlvbnMubWF4X3N0YXJ0X3RpbWUsXG4gICAgICB9KSxcbiAgICB9O1xuXG4gICAgY29uc3Qgc2NoZWR1bGVkRXZlbnRzUmVzcG9uc2UgPVxuICAgICAgYXdhaXQgY2xpZW50LnNjaGVkdWxlZEV2ZW50cy5saXN0KGFwaU9wdGlvbnMpO1xuXG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiB0cnVlLFxuICAgICAgY29sbGVjdGlvbjpcbiAgICAgICAgc2NoZWR1bGVkRXZlbnRzUmVzcG9uc2UuY29sbGVjdGlvbiBhcyBDYWxlbmRseVNjaGVkdWxlZEV2ZW50W10sXG4gICAgICBwYWdpbmF0aW9uOiBzY2hlZHVsZWRFdmVudHNSZXNwb25zZS5wYWdpbmF0aW9uIGFzIENhbGVuZGx5UGFnaW5hdGlvbixcbiAgICB9O1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcihcbiAgICAgIGBFcnJvciBsaXN0aW5nIENhbGVuZGx5IHNjaGVkdWxlZCBldmVudHMgZm9yIHVzZXJJZCAke2NhbGxpbmdVc2VySWR9OmAsXG4gICAgICBlcnJvci5tZXNzYWdlXG4gICAgKTtcbiAgICBpZiAoZXJyb3IucmVzcG9uc2UgJiYgZXJyb3IucmVzcG9uc2UuZGF0YSkge1xuICAgICAgY29uc29sZS5lcnJvcignQ2FsZW5kbHkgQVBJIEVycm9yIERldGFpbHM6JywgZXJyb3IucmVzcG9uc2UuZGF0YSk7XG4gICAgICBjb25zdCBkZXRhaWxzID0gZXJyb3IucmVzcG9uc2UuZGF0YTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6XG4gICAgICAgICAgZGV0YWlscy5tZXNzYWdlIHx8XG4gICAgICAgICAgZGV0YWlscy50aXRsZSB8fFxuICAgICAgICAgIGVycm9yLm1lc3NhZ2UgfHxcbiAgICAgICAgICAnRmFpbGVkIHRvIGxpc3QgQ2FsZW5kbHkgc2NoZWR1bGVkIGV2ZW50cycsXG4gICAgICB9O1xuICAgIH1cbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IGVycm9yLm1lc3NhZ2UgfHwgJ0ZhaWxlZCB0byBsaXN0IENhbGVuZGx5IHNjaGVkdWxlZCBldmVudHMnLFxuICAgIH07XG4gIH1cbn1cbiJdfQ==