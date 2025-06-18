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
  MSGraphEvent,
  // Stripe Types
  ListStripePaymentsResponse,
  GetStripePaymentDetailsResponse,
  StripePaymentIntent,
  // QuickBooks Types
  ListQuickBooksInvoicesResponse,
  GetQuickBooksInvoiceDetailsResponse,
  QuickBooksInvoice,
  // NLU
  ProcessedNLUResponse
} from '../types';
import { createHubSpotContact, getHubSpotContactByEmail } from './skills/hubspotSkills'; // Added getHubSpotContactByEmail
import { sendSlackMessage } from './skills/slackSkills';
import { listCalendlyEventTypes, listCalendlyScheduledEvents } from './skills/calendlySkills';
import { listZoomMeetings, getZoomMeetingDetails } from './skills/zoomSkills';
import {
    listUpcomingEvents,
    createCalendarEvent,
    listUpcomingGoogleMeetEvents,
    getGoogleMeetEventDetails
} from './skills/calendarSkills';
import { listMicrosoftTeamsMeetings, getMicrosoftTeamsMeetingDetails } from './skills/msTeamsSkills';
import { listStripePayments, getStripePaymentDetails } from './skills/stripeSkills';
import {
    listQuickBooksInvoices,
    getQuickBooksInvoiceDetails,
    getAuthUri as getQuickBooksAuthUri
} from './skills/quickbooksSkills';
import {
    createSchedulingRule,
    blockCalendarTime,
    initiateTeamMeetingScheduling,
    NLUCreateTimePreferenceRuleEntities,
    NLUBlockTimeSlotEntities,
    NLUScheduleTeamMeetingEntities,
    SchedulingResponse
} from './skills/schedulingSkills';
import { understandMessage } from './skills/nluService'; // Added NLU Service
import { ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID, ATOM_HUBSPOT_PORTAL_ID, ATOM_QB_TOKEN_FILE_PATH } from '../_libs/constants';


