import { ListCalendlyEventTypesResponse, ListCalendlyScheduledEventsResponse } from '../../types';
import { listCalendlyEventTypes as listTypes, listCalendlyScheduledEvents as listScheduled } from './calendlySkills';
import { handleError } from '../../_utils/errorHandler';

export async function handleListCalendlyEventTypes(userId: string, entities: any): Promise<string> {
    try {
        const calendlyUserId = entities?.user_id && typeof entities.user_id === 'string' ? entities.user_id : userId;
        const response: ListCalendlyEventTypesResponse = await listTypes(calendlyUserId);
        if (response.ok && response.collection && response.collection.length > 0) {
            let output = "Your Calendly Event Types (via NLU):\n";
            for (const et of response.collection) {
                output += `- ${et.name} (${et.duration} mins) - Active: ${et.active} - URL: ${et.scheduling_url}\n`;
            }
            if (response.pagination?.next_page_token) {
                output += `More event types available. Use next page token: ${response.pagination.next_page_token}\n`;
            }
            return output;
        } else if (response.ok) {
            return "No active Calendly event types found (via NLU).";
        } else {
            return `Error fetching Calendly event types (via NLU): ${response.error || 'Unknown error'}`;
        }
    } catch (error: any) {
        return handleError(error, "Sorry, an unexpected error occurred while fetching your Calendly event types (NLU path).");
    }
}

export async function handleListCalendlyScheduledEvents(userId: string, entities: any): Promise<string> {
    try {
        const calendlyUserId = entities?.user_id && typeof entities.user_id === 'string' ? entities.user_id : userId;
        const count = entities?.count && typeof entities.count === 'number' ? entities.count : 10;
        const status = entities?.status && typeof entities.status === 'string' ? entities.status as ('active' | 'canceled') : 'active';
        const sort = entities?.sort && typeof entities.sort === 'string' ? entities.sort : 'start_time:asc';
        const options = { count, status, sort, user: calendlyUserId };
        const response: ListCalendlyScheduledEventsResponse = await listScheduled(calendlyUserId, options);
        if (response.ok && response.collection && response.collection.length > 0) {
            let output = `Your Calendly Bookings (${status}, via NLU):\n`;
            for (const se of response.collection) {
                output += `- ${se.name} (Starts: ${new Date(se.start_time).toLocaleString()}, Ends: ${new Date(se.end_time).toLocaleString()}) - Status: ${se.status}\n`;
            }
            if (response.pagination?.next_page_token) {
                output += `More bookings available. Use next page token: ${response.pagination.next_page_token}\n`;
            }
            return output;
        } else if (response.ok) {
            return `No ${status} scheduled Calendly bookings found (via NLU).`;
        } else {
            return `Error fetching Calendly bookings (via NLU): ${response.error || 'Unknown error'}`;
        }
    } catch (error: any) {
        return handleError(error, "Sorry, an unexpected error occurred while fetching your Calendly bookings (NLU path).");
    }
}
