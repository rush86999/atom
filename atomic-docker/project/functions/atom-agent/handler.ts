import { listUpcomingEvents, createCalendarEvent } from './skills/calendarSkills';
import { listRecentEmails, readEmail, sendEmail, EmailDetails } from './skills/emailSkills';
import { searchWeb } from './skills/webResearchSkills';
import { triggerZap, ZapData } from './skills/zapierSkills';
import {
  CalendarEvent, CreateEventResponse,
  Email, ReadEmailResponse, SendEmailResponse,
  SearchResult,
  ZapTriggerResponse,
  HubSpotContactProperties,
  CreateHubSpotContactResponse,
  HubSpotContact,
  // Calendly Types - Assuming they are exported from types.ts or directly from calendlySkills
  ListCalendlyEventTypesResponse,
  ListCalendlyScheduledEventsResponse,
  CalendlyEventType,
  CalendlyScheduledEvent,
  // Zoom Types
  ListZoomMeetingsResponse,
  GetZoomMeetingDetailsResponse,
  ZoomMeeting,
  // Google Meet types are already in CalendarEvent and new response types
  ListGoogleMeetEventsResponse,
  GetGoogleMeetEventDetailsResponse,
  // MS Teams Types
  ListMSTeamsMeetingsResponse,
  GetMSTeamsMeetingDetailsResponse,
  MSGraphEvent
} from '../types';
import { createHubSpotContact } from './skills/hubspotSkills';
import { sendSlackMessage } from './skills/slackSkills';
import { listCalendlyEventTypes, listCalendlyScheduledEvents } from './skills/calendlySkills';
import { listZoomMeetings, getZoomMeetingDetails } from './skills/zoomSkills';
import { listUpcomingGoogleMeetEvents, getGoogleMeetEventDetails } from './skills/calendarSkills';
import { listMicrosoftTeamsMeetings, getMicrosoftTeamsMeetingDetails } from './skills/msTeamsSkills'; // Added
import { ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID, ATOM_HUBSPOT_PORTAL_ID } from '../_libs/constants';


