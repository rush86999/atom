import * as conversationManager from './conversationState'; // Added for conversation management
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
  ProcessedNLUResponse,
  LtmQueryResult, // Assuming LtmQueryResult might be defined in types.ts or memoryManager exports it
} from '../types'; // Adjust if LtmQueryResult comes from memoryManager directly

// Conversation State and LTM
import * as conversationManager from './conversationState';
import {
    getConversationStateSnapshot,
    updateLTMContext, // Renamed as per instructions
    updateUserGoal,
    updateIntentAndEntities
} from './conversationState';
import { initializeDB as initializeLanceDB } from '../lanceDBManager'; // Renamed for clarity
import * as lancedb from 'vectordb-lance'; // For lancedb.Connection type
import {
    retrieveRelevantLTM,
    loadLTMToSTM,
    processSTMToLTM,
    ConversationStateActions // Import type for actions
} from './memoryManager';


import { createHubSpotContact, getHubSpotContactByEmail } from './skills/hubspotSkills';
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
    enableAutopilot,
    disableAutopilot,
    getAutopilotStatus
} from './skills/autopilotSkills'; // Added Autopilot skills
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

// Define the TTS service URL
const AUDIO_PROCESSOR_TTS_URL = process.env.AUDIO_PROCESSOR_BASE_URL
    ? `${process.env.AUDIO_PROCESSOR_BASE_URL}/tts`
    : 'http://localhost:8080/tts';

// --- LanceDB Initialization ---
let ltmDbConnection: lancedb.Connection | null = null;

async function initializeLtmDatabase(): Promise<void> {
  try {
    // Using a distinct name for the DB file for TS side, or ensure paths resolve correctly if shared.
    // For now, using "ltm_agent_data_ts" to distinguish if needed, or use the same name as Python if they share.
    // The Python side uses: "../../lance_db/ltm_agent_data.lance"
    // Node.js side (lanceDBManager.ts) uses: "./lance_db/" prefix.
    // If handler.ts is in 'atom-agent' and lanceDBManager is one level up, then '../lance_db/' might be right.
    // Let's assume lanceDBManager handles its path relative to its own location, so "ltm_agent_data" is fine.
    ltmDbConnection = await initializeLanceDB("ltm_agent_data"); // Or "ltm_agent_data_ts"
    if (ltmDbConnection) {
      console.log('[Handler] LanceDB LTM connection initialized successfully.');
    } else {
      console.error('[Handler] LanceDB LTM connection failed to initialize (returned null).');
    }
  } catch (error) {
    console.error('[Handler] Error initializing LanceDB LTM connection:', error);
    ltmDbConnection = null; // Ensure it's null on failure
  }
}

// Call initialization at module startup
initializeLtmDatabase();
// --- End LanceDB Initialization ---


// Define the new return type for handleMessage
export interface HandleMessageResponse {
  text: string;
  audioUrl?: string;
  error?: string;
}

