/**
 * Represents a summary of a calendar event.
 * This structure will need to be defined based on the actual data available
 * from the calendar API and the needs of the Proactive Meeting Prep Assistant.
 */
export interface CalendarEventSummary {
    id: string;
    title: string;
    startTime: Date;
    endTime: Date;
    description?: string;
    attendees?: string[];
    location?: string;
    organizer?: string;
}
/**
 * Optional date hints to narrow down the search for a calendar event.
 * - specificDate: Looks for events on this particular day.
 * - startDate/endDate: Defines a window to search for events.
 * If multiple hints are provided, the narrowest possible range should be prioritized.
 * For example, if specificDate is given, startDate and endDate might be ignored or used as validation.
 */
export interface DateHints {
    specificDate?: Date;
    startDate?: Date;
    endDate?: Date;
}
/**
 * Finds a calendar event based on a natural language reference and optional date hints.
 *
 * @param userId The ID of the user whose calendar is to be searched.
 * @param meeting_reference A natural language string describing the meeting
 *                          (e.g., "my sync up tomorrow", "budget review next week").
 * @param date_hints Optional hints to narrow down the date range for the search.
 * @returns A Promise that resolves to a CalendarEventSummary if a suitable event
 *          is found, or undefined otherwise.
 */
export declare function findCalendarEventByFuzzyReference(userId: string, meeting_reference: string, date_hints?: DateHints): Promise<CalendarEventSummary | undefined>;
