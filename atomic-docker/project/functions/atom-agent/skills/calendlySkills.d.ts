import { ListCalendlyEventTypesResponse, ListCalendlyScheduledEventsResponse } from '../types';
export declare function listCalendlyEventTypes(callingUserId: string): Promise<ListCalendlyEventTypesResponse>;
export declare function listCalendlyScheduledEvents(callingUserId: string, options?: {
    count?: number;
    status?: 'active' | 'canceled';
    sort?: string;
    pageToken?: string;
    min_start_time?: string;
    max_start_time?: string;
}): Promise<ListCalendlyScheduledEventsResponse>;