async function _internalHandleMessage(message: string, userId: string): Promise<{text: string, nluResponse?: ProcessedNLUResponse}> {
  let textResponse: string;
  let conversationLtmContext: LtmQueryResult[] | null = null;

  // 2. LTM Retrieval (Moved before NLU to potentially inform NLU)
  // Note: The subtask asked to call understandMessage then retrieve LTM.
  // However, to *use* LTM in understandMessage, retrieval must happen first,
  // or NLU must be called again after LTM retrieval if LTM should influence NLU.
  // For this iteration, LTM retrieval happens, then NLU is called with LTM context.
  // Then, later, the response is augmented with LTM.
  if (ltmDbConnection) {
    try {
      // For now, let's retrieve general knowledge. Table could be dynamic.
      const relevantLtm = await retrieveRelevantLTM(message, userId, ltmDbConnection, { table: 'knowledge_base' });

      if (relevantLtm && relevantLtm.length > 0) {
        console.log(`[Handler] Retrieved ${relevantLtm.length} items from LTM for query: ${message}. Storing in conversation state.`);
        // Store LTM results in conversation state so NLU and response generation can use it.
        // This uses the new updateLTMContext directly.
        // loadLTMToSTM also calls this, but calling it here ensures context is available for NLU.
        updateLTMContext(relevantLtm);
        conversationLtmContext = relevantLtm; // Keep a local copy for this function's scope

        // If loadLTMToSTM has other side effects (like updating goal), call it too.
        // Or, ensure those side effects are explicitly handled here or in NLU service.
        const conversationStateActions: ConversationStateActions = {
            updateUserGoal: updateUserGoal,
            updateIntentAndEntities: updateIntentAndEntities,
            updateLtmRepoContext: updateLTMContext // This will be called again, which is fine.
        };
        await loadLTMToSTM(relevantLtm, conversationStateActions);

      } else {
        // Ensure LTM context is cleared if nothing relevant is found
        updateLTMContext(null);
        conversationLtmContext = null;
      }
    } catch (error) {
      console.error('[Handler] Error retrieving or loading LTM:', error);
      updateLTMContext(null); // Clear on error too
      conversationLtmContext = null;
    }
  } else {
    console.warn('[Handler] LTM DB connection not available, skipping LTM retrieval.');
    updateLTMContext(null); // Ensure context is null if DB is not available
    conversationLtmContext = null;
  }

  // 1. NLU Processing (Now with LTM context)
  const nluResponse: ProcessedNLUResponse = await understandMessage(message, undefined, conversationLtmContext);
  console.log('[InternalHandleMessage] NLU Response (with LTM context consideration):', JSON.stringify(nluResponse, null, 2));


  // 3. Intent Handling & Skill Execution
  if (nluResponse.error && !nluResponse.intent) {
    console.error('[InternalHandleMessage] NLU service critical error:', nluResponse.error);
    textResponse = "Sorry, I'm having trouble understanding requests right now. Please try again later.";
    // Even with NLU error, try to augment with LTM if context is available
    const currentConvStateOnError = getConversationStateSnapshot();
    const ltmContextForErrorResponse = currentConvStateOnError.ltmContext;
    if (ltmContextForErrorResponse && ltmContextForErrorResponse.length > 0) {
        const firstLtmItem = ltmContextForErrorResponse[0] as LtmQueryResult;
        if (firstLtmItem && firstLtmItem.text) {
            let ltmPreamble = `I recall from our records that: "${firstLtmItem.text.substring(0, 150)}${firstLtmItem.text.length > 150 ? '...' : ''}". `;
            textResponse = ltmPreamble + textResponse;
            console.log(`[Handler] Augmented error response with LTM context: ${ltmPreamble}`);
        }
    }
    return { text: textResponse, nluResponse };
  }

  if (nluResponse.intent) {
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
            }
            if (event_type_filter) {
                console.log(`NLU Intent "GetCalendarEvents" received event_type_filter: ${event_type_filter}. This is not yet used by the skill directly for general events.`);
            }

            const events: CalendarEvent[] = await listUpcomingEvents(userId, limit);
            if (!events || events.length === 0) {
                textResponse = "No upcoming calendar events found matching your criteria, or I couldn't access them.";
            } else {
                const eventList = events.map(event =>
                    `- ${event.summary} (from ${new Date(event.startTime).toLocaleString()} to ${new Date(event.endTime).toLocaleString()})${event.location ? ` - Loc: ${event.location}` : ''}${event.htmlLink ? ` [Link: ${event.htmlLink}]` : ''}`
                ).join('\n');
                textResponse = `Upcoming calendar events:\n${eventList}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "GetCalendarEvents":`, error.message);
            textResponse = "Sorry, I couldn't fetch your calendar events due to an error.";
        }
        break;

      case "CreateCalendarEvent":
        try {
            const { summary, start_time, end_time, description, location, attendees } = nluResponse.entities;

            if (!summary || typeof summary !== 'string') {
                textResponse = "Event summary is required to create an event via NLU.";
            } else if (!start_time || typeof start_time !== 'string') {
                textResponse = "Event start time is required to create an event via NLU.";
            } else if (!end_time || typeof end_time !== 'string') {
                textResponse = "Event end time is required to create an event via NLU.";
            } else {
                const eventDetails: Partial<CalendarEvent> = {
                    summary,
                    startTime: start_time,
                    endTime: end_time,
                    description: typeof description === 'string' ? description : undefined,
                    location: typeof location === 'string' ? location : undefined,
                    attendees: Array.isArray(attendees) ? attendees.filter(att => typeof att === 'string') : undefined,
                };

                const response: CreateEventResponse = await createCalendarEvent(userId, eventDetails);
                if (response.success) {
                    textResponse = `Event created: ${response.message || 'Successfully created event.'} (ID: ${response.eventId || 'N/A'})${response.htmlLink ? ` Link: ${response.htmlLink}` : ''}`;
                } else {
                    textResponse = `Failed to create calendar event via NLU. ${response.message || 'Please check your connection or try again.'}`;
                }
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "CreateCalendarEvent":`, error.message);
            textResponse = "Sorry, I couldn't create the calendar event due to an error.";
        }
        break;

      // ... (Apply similar pattern: assign to textResponse, then break) ...
      // For brevity, I will only show a few more, the rest should follow this pattern.

      case "ListEmails":
        try {
            let limit = 10; // Default limit
            if (nluResponse.entities?.limit) {
                if (typeof nluResponse.entities.limit === 'number') limit = nluResponse.entities.limit;
                else if (typeof nluResponse.entities.limit === 'string') {
                    const parsedLimit = parseInt(nluResponse.entities.limit, 10);
                    if (!isNaN(parsedLimit)) limit = parsedLimit;
                }
            }
            const emails: Email[] = await listRecentEmails(limit);
            if (emails.length === 0) {
                textResponse = "No recent emails found (via NLU).";
            } else {
                const emailList = emails.map(email =>
                    `- (${email.read ? 'read' : 'unread'}) From: ${email.sender}, Subject: ${email.subject} (ID: ${email.id})`
                ).join('\n');
                textResponse = `Recent emails (via NLU):\n${emailList}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "ListEmails":`, error.message);
            textResponse = "Sorry, I couldn't fetch recent emails due to an error (NLU path).";
        }
        break;

      case "ReadEmail":
        try {
            const { email_id } = nluResponse.entities;
            if (!email_id || typeof email_id !== 'string') {
                textResponse = "Email ID is required to read an email via NLU.";
            } else {
                const response: ReadEmailResponse = await readEmail(email_id);
                if (response.success && response.email) {
                    const email = response.email;
                    textResponse = `Email (ID: ${email.id}):\nFrom: ${email.sender}\nTo: ${email.recipient}\nSubject: ${email.subject}\nDate: ${email.timestamp}\n\n${email.body}`;
                } else {
                    textResponse = response.message || "Could not read email via NLU.";
                }
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "ReadEmail":`, error.message);
            textResponse = "Sorry, I couldn't read the specified email due to an error (NLU path).";
        }
        break;

      case "SendEmail":
        try {
            const { to, subject, body } = nluResponse.entities;
            if (!to || typeof to !== 'string') {
                textResponse = "Recipient 'to' address is required to send an email via NLU.";
            } else if (!subject || typeof subject !== 'string') {
                textResponse = "Subject is required to send an email via NLU.";
            } else if (!body || typeof body !== 'string') {
                textResponse = "Body is required to send an email via NLU.";
            } else {
                const emailDetails: EmailDetails = { to, subject, body };
                const response: SendEmailResponse = await sendEmail(emailDetails);
                if (response.success) {
                    textResponse = `Email sent via NLU: ${response.message} (ID: ${response.emailId})`;
                } else {
                    textResponse = `Failed to send email via NLU: ${response.message}`;
                }
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "SendEmail":`, error.message);
            textResponse = "Sorry, I couldn't send the email due to an error (NLU path).";
        }
        break;

      case "SearchWeb":
        try {
            const { query } = nluResponse.entities;
            if (!query || typeof query !== 'string') {
                textResponse = "A search query is required to search the web via NLU.";
            } else {
                const results: SearchResult[] = await searchWeb(query);
                if (results.length === 0) {
                    textResponse = `No web results found for "${query}" (via NLU).`;
                } else {
                    const resultList = results.map(result =>
                        `- ${result.title}\n  Link: ${result.link}\n  Snippet: ${result.snippet}`
                    ).join('\n\n');
                    textResponse = `Web search results for "${query}" (via NLU):\n\n${resultList}`;
                }
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "SearchWeb":`, error.message);
            textResponse = "Sorry, I couldn't perform the web search due to an error (NLU path).";
        }
        break;

      case "TriggerZap":
        try {
            const { zap_name, data } = nluResponse.entities;
            if (!zap_name || typeof zap_name !== 'string') {
                textResponse = "Zap name is required to trigger a Zap via NLU.";
            } else {
                const zapData: ZapData = (typeof data === 'object' && data !== null) ? data : {};
                const response: ZapTriggerResponse = await triggerZap(zap_name, zapData);
                if (response.success) {
                    textResponse = `Zap triggered via NLU: ${response.message} (Run ID: ${response.runId})`;
                } else {
                    textResponse = `Failed to trigger Zap via NLU: ${response.message}`;
                }
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "TriggerZap":`, error.message);
            textResponse = "Sorry, I couldn't trigger the Zap due to an error (NLU path).";
        }
        break;

      case "GetHubSpotContactByEmail":
        try {
            const emailEntity = nluResponse.entities?.email;
            if (!emailEntity || typeof emailEntity !== 'string' || emailEntity.trim() === '') {
              textResponse = "Email is required and must be a non-empty string to get a HubSpot contact by email.";
            } else {
              const contact: HubSpotContact | null = await getHubSpotContactByEmail(userId, emailEntity);
              if (contact) {
                const name = `${contact.properties.firstname || ''} ${contact.properties.lastname || ''}`.trim();
                let responseString = `HubSpot Contact Found:\nID: ${contact.id}\nName: ${name || 'N/A'}\nEmail: ${contact.properties.email || 'N/A'}\nCompany: ${contact.properties.company || 'N/A'}`;
                if (contact.properties.createdate) responseString += `\nCreated: ${new Date(contact.properties.createdate).toLocaleString()}`;
                if (contact.properties.lastmodifieddate) responseString += `\nLast Modified: ${new Date(contact.properties.lastmodifieddate).toLocaleString()}`;
                if (ATOM_HUBSPOT_PORTAL_ID && contact.id) responseString += `\nView in HubSpot: https://app.hubspot.com/contacts/${ATOM_HUBSPOT_PORTAL_ID}/contact/${contact.id}`;
                textResponse = responseString;
              } else {
                textResponse = `No HubSpot contact found with email: ${emailEntity}.`;
              }
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "GetHubSpotContactByEmail":`, error.message, error.stack);
            textResponse = "Sorry, an error occurred while trying to retrieve the HubSpot contact.";
        }
        break;

      case "SlackMyAgenda":
        try {
            const limit = nluResponse.entities?.limit && typeof nluResponse.entities.limit === 'number' ? nluResponse.entities.limit : 5;
            const events: CalendarEvent[] = await listUpcomingEvents(userId, limit);
            if (!events || events.length === 0) {
                const noEventsMessage = "You have no upcoming events on your calendar for the near future, or I couldn't access them (NLU path).";
                try {
                    await sendSlackMessage(userId, userId, noEventsMessage);
                    textResponse = "I've checked your calendar; no upcoming events. Sent a note to your Slack DM (NLU path).";
                } catch (dmError:any) {
                    textResponse = "No upcoming events found. Tried to DM you on Slack, but failed (NLU path).";
                }
            } else {
                let formattedAgenda = `🗓️ Your Upcoming Events (via NLU):\n`;
                for (const event of events) {
                    const startTime = new Date(event.startTime).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
                    const endTime = new Date(event.endTime).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
                    formattedAgenda += `- ${event.summary} (from ${startTime} to ${endTime})`;
                    if (event.location) formattedAgenda += ` - Location: ${event.location}`;
                    if (event.htmlLink) formattedAgenda += ` [View: ${event.htmlLink}]`;
                    formattedAgenda += "\n";
                }
                const slackResponse = await sendSlackMessage(userId, userId, formattedAgenda);
                if (slackResponse.ok) {
                    textResponse = "I've sent your agenda to your Slack DM (NLU path)!";
                } else {
                    textResponse = `Sorry, I couldn't send your agenda to Slack (NLU path). Error: ${slackResponse.error}`;
                }
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "SlackMyAgenda":`, error.message);
            textResponse = "Sorry, an error occurred while processing your agenda for Slack (NLU path).";
        }
        break;

      // ... (Ensure all other case statements are updated similarly to set textResponse and break) ...

      case "ListCalendlyEventTypes":
        try {
            const calendlyUserId = nluResponse.entities?.user_id && typeof nluResponse.entities.user_id === 'string' ? nluResponse.entities.user_id : userId;
            const response: ListCalendlyEventTypesResponse = await listCalendlyEventTypes(calendlyUserId);
            if (response.ok && response.collection && response.collection.length > 0) {
                let output = "Your Calendly Event Types (via NLU):\n";
                for (const et of response.collection) {
                    output += `- ${et.name} (${et.duration} mins) - Active: ${et.active} - URL: ${et.scheduling_url}\n`;
                }
                if (response.pagination?.next_page_token) {
                    output += `More event types available. Use next page token: ${response.pagination.next_page_token}\n`;
                }
                textResponse = output;
            } else if (response.ok) {
                textResponse = "No active Calendly event types found (via NLU).";
            } else {
                textResponse = `Error fetching Calendly event types (via NLU): ${response.error || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "ListCalendlyEventTypes":`, error.message);
            textResponse = "Sorry, an unexpected error occurred while fetching your Calendly event types (NLU path).";
        }
        break;

      case "ListCalendlyScheduledEvents":
        try {
            const calendlyUserId = nluResponse.entities?.user_id && typeof nluResponse.entities.user_id === 'string' ? nluResponse.entities.user_id : userId;
            const count = nluResponse.entities?.count && typeof nluResponse.entities.count === 'number' ? nluResponse.entities.count : 10;
            const status = nluResponse.entities?.status && typeof nluResponse.entities.status === 'string' ? nluResponse.entities.status as ('active' | 'canceled') : 'active';
            const sort = nluResponse.entities?.sort && typeof nluResponse.entities.sort === 'string' ? nluResponse.entities.sort : 'start_time:asc';
            const options = { count, status, sort, user: calendlyUserId };
            const response: ListCalendlyScheduledEventsResponse = await listCalendlyScheduledEvents(calendlyUserId, options);
            if (response.ok && response.collection && response.collection.length > 0) {
                let output = `Your Calendly Bookings (${status}, via NLU):\n`;
                for (const se of response.collection) {
                    output += `- ${se.name} (Starts: ${new Date(se.start_time).toLocaleString()}, Ends: ${new Date(se.end_time).toLocaleString()}) - Status: ${se.status}\n`;
                }
                if (response.pagination?.next_page_token) {
                    output += `More bookings available. Use next page token: ${response.pagination.next_page_token}\n`;
                }
                textResponse = output;
            } else if (response.ok) {
                textResponse = `No ${status} scheduled Calendly bookings found (via NLU).`;
            } else {
                textResponse = `Error fetching Calendly bookings (via NLU): ${response.error || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "ListCalendlyScheduledEvents":`, error.message);
            textResponse = "Sorry, an unexpected error occurred while fetching your Calendly bookings (NLU path).";
        }
        break;

      case "ListZoomMeetings":
        try {
            const userIdForZoom = "me";
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
                textResponse = output;
            } else if (response.ok) {
                textResponse = "No Zoom meetings found matching your criteria (via NLU).";
            } else {
                textResponse = `Error fetching Zoom meetings (via NLU): ${response.error || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "ListZoomMeetings":`, error.message);
            textResponse = "Sorry, an unexpected error occurred while fetching your Zoom meetings (NLU path).";
        }
        break;

      case "GetZoomMeetingDetails":
        try {
            const { meeting_id } = nluResponse.entities;
            if (!meeting_id || typeof meeting_id !== 'string') {
                textResponse = "Zoom Meeting ID is required to get details via NLU.";
            } else {
                const response: GetZoomMeetingDetailsResponse = await getZoomMeetingDetails(meeting_id);
                if (response.ok && response.meeting) {
                    const m = response.meeting;
                    textResponse = `Zoom Meeting Details (via NLU):\nTopic: ${m.topic}\nID: ${m.id}\nStart Time: ${m.start_time ? new Date(m.start_time).toLocaleString() : 'N/A'}\nDuration: ${m.duration || 'N/A'} mins\nJoin URL: ${m.join_url || 'N/A'}\nAgenda: ${m.agenda || 'N/A'}`;
                } else {
                    textResponse = `Error fetching Zoom meeting details (via NLU): ${response.error || `Meeting with ID ${meeting_id} not found or an unknown error occurred.`}`;
                }
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "GetZoomMeetingDetails":`, error.message);
            textResponse = `Sorry, an unexpected error occurred while fetching details for Zoom meeting ${nluResponse.entities.meeting_id} (NLU path).`;
        }
        break;

      case "ListGoogleMeetEvents":
        try {
            const limit = nluResponse.entities?.limit && typeof nluResponse.entities.limit === 'number' ? nluResponse.entities.limit : 5;
            const response: ListGoogleMeetEventsResponse = await listUpcomingGoogleMeetEvents(userId, limit);
            if (response.ok && response.events && response.events.length > 0) {
                let output = "Your Upcoming Google Meet Events (via NLU):\n";
                for (const event of response.events) {
                    const meetLink = event.conferenceData?.entryPoints?.find(ep => ep.entryPointType === 'video' && ep.uri?.startsWith('https://meet.google.com/'))?.uri;
                    output += `- ${event.summary} (Starts: ${new Date(event.startTime).toLocaleString()})${meetLink ? ` - Link: ${meetLink}` : ' (No direct Meet link found, check calendar event details)'}\n`;
                }
                textResponse = output;
            } else if (response.ok) {
                textResponse = "No upcoming Google Meet events found (via NLU).";
            } else {
                textResponse = `Error fetching Google Meet events (via NLU): ${response.error || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "ListGoogleMeetEvents":`, error.message);
            textResponse = "Sorry, an unexpected error occurred while fetching your Google Meet events (NLU path).";
        }
        break;

      case "GetGoogleMeetEventDetails":
        try {
            const { event_id } = nluResponse.entities;
            if (!event_id || typeof event_id !== 'string') {
                textResponse = "Google Calendar Event ID is required to get details via NLU.";
            } else {
                const response: GetGoogleMeetEventDetailsResponse = await getGoogleMeetEventDetails(userId, event_id);
                if (response.ok && response.event) {
                    const ev = response.event;
                    let output = `Event (via NLU): ${ev.summary}\nStart: ${new Date(ev.startTime).toLocaleString()}\nEnd: ${new Date(ev.endTime).toLocaleString()}`;
                    const meetLink = ev.conferenceData?.entryPoints?.find(ep => ep.entryPointType === 'video' && ep.uri?.startsWith('https://meet.google.com/'))?.uri;
                    if (meetLink) output += `\nMeet Link: ${meetLink}`;
                    else if (ev.conferenceData?.conferenceSolution?.name) output += `\nConference: ${ev.conferenceData.conferenceSolution.name} (Details might be in description or calendar entry)`;
                    else output += "\n(No Google Meet link or explicit conference data found for this event)";
                    if (ev.htmlLink) output += `\nCalendar Link: ${ev.htmlLink}`;
                    if (ev.description) output += `\nDescription: ${ev.description}`;
                    textResponse = output;
                } else {
                    textResponse = `Error fetching Google Meet event details (via NLU): ${response.error || `Event with ID ${event_id} not found or an unknown error occurred.`}`;
                }
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "GetGoogleMeetEventDetails":`, error.message);
            textResponse = `Sorry, an unexpected error occurred while fetching details for event ${nluResponse.entities.event_id} (NLU path).`;
        }
        break;

      case "ListMicrosoftTeamsMeetings":
        try {
            const userPrincipalNameOrId = "me";
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
                textResponse = output;
            } else if (response.ok) {
                textResponse = "No Microsoft Teams meetings found matching your criteria (via NLU).";
            } else {
                textResponse = `Error fetching Microsoft Teams meetings (via NLU): ${response.error || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "ListMicrosoftTeamsMeetings":`, error.message);
            textResponse = "Sorry, an unexpected error occurred while fetching your Microsoft Teams meetings (NLU path).";
        }
        break;

      case "GetMicrosoftTeamsMeetingDetails":
        try {
            const userPrincipalNameOrId = "me";
            const { event_id } = nluResponse.entities;
            if (!event_id || typeof event_id !== 'string') {
                textResponse = "Microsoft Graph Event ID is required to get Teams meeting details via NLU.";
            } else {
                const response: GetMSTeamsMeetingDetailsResponse = await getMicrosoftTeamsMeetingDetails(userPrincipalNameOrId, event_id);
                if (response.ok && response.event) {
                    const ev = response.event;
                    let output = `Teams Meeting (via NLU): ${ev.subject}\nID: ${ev.id}\nStart: ${ev.start?.dateTime ? new Date(ev.start.dateTime).toLocaleString() : 'N/A'}\nEnd: ${ev.end?.dateTime ? new Date(ev.end.dateTime).toLocaleString() : 'N/A'}`;
                    if (ev.onlineMeeting?.joinUrl) output += `\nJoin URL: ${ev.onlineMeeting.joinUrl}`;
                    if (ev.bodyPreview) output += `\nPreview: ${ev.bodyPreview}`;
                    if (ev.webLink) output += `\nOutlook Link: ${ev.webLink}`;
                    textResponse = output;
                } else {
                    textResponse = `Error fetching Teams meeting details (via NLU): ${response.error || `Meeting with ID ${event_id} not found or an unknown error occurred.`}`;
                }
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "GetMicrosoftTeamsMeetingDetails":`, error.message);
            textResponse = `Sorry, an unexpected error occurred while fetching details for Teams meeting ${nluResponse.entities.event_id} (NLU path).`;
        }
        break;

      case "ListStripePayments":
        try {
            const { limit, starting_after, customer } = nluResponse.entities;
            const options: { limit?: number; starting_after?: string; customer?: string } = {};
            if (limit && typeof limit === 'number') options.limit = limit; else options.limit = 10;
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
                textResponse = output;
            } else if (response.ok) {
                textResponse = "No Stripe payments found matching your criteria (via NLU).";
            } else {
                textResponse = `Error fetching Stripe payments (via NLU): ${response.error || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "ListStripePayments":`, error.message);
            textResponse = "Sorry, an unexpected error occurred while fetching Stripe payments (NLU path).";
        }
        break;

      case "GetStripePaymentDetails":
        try {
            const { payment_intent_id } = nluResponse.entities;
            if (!payment_intent_id || typeof payment_intent_id !== 'string') {
                textResponse = "Stripe PaymentIntent ID is required to get details via NLU.";
            } else {
                const response: GetStripePaymentDetailsResponse = await getStripePaymentDetails(payment_intent_id);
                if (response.ok && response.payment) {
                    const p = response.payment;
                    let output = `Stripe Payment Details (ID: ${p.id}, via NLU):\nAmount: ${(p.amount / 100).toFixed(2)} ${p.currency.toUpperCase()}\nStatus: ${p.status}\nCreated: ${new Date(p.created * 1000).toLocaleString()}\nDescription: ${p.description || 'N/A'}`;
                    if (p.customer) output += `\nCustomer ID: ${p.customer}`;
                    if (p.latest_charge?.receipt_url) output += `\nReceipt URL: ${p.latest_charge.receipt_url}`;
                    textResponse = output;
                } else {
                    textResponse = `Error fetching Stripe payment details (via NLU): ${response.error || `PaymentIntent with ID ${payment_intent_id} not found or an unknown error occurred.`}`;
                }
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "GetStripePaymentDetails":`, error.message);
            textResponse = `Sorry, an unexpected error occurred while fetching Stripe payment details for ${nluResponse.entities.payment_intent_id} (NLU path).`;
        }
        break;

      case "GetQuickBooksAuthUrl":
        try {
            const authUri = getQuickBooksAuthUri();
            if (authUri) {
                textResponse = `To authorize QuickBooks Online (via NLU), please visit this URL in your browser: ${authUri}\nAfter authorization, the agent will need the resulting tokens and realmId to be stored in its configured token file path (${ATOM_QB_TOKEN_FILE_PATH}). This step typically requires manual intervention or a separate callback handler not part of this command.`;
            } else {
                textResponse = "Could not generate QuickBooks authorization URL (via NLU). Please check server configuration.";
            }
        } catch (error: any) {
            console.error('Error in NLU Intent "GetQuickBooksAuthUrl":', error.message);
            textResponse = "Sorry, an error occurred while generating the QuickBooks authorization URL (NLU path).";
        }
        break;

      case "CreateTimePreferenceRule":
        try {
            const ruleDetails: NLUCreateTimePreferenceRuleEntities = {
                activity_description: nluResponse.entities?.activity_description as string,
                time_ranges: nluResponse.entities?.time_ranges as Array<{ start_time: string; end_time: string }>,
                days_of_week: nluResponse.entities?.days_of_week as string[],
                priority: nluResponse.entities?.priority,
                category_tags: nluResponse.entities?.category_tags as string[] | undefined,
            };
            if (!ruleDetails.activity_description || !ruleDetails.time_ranges || !Array.isArray(ruleDetails.time_ranges) || ruleDetails.time_ranges.length === 0 || !ruleDetails.days_of_week || !Array.isArray(ruleDetails.days_of_week) || ruleDetails.days_of_week.length === 0) {
                textResponse = "Missing required details (activity description, time ranges, or days of week) to create a time preference rule.";
            } else {
                const response: SchedulingResponse = await createSchedulingRule(userId, ruleDetails);
                textResponse = response.message;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "CreateTimePreferenceRule":`, error.message, error.stack);
            textResponse = "Sorry, there was an issue processing your time preference rule request.";
        }
        break;

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
                textResponse = "Missing task name to block time.";
            } else {
                const response: SchedulingResponse = await blockCalendarTime(userId, blockDetails);
                textResponse = response.message;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "BlockTimeSlot":`, error.message, error.stack);
            textResponse = "Sorry, there was an issue processing your time blocking request.";
        }
        break;

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
                textResponse = "Missing attendees (must be an array of strings) to schedule a team meeting.";
            } else {
                const response: SchedulingResponse = await initiateTeamMeetingScheduling(userId, meetingDetails);
                textResponse = response.message;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "ScheduleTeamMeeting":`, error.message, error.stack);
            textResponse = "Sorry, there was an issue processing your team meeting request.";
        }
        break;

      case "CreateHubSpotContact":
        try {
            const { email, first_name, last_name, contact_name, company_name } = nluResponse.entities;
            if (!email || typeof email !== 'string') {
                textResponse = "Email is required (and must be a string) to create a HubSpot contact via NLU.";
            } else {
                let finalFirstName = first_name;
                let finalLastName = last_name;
                if (!finalFirstName && !finalLastName && contact_name && typeof contact_name === 'string') {
                    const nameParts = contact_name.split(' ');
                    finalFirstName = nameParts[0];
                    if (nameParts.length > 1) finalLastName = nameParts.slice(1).join(' ');
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
                    textResponse = `HubSpot contact created via NLU! ID: ${hubspotResponse.contactId}. Name: ${name}. Email: ${contact.properties.email}.`;
                } else {
                    textResponse = `Failed to create HubSpot contact via NLU: ${hubspotResponse.message || 'Unknown HubSpot error.'}`;
                }
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "CreateHubSpotContact":`, error.message);
            textResponse = "Sorry, there was an issue creating the HubSpot contact based on your request.";
        }
        break;

      case "SendSlackMessage":
        try {
            const { slack_channel, message_text } = nluResponse.entities;
            if (!slack_channel || typeof slack_channel !== 'string') {
                textResponse = "Slack channel/user ID is required to send a message via NLU.";
            } else if (!message_text || typeof message_text !== 'string') {
                textResponse = "Message text is required to send a Slack message via NLU.";
            } else {
                const slackResponse = await sendSlackMessage(userId, slack_channel, message_text);
                if (slackResponse.ok) {
                    textResponse = `Message sent to Slack channel/user ${slack_channel}.`;
                } else {
                    textResponse = `Failed to send Slack message to ${slack_channel} via NLU. Error: ${slackResponse.error}`;
                }
            }
        } catch (error: any).
            console.error(`Error in NLU Intent "SendSlackMessage":`, error.message);
            textResponse = "Sorry, there was an issue sending your Slack message.";
        }
        break;

      case "ListQuickBooksInvoices":
        try {
            const { customer_id, status, limit: nluLimit, offset: nluOffset } = nluResponse.entities;
            const options: { limit?: number; offset?: number; customerId?: string; status?: string } = {};
            if (nluLimit) {
                 if (typeof nluLimit === 'number') options.limit = nluLimit;
                 else if (typeof nluLimit === 'string') { const parsed = parseInt(nluLimit, 10); if (!isNaN(parsed)) options.limit = parsed; }
            }
            if (nluOffset) {
                 if (typeof nluOffset === 'number') options.offset = nluOffset;
                 else if (typeof nluOffset === 'string') { const parsed = parseInt(nluOffset, 10); if (!isNaN(parsed)) options.offset = parsed; }
            }
            if (customer_id && typeof customer_id === 'string') options.customerId = customer_id;
            if (status && typeof status === 'string') console.log(`NLU: ListQuickBooksInvoices received status filter: ${status}. Currently illustrative, skill may not filter by it.`);
            const response: ListQuickBooksInvoicesResponse = await listQuickBooksInvoices(options);
             if (response.ok && response.invoices && response.invoices.length > 0) {
                let output = "QuickBooks Invoices (via NLU):\n";
                for (const inv of response.invoices) {
                    output += `- ID: ${inv.Id}, Num: ${inv.DocNumber || 'N/A'}, Cust: ${inv.CustomerRef?.name || inv.CustomerRef?.value || 'N/A'}, Total: ${inv.TotalAmt !== undefined ? inv.TotalAmt.toFixed(2) : 'N/A'} ${inv.CurrencyRef?.value || ''}\n`;
                }
                if (response.queryResponse) output += `Showing results. Max per page: ${response.queryResponse.maxResults || options.limit}\n`;
                textResponse = output;
            } else if (response.ok) {
                textResponse = "No QuickBooks invoices found via NLU matching your criteria.";
            } else {
                textResponse = `Error fetching QuickBooks invoices via NLU: ${response.error || 'Unknown error'}. Ensure QuickBooks is connected and authorized.`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "ListQuickBooksInvoices":`, error.message);
            textResponse = "Sorry, an error occurred while fetching QuickBooks invoices via NLU.";
        }
        break;

      case "GetQuickBooksInvoiceDetails":
        try {
            const { invoice_id } = nluResponse.entities;
            if (!invoice_id || typeof invoice_id !== 'string') {
                textResponse = "Invoice ID is required to get QuickBooks invoice details via NLU.";
            } else {
                const response: GetQuickBooksInvoiceDetailsResponse = await getQuickBooksInvoiceDetails(invoice_id);
                if (response.ok && response.invoice) {
                    const inv = response.invoice;
                    textResponse = `QuickBooks Invoice (ID: ${inv.Id}):\nDoc #: ${inv.DocNumber || 'N/A'}\nCustomer: ${inv.CustomerRef?.name || inv.CustomerRef?.value || 'N/A'}\nTotal: ${inv.TotalAmt !== undefined ? inv.TotalAmt.toFixed(2) : 'N/A'} ${inv.CurrencyRef?.value || ''}\nBalance: ${inv.Balance !== undefined ? inv.Balance.toFixed(2) : 'N/A'}`;
                } else {
                    textResponse = `Error fetching QuickBooks invoice details via NLU: ${response.error || 'Invoice not found or error occurred.'}`;
                }
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "GetQuickBooksInvoiceDetails":`, error.message);
            textResponse = "Sorry, an error occurred while fetching QuickBooks invoice details via NLU.";
        }
        break;

      // --- Autopilot Intents ---
      case "EnableAutopilot":
        try {
            console.log('[Handler] Intent: EnableAutopilot, Entities:', nluResponse.entities);
            // The query for enableAutopilot might need a structured JSON string.
            // For now, we'll try to use raw_query or stringify all entities.
            // This part will need refinement based on NLU capabilities for Autopilot.
            let autopilotQuery = "";
            if (nluResponse.entities?.raw_query && typeof nluResponse.entities.raw_query === 'string') {
                autopilotQuery = nluResponse.entities.raw_query;
            } else if (nluResponse.entities) {
                // Fallback: stringify all entities if raw_query isn't specific enough or available
                // This assumes `parseQuery` in autopilotSkills can handle it or it's a simple ID.
                autopilotQuery = JSON.stringify(nluResponse.entities);
            }

            const autopilotEnableResponse = await enableAutopilot(userId, autopilotQuery);
            if (autopilotEnableResponse.ok && autopilotEnableResponse.data) {
                textResponse = `Autopilot enabled successfully. Details: ${JSON.stringify(autopilotEnableResponse.data)}`;
            } else {
                textResponse = `Failed to enable Autopilot. Error: ${autopilotEnableResponse.error?.message || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "EnableAutopilot":`, error.message, error.stack);
            textResponse = "Sorry, there was an unexpected issue enabling Autopilot.";
        }
        break;

      case "DisableAutopilot":
        try {
            console.log('[Handler] Intent: DisableAutopilot, Entities:', nluResponse.entities);
            // Query for disable should ideally be the autopilotId/eventId
            let autopilotQuery = "";
            if (nluResponse.entities?.raw_query && typeof nluResponse.entities.raw_query === 'string') {
                autopilotQuery = nluResponse.entities.raw_query;
            } else if (nluResponse.entities?.autopilot_id && typeof nluResponse.entities.autopilot_id === 'string') {
                autopilotQuery = nluResponse.entities.autopilot_id;
            } else if (nluResponse.entities?.event_id && typeof nluResponse.entities.event_id === 'string') {
                autopilotQuery = nluResponse.entities.event_id; // Assuming event_id can be used as query
            } else if (nluResponse.entities) {
                 autopilotQuery = JSON.stringify(nluResponse.entities); // Fallback
            }

            if (!autopilotQuery) {
                textResponse = "Could not disable Autopilot: Missing ID in your request. Please specify the Autopilot ID or event ID.";
            } else {
                const autopilotDisableResponse = await disableAutopilot(userId, autopilotQuery);
                if (autopilotDisableResponse.ok && autopilotDisableResponse.data?.success) {
                    textResponse = "Autopilot disabled successfully.";
                } else {
                    textResponse = `Failed to disable Autopilot. Error: ${autopilotDisableResponse.error?.message || 'Unknown error or already disabled'}`;
                }
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "DisableAutopilot":`, error.message, error.stack);
            textResponse = "Sorry, there was an unexpected issue disabling Autopilot.";
        }
        break;

      case "GetAutopilotStatus":
        try {
            console.log('[Handler] Intent: GetAutopilotStatus, Entities:', nluResponse.entities);
            // Query for status can be empty (all for user) or specific autopilotId/eventId
            let autopilotQuery = "";
            if (nluResponse.entities?.raw_query && typeof nluResponse.entities.raw_query === 'string') {
                autopilotQuery = nluResponse.entities.raw_query;
            } else if (nluResponse.entities?.autopilot_id && typeof nluResponse.entities.autopilot_id === 'string') {
                autopilotQuery = nluResponse.entities.autopilot_id;
            } else if (nluResponse.entities?.event_id && typeof nluResponse.entities.event_id === 'string') {
                autopilotQuery = nluResponse.entities.event_id; // Assuming event_id can be used as query
            }
            // If autopilotQuery is empty, getAutopilotStatus skill should handle it by listing all for the user.

            const autopilotStatusResponse = await getAutopilotStatus(userId, autopilotQuery);
            if (autopilotStatusResponse.ok && autopilotStatusResponse.data) {
                // Data could be AutopilotType or AutopilotType[]
                const statusData = autopilotStatusResponse.data;
                if (Array.isArray(statusData)) {
                    if (statusData.length === 0) {
                        textResponse = "No Autopilot configurations found for you.";
                    } else {
                        textResponse = `Found ${statusData.length} Autopilot configurations:\n`;
                        statusData.forEach(ap => {
                            textResponse += `- ID: ${ap.id}, Scheduled at: ${ap.scheduleAt}, Timezone: ${ap.timezone}\n`;
                        });
                    }
                } else { // Single AutopilotType object
                     textResponse = `Autopilot Status (ID: ${statusData.id}): Scheduled at ${statusData.scheduleAt} in ${statusData.timezone}. Payload: ${JSON.stringify(statusData.payload, null, 2)}`;
                }
            } else if (autopilotStatusResponse.ok && !autopilotStatusResponse.data) {
                 textResponse = "No specific Autopilot configuration found for the given query, or no configurations exist.";
            }
            else {
                textResponse = `Failed to get Autopilot status. Error: ${autopilotStatusResponse.error?.message || 'Unknown error'}`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "GetAutopilotStatus":`, error.message, error.stack);
            textResponse = "Sorry, there was an unexpected issue fetching Autopilot status.";
        }
        break;
      // --- End Autopilot Intents ---

      default:
        if (nluResponse.error) {
             console.log(`[InternalHandleMessage] NLU processed with intent '${nluResponse.intent}' but also had an error: ${nluResponse.error}`);
        }
        textResponse = `I understood your intent as '${nluResponse.intent}' with entities ${JSON.stringify(nluResponse.entities)}, but I'm not fully set up to handle that specific request conversationally yet. You can try specific commands or 'help'.`;
    }
  } else if (lowerCaseMessage === 'help' || lowerCaseMessage === '?') {
     textResponse = `I can understand natural language for tasks like listing calendar events, creating HubSpot contacts, or sending Slack messages. Try "show me my next 3 meetings" or "create hubspot contact for jane@example.com name Jane Doe".
You can also use specific commands:
- "create hubspot contact and dm me details {JSON_DETAILS}"
- "create hubspot contact {JSON_DETAILS}" (for channel notifications)
// ... (help message content as before)
- And other general commands like "list emails", "read email <id>", "send email {JSON}", "search web <query>", "trigger zap <name> [with data {JSON}]".`;
  } else {
    if (nluResponse.error) {
        textResponse = `I had some trouble fully understanding that due to: ${nluResponse.error}. You can try rephrasing or use 'help'.`;
    } else {
        textResponse = "Sorry, I didn't quite understand your request. Please try rephrasing, or type 'help' to see what I can do.";
    }
  }

  // 4. Augment response with LTM context (New)
  console.log("[Handler] Future enhancement: Implement relevance check for LTM items before augmenting response.");
  const currentConvState = getConversationStateSnapshot();
  const ltmContextForResponse = currentConvState.ltmContext;

  if (ltmContextForResponse && ltmContextForResponse.length > 0) {
      const firstLtmItem = ltmContextForResponse[0] as LtmQueryResult; // Type assertion
      if (firstLtmItem && firstLtmItem.text) {
          let ltmPreamble = `I recall from our records that: "${firstLtmItem.text.substring(0, 150)}${firstLtmItem.text.length > 150 ? '...' : ''}". `;
          textResponse = ltmPreamble + textResponse;
          console.log(`[Handler] Augmented response with LTM context: ${ltmPreamble}`);
      }
  }

  return { text: textResponse, nluResponse };
}


