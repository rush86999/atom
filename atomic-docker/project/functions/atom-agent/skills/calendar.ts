import { CalendarEvent, CreateEventResponse } from '../../types';
import {
  listUpcomingEvents as listEvents,
  createCalendarEvent as createEvent,
} from './calendarSkills';
import { handleError } from '../../_utils/errorHandler';

export async function handleGetCalendarEvents(
  userId: string,
  entities: any,
  integrations: any
): Promise<string> {
  try {
    let limit = 7;
    if (entities.limit) {
      if (typeof entities.limit === 'number') {
        limit = entities.limit;
      } else if (typeof entities.limit === 'string') {
        const parsedLimit = parseInt(entities.limit, 10);
        if (!isNaN(parsedLimit)) limit = parsedLimit;
      }
    }
    const date_range = entities.date_range as string | undefined;
    const event_type_filter = entities.event_type_filter as string | undefined;
    const time_query = entities.time_query as string | undefined;
    const query_type = entities.query_type as string | undefined;

    if (time_query)
      console.log(`[handleGetCalendarEvents] time_query found - ${time_query}`);
    if (query_type)
      console.log(`[handleGetCalendarEvents] query_type found - ${query_type}`);
    if (date_range)
      console.log(
        `[handleGetCalendarEvents] date_range found - ${date_range}.`
      );
    if (event_type_filter)
      console.log(
        `[handleGetCalendarEvents] event_type_filter found - ${event_type_filter}.`
      );

    const events = await listUpcomingEvents(userId, 10, integrations);
    if (!events || events.length === 0) {
      return "No upcoming calendar events found matching your criteria, or I couldn't access them.";
    } else {
      const eventList = events
        .map(
          (event) =>
            `- ${event.summary} (from ${new Date(event.startTime).toLocaleString()} to ${new Date(event.endTime).toLocaleString()})${event.location ? ` - Loc: ${event.location}` : ''}${event.htmlLink ? ` [Link: ${event.htmlLink}]` : ''}`
        )
        .join('\n');
      return `Upcoming calendar events:\n${eventList}`;
    }
  } catch (error: any) {
    return handleError(
      error,
      "Sorry, I couldn't fetch your calendar events due to an error."
    );
  }
}

export async function handleCreateCalendarEvent(
  userId: string,
  entities: any,
  integrations: any
): Promise<string> {
  try {
    const { summary, start_time, end_time, description, location, attendees } =
      entities;
    const duration = entities.duration as string | undefined;

    if (!summary || typeof summary !== 'string') {
      return 'Event summary is required to create an event via NLU.';
    } else if (!start_time || typeof start_time !== 'string') {
      return 'Event start time is required to create an event via NLU.';
    } else if (!end_time && !duration) {
      return 'Event end time or duration is required to create an event via NLU.';
    } else {
      const eventDetails: Partial<CalendarEvent & { duration?: string }> = {
        summary: summary as string,
        startTime: start_time as string,
        endTime: end_time as string | undefined,
        description: typeof description === 'string' ? description : undefined,
        location: typeof location === 'string' ? location : undefined,
        attendees: Array.isArray(attendees)
          ? attendees.filter((att) => typeof att === 'string')
          : undefined,
      };
      if (duration) {
        eventDetails.duration = duration;
        console.log(`[handleCreateCalendarEvent] duration found - ${duration}`);
      }
      const response: CreateEventResponse = await createEvent(
        userId,
        eventDetails,
        integrations
      );
      if (response.success) {
        return `Event created: ${response.message || 'Successfully created event.'} (ID: ${response.eventId || 'N/A'})${response.htmlLink ? ` Link: ${response.htmlLink}` : ''}`;
      } else {
        return `Failed to create calendar event via NLU. ${response.message || 'Please check your connection or try again.'}`;
      }
    }
  } catch (error: any) {
    return handleError(
      error,
      "Sorry, I couldn't create the calendar event due to an error."
    );
  }
}
