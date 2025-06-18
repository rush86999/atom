import { Calendly } from '@calendly/api-client';
import { ATOM_CALENDLY_PERSONAL_ACCESS_TOKEN } from '../_libs/constants';
import {
  CalendlyEventType,
  CalendlyScheduledEvent,
  CalendlyPagination,
  ListCalendlyEventTypesResponse,
  ListCalendlyScheduledEventsResponse,
  // Assuming CalendlyUser and other sub-types will be implicitly handled by the SDK's response types
  // or we can use the SDK's own types like UserResource, EventTypeResource, ScheduledEventResource.
} from '../types'; // Using our defined types for response structure consistency.

// SDK specific types can be used for casting if needed, e.g.
// import { UserResource, EventTypeResource, ScheduledEventResource, Pagination as CalendlySDKPagination } from '@calendly/api-client/lib/models';

const getCalendlyClient = () => {
  if (!ATOM_CALENDLY_PERSONAL_ACCESS_TOKEN) {
    console.error('Calendly Personal Access Token not configured.');
    return null;
  }
  // The Calendly SDK constructor takes an object with an `auth` property
  // which in turn is an object with `personalAccessToken`.
  return new Calendly({
    auth: {
      personalAccessToken: ATOM_CALENDLY_PERSONAL_ACCESS_TOKEN,
    },
  });
};

export async function listCalendlyEventTypes(
  callingUserId: string
): Promise<ListCalendlyEventTypesResponse> {
  console.log(`listCalendlyEventTypes called by userId: ${callingUserId}`);
  const client = getCalendlyClient();
  if (!client) {
    return { ok: false, error: 'Calendly Personal Access Token not configured.' };
  }

  try {
    // First, get the current user's URI, as event types are typically listed for a user.
    const meResponse = await client.users.getCurrent(); // SDK should provide a method like this.
    if (!meResponse || !meResponse.resource || !meResponse.resource.uri) {
        console.error('Failed to retrieve current user URI from Calendly.');
        return { ok: false, error: 'Failed to retrieve current user URI from Calendly.'};
    }
    const userUri = meResponse.resource.uri;

    // Now list event types for this user.
    // The SDK's list method might take slightly different parameters.
    // Common parameters are `user`, `active`, `count`.
    const eventTypesResponse = await client.eventTypes.list({
      user: userUri,
      active: true, // Typically, you want active event types.
      count: 100,   // Adjust count as needed, or handle pagination more robustly.
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
    console.error(`Error listing Calendly event types for userId ${callingUserId}:`, error.message);
    if (error.response && error.response.data) { // Calendly SDK might wrap error details in response.data
        console.error('Calendly API Error Details:', error.response.data);
        const details = error.response.data;
        return { ok: false, error: details.message || details.title || error.message || 'Failed to list Calendly event types' };
    }
    return { ok: false, error: error.message || 'Failed to list Calendly event types' };
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
  console.log(`listCalendlyScheduledEvents called by userId: ${callingUserId} with options:`, options);
  const client = getCalendlyClient();
  if (!client) {
    return { ok: false, error: 'Calendly Personal Access Token not configured.' };
  }

  try {
    const meResponse = await client.users.getCurrent();
     if (!meResponse || !meResponse.resource || !meResponse.resource.uri) {
        console.error('Failed to retrieve current user URI from Calendly.');
        return { ok: false, error: 'Failed to retrieve current user URI from Calendly.'};
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
      ...(options?.min_start_time && { min_start_time: options.min_start_time }),
      ...(options?.max_start_time && { max_start_time: options.max_start_time }),
    };

    const scheduledEventsResponse = await client.scheduledEvents.list(apiOptions);

    return {
      ok: true,
      collection: scheduledEventsResponse.collection as CalendlyScheduledEvent[],
      pagination: scheduledEventsResponse.pagination as CalendlyPagination,
    };
  } catch (error: any) {
    console.error(`Error listing Calendly scheduled events for userId ${callingUserId}:`, error.message);
     if (error.response && error.response.data) {
        console.error('Calendly API Error Details:', error.response.data);
        const details = error.response.data;
        return { ok: false, error: details.message || details.title || error.message || 'Failed to list Calendly scheduled events' };
    }
    return { ok: false, error: error.message || 'Failed to list Calendly scheduled events' };
  }
}