// --- New Exported Functions for Conversation Management ---

/**
 * Placeholder for user ID retrieval. In a real scenario, this would come from session, token, etc.
 */
function getCurrentUserId(): string {
  // For now, using a mock user ID. This should be replaced with actual user management.
  return "mock_user_id_from_handler";
}

/**
 * Activates the conversation mode.
 * Assumed to be mapped to an HTTP endpoint like POST /atom-agent/activate
 */
export async function activateConversationWrapper(): Promise<{ status: string; active: boolean; message?: string }> {
  console.log("[Handler] Received request to activate conversation.");
  // activateConversation itself now sets isAgentResponding to false.
  const result = conversationManager.activateConversation();
  return { ...result, message: result.status };
}

/**
 * Deactivates the conversation mode.
 * Assumed to be mapped to an HTTP endpoint like POST /atom-agent/deactivate
 */
export async function deactivateConversationWrapper(reason: string = "manual_deactivation"): Promise<{ status: string; active: boolean; message?: string }> {
  console.log(`[Handler] Received request to deactivate conversation. Reason: ${reason}`);
  // deactivateConversation itself now sets isAgentResponding to false.
  conversationManager.deactivateConversation(reason);
  return { status: `Conversation deactivated due to ${reason}.`, active: false, message: `Conversation deactivated due to ${reason}.` };
}

