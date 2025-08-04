import { createCalendarEvent as createEvent, } from './calendarSkills';
import { handleError } from '../../_utils/errorHandler';
export async function handleGetCalendarEvents(userId, entities, integrations) {
    try {
        let limit = 7;
        if (entities.limit) {
            if (typeof entities.limit === 'number') {
                limit = entities.limit;
            }
            else if (typeof entities.limit === 'string') {
                const parsedLimit = parseInt(entities.limit, 10);
                if (!isNaN(parsedLimit))
                    limit = parsedLimit;
            }
        }
        const date_range = entities.date_range;
        const event_type_filter = entities.event_type_filter;
        const time_query = entities.time_query;
        const query_type = entities.query_type;
        if (time_query)
            console.log(`[handleGetCalendarEvents] time_query found - ${time_query}`);
        if (query_type)
            console.log(`[handleGetCalendarEvents] query_type found - ${query_type}`);
        if (date_range)
            console.log(`[handleGetCalendarEvents] date_range found - ${date_range}.`);
        if (event_type_filter)
            console.log(`[handleGetCalendarEvents] event_type_filter found - ${event_type_filter}.`);
        const events = await listUpcomingEvents(userId, 10, integrations);
        if (!events || events.length === 0) {
            return "No upcoming calendar events found matching your criteria, or I couldn't access them.";
        }
        else {
            const eventList = events
                .map((event) => `- ${event.summary} (from ${new Date(event.startTime).toLocaleString()} to ${new Date(event.endTime).toLocaleString()})${event.location ? ` - Loc: ${event.location}` : ''}${event.htmlLink ? ` [Link: ${event.htmlLink}]` : ''}`)
                .join('\n');
            return `Upcoming calendar events:\n${eventList}`;
        }
    }
    catch (error) {
        return handleError(error, "Sorry, I couldn't fetch your calendar events due to an error.");
    }
}
export async function handleCreateCalendarEvent(userId, entities, integrations) {
    try {
        const { summary, start_time, end_time, description, location, attendees } = entities;
        const duration = entities.duration;
        if (!summary || typeof summary !== 'string') {
            return 'Event summary is required to create an event via NLU.';
        }
        else if (!start_time || typeof start_time !== 'string') {
            return 'Event start time is required to create an event via NLU.';
        }
        else if (!end_time && !duration) {
            return 'Event end time or duration is required to create an event via NLU.';
        }
        else {
            const eventDetails = {
                summary: summary,
                startTime: start_time,
                endTime: end_time,
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
            const response = await createEvent(userId, eventDetails, integrations);
            if (response.success) {
                return `Event created: ${response.message || 'Successfully created event.'} (ID: ${response.eventId || 'N/A'})${response.htmlLink ? ` Link: ${response.htmlLink}` : ''}`;
            }
            else {
                return `Failed to create calendar event via NLU. ${response.message || 'Please check your connection or try again.'}`;
            }
        }
    }
    catch (error) {
        return handleError(error, "Sorry, I couldn't create the calendar event due to an error.");
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsZW5kYXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjYWxlbmRhci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFDQSxPQUFPLEVBRUwsbUJBQW1CLElBQUksV0FBVyxHQUNuQyxNQUFNLGtCQUFrQixDQUFDO0FBQzFCLE9BQU8sRUFBRSxXQUFXLEVBQUUsTUFBTSwyQkFBMkIsQ0FBQztBQUV4RCxNQUFNLENBQUMsS0FBSyxVQUFVLHVCQUF1QixDQUMzQyxNQUFjLEVBQ2QsUUFBYSxFQUNiLFlBQWlCO0lBRWpCLElBQUksQ0FBQztRQUNILElBQUksS0FBSyxHQUFHLENBQUMsQ0FBQztRQUNkLElBQUksUUFBUSxDQUFDLEtBQUssRUFBRSxDQUFDO1lBQ25CLElBQUksT0FBTyxRQUFRLENBQUMsS0FBSyxLQUFLLFFBQVEsRUFBRSxDQUFDO2dCQUN2QyxLQUFLLEdBQUcsUUFBUSxDQUFDLEtBQUssQ0FBQztZQUN6QixDQUFDO2lCQUFNLElBQUksT0FBTyxRQUFRLENBQUMsS0FBSyxLQUFLLFFBQVEsRUFBRSxDQUFDO2dCQUM5QyxNQUFNLFdBQVcsR0FBRyxRQUFRLENBQUMsUUFBUSxDQUFDLEtBQUssRUFBRSxFQUFFLENBQUMsQ0FBQztnQkFDakQsSUFBSSxDQUFDLEtBQUssQ0FBQyxXQUFXLENBQUM7b0JBQUUsS0FBSyxHQUFHLFdBQVcsQ0FBQztZQUMvQyxDQUFDO1FBQ0gsQ0FBQztRQUNELE1BQU0sVUFBVSxHQUFHLFFBQVEsQ0FBQyxVQUFnQyxDQUFDO1FBQzdELE1BQU0saUJBQWlCLEdBQUcsUUFBUSxDQUFDLGlCQUF1QyxDQUFDO1FBQzNFLE1BQU0sVUFBVSxHQUFHLFFBQVEsQ0FBQyxVQUFnQyxDQUFDO1FBQzdELE1BQU0sVUFBVSxHQUFHLFFBQVEsQ0FBQyxVQUFnQyxDQUFDO1FBRTdELElBQUksVUFBVTtZQUNaLE9BQU8sQ0FBQyxHQUFHLENBQUMsZ0RBQWdELFVBQVUsRUFBRSxDQUFDLENBQUM7UUFDNUUsSUFBSSxVQUFVO1lB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LENBQUM7WUFDRixJQUFJLFFBQVEsRUFBRSxDQUFDO2dCQUNiLFlBQVksQ0FBQyxRQUFRLEdBQUcsUUFBUSxDQUFDO2dCQUNqQyxPQUFPLENBQUMsR0FBRyxDQUFDLGdEQUFnRCxRQUFRLEVBQUUsQ0FBQyxDQUFDO1lBQzFFLENBQUM7WUFDRCxNQUFNLFFBQVEsR0FBd0IsTUFBTSxXQUFXLENBQ3JELE1BQU0sRUFDTixZQUFZLEVBQ1osWUFBWSxDQUNiLENBQUM7WUFDRixJQUFJLFFBQVEsQ0FBQyxPQUFPLEVBQUUsQ0FBQztnQkFDckIsT0FBTyxrQkFBa0IsUUFBUSxDQUFDLE9BQU8sSUFBSSw2QkFBNkIsU0FBUyxRQUFRLENBQUMsT0FBTyxJQUFJLEtBQUssSUFBSSxRQUFRLENBQUMsUUFBUSxDQUFDLENBQUMsQ0FBQyxVQUFVLFFBQVEsQ0FBQyxRQUFRLEVBQUUsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUM7WUFDM0ssQ0FBQztpQkFBTSxDQUFDO2dCQUNOLE9BQU8sNENBQTRDLFFBQVEsQ0FBQyxPQUFPLElBQUksNENBQTRDLEVBQUUsQ0FBQztZQUN4SCxDQUFDO1FBQ0gsQ0FBQztJQUNILENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLE9BQU8sV0FBVyxDQUNoQixLQUFLLEVBQ0wsOERBQThELENBQy9ELENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IENhbGVuZGFyRXZlbnQsIENyZWF0ZUV2ZW50UmVzcG9uc2UgfSBmcm9tICcuLi8uLi90eXBlcyc7XG5pbXBvcnQge1xuICBsaXN0VXBjb21pbmdFdmVudHMgYXMgbGlzdEV2ZW50cyxcbiAgY3JlYXRlQ2FsZW5kYXJFdmVudCBhcyBjcmVhdGVFdmVudCxcbn0gZnJvbSAnLi9jYWxlbmRhclNraWxscyc7XG5pbXBvcnQgeyBoYW5kbGVFcnJvciB9IGZyb20gJy4uLy4uL191dGlscy9lcnJvckhhbmRsZXInO1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlR2V0Q2FsZW5kYXJFdmVudHMoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBlbnRpdGllczogYW55LFxuICBpbnRlZ3JhdGlvbnM6IGFueVxuKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgdHJ5IHtcbiAgICBsZXQgbGltaXQgPSA3O1xuICAgIGlmIChlbnRpdGllcy5saW1pdCkge1xuICAgICAgaWYgKHR5cGVvZiBlbnRpdGllcy5saW1pdCA9PT0gJ251bWJlcicpIHtcbiAgICAgICAgbGltaXQgPSBlbnRpdGllcy5saW1pdDtcbiAgICAgIH0gZWxzZSBpZiAodHlwZW9mIGVudGl0aWVzLmxpbWl0ID09PSAnc3RyaW5nJykge1xuICAgICAgICBjb25zdCBwYXJzZWRMaW1pdCA9IHBhcnNlSW50KGVudGl0aWVzLmxpbWl0LCAxMCk7XG4gICAgICAgIGlmICghaXNOYU4ocGFyc2VkTGltaXQpKSBsaW1pdCA9IHBhcnNlZExpbWl0O1xuICAgICAgfVxuICAgIH1cbiAgICBjb25zdCBkYXRlX3JhbmdlID0gZW50aXRpZXMuZGF0ZV9yYW5nZSBhcyBzdHJpbmcgfCB1bmRlZmluZWQ7XG4gICAgY29uc3QgZXZlbnRfdHlwZV9maWx0ZXIgPSBlbnRpdGllcy5ldmVudF90eXBlX2ZpbHRlciBhcyBzdHJpbmcgfCB1bmRlZmluZWQ7XG4gICAgY29uc3QgdGltZV9xdWVyeSA9IGVudGl0aWVzLnRpbWVfcXVlcnkgYXMgc3RyaW5nIHwgdW5kZWZpbmVkO1xuICAgIGNvbnN0IHF1ZXJ5X3R5cGUgPSBlbnRpdGllcy5xdWVyeV90eXBlIGFzIHN0cmluZyB8IHVuZGVmaW5lZDtcblxuICAgIGlmICh0aW1lX3F1ZXJ5KVxuICAgICAgY29uc29sZS5sb2coYFtoYW5kbGVHZXRDYWxlbmRhckV2ZW50c10gdGltZV9xdWVyeSBmb3VuZCAtICR7dGltZV9xdWVyeX1gKTtcbiAgICBpZiAocXVlcnlfdHlwZSlcbiAgICAgIGNvbnNvbGUubG9nKGBbaGFuZGxlR2V0Q2FsZW5kYXJFdmVudHNdIHF1ZXJ5X3R5cGUgZm91bmQgLSAke3F1ZXJ5X3R5cGV9YCk7XG4gICAgaWYgKGRhdGVfcmFuZ2UpXG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYFtoYW5kbGVHZXRDYWxlbmRhckV2ZW50c10gZGF0ZV9yYW5nZSBmb3VuZCAtICR7ZGF0ZV9yYW5nZX0uYFxuICAgICAgKTtcbiAgICBpZiAoZXZlbnRfdHlwZV9maWx0ZXIpXG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYFtoYW5kbGVHZXRDYWxlbmRhckV2ZW50c10gZXZlbnRfdHlwZV9maWx0ZXIgZm91bmQgLSAke2V2ZW50X3R5cGVfZmlsdGVyfS5gXG4gICAgICApO1xuXG4gICAgY29uc3QgZXZlbnRzID0gYXdhaXQgbGlzdFVwY29taW5nRXZlbnRzKHVzZXJJZCwgMTAsIGludGVncmF0aW9ucyk7XG4gICAgaWYgKCFldmVudHMgfHwgZXZlbnRzLmxlbmd0aCA9PT0gMCkge1xuICAgICAgcmV0dXJuIFwiTm8gdXBjb21pbmcgY2FsZW5kYXIgZXZlbnRzIGZvdW5kIG1hdGNoaW5nIHlvdXIgY3JpdGVyaWEsIG9yIEkgY291bGRuJ3QgYWNjZXNzIHRoZW0uXCI7XG4gICAgfSBlbHNlIHtcbiAgICAgIGNvbnN0IGV2ZW50TGlzdCA9IGV2ZW50c1xuICAgICAgICAubWFwKFxuICAgICAgICAgIChldmVudCkgPT5cbiAgICAgICAgICAgIGAtICR7ZXZlbnQuc3VtbWFyeX0gKGZyb20gJHtuZXcgRGF0ZShldmVudC5zdGFydFRpbWUpLnRvTG9jYWxlU3RyaW5nKCl9IHRvICR7bmV3IERhdGUoZXZlbnQuZW5kVGltZSkudG9Mb2NhbGVTdHJpbmcoKX0pJHtldmVudC5sb2NhdGlvbiA/IGAgLSBMb2M6ICR7ZXZlbnQubG9jYXRpb259YCA6ICcnfSR7ZXZlbnQuaHRtbExpbmsgPyBgIFtMaW5rOiAke2V2ZW50Lmh0bWxMaW5rfV1gIDogJyd9YFxuICAgICAgICApXG4gICAgICAgIC5qb2luKCdcXG4nKTtcbiAgICAgIHJldHVybiBgVXBjb21pbmcgY2FsZW5kYXIgZXZlbnRzOlxcbiR7ZXZlbnRMaXN0fWA7XG4gICAgfVxuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgcmV0dXJuIGhhbmRsZUVycm9yKFxuICAgICAgZXJyb3IsXG4gICAgICBcIlNvcnJ5LCBJIGNvdWxkbid0IGZldGNoIHlvdXIgY2FsZW5kYXIgZXZlbnRzIGR1ZSB0byBhbiBlcnJvci5cIlxuICAgICk7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZUNyZWF0ZUNhbGVuZGFyRXZlbnQoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBlbnRpdGllczogYW55LFxuICBpbnRlZ3JhdGlvbnM6IGFueVxuKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IHN1bW1hcnksIHN0YXJ0X3RpbWUsIGVuZF90aW1lLCBkZXNjcmlwdGlvbiwgbG9jYXRpb24sIGF0dGVuZGVlcyB9ID1cbiAgICAgIGVudGl0aWVzO1xuICAgIGNvbnN0IGR1cmF0aW9uID0gZW50aXRpZXMuZHVyYXRpb24gYXMgc3RyaW5nIHwgdW5kZWZpbmVkO1xuXG4gICAgaWYgKCFzdW1tYXJ5IHx8IHR5cGVvZiBzdW1tYXJ5ICE9PSAnc3RyaW5nJykge1xuICAgICAgcmV0dXJuICdFdmVudCBzdW1tYXJ5IGlzIHJlcXVpcmVkIHRvIGNyZWF0ZSBhbiBldmVudCB2aWEgTkxVLic7XG4gICAgfSBlbHNlIGlmICghc3RhcnRfdGltZSB8fCB0eXBlb2Ygc3RhcnRfdGltZSAhPT0gJ3N0cmluZycpIHtcbiAgICAgIHJldHVybiAnRXZlbnQgc3RhcnQgdGltZSBpcyByZXF1aXJlZCB0byBjcmVhdGUgYW4gZXZlbnQgdmlhIE5MVS4nO1xuICAgIH0gZWxzZSBpZiAoIWVuZF90aW1lICYmICFkdXJhdGlvbikge1xuICAgICAgcmV0dXJuICdFdmVudCBlbmQgdGltZSBvciBkdXJhdGlvbiBpcyByZXF1aXJlZCB0byBjcmVhdGUgYW4gZXZlbnQgdmlhIE5MVS4nO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zdCBldmVudERldGFpbHM6IFBhcnRpYWw8Q2FsZW5kYXJFdmVudCAmIHsgZHVyYXRpb24/OiBzdHJpbmcgfT4gPSB7XG4gICAgICAgIHN1bW1hcnk6IHN1bW1hcnkgYXMgc3RyaW5nLFxuICAgICAgICBzdGFydFRpbWU6IHN0YXJ0X3RpbWUgYXMgc3RyaW5nLFxuICAgICAgICBlbmRUaW1lOiBlbmRfdGltZSBhcyBzdHJpbmcgfCB1bmRlZmluZWQsXG4gICAgICAgIGRlc2NyaXB0aW9uOiB0eXBlb2YgZGVzY3JpcHRpb24gPT09ICdzdHJpbmcnID8gZGVzY3JpcHRpb24gOiB1bmRlZmluZWQsXG4gICAgICAgIGxvY2F0aW9uOiB0eXBlb2YgbG9jYXRpb24gPT09ICdzdHJpbmcnID8gbG9jYXRpb24gOiB1bmRlZmluZWQsXG4gICAgICAgIGF0dGVuZGVlczogQXJyYXkuaXNBcnJheShhdHRlbmRlZXMpXG4gICAgICAgICAgPyBhdHRlbmRlZXMuZmlsdGVyKChhdHQpID0+IHR5cGVvZiBhdHQgPT09ICdzdHJpbmcnKVxuICAgICAgICAgIDogdW5kZWZpbmVkLFxuICAgICAgfTtcbiAgICAgIGlmIChkdXJhdGlvbikge1xuICAgICAgICBldmVudERldGFpbHMuZHVyYXRpb24gPSBkdXJhdGlvbjtcbiAgICAgICAgY29uc29sZS5sb2coYFtoYW5kbGVDcmVhdGVDYWxlbmRhckV2ZW50XSBkdXJhdGlvbiBmb3VuZCAtICR7ZHVyYXRpb259YCk7XG4gICAgICB9XG4gICAgICBjb25zdCByZXNwb25zZTogQ3JlYXRlRXZlbnRSZXNwb25zZSA9IGF3YWl0IGNyZWF0ZUV2ZW50KFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGV2ZW50RGV0YWlscyxcbiAgICAgICAgaW50ZWdyYXRpb25zXG4gICAgICApO1xuICAgICAgaWYgKHJlc3BvbnNlLnN1Y2Nlc3MpIHtcbiAgICAgICAgcmV0dXJuIGBFdmVudCBjcmVhdGVkOiAke3Jlc3BvbnNlLm1lc3NhZ2UgfHwgJ1N1Y2Nlc3NmdWxseSBjcmVhdGVkIGV2ZW50Lid9IChJRDogJHtyZXNwb25zZS5ldmVudElkIHx8ICdOL0EnfSkke3Jlc3BvbnNlLmh0bWxMaW5rID8gYCBMaW5rOiAke3Jlc3BvbnNlLmh0bWxMaW5rfWAgOiAnJ31gO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgcmV0dXJuIGBGYWlsZWQgdG8gY3JlYXRlIGNhbGVuZGFyIGV2ZW50IHZpYSBOTFUuICR7cmVzcG9uc2UubWVzc2FnZSB8fCAnUGxlYXNlIGNoZWNrIHlvdXIgY29ubmVjdGlvbiBvciB0cnkgYWdhaW4uJ31gO1xuICAgICAgfVxuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIHJldHVybiBoYW5kbGVFcnJvcihcbiAgICAgIGVycm9yLFxuICAgICAgXCJTb3JyeSwgSSBjb3VsZG4ndCBjcmVhdGUgdGhlIGNhbGVuZGFyIGV2ZW50IGR1ZSB0byBhbiBlcnJvci5cIlxuICAgICk7XG4gIH1cbn1cbiJdfQ==