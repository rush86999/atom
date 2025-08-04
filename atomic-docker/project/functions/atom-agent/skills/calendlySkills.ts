import { Calendly } from '@calendly/api-client';
import { decrypt } from '../_libs/crypto';
import { executeGraphQLQuery } from '../_libs/graphqlClient';
import {
  CalendlyEventType,
  CalendlyScheduledEvent,
  CalendlyPagination,
  ListCalendlyEventTypesResponse,
  ListCalendlyScheduledEventsResponse,
} from '../types';

async function getCalendlyApiKey(userId: string): Promise<string | null> {
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
  const response = await executeGraphQLQuery<{
    user_credentials: { encrypted_secret: string }[];
  }>(query, variables, 'GetUserCredential', userId);
  if (response.user_credentials && response.user_credentials.length > 0) {
    return decrypt(response.user_credentials[0].encrypted_secret);
  }
  return null;
}

const getCalendlyClient = async (userId: string) => {
  const personalAccessToken = await getCalendlyApiKey(userId);
  if (!personalAccessToken) {
    console.error(
      'Calendly Personal Access Token not configured for this user.'
    );
    return null;
  }
  return new Calendly({
    auth: {
      personalAccessToken,
    },
  });
};

export async function listCalendlyEventTypes(
  callingUserId: string
): Promise<ListCalendlyEventTypesResponse> {
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
      collection: eventTypesResponse.collection as CalendlyEventType[],
      pagination: eventTypesResponse.pagination as CalendlyPagination,
    };
  } catch (error: any) {
    console.error(
      `Error listing Calendly event types for userId ${callingUserId}:`,
      error.message
    );
    if (error.response && error.response.data) {
      // Calendly SDK might wrap error details in response.data
      console.error('Calendly API Error Details:', error.response.data);
      const details = error.response.data;
      return {
        ok: false,
        error:
          details.message ||
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

export async function listCalendlyScheduledEvents(
  callingUserId: string,
  options?: {
    count?: number;
    status?: 'active' | 'canceled';
    sort?: string; // e.g., "start_time:desc"
    pageToken?: string; // For token-based pagination
    min_start_time?: string; // ISO 8601 format
    max_start_time?: string; // ISO 8601 format
    // invitee_email?: string; // If filtering by invitee
  }
): Promise<ListCalendlyScheduledEventsResponse> {
  console.log(
    `listCalendlyScheduledEvents called by userId: ${callingUserId} with options:`,
    options
  );
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
    const apiOptions: Record<string, any> = {
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

    const scheduledEventsResponse =
      await client.scheduledEvents.list(apiOptions);

    return {
      ok: true,
      collection:
        scheduledEventsResponse.collection as CalendlyScheduledEvent[],
      pagination: scheduledEventsResponse.pagination as CalendlyPagination,
    };
  } catch (error: any) {
    console.error(
      `Error listing Calendly scheduled events for userId ${callingUserId}:`,
      error.message
    );
    if (error.response && error.response.data) {
      console.error('Calendly API Error Details:', error.response.data);
      const details = error.response.data;
      return {
        ok: false,
        error:
          details.message ||
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