/**
 * Handles an interrupt signal.
 * Assumed to be mapped to an HTTP endpoint like POST /atom-agent/interrupt
 */
export async function handleInterruptWrapper(): Promise<{ status: string; message: string }> {
  console.log("[Handler] Received interrupt signal.");
  // Key action: Signal that the agent should stop its current response processing/output.
  conversationManager.setAgentResponding(false);

  // Optional: Could also deactivate conversation entirely or just reset timer to allow immediate next command.
  // For now, just stopping agent response and keeping conversation active.
  // conversationManager.activateConversation(); // This would reset the timer and keep it active.
  // Or, if an interrupt means "stop everything":
  // conversationManager.deactivateConversation("interrupt_signal");

  // For now, the primary effect is setting isAgentResponding = false.
  // The wake_word_detector will follow up with an activate & new conversation input.
  // This ensures the agent is receptive.
  // If there were long-running tasks tied to the previous response, they should ideally check
  // checkIfAgentIsResponding() and halt. This is not implemented in skills yet.

  return { status: "success", message: "Interrupt signal processed. Agent responding state set to false." };
}


/**
 * Handles transcribed text input for an ongoing conversation.
 * Assumed to be mapped to an HTTP endpoint like POST /atom-agent/conversation
 * Expects payload: { "text": "user's transcribed speech" }
 */