export async function handleMessage(message: string): Promise<string> {
  const lowerCaseMessage = message.toLowerCase();
  const userId = "mock_user_id_from_handler"; // Placeholder for actual user ID retrieval

  if (lowerCaseMessage.startsWith('list events')) {
    try {
      // Optional: parse limit from message, e.g., "list events 5"
      const parts = message.split(' ');
      const limit = parts.length > 2 && !isNaN(parseInt(parts[2])) ? parseInt(parts[2]) : 10;

      // TODO: Refine error propagation from skills.
      // listUpcomingEvents should ideally return a more explicit error object
      // (e.g., { success: false, message: "Token error", events: [] })
      // to distinguish "no events" from "an error occurred".
      // For now, an empty array implies either no events or an auth/API issue.
      const events: CalendarEvent[] = await listUpcomingEvents(userId, limit);
      if (events.length === 0) {
        // Given current mock token setup, this often means tokens are missing or invalid.
        return "Could not retrieve calendar events. Please ensure your Google Calendar is connected in settings and try again, or there might be no upcoming events.";
      }
      const eventList = events.map(event =>
        `- ${event.summary} (${event.startTime} - ${event.endTime})${event.description ? ': ' + event.description : ''}${event.htmlLink ? ` [Link: ${event.htmlLink}]` : ''}`
      ).join('\n');
      return `Upcoming events:\n${eventList}`;
    } catch (error) {
      console.error('Error listing events:', error);
      return "Sorry, I couldn't fetch the upcoming events.";
    }
  } else if (lowerCaseMessage.startsWith('create event')) {
    try {
      // This is a very basic parsing. A real agent would use NLP to extract details.
      // Example: "create event Meeting with John from 2024-03-20T10:00 to 2024-03-20T11:00 about Project Alpha"
      // For now, we'll expect a JSON-like structure or rely on predefined details for simplicity.
      // Let's assume the message format "create event {"summary":"Test Event","startTime":"2024-03-20T14:00:00Z","endTime":"2024-03-20T15:00:00Z"}"
      const eventDetailsJson = message.substring(message.indexOf('{')).trim();
      let eventDetails: Partial<CalendarEvent>;

      if (eventDetailsJson) {
        try {
            eventDetails = JSON.parse(eventDetailsJson);
        } catch (e) {
            return "Invalid event details format. Please provide JSON for event details. Example: create event {\"summary\":\"My Event\",\"startTime\":\"YYYY-MM-DDTHH:mm:ssZ\",\"endTime\":\"YYYY-MM-DDTHH:mm:ssZ\"}";
        }
      } else {
        // Fallback to a default event if no details are provided
        eventDetails = {
            summary: 'Default Event',
            startTime: new Date().toISOString(),
            endTime: new Date(Date.now() + 60 * 60 * 1000).toISOString(), // 1 hour from now
            description: 'Created by Atom Agent (default)'
        };
      }

      const response: CreateEventResponse = await createCalendarEvent(userId, eventDetails);
      if (response.success) {
        return `Event created: ${response.message || 'Successfully created event.'} (ID: ${response.eventId || 'N/A'})${response.htmlLink ? ` Link: ${response.htmlLink}` : ''}`;
      } else {
        return `Failed to create calendar event. ${response.message || 'Please check your connection or try again.'}`;
      }
    } catch (error) {
      console.error('Error creating event:', error);
      return "Sorry, I couldn't create the calendar event.";
    }
  } else if (lowerCaseMessage.startsWith('list emails')) {
    try {
      const parts = message.split(' ');
      const limit = parts.length > 2 && !isNaN(parseInt(parts[2])) ? parseInt(parts[2]) : 10;

      const emails: Email[] = await listRecentEmails(limit);
      if (emails.length === 0) {
        return "No recent emails found.";
      }
      const emailList = emails.map(email =>
        `- (${email.read ? 'read' : 'unread'}) From: ${email.sender}, Subject: ${email.subject} (ID: ${email.id})`
      ).join('\n');
      return `Recent emails:\n${emailList}`;
    } catch (error) {
      console.error('Error listing emails:', error);
      return "Sorry, I couldn't fetch recent emails.";
    }
  } else if (lowerCaseMessage.startsWith('read email')) {
    try {
      const parts = message.split(' ');
      if (parts.length < 3) {
        return "Please provide an email ID to read. Usage: read email <emailId>";
      }
      const emailId = parts[2];
      const response: ReadEmailResponse = await readEmail(emailId);

      if (response.success && response.email) {
        const email = response.email;
        return `Email (ID: ${email.id}):\nFrom: ${email.sender}\nTo: ${email.recipient}\nSubject: ${email.subject}\nDate: ${email.timestamp}\n\n${email.body}`;
      } else {
        return response.message || "Could not read email.";
      }
    } catch (error) {
      console.error('Error reading email:', error);
      return "Sorry, I couldn't read the specified email.";
    }
  } else if (lowerCaseMessage.startsWith('send email')) {
    try {
      // Example: send email {"to":"test@example.com","subject":"Hello","body":"This is a test."}
      const emailDetailsJson = message.substring(message.indexOf('{')).trim();
      let emailDetails: EmailDetails;

      if (emailDetailsJson) {
        try {
          emailDetails = JSON.parse(emailDetailsJson);
        } catch (e) {
          return "Invalid email details format. Please provide JSON. Example: send email {\"to\":\"recipient@example.com\",\"subject\":\"Your Subject\",\"body\":\"Email content...\"}";
        }
      } else {
        return "Please provide email details in JSON format after 'send email'.";
      }

      const response: SendEmailResponse = await sendEmail(emailDetails);
      if (response.success) {
        return `Email sent: ${response.message} (ID: ${response.emailId})`;
      } else {
        return `Failed to send email: ${response.message}`;
      }
    } catch (error) {
      console.error('Error sending email:', error);
      return "Sorry, I couldn't send the email.";
    }
  } else if (lowerCaseMessage.startsWith('search web')) {
    try {
      const query = message.substring('search web'.length).trim();
      if (!query) {
        return "Please provide a search query. Usage: search web <your query>";
      }

      const results: SearchResult[] = await searchWeb(query);
      if (results.length === 0) {
        return `No web results found for "${query}".`;
      }
      const resultList = results.map(result =>
        `- ${result.title}\n  Link: ${result.link}\n  Snippet: ${result.snippet}`
      ).join('\n\n');
      return `Web search results for "${query}":\n\n${resultList}`;
    } catch (error) {
      console.error('Error performing web search:', error);
      return "Sorry, I couldn't perform the web search.";
    }
  } else if (lowerCaseMessage.startsWith('trigger zap')) {
    try {
      // Example: trigger zap MyZapName with data {"key":"value"}
      const withDataIndex = lowerCaseMessage.indexOf(' with data ');
      let zapName: string;
      let jsonData: string | undefined;

      if (withDataIndex === -1) {
        // No data provided
        zapName = message.substring('trigger zap'.length).trim();
      } else {
        zapName = message.substring('trigger zap'.length, withDataIndex).trim();
        jsonData = message.substring(withDataIndex + ' with data '.length).trim();
      }

      if (!zapName) {
        return "Please provide a Zap name. Usage: trigger zap <ZapName> [with data {JSON_DATA}]";
      }

      let data: ZapData = {};
      if (jsonData) {
        try {
          data = JSON.parse(jsonData);
        } catch (e) {
          return "Invalid JSON data format. Please provide valid JSON for the Zap data.";
        }
      }

      const response: ZapTriggerResponse = await triggerZap(zapName, data);
      if (response.success) {
        return `Zap triggered: ${response.message} (Run ID: ${response.runId})`;
      } else {
        return `Failed to trigger Zap: ${response.message}`;
      }
    } catch (error) {
      console.error('Error triggering Zap:', error);
      return "Sorry, I couldn't trigger the Zap.";
    }
  } else if (lowerCaseMessage.startsWith('create hubspot contact')) {
    const userId = "mock_user_id_from_handler"; // Consistent with other handlers
    let userMessage: string;

    try {
      const jsonDetailsString = message.substring(message.toLowerCase().indexOf('{')).trim();
      if (!jsonDetailsString) {
        return "Please provide contact details in JSON format. Usage: create hubspot contact {\"email\":\"test@example.com\",\"firstname\":\"Test\"}";
      }

      let contactDetails: HubSpotContactProperties;
      try {
        contactDetails = JSON.parse(jsonDetailsString);
      } catch (e: any) {
        console.error('Error parsing HubSpot contact JSON:', e.message);
        return `Invalid JSON format for contact details: ${e.message}. Please ensure you provide valid JSON.`;
      }

      if (!contactDetails.email) { // Basic validation
          return "The 'email' property is required in the JSON details to create a HubSpot contact.";
      }

      const hubspotResponse: CreateHubSpotContactResponse = await createHubSpotContact(userId, contactDetails);

      if (hubspotResponse.success && hubspotResponse.contactId && hubspotResponse.hubSpotContact) {
        const contact = hubspotResponse.hubSpotContact;
        userMessage = `HubSpot contact created successfully! ID: ${hubspotResponse.contactId}. Name: ${contact.properties.firstname || ''} ${contact.properties.lastname || ''}. Email: ${contact.properties.email}.`;

        if (ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID) {
          let slackMessage = `🎉 New HubSpot Contact Created by Atom Agent! 🎉\n`;
          slackMessage += `ID: ${hubspotResponse.contactId}\n`;
          slackMessage += `Name: ${contact.properties.firstname || '(not set)'} ${contact.properties.lastname || '(not set)'}\n`;
          slackMessage += `Email: ${contact.properties.email || '(not set)'}\n`;
          if (contact.properties.company) {
            slackMessage += `Company: ${contact.properties.company}\n`;
          }
          if (ATOM_HUBSPOT_PORTAL_ID) {
            slackMessage += `View in HubSpot: https://app.hubspot.com/contacts/${ATOM_HUBSPOT_PORTAL_ID}/contact/${hubspotResponse.contactId}\n`;
          }
          slackMessage += `Created by User: ${userId}`; // Or a more user-friendly name if available

          try {
            const slackResponse = await sendSlackMessage(userId, ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID, slackMessage);
            if (!slackResponse.ok) {
              console.error('Failed to send Slack notification for HubSpot contact creation:', slackResponse.error);
              // Do not alter userMessage, primary action (HubSpot creation) was successful.
            } else {
              console.log('Slack notification sent for new HubSpot contact:', hubspotResponse.contactId);
            }
          } catch (slackError: any) {
            console.error('Error sending Slack notification:', slackError.message);
          }
        } else {
          console.log('Slack notification channel ID for HubSpot not configured. Skipping notification.');
        }
      } else {
        userMessage = `Failed to create HubSpot contact: ${hubspotResponse.message || 'An unknown error occurred.'}`;
      }
      return userMessage;
    } catch (error: any) {
      console.error('Error in "create hubspot contact" handler:', error.message);
      return `An unexpected error occurred while creating the HubSpot contact: ${error.message}`;
    }
  } else if (lowerCaseMessage.startsWith('slack my agenda')) {
    const userId = "mock_user_id_from_handler"; // IMPORTANT: This is assumed to be the Slack User ID for DM purposes.
    const limit = 5; // Default limit for agenda items.

    try {
      const events: CalendarEvent[] = await listUpcomingEvents(userId, limit);

      if (!events || events.length === 0) {
        const noEventsMessage = "You have no upcoming events on your calendar for the near future, or I couldn't access them.";
        // Attempt to send this to Slack DM
        try {
            await sendSlackMessage(userId, userId, noEventsMessage); // Send to user's own DM
            return "I've checked your calendar. It seems there are no upcoming events. I've sent a note to your Slack DM too.";
        } catch (dmError: any) {
            console.error('Failed to send "no events" DM to user:', dmError.message);
            // If DM fails, still inform the user through the primary channel if possible
            return "I've checked your calendar. It seems there are no upcoming events. I tried to send a note to your Slack DM, but it failed.";
        }
      }

      let formattedAgenda = "🗓️ Your Upcoming Events:\n";
      for (const event of events) {
        // Basic date/time formatting. For production, consider user's timezone and locale.
        const startTime = new Date(event.startTime).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short'});
        const endTime = new Date(event.endTime).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short'});

        formattedAgenda += `- ${event.summary} (from ${startTime} to ${endTime})`;
        if (event.location) formattedAgenda += ` - Location: ${event.location}`;
        if (event.htmlLink) formattedAgenda += ` [View: ${event.htmlLink}]`;
        formattedAgenda += "\n";
      }

      const slackResponse = await sendSlackMessage(userId, userId, formattedAgenda); // Send to user's own DM (userId as channel for DMs)
      if (slackResponse.ok) {
        return "I've sent your agenda to your Slack DM!";
      } else {
        console.error(`Failed to send Slack DM for agenda: ${slackResponse.error}`);
        return `Sorry, I couldn't send your agenda to Slack. Error: ${slackResponse.error}`;
      }
    } catch (error: any) {
      console.error('Error in "slack my agenda" command:', error.message);
      // Attempt to notify user in Slack about the failure too, if possible
      try {
        await sendSlackMessage(userId, userId, "Sorry, I encountered an error while trying to fetch your agenda. Please check the application logs.");
      } catch (dmError: any) {
        console.error('Failed to send error DM to user:', dmError.message);
      }
      return "Sorry, I encountered an error while fetching your agenda. I've attempted to send a notification to your Slack DM about this.";
    }
  } else if (lowerCaseMessage.startsWith('list calendly event types')) {
    const userId = "mock_user_id_from_handler";
    try {
      const response: ListCalendlyEventTypesResponse = await listCalendlyEventTypes(userId);
      if (response.ok && response.collection && response.collection.length > 0) {
        let output = "Your Calendly Event Types:\n";
        for (const et of response.collection) {
          output += `- ${et.name} (${et.duration} mins) - Active: ${et.active} - URL: ${et.scheduling_url}\n`;
        }
        if (response.pagination?.next_page_token) {
          output += `More event types available. Use next page token: ${response.pagination.next_page_token}\n`;
        }
        return output;
      } else if (response.ok) {
        return "No active Calendly event types found.";
      } else {
        return `Error fetching Calendly event types: ${response.error || 'Unknown error'}`;
      }
    } catch (error: any) {
      console.error('Error in "list calendly event types" command:', error.message);
      return "Sorry, an unexpected error occurred while fetching your Calendly event types.";
    }
  } else if (lowerCaseMessage.startsWith('list calendly bookings')) {
    const userId = "mock_user_id_from_handler";
    // Basic options parsing: "list calendly bookings active 5"
    const parts = lowerCaseMessage.split(' '); // parts[0]=list, parts[1]=calendly, parts[2]=bookings
    const status = parts[3] === 'active' || parts[3] === 'canceled' ? parts[3] as ('active' | 'canceled') : 'active';
    const count = parts.length > 4 && !isNaN(parseInt(parts[4])) ? parseInt(parts[4]) : 10;

    // Example for more advanced parsing if needed:
    // let pageToken: string | undefined;
    // const tokenIndex = parts.indexOf('token');
    // if (tokenIndex !== -1 && parts.length > tokenIndex + 1) {
    //   pageToken = parts[tokenIndex + 1];
    // }
    // const options = { count, status, sort: 'start_time:asc', pageToken };

    const options = { count, status, sort: 'start_time:asc' }; // Default sort to ascending start time

    try {
      const response: ListCalendlyScheduledEventsResponse = await listCalendlyScheduledEvents(userId, options);
      if (response.ok && response.collection && response.collection.length > 0) {
        let output = `Your Calendly Bookings (${status}):\n`;
        for (const se of response.collection) {
          output += `- ${se.name} (Starts: ${new Date(se.start_time).toLocaleString()}, Ends: ${new Date(se.end_time).toLocaleString()}) - Status: ${se.status}\n`;
        }
        if (response.pagination?.next_page_token) {
          output += `More bookings available. Use next page token: ${response.pagination.next_page_token}\n`;
        }
        return output;
      } else if (response.ok) {
        return `No ${status} scheduled Calendly bookings found.`;
      } else {
        return `Error fetching Calendly bookings: ${response.error || 'Unknown error'}`;
      }
    } catch (error: any) {
      console.error('Error in "list calendly bookings" command:', error.message);
      return "Sorry, an unexpected error occurred while fetching your Calendly bookings.";
    }
  } else if (lowerCaseMessage.startsWith('list zoom meetings')) {
    const userIdForZoom = "me"; // For Server-to-Server OAuth, 'me' refers to the user under whom the app was created.
    const parts = lowerCaseMessage.split(' '); // "list zoom meetings type page_size next_page_token"
                                          // parts[0]=list, parts[1]=zoom, parts[2]=meetings

    let type: 'live' | 'upcoming' | 'scheduled' | 'upcoming_meetings' | 'previous_meetings' = 'upcoming';
    if (parts.length > 3 && ['live', 'upcoming', 'scheduled', 'upcoming_meetings', 'previous_meetings'].includes(parts[3].toLowerCase())) {
        type = parts[3].toLowerCase() as typeof type;
    }

    const page_size = parts.length > 4 && !isNaN(parseInt(parts[4])) ? parseInt(parts[4]) : 30;
    const next_page_token = parts.length > 5 ? parts[5] : undefined;
    const options = { type, page_size, next_page_token };

    try {
      const response: ListZoomMeetingsResponse = await listZoomMeetings(userIdForZoom, options);
      if (response.ok && response.meetings && response.meetings.length > 0) {
        let output = `Your Zoom Meetings (${type}):\n`;
        for (const meeting of response.meetings) {
          output += `- ${meeting.topic} (ID: ${meeting.id}) - Start: ${meeting.start_time ? new Date(meeting.start_time).toLocaleString() : 'N/A'} - Join: ${meeting.join_url || 'N/A'}\n`;
        }
        if (response.next_page_token) {
          output += `More meetings available. For next page, use token: ${response.next_page_token}\n`;
        }
        return output;
      } else if (response.ok) {
        return "No Zoom meetings found matching your criteria.";
      } else {
        return `Error fetching Zoom meetings: ${response.error || 'Unknown error'}`;
      }
    } catch (error: any) {
      console.error('Error in "list zoom meetings" command:', error.message);
      return "Sorry, an unexpected error occurred while fetching your Zoom meetings.";
    }
  } else if (lowerCaseMessage.startsWith('get zoom meeting')) {
    const parts = lowerCaseMessage.split(' '); // "get zoom meeting <meetingId>"
    if (parts.length < 4) {
      return "Please provide a Zoom Meeting ID. Usage: get zoom meeting <meetingId>";
    }
    const meetingId = parts[3];

    try {
      const response: GetZoomMeetingDetailsResponse = await getZoomMeetingDetails(meetingId);
      if (response.ok && response.meeting) {
        const m = response.meeting;
        return `Zoom Meeting Details:\nTopic: ${m.topic}\nID: ${m.id}\nStart Time: ${m.start_time ? new Date(m.start_time).toLocaleString() : 'N/A'}\nDuration: ${m.duration || 'N/A'} mins\nJoin URL: ${m.join_url || 'N/A'}\nAgenda: ${m.agenda || 'N/A'}`;
      } else { // response.ok might be true if meeting not found by ID but API call itself was fine (e.g. skill handles 404)
        return `Error fetching Zoom meeting details: ${response.error || `Meeting with ID ${meetingId} not found or an unknown error occurred.`}`;
      }
    } catch (error: any) {
      console.error(`Error in "get zoom meeting ${meetingId}" command:`, error.message);
      return `Sorry, an unexpected error occurred while fetching details for Zoom meeting ${meetingId}.`;
    }
  } else if (lowerCaseMessage.startsWith('list google meet events')) {
    const userId = "mock_user_id_from_handler";
    const parts = lowerCaseMessage.split(' '); // "list google meet events [limit]"
                                          // parts[0]=list, parts[1]=google, parts[2]=meet, parts[3]=events
    const limit = parts.length > 4 && !isNaN(parseInt(parts[4])) ? parseInt(parts[4]) : 5;

    try {
      const response: ListGoogleMeetEventsResponse = await listUpcomingGoogleMeetEvents(userId, limit);
      if (response.ok && response.events && response.events.length > 0) {
        let output = "Your Upcoming Google Meet Events:\n";
        for (const event of response.events) {
          const meetLink = event.conferenceData?.entryPoints?.find(ep => ep.entryPointType === 'video' && ep.uri?.startsWith('https://meet.google.com/'))?.uri;
          output += `- ${event.summary} (Starts: ${new Date(event.startTime).toLocaleString()})${meetLink ? ` - Link: ${meetLink}` : ' (No direct Meet link found, check calendar event details)'}\n`;
        }
        return output;
      } else if (response.ok) {
        return "No upcoming Google Meet events found.";
      } else {
        return `Error fetching Google Meet events: ${response.error || 'Unknown error'}`;
      }
    } catch (error: any) {
      console.error('Error in "list google meet events" command:', error.message);
      return "Sorry, an unexpected error occurred while fetching your Google Meet events.";
    }
  } else if (lowerCaseMessage.startsWith('get google meet event')) {
    const userId = "mock_user_id_from_handler";
    const parts = lowerCaseMessage.split(' '); // "get google meet event <eventId>"
    if (parts.length < 5) { // get google meet event <ID> -> 5 parts
      return "Please provide a Google Calendar Event ID. Usage: get google meet event <eventId>";
    }
    const eventId = parts[4];

    try {
      const response: GetGoogleMeetEventDetailsResponse = await getGoogleMeetEventDetails(userId, eventId);
      if (response.ok && response.event) {
        const ev = response.event;
        let output = `Event: ${ev.summary}\nStart: ${new Date(ev.startTime).toLocaleString()}\nEnd: ${new Date(ev.endTime).toLocaleString()}`;
        const meetLink = ev.conferenceData?.entryPoints?.find(ep => ep.entryPointType === 'video' && ep.uri?.startsWith('https://meet.google.com/'))?.uri;

        if (meetLink) {
          output += `\nMeet Link: ${meetLink}`;
        } else if (ev.conferenceData?.conferenceSolution?.name) {
          output += `\nConference: ${ev.conferenceData.conferenceSolution.name} (Details might be in description or calendar entry)`;
        } else {
            output += "\n(No Google Meet link or explicit conference data found for this event)";
        }
        if (ev.htmlLink) output += `\nCalendar Link: ${ev.htmlLink}`;
        if (ev.description) output += `\nDescription: ${ev.description}`;

        return output;
      } else {
        return `Error fetching Google Meet event details: ${response.error || `Event with ID ${eventId} not found or an unknown error occurred.`}`;
      }
    } catch (error: any) {
      console.error(`Error in "get google meet event ${eventId}" command:`, error.message);
      return `Sorry, an unexpected error occurred while fetching details for event ${eventId}.`;
    }
  } else if (lowerCaseMessage.startsWith('list teams meetings')) {
    const userPrincipalNameOrId = "me"; // Default for app-only permissions or replace with actual UPN/ID if user-delegated
    const parts = lowerCaseMessage.split(' '); // "list teams meetings [limit] [nextLink]"
                                          // parts[0]=list, parts[1]=teams, parts[2]=meetings
    const limit = parts.length > 3 && !isNaN(parseInt(parts[3])) ? parseInt(parts[3]) : 10;
    const nextLink = parts.length > 4 ? parts[4] : undefined; // If nextLink is provided, it contains all other params

    const options = { limit, nextLink, filterForTeams: true };

    try {
      const response: ListMSTeamsMeetingsResponse = await listMicrosoftTeamsMeetings(userPrincipalNameOrId, options);
      if (response.ok && response.events && response.events.length > 0) {
        let output = "Your Microsoft Teams Meetings:\n";
        for (const event of response.events) {
          output += `- ${event.subject} (ID: ${event.id}) - Start: ${event.start?.dateTime ? new Date(event.start.dateTime).toLocaleString() : 'N/A'} - Join: ${event.onlineMeeting?.joinUrl || 'N/A'}\n`;
        }
        if (response.nextLink) {
          // The nextLink is a full URL, so the user would just use it directly if they could.
          // For a chat interface, we might need to store this and allow a "next page" command.
          // For now, just inform them and show the link (which they can't directly use in a chat).
          output += `More meetings available. Next page link (for API use): ${response.nextLink}\nTo get next page, you could say: list teams meetings ${limit} ${response.nextLink}\n`;
        }
        return output;
      } else if (response.ok) {
        return "No Microsoft Teams meetings found matching your criteria.";
      } else {
        return `Error fetching Microsoft Teams meetings: ${response.error || 'Unknown error'}`;
      }
    } catch (error: any) {
      console.error('Error in "list teams meetings" command:', error.message);
      return "Sorry, an unexpected error occurred while fetching your Microsoft Teams meetings.";
    }
  } else if (lowerCaseMessage.startsWith('get teams meeting')) {
    const userPrincipalNameOrId = "me"; // As above
    const parts = lowerCaseMessage.split(' '); // "get teams meeting <eventId>"
    if (parts.length < 4) {
      return "Please provide a Microsoft Graph Event ID. Usage: get teams meeting <eventId>";
    }
    const eventId = parts[3];

    try {
      const response: GetMSTeamsMeetingDetailsResponse = await getMicrosoftTeamsMeetingDetails(userPrincipalNameOrId, eventId);
      if (response.ok && response.event) {
        const ev = response.event;
        let output = `Teams Meeting: ${ev.subject}\nID: ${ev.id}\nStart: ${ev.start?.dateTime ? new Date(ev.start.dateTime).toLocaleString() : 'N/A'}\nEnd: ${ev.end?.dateTime ? new Date(ev.end.dateTime).toLocaleString() : 'N/A'}`;
        if (ev.onlineMeeting?.joinUrl) {
          output += `\nJoin URL: ${ev.onlineMeeting.joinUrl}`;
        }
        if (ev.bodyPreview) {
          output += `\nPreview: ${ev.bodyPreview}`;
        }
         if (ev.webLink) output += `\nOutlook Link: ${ev.webLink}`;
        return output;
      } else {
        return `Error fetching Teams meeting details: ${response.error || `Meeting with ID ${eventId} not found or an unknown error occurred.`}`;
      }
    } catch (error: any) {
      console.error(`Error in "get teams meeting ${eventId}" command:`, error.message);
      return `Sorry, an unexpected error occurred while fetching details for Teams meeting ${eventId}.`;
    }
  }


  return `Atom received: "${message}". I can understand "list events", "create event {JSON_DETAILS}", "list emails", "read email <id>", "send email {JSON_DETAILS}", "search web <query>", "trigger zap <ZapName> [with data {JSON_DATA}]", "create hubspot contact {JSON_DETAILS}", "slack my agenda", "list calendly event types", "list calendly bookings [active|canceled] [count]", "list zoom meetings [live|upcoming|scheduled|upcoming_meetings|previous_meetings] [page_size] [next_page_token]", "get zoom meeting <meetingId>", "list google meet events [limit]", "get google meet event <eventId>", "list teams meetings [limit] [nextLink]", or "get teams meeting <eventId>".`;
}