export async function handleMessage(message: string): Promise<string> {
  const lowerCaseMessage = message.toLowerCase(); // Keep for simple fallbacks initially
  const userId = "mock_user_id_from_handler"; // Placeholder for actual user ID retrieval

  // Initial NLU Call
  const nluResponse: ProcessedNLUResponse = await understandMessage(message);
  console.log('NLU Response:', JSON.stringify(nluResponse, null, 2)); // For debugging

  // Handle NLU Service Errors (e.g., API key, network)
  if (nluResponse.error && !nluResponse.intent) { // Critical NLU failure
    console.error('NLU service critical error:', nluResponse.error);
    return "Sorry, I'm having trouble understanding requests right now. Please try again later.";
  }

  if (nluResponse.intent) { // If NLU identified an intent
    switch (nluResponse.intent) {
      case "GetCalendarEvents":
        try {
            let limit = 7; // Default limit
            if (nluResponse.entities?.limit) {
                if (typeof nluResponse.entities.limit === 'number') {
                    limit = nluResponse.entities.limit;
                } else if (typeof nluResponse.entities.limit === 'string') {
                    const parsedLimit = parseInt(nluResponse.entities.limit, 10);
                    if (!isNaN(parsedLimit)) limit = parsedLimit;
                }
            }

            const date_range = nluResponse.entities?.date_range as string | undefined;
            const event_type_filter = nluResponse.entities?.event_type_filter as string | undefined;

            if (date_range) {
                console.log(`NLU Intent "GetCalendarEvents" received date_range: ${date_range}. This is not yet used by the skill.`);
                // Future: Pass to listUpcomingEvents if skill supports it, or implement date parsing logic.
            }
            if (event_type_filter) {
                console.log(`NLU Intent "GetCalendarEvents" received event_type_filter: ${event_type_filter}. This is not yet used by the skill directly for general events.`);
                // Future: Could switch to a specific skill like listUpcomingGoogleMeetEvents if filter matches,
                // or pass to listUpcomingEvents if skill supports generalized filtering.
                // For now, specific intents like ListGoogleMeetEvents handle their own filtering.
            }

            const events: CalendarEvent[] = await listUpcomingEvents(userId, limit);
            if (!events || events.length === 0) {
                return "No upcoming calendar events found matching your criteria, or I couldn't access them.";
            }
            const eventList = events.map(event =>
                `- ${event.summary} (from ${new Date(event.startTime).toLocaleString()} to ${new Date(event.endTime).toLocaleString()})${event.location ? ` - Loc: ${event.location}` : ''}${event.htmlLink ? ` [Link: ${event.htmlLink}]` : ''}`
            ).join('\n');
            return `Upcoming calendar events:\n${eventList}`;
        } catch (error: any) {
            console.error(`Error in NLU Intent "GetCalendarEvents":`, error.message);
            return "Sorry, I couldn't fetch your calendar events due to an error.";
        }

      case "CreateCalendarEvent":
        try {
            const { summary, start_time, end_time, description, location, attendees } = nluResponse.entities;

            if (!summary || typeof summary !== 'string') {
                return "Event summary is required to create an event via NLU.";
            }
            if (!start_time || typeof start_time !== 'string') {
                return "Event start time is required to create an event via NLU.";
            }
            if (!end_time || typeof end_time !== 'string') {
                return "Event end time is required to create an event via NLU.";
            }

            const eventDetails: Partial<CalendarEvent> = {
                summary,
                startTime: start_time,
                endTime: end_time,
                description: typeof description === 'string' ? description : undefined,
                location: typeof location === 'string' ? location : undefined,
                // TODO: NLU currently sends attendees as a string, might need parsing if it's "email1, email2"
                // For now, assuming skill can handle array or it's passed correctly by NLU as array.
                attendees: Array.isArray(attendees) ? attendees.filter(att => typeof att === 'string') : undefined,
            };

            const response: CreateEventResponse = await createCalendarEvent(userId, eventDetails);
            if (response.success) {
                return `Event created: ${response.message || 'Successfully created event.'} (ID: ${response.eventId || 'N/A'})${response.htmlLink ? ` Link: ${response.htmlLink}` : ''}`;
            } else {
                return `Failed to create calendar event via NLU. ${response.message || 'Please check your connection or try again.'}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "CreateCalendarEvent":`, error.message);
            return "Sorry, I couldn't create the calendar event due to an error.";
        }

      case "ListEmails":
        try {
            let limit = 10; // Default limit
            if (nluResponse.entities?.limit) {
                if (typeof nluResponse.entities.limit === 'number') {
                    limit = nluResponse.entities.limit;
                } else if (typeof nluResponse.entities.limit === 'string') {
                    const parsedLimit = parseInt(nluResponse.entities.limit, 10);
                    if (!isNaN(parsedLimit)) limit = parsedLimit;
                }
            }
            const emails: Email[] = await listRecentEmails(limit);
            if (emails.length === 0) {
                return "No recent emails found (via NLU).";
            }
            const emailList = emails.map(email =>
                `- (${email.read ? 'read' : 'unread'}) From: ${email.sender}, Subject: ${email.subject} (ID: ${email.id})`
            ).join('\n');
            return `Recent emails (via NLU):\n${emailList}`;
        } catch (error: any) {
            console.error(`Error in NLU Intent "ListEmails":`, error.message);
            return "Sorry, I couldn't fetch recent emails due to an error (NLU path).";
        }

      case "ReadEmail":
        try {
            const { email_id } = nluResponse.entities;
            if (!email_id || typeof email_id !== 'string') {
                return "Email ID is required to read an email via NLU.";
            }
            const response: ReadEmailResponse = await readEmail(email_id);
            if (response.success && response.email) {
                const email = response.email;
                return `Email (ID: ${email.id}):\nFrom: ${email.sender}\nTo: ${email.recipient}\nSubject: ${email.subject}\nDate: ${email.timestamp}\n\n${email.body}`;
            } else {
                return response.message || "Could not read email via NLU.";
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "ReadEmail":`, error.message);
            return "Sorry, I couldn't read the specified email due to an error (NLU path).";
        }

      case "SendEmail":
        try {
            const { to, subject, body } = nluResponse.entities;
            if (!to || typeof to !== 'string') {
                return "Recipient 'to' address is required to send an email via NLU.";
            }
            if (!subject || typeof subject !== 'string') {
                return "Subject is required to send an email via NLU.";
            }
            if (!body || typeof body !== 'string') {
                return "Body is required to send an email via NLU.";
            }
            const emailDetails: EmailDetails = { to, subject, body };
            const response: SendEmailResponse = await sendEmail(emailDetails);
            if (response.success) {
                return `Email sent via NLU: ${response.message} (ID: ${response.emailId})`;
            } else {
                return `Failed to send email via NLU: ${response.message}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "SendEmail":`, error.message);
            return "Sorry, I couldn't send the email due to an error (NLU path).";
        }

      case "SearchWeb":
        try {
            const { query } = nluResponse.entities;
            if (!query || typeof query !== 'string') {
                return "A search query is required to search the web via NLU.";
            }
            const results: SearchResult[] = await searchWeb(query);
            if (results.length === 0) {
                return `No web results found for "${query}" (via NLU).`;
            }
            const resultList = results.map(result =>
                `- ${result.title}\n  Link: ${result.link}\n  Snippet: ${result.snippet}`
            ).join('\n\n');
            return `Web search results for "${query}" (via NLU):\n\n${resultList}`;
        } catch (error: any) {
            console.error(`Error in NLU Intent "SearchWeb":`, error.message);
            return "Sorry, I couldn't perform the web search due to an error (NLU path).";
        }

      case "TriggerZap":
        try {
            const { zap_name, data } = nluResponse.entities;

            if (!zap_name || typeof zap_name !== 'string') {
                return "Zap name is required to trigger a Zap via NLU.";
            }

            // Ensure data is an object if provided
            const zapData: ZapData = (typeof data === 'object' && data !== null) ? data : {};

            const response: ZapTriggerResponse = await triggerZap(zap_name, zapData);
            if (response.success) {
                return `Zap triggered via NLU: ${response.message} (Run ID: ${response.runId})`;
            } else {
                return `Failed to trigger Zap via NLU: ${response.message}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "TriggerZap":`, error.message);
            return "Sorry, I couldn't trigger the Zap due to an error (NLU path).";
        }

      case "GetHubSpotContactByEmail":
        try {
            const emailEntity = nluResponse.entities?.email;

            if (!emailEntity || typeof emailEntity !== 'string' || emailEntity.trim() === '') {
              return "Email is required and must be a non-empty string to get a HubSpot contact by email.";
            }
            // Assuming userId is available in this scope from the top of the handleMessage function
            const contact: HubSpotContact | null = await getHubSpotContactByEmail(userId, emailEntity);

            if (contact) {
              const name = `${contact.properties.firstname || ''} ${contact.properties.lastname || ''}`.trim();
              let responseString = `HubSpot Contact Found:
ID: ${contact.id}
Name: ${name || 'N/A'}
Email: ${contact.properties.email || 'N/A'}
Company: ${contact.properties.company || 'N/A'}`;
              if (contact.properties.createdate) {
                responseString += `\nCreated: ${new Date(contact.properties.createdate).toLocaleString()}`;
              }
              if (contact.properties.lastmodifieddate) {
                responseString += `\nLast Modified: ${new Date(contact.properties.lastmodifieddate).toLocaleString()}`;
              }
              if (ATOM_HUBSPOT_PORTAL_ID && contact.id) {
                responseString += `\nView in HubSpot: https://app.hubspot.com/contacts/${ATOM_HUBSPOT_PORTAL_ID}/contact/${contact.id}`;
              }
              return responseString;
            } else {
              return `No HubSpot contact found with email: ${emailEntity}.`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "GetHubSpotContactByEmail":`, error.message, error.stack);
            return "Sorry, an error occurred while trying to retrieve the HubSpot contact.";
        }

      case "SlackMyAgenda":
        try {
            const limit = nluResponse.entities?.limit && typeof nluResponse.entities.limit === 'number' ? nluResponse.entities.limit : 5; // Default limit
            const events: CalendarEvent[] = await listUpcomingEvents(userId, limit);

            if (!events || events.length === 0) {
                const noEventsMessage = "You have no upcoming events on your calendar for the near future, or I couldn't access them (NLU path).";
                // Try sending to DM
                try {
                    await sendSlackMessage(userId, userId, noEventsMessage);
                    return "I've checked your calendar; no upcoming events. Sent a note to your Slack DM (NLU path).";
                } catch (dmError:any) {
                    return "No upcoming events found. Tried to DM you on Slack, but failed (NLU path).";
                }
            }

            let formattedAgenda = `🗓️ Your Upcoming Events (via NLU):\n`;
            for (const event of events) {
                const startTime = new Date(event.startTime).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
                const endTime = new Date(event.endTime).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
                formattedAgenda += `- ${event.summary} (from ${startTime} to ${endTime})`;
                if (event.location) formattedAgenda += ` - Location: ${event.location}`;
                if (event.htmlLink) formattedAgenda += ` [View: ${event.htmlLink}]`;
                formattedAgenda += "\n";
            }

            const slackResponse = await sendSlackMessage(userId, userId, formattedAgenda); // Send to user's own DM
            if (slackResponse.ok) {
                return "I've sent your agenda to your Slack DM (NLU path)!";
            } else {
                return `Sorry, I couldn't send your agenda to Slack (NLU path). Error: ${slackResponse.error}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "SlackMyAgenda":`, error.message);
            return "Sorry, an error occurred while processing your agenda for Slack (NLU path).";
        }

      case "ListCalendlyEventTypes":
        try {
            // userId for calendly might be different or derived if supporting multiple users
            const calendlyUserId = nluResponse.entities?.user_id && typeof nluResponse.entities.user_id === 'string' ? nluResponse.entities.user_id : userId; // Default to current user if not specified

            const response: ListCalendlyEventTypesResponse = await listCalendlyEventTypes(calendlyUserId);
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
            console.error(`Error in NLU Intent "ListCalendlyEventTypes":`, error.message);
            return "Sorry, an unexpected error occurred while fetching your Calendly event types (NLU path).";
        }

      case "ListCalendlyScheduledEvents":
        try {
            const calendlyUserId = nluResponse.entities?.user_id && typeof nluResponse.entities.user_id === 'string' ? nluResponse.entities.user_id : userId;
            const count = nluResponse.entities?.count && typeof nluResponse.entities.count === 'number' ? nluResponse.entities.count : 10;
            const status = nluResponse.entities?.status && typeof nluResponse.entities.status === 'string' ? nluResponse.entities.status as ('active' | 'canceled') : 'active';
            const sort = nluResponse.entities?.sort && typeof nluResponse.entities.sort === 'string' ? nluResponse.entities.sort : 'start_time:asc';
            // Note: The skill might need more specific type for 'status' and 'sort' if they are enums.

            const options = { count, status, sort, user: calendlyUserId }; // Pass user to skill if it handles user context

            const response: ListCalendlyScheduledEventsResponse = await listCalendlyScheduledEvents(calendlyUserId, options); // calendlyUserId might be options.user
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
            console.error(`Error in NLU Intent "ListCalendlyScheduledEvents":`, error.message);
            return "Sorry, an unexpected error occurred while fetching your Calendly bookings (NLU path).";
        }

      case "ListZoomMeetings":
        try {
            const userIdForZoom = "me"; // For Server-to-Server OAuth
            const type = (nluResponse.entities?.type && typeof nluResponse.entities.type === 'string' ? nluResponse.entities.type : 'upcoming') as 'live' | 'upcoming' | 'scheduled' | 'upcoming_meetings' | 'previous_meetings';
            const page_size = nluResponse.entities?.page_size && typeof nluResponse.entities.page_size === 'number' ? nluResponse.entities.page_size : 30;
            const next_page_token = nluResponse.entities?.next_page_token && typeof nluResponse.entities.next_page_token === 'string' ? nluResponse.entities.next_page_token : undefined;

            const options = { type, page_size, next_page_token };
            const response: ListZoomMeetingsResponse = await listZoomMeetings(userIdForZoom, options);

            if (response.ok && response.meetings && response.meetings.length > 0) {
                let output = `Your Zoom Meetings (${type}, via NLU):\n`;
                for (const meeting of response.meetings) {
                    output += `- ${meeting.topic} (ID: ${meeting.id}) - Start: ${meeting.start_time ? new Date(meeting.start_time).toLocaleString() : 'N/A'} - Join: ${meeting.join_url || 'N/A'}\n`;
                }
                if (response.next_page_token) {
                    output += `More meetings available. For next page, use token: ${response.next_page_token}\n`;
                }
                return output;
            } else if (response.ok) {
                return "No Zoom meetings found matching your criteria (via NLU).";
            } else {
                return `Error fetching Zoom meetings (via NLU): ${response.error || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "ListZoomMeetings":`, error.message);
            return "Sorry, an unexpected error occurred while fetching your Zoom meetings (NLU path).";
        }

      case "GetZoomMeetingDetails":
        try {
            const { meeting_id } = nluResponse.entities;
            if (!meeting_id || typeof meeting_id !== 'string') {
                return "Zoom Meeting ID is required to get details via NLU.";
            }
            const response: GetZoomMeetingDetailsResponse = await getZoomMeetingDetails(meeting_id);
            if (response.ok && response.meeting) {
                const m = response.meeting;
                return `Zoom Meeting Details (via NLU):\nTopic: ${m.topic}\nID: ${m.id}\nStart Time: ${m.start_time ? new Date(m.start_time).toLocaleString() : 'N/A'}\nDuration: ${m.duration || 'N/A'} mins\nJoin URL: ${m.join_url || 'N/A'}\nAgenda: ${m.agenda || 'N/A'}`;
            } else {
                return `Error fetching Zoom meeting details (via NLU): ${response.error || `Meeting with ID ${meeting_id} not found or an unknown error occurred.`}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "GetZoomMeetingDetails":`, error.message);
            return `Sorry, an unexpected error occurred while fetching details for Zoom meeting ${nluResponse.entities.meeting_id} (NLU path).`;
        }

      case "ListGoogleMeetEvents":
        try {
            const limit = nluResponse.entities?.limit && typeof nluResponse.entities.limit === 'number' ? nluResponse.entities.limit : 5;
            const response: ListGoogleMeetEventsResponse = await listUpcomingGoogleMeetEvents(userId, limit); // userId from handler scope

            if (response.ok && response.events && response.events.length > 0) {
                let output = "Your Upcoming Google Meet Events (via NLU):\n";
                for (const event of response.events) {
                    const meetLink = event.conferenceData?.entryPoints?.find(ep => ep.entryPointType === 'video' && ep.uri?.startsWith('https://meet.google.com/'))?.uri;
                    output += `- ${event.summary} (Starts: ${new Date(event.startTime).toLocaleString()})${meetLink ? ` - Link: ${meetLink}` : ' (No direct Meet link found, check calendar event details)'}\n`;
                }
                return output;
            } else if (response.ok) {
                return "No upcoming Google Meet events found (via NLU).";
            } else {
                return `Error fetching Google Meet events (via NLU): ${response.error || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "ListGoogleMeetEvents":`, error.message);
            return "Sorry, an unexpected error occurred while fetching your Google Meet events (NLU path).";
        }

      case "GetGoogleMeetEventDetails":
        try {
            const { event_id } = nluResponse.entities;
            if (!event_id || typeof event_id !== 'string') {
                return "Google Calendar Event ID is required to get details via NLU.";
            }
            const response: GetGoogleMeetEventDetailsResponse = await getGoogleMeetEventDetails(userId, event_id); // userId from handler scope

            if (response.ok && response.event) {
                const ev = response.event;
                let output = `Event (via NLU): ${ev.summary}\nStart: ${new Date(ev.startTime).toLocaleString()}\nEnd: ${new Date(ev.endTime).toLocaleString()}`;
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
                return `Error fetching Google Meet event details (via NLU): ${response.error || `Event with ID ${event_id} not found or an unknown error occurred.`}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "GetGoogleMeetEventDetails":`, error.message);
            return `Sorry, an unexpected error occurred while fetching details for event ${nluResponse.entities.event_id} (NLU path).`;
        }

      case "ListMicrosoftTeamsMeetings":
        try {
            const userPrincipalNameOrId = "me"; // Default for app-only or replace if user-delegated
            const limit = nluResponse.entities?.limit && typeof nluResponse.entities.limit === 'number' ? nluResponse.entities.limit : 10;
            const next_link = nluResponse.entities?.next_link && typeof nluResponse.entities.next_link === 'string' ? nluResponse.entities.next_link : undefined;

            const options = { limit, nextLink: next_link, filterForTeams: true };
            const response: ListMSTeamsMeetingsResponse = await listMicrosoftTeamsMeetings(userPrincipalNameOrId, options);

            if (response.ok && response.events && response.events.length > 0) {
                let output = "Your Microsoft Teams Meetings (via NLU):\n";
                for (const event of response.events) {
                    output += `- ${event.subject} (ID: ${event.id}) - Start: ${event.start?.dateTime ? new Date(event.start.dateTime).toLocaleString() : 'N/A'} - Join: ${event.onlineMeeting?.joinUrl || 'N/A'}\n`;
                }
                if (response.nextLink) {
                    output += `More meetings available. Next page link (for API use): ${response.nextLink}\nTo get next page, you could say: list teams meetings with limit ${limit} and next_link ${response.nextLink}\n`;
                }
                return output;
            } else if (response.ok) {
                return "No Microsoft Teams meetings found matching your criteria (via NLU).";
            } else {
                return `Error fetching Microsoft Teams meetings (via NLU): ${response.error || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "ListMicrosoftTeamsMeetings":`, error.message);
            return "Sorry, an unexpected error occurred while fetching your Microsoft Teams meetings (NLU path).";
        }

      case "GetMicrosoftTeamsMeetingDetails":
        try {
            const userPrincipalNameOrId = "me";
            const { event_id } = nluResponse.entities;
            if (!event_id || typeof event_id !== 'string') {
                return "Microsoft Graph Event ID is required to get Teams meeting details via NLU.";
            }
            const response: GetMSTeamsMeetingDetailsResponse = await getMicrosoftTeamsMeetingDetails(userPrincipalNameOrId, event_id);

            if (response.ok && response.event) {
                const ev = response.event;
                let output = `Teams Meeting (via NLU): ${ev.subject}\nID: ${ev.id}\nStart: ${ev.start?.dateTime ? new Date(ev.start.dateTime).toLocaleString() : 'N/A'}\nEnd: ${ev.end?.dateTime ? new Date(ev.end.dateTime).toLocaleString() : 'N/A'}`;
                if (ev.onlineMeeting?.joinUrl) {
                    output += `\nJoin URL: ${ev.onlineMeeting.joinUrl}`;
                }
                if (ev.bodyPreview) {
                    output += `\nPreview: ${ev.bodyPreview}`;
                }
                if (ev.webLink) output += `\nOutlook Link: ${ev.webLink}`;
                return output;
            } else {
                return `Error fetching Teams meeting details (via NLU): ${response.error || `Meeting with ID ${event_id} not found or an unknown error occurred.`}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "GetMicrosoftTeamsMeetingDetails":`, error.message);
            return `Sorry, an unexpected error occurred while fetching details for Teams meeting ${nluResponse.entities.event_id} (NLU path).`;
        }

      case "ListStripePayments":
        try {
            const { limit, starting_after, customer } = nluResponse.entities;
            const options: { limit?: number; starting_after?: string; customer?: string } = {};

            if (limit && typeof limit === 'number') options.limit = limit;
            else options.limit = 10; // Default limit

            if (starting_after && typeof starting_after === 'string') options.starting_after = starting_after;
            if (customer && typeof customer === 'string') options.customer = customer;

            const response: ListStripePaymentsResponse = await listStripePayments(options);
            if (response.ok && response.payments && response.payments.length > 0) {
                let output = "Stripe Payments (via NLU):\n";
                for (const payment of response.payments) {
                    output += `- ID: ${payment.id}, Amount: ${(payment.amount / 100).toFixed(2)} ${payment.currency.toUpperCase()}, Status: ${payment.status}, Created: ${new Date(payment.created * 1000).toLocaleDateString()}${payment.latest_charge?.receipt_url ? `, Receipt: ${payment.latest_charge.receipt_url}` : ''}\n`;
                }
                if (response.has_more && response.payments.length > 0) {
                    output += `More payments available. For next page, use option: starting_after=${response.payments[response.payments.length - 1].id}\n`;
                }
                return output;
            } else if (response.ok) {
                return "No Stripe payments found matching your criteria (via NLU).";
            } else {
                return `Error fetching Stripe payments (via NLU): ${response.error || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "ListStripePayments":`, error.message);
            return "Sorry, an unexpected error occurred while fetching Stripe payments (NLU path).";
        }

      case "GetStripePaymentDetails":
        try {
            const { payment_intent_id } = nluResponse.entities;
            if (!payment_intent_id || typeof payment_intent_id !== 'string') {
                return "Stripe PaymentIntent ID is required to get details via NLU.";
            }
            const response: GetStripePaymentDetailsResponse = await getStripePaymentDetails(payment_intent_id);
            if (response.ok && response.payment) {
                const p = response.payment;
                let output = `Stripe Payment Details (ID: ${p.id}, via NLU):\nAmount: ${(p.amount / 100).toFixed(2)} ${p.currency.toUpperCase()}\nStatus: ${p.status}\nCreated: ${new Date(p.created * 1000).toLocaleString()}\nDescription: ${p.description || 'N/A'}`;
                if (p.customer) output += `\nCustomer ID: ${p.customer}`;
                if (p.latest_charge?.receipt_url) output += `\nReceipt URL: ${p.latest_charge.receipt_url}`;
                return output;
            } else {
                return `Error fetching Stripe payment details (via NLU): ${response.error || `PaymentIntent with ID ${payment_intent_id} not found or an unknown error occurred.`}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "GetStripePaymentDetails":`, error.message);
            return `Sorry, an unexpected error occurred while fetching Stripe payment details for ${nluResponse.entities.payment_intent_id} (NLU path).`;
        }

      case "GetQuickBooksAuthUrl":
        try {
            const authUri = getQuickBooksAuthUri();
            if (authUri) {
                return `To authorize QuickBooks Online (via NLU), please visit this URL in your browser: ${authUri}\nAfter authorization, the agent will need the resulting tokens and realmId to be stored in its configured token file path (${ATOM_QB_TOKEN_FILE_PATH}). This step typically requires manual intervention or a separate callback handler not part of this command.`;
            } else {
                return "Could not generate QuickBooks authorization URL (via NLU). Please check server configuration.";
            }
        } catch (error: any) {
            console.error('Error in NLU Intent "GetQuickBooksAuthUrl":', error.message);
            return "Sorry, an error occurred while generating the QuickBooks authorization URL (NLU path).";
        }

      case "CreateTimePreferenceRule":
        try {
            const ruleDetails: NLUCreateTimePreferenceRuleEntities = {
                activity_description: nluResponse.entities?.activity_description as string,
                time_ranges: nluResponse.entities?.time_ranges as Array<{ start_time: string; end_time: string }>,
                days_of_week: nluResponse.entities?.days_of_week as string[],
                priority: nluResponse.entities?.priority, // Can be string or number
                category_tags: nluResponse.entities?.category_tags as string[] | undefined,
            };

            if (!ruleDetails.activity_description || !ruleDetails.time_ranges || !Array.isArray(ruleDetails.time_ranges) || ruleDetails.time_ranges.length === 0 || !ruleDetails.days_of_week || !Array.isArray(ruleDetails.days_of_week) || ruleDetails.days_of_week.length === 0) {
                return "Missing required details (activity description, time ranges, or days of week) to create a time preference rule.";
            }

            const response: SchedulingResponse = await createSchedulingRule(userId, ruleDetails);
            return response.message; // Return the message from the skill's response
        } catch (error: any) {
            console.error(`Error in NLU Intent "CreateTimePreferenceRule":`, error.message, error.stack);
            return "Sorry, there was an issue processing your time preference rule request.";
        }

      case "BlockTimeSlot":
        try {
            const blockDetails: NLUBlockTimeSlotEntities = {
                task_name: nluResponse.entities?.task_name as string,
                start_time: nluResponse.entities?.start_time as string | undefined,
                end_time: nluResponse.entities?.end_time as string | undefined,
                duration: nluResponse.entities?.duration as string | undefined,
                date: nluResponse.entities?.date as string | undefined,
                purpose: nluResponse.entities?.purpose as string | undefined,
            };

            if (!blockDetails.task_name) {
                return "Missing task name to block time.";
            }
            // Additional validation could be added here for start_time/end_time/duration combinations

            const response: SchedulingResponse = await blockCalendarTime(userId, blockDetails);
            return response.message;
        } catch (error: any) {
            console.error(`Error in NLU Intent "BlockTimeSlot":`, error.message, error.stack);
            return "Sorry, there was an issue processing your time blocking request.";
        }

      case "ScheduleTeamMeeting":
        try {
            const meetingDetails: NLUScheduleTeamMeetingEntities = {
                attendees: nluResponse.entities?.attendees as string[],
                purpose: nluResponse.entities?.purpose as string | undefined,
                duration_preference: nluResponse.entities?.duration_preference as string | undefined,
                time_preference_details: nluResponse.entities?.time_preference_details as string | undefined,
                meeting_title: nluResponse.entities?.meeting_title as string | undefined,
            };

            if (!meetingDetails.attendees || !Array.isArray(meetingDetails.attendees) || meetingDetails.attendees.length === 0) {
                return "Missing attendees (must be an array of strings) to schedule a team meeting.";
            }

            const response: SchedulingResponse = await initiateTeamMeetingScheduling(userId, meetingDetails);
            return response.message;
        } catch (error: any) {
            console.error(`Error in NLU Intent "ScheduleTeamMeeting":`, error.message, error.stack);
            return "Sorry, there was an issue processing your team meeting request.";
        }

      // Existing NLU Handlers
      case "CreateHubSpotContact":
        try {
            const { email, first_name, last_name, contact_name, company_name } = nluResponse.entities;
            if (!email || typeof email !== 'string') {
                return "Email is required (and must be a string) to create a HubSpot contact via NLU.";
            }

            let finalFirstName = first_name;
            let finalLastName = last_name;

            if (!finalFirstName && !finalLastName && contact_name && typeof contact_name === 'string') {
                const nameParts = contact_name.split(' ');
                finalFirstName = nameParts[0];
                if (nameParts.length > 1) {
                    finalLastName = nameParts.slice(1).join(' ');
                }
            }

            const contactDetails: HubSpotContactProperties = {
                email,
                firstname: typeof finalFirstName === 'string' ? finalFirstName : undefined,
                lastname: typeof finalLastName === 'string' ? finalLastName : undefined,
                company: typeof company_name === 'string' ? company_name : undefined,
            };

            const hubspotResponse: CreateHubSpotContactResponse = await createHubSpotContact(userId, contactDetails);
            if (hubspotResponse.success && hubspotResponse.contactId && hubspotResponse.hubSpotContact) {
                const contact = hubspotResponse.hubSpotContact;
                const name = `${contact.properties.firstname || ''} ${contact.properties.lastname || ''}`.trim() || 'N/A';
                return `HubSpot contact created via NLU! ID: ${hubspotResponse.contactId}. Name: ${name}. Email: ${contact.properties.email}.`;
            } else {
                return `Failed to create HubSpot contact via NLU: ${hubspotResponse.message || 'Unknown HubSpot error.'}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "CreateHubSpotContact":`, error.message);
            return "Sorry, there was an issue creating the HubSpot contact based on your request.";
        }

      case "SendSlackMessage":
        try {
            const { slack_channel, message_text } = nluResponse.entities;
            if (!slack_channel || typeof slack_channel !== 'string') {
                return "Slack channel/user ID is required to send a message via NLU.";
            }
            if (!message_text || typeof message_text !== 'string') {
                return "Message text is required to send a Slack message via NLU.";
            }
            const slackResponse = await sendSlackMessage(userId, slack_channel, message_text);
            if (slackResponse.ok) {
                return `Message sent to Slack channel/user ${slack_channel}.`;
            } else {
                return `Failed to send Slack message to ${slack_channel} via NLU. Error: ${slackResponse.error}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "SendSlackMessage":`, error.message);
            return "Sorry, there was an issue sending your Slack message.";
        }

      case "ListQuickBooksInvoices": // Renamed from ListInvoices
        try {
            const { customer_id, status, limit: nluLimit, offset: nluOffset } = nluResponse.entities;
            const options: { limit?: number; offset?: number; customerId?: string; status?: string } = {}; // Defaulting to skill's defaults initially

            if (nluLimit) {
                 if (typeof nluLimit === 'number') options.limit = nluLimit;
                 else if (typeof nluLimit === 'string') {
                    const parsed = parseInt(nluLimit, 10);
                    if (!isNaN(parsed)) options.limit = parsed;
                 }
            }
            if (nluOffset) { // Added offset handling
                 if (typeof nluOffset === 'number') options.offset = nluOffset;
                 else if (typeof nluOffset === 'string') {
                    const parsed = parseInt(nluOffset, 10);
                    if (!isNaN(parsed)) options.offset = parsed;
                 }
            }
            if (customer_id && typeof customer_id === 'string') options.customerId = customer_id;
            if (status && typeof status === 'string') {
                // Assuming skill might support status directly or needs filtering after fetch
                // For now, let's pass it if skill is updated to use it.
                // options.status = status; // If skill supports it.
                console.log(`NLU: ListQuickBooksInvoices received status filter: ${status}. Currently illustrative, skill may not filter by it.`);
            }

            const response: ListQuickBooksInvoicesResponse = await listQuickBooksInvoices(options);
             if (response.ok && response.invoices && response.invoices.length > 0) {
                let output = "QuickBooks Invoices (via NLU):\n";
                for (const inv of response.invoices) {
                    output += `- ID: ${inv.Id}, Num: ${inv.DocNumber || 'N/A'}, Cust: ${inv.CustomerRef?.name || inv.CustomerRef?.value || 'N/A'}, Total: ${inv.TotalAmt !== undefined ? inv.TotalAmt.toFixed(2) : 'N/A'} ${inv.CurrencyRef?.value || ''}\n`;
                }
                if (response.queryResponse) {
                    output += `Showing results. Max per page: ${response.queryResponse.maxResults || options.limit}\n`;
                }
                return output;
            } else if (response.ok) {
                return "No QuickBooks invoices found via NLU matching your criteria.";
            } else {
                return `Error fetching QuickBooks invoices via NLU: ${response.error || 'Unknown error'}. Ensure QuickBooks is connected and authorized.`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "ListQuickBooksInvoices":`, error.message);
            return "Sorry, an error occurred while fetching QuickBooks invoices via NLU.";
        }

      case "GetQuickBooksInvoiceDetails": // Renamed from GetInvoiceDetails
        try {
            const { invoice_id } = nluResponse.entities;
            if (!invoice_id || typeof invoice_id !== 'string') {
                return "Invoice ID is required to get QuickBooks invoice details via NLU.";
            }
            const response: GetQuickBooksInvoiceDetailsResponse = await getQuickBooksInvoiceDetails(invoice_id);
            if (response.ok && response.invoice) {
                const inv = response.invoice;
                return `QuickBooks Invoice (ID: ${inv.Id}):\nDoc #: ${inv.DocNumber || 'N/A'}\nCustomer: ${inv.CustomerRef?.name || inv.CustomerRef?.value || 'N/A'}\nTotal: ${inv.TotalAmt !== undefined ? inv.TotalAmt.toFixed(2) : 'N/A'} ${inv.CurrencyRef?.value || ''}\nBalance: ${inv.Balance !== undefined ? inv.Balance.toFixed(2) : 'N/A'}`;
            } else {
                return `Error fetching QuickBooks invoice details via NLU: ${response.error || 'Invoice not found or error occurred.'}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "GetQuickBooksInvoiceDetails":`, error.message);
            return "Sorry, an error occurred while fetching QuickBooks invoice details via NLU.";
        }

      default:
        // This case handles intents recognized by NLU but not yet implemented in the switch.
        if (nluResponse.error) { // NLU had an issue but still returned an intent somehow (less likely with current NLU error handling)
             console.log(`NLU processed with intent '${nluResponse.intent}' but also had an error: ${nluResponse.error}`);
        }
        return `I understood your intent as '${nluResponse.intent}' with entities ${JSON.stringify(nluResponse.entities)}, but I'm not fully set up to handle that specific request conversationally yet. You can try specific commands or 'help'.`;
    }
  }
  // The old if-else if chain for startsWith will be removed from here.
  // The 'help' command and the final 'else' for unknown commands will remain as fallbacks
  // if NLU returns null intent.
  else if (lowerCaseMessage === 'help' || lowerCaseMessage === '?') {
     return `I can understand natural language for tasks like listing calendar events, creating HubSpot contacts, or sending Slack messages. Try "show me my next 3 meetings" or "create hubspot contact for jane@example.com name Jane Doe".
You can also use specific commands:
- "create hubspot contact and dm me details {JSON_DETAILS}"
- "create hubspot contact {JSON_DETAILS}" (for channel notifications)
- "slack my agenda"
- "list calendly event types" / "list calendly bookings [active|canceled] [count]"
- "list zoom meetings [type] [page_size] [next_page_token]" / "get zoom meeting <id>"
- "list google meet events [limit]" / "get google meet event <id>"
- "list teams meetings [limit] [nextLink]" / "get teams meeting <id>"
- "list stripe payments [limit=N] [starting_after=ID] [customer=ID]" / "get stripe payment <id>"
- "qb get auth url" / "list qb invoices [limit=N] [offset=N] [customer=ID]" / "get qb invoice <id>"
- And other general commands like "list emails", "read email <id>", "send email {JSON}", "search web <query>", "trigger zap <name> [with data {JSON}]".`;
  } else {
    if (nluResponse.error) { // NLU had an error but didn't qualify as critical earlier
        return `I had some trouble fully understanding that due to: ${nluResponse.error}. You can try rephrasing or use 'help'.`;
    }
    // Default response if NLU returns null intent and no specific fallback command matches
    return "Sorry, I didn't quite understand your request. Please try rephrasing, or type 'help' to see what I can do.";
  }
}