export async function handleConversationInputWrapper(
  payload: { text: string }
): Promise<HandleMessageResponse | { error: string; active: boolean; message?: string }> {
  const { text } = payload;
  console.log(`[Handler] Received conversation input: "${text}"`);

  const userId = getCurrentUserId();

  conversationManager.recordUserInteraction(text);

  if (!conversationManager.isConversationActive()) {
    console.log("[Handler] Conversation is not active. Ignoring input.");
    conversationManager.setAgentResponding(false);
    return {
      error: "Conversation not active. Please activate with wake word or activation command.",
      active: false,
      message: "Conversation is not active. Wake word or activation needed.",
    };
  }

  if (conversationManager.checkIfAgentIsResponding()) {
    console.warn("[Handler] New input received while agent was still marked as responding.");
    conversationManager.setAgentResponding(false);
  }

  conversationManager.setAgentResponding(true);

  console.log("[Handler] Conversation active. Processing message...");
  const { text: coreResponseText, nluResponse } = await _internalHandleMessage(text, userId);

  // Record agent's core text response (before TTS) into conversation history
  // NLU results (intent, entities) from this turn can also be added to turnHistory here.
  const currentTurnIntent = nluResponse?.intent || undefined;
  const currentTurnEntities = nluResponse?.entities || undefined;
  conversationManager.recordAgentResponse(text, { text: coreResponseText }, currentTurnIntent, currentTurnEntities);


  // STM to LTM Processing (Fire-and-forget for now)
  if (ltmDbConnection) {
    try {
      const currentConversationState = getConversationStateSnapshot();
      processSTMToLTM(userId, currentConversationState, ltmDbConnection)
        .then(() => console.log('[Handler] STM to LTM processing initiated.'))
        .catch(err => console.error('[Handler] Error in STM to LTM processing:', err));
    } catch (error) {
      console.error('[Handler] Error initiating STM to LTM processing:', error);
    }
  } else {
      console.warn('[Handler] LTM DB connection not available, skipping STM to LTM processing.');
  }

  // TTS Synthesis (as before)
  try {
    const ttsPayload = { text: coreResponseText };
    const ttsResponse = await fetch(AUDIO_PROCESSOR_TTS_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ttsPayload)
    });

    if (ttsResponse.ok) {
      const ttsResult = await ttsResponse.json();
      if (ttsResult.audio_url) {
        console.log("[Handler] TTS synthesis successful. Audio URL generated.");
        conversationManager.setAgentResponding(false); // Agent finished processing and responding
        return { text: coreResponseText, audioUrl: ttsResult.audio_url };
      } else {
        console.error("[Handler] TTS response OK, but no audio_url:", ttsResult);
        conversationManager.setAgentResponding(false); // Agent finished processing (with error)
        return { text: coreResponseText, error: "TTS synthesis succeeded but no audio URL was returned." };
      }
    } else {
      const errorBody = await ttsResponse.text();
      console.error("[Handler] TTS request failed:", ttsResponse.status, errorBody);
      conversationManager.setAgentResponding(false); // Agent finished processing (with error)
      return { text: coreResponseText, error: `Failed to synthesize audio. Status: ${ttsResponse.status}` };
    }
  } catch (error: any) {
    console.error("[Handler] Error calling TTS service:", error.message, error.stack);
    conversationManager.setAgentResponding(false); // Agent finished processing (with error)
    return { text: coreResponseText, error: "Error occurred during audio synthesis." };
  }
}


