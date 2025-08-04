import {
  ListGoogleMeetEventsResponse,
  GetGoogleMeetEventDetailsResponse,
} from '../../types';
import {
  listUpcomingGoogleMeetEvents as listEvents,
  getGoogleMeetEventDetails as getDetails,
} from './calendarSkills';
import { handleError } from '../../_utils/errorHandler';

export async function handleListGoogleMeetEvents(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const limit =
      entities?.limit && typeof entities.limit === 'number'
        ? entities.limit
        : 5;
    const response: ListGoogleMeetEventsResponse = await listEvents(
      userId,
      limit
    );
    if (response.ok && response.events && response.events.length > 0) {
      let output = 'Your Upcoming Google Meet Events (via NLU):\n';
      for (const event of response.events) {
        const meetLink = event.conferenceData?.entryPoints?.find(
          (ep) =>
            ep.entryPointType === 'video' &&
            ep.uri?.startsWith('https://meet.google.com/')
        )?.uri;
        output += `- ${event.summary} (Starts: ${new Date(event.startTime).toLocaleString()})${meetLink ? ` - Link: ${meetLink}` : ' (No direct Meet link found, check calendar event details)'}\n`;
      }
      return output;
    } else if (response.ok) {
      return 'No upcoming Google Meet events found (via NLU).';
    } else {
      return `Error fetching Google Meet events (via NLU): ${response.error || 'Unknown error'}`;
    }
  } catch (error: any) {
    return handleError(
      error,
      'Sorry, an unexpected error occurred while fetching your Google Meet events (NLU path).'
    );
  }
}

export async function handleGetGoogleMeetEventDetails(
  userId: string,
  entities: any
): Promise<string> {
  try {
    const { event_id } = entities;
    if (!event_id || typeof event_id !== 'string') {
      return 'Google Calendar Event ID is required to get details via NLU.';
    } else {
      const response: GetGoogleMeetEventDetailsResponse = await getDetails(
        userId,
        event_id
      );
      if (response.ok && response.event) {
        const ev = response.event;
        let output = `Event (via NLU): ${ev.summary}\nStart: ${new Date(ev.startTime).toLocaleString()}\nEnd: ${new Date(ev.endTime).toLocaleString()}`;
        const meetLink = ev.conferenceData?.entryPoints?.find(
          (ep) =>
            ep.entryPointType === 'video' &&
            ep.uri?.startsWith('https://meet.google.com/')
        )?.uri;
        if (meetLink) output += `\nMeet Link: ${meetLink}`;
        else if (ev.conferenceData?.conferenceSolution?.name)
          output += `\nConference: ${ev.conferenceData.conferenceSolution.name} (Details might be in description or calendar entry)`;
        else
          output +=
            '\n(No Google Meet link or explicit conference data found for this event)';
        if (ev.htmlLink) output += `\nCalendar Link: ${ev.htmlLink}`;
        if (ev.description) output += `\nDescription: ${ev.description}`;
        return output;
      } else {
        return `Error fetching Google Meet event details (via NLU): ${response.error || `Event with ID ${event_id} not found or an unknown error occurred.`}`;
      }
    }
  } catch (error: any) {
    return handleError(
      error,
      `Sorry, an unexpected error occurred while fetching details for event ${entities.event_id} (NLU path).`
    );
  }
}