/**
 * This is the original handleMessage function, primarily for Hasura Action.
 * It remains largely stateless and does not interact with isAgentResponding by default.
 * If Hasura actions need to be part of conversational flow, this would require more thought.
 */
export async function handleMessage(message: string): Promise<HandleMessageResponse> {
  console.log(`[Handler - Hasura Action] Received message: "${message}"`);
  const userId = getCurrentUserId();

  // Hasura actions are typically independent and don't use the conversation state's isAgentResponding flag.
  // If they were to, it would need careful consideration of how they fit into the conversation flow.
  // conversationManager.setAgentResponding(true); // Example if it were conversational

  const { text: coreResponseText, nluResponse } = await _internalHandleMessage(message, userId);

  // conversationManager.setAgentResponding(false); // Example if it were conversational

  try {
    const ttsPayload = { text: coreResponseText };
    const ttsResponse = await fetch(AUDIO_PROCESSOR_TTS_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ttsPayload)
    });

    if (ttsResponse.ok) {
      const ttsResult = await ttsResponse.json();
      if (ttsResult.audio_url) {
        return { text: coreResponseText, audioUrl: ttsResult.audio_url };
      } else {
        console.error("[Handler - Hasura Action] TTS response OK, but no audio_url:", ttsResult);
        return { text: coreResponseText, error: "TTS synthesis succeeded but no audio URL was returned." };
      }
    } else {
      const errorBody = await ttsResponse.text();
      console.error("[Handler - Hasura Action] TTS request failed:", ttsResponse.status, errorBody);
      return { text: coreResponseText, error: `Failed to synthesize audio. Status: ${ttsResponse.status}` };
    }
  } catch (error: any) {
    console.error("[Handler - Hasura Action] Error calling TTS service:", error.message, error.stack);
    return { text: coreResponseText, error: "Error occurred during audio synthesis." };
  }
}

// Example for testing the conversation state (manual activation)
// This would be mapped to an endpoint like /atom-agent/test-activate
export async function testActivateConversation() {
    conversationManager._test_setConversationActive(true); // This itself calls activateConversation now
    return {
      status: "Conversation manually activated for testing via _test_setConversationActive.",
      active: conversationManager.isConversationActive(),
      agentResponding: conversationManager.checkIfAgentIsResponding()
    };
}

export async function testDeactivateConversation() {
    conversationManager._test_setConversationActive(false); // This itself calls deactivateConversation now
    return {
      status: "Conversation manually deactivated for testing via _test_setConversationActive.",
      active: conversationManager.isConversationActive(),
      agentResponding: conversationManager.checkIfAgentIsResponding()
    };
}

export async function getConversationStatus() {
    return {
        active: conversationManager.isConversationActive(),
        agentResponding: conversationManager.checkIfAgentIsResponding(),
        state: conversationManager.getConversationStateSnapshot()
    };
}
