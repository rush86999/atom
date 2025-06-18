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
import { createHubSpotContact } from './skills/hubspotSkills';
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
            // TODO: Date range and event type filter parsing deferred for this phase.
            // For now, event_type_filter will be handled by specific commands if needed e.g. "list google meet events"

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

      case "ListInvoices":
        try {
            const { customer_id, status, limit: nluLimit } = nluResponse.entities;
            const options: { limit?: number; offset?: number; customerId?: string; status?: string } = {limit: 10, offset: 1};
            if (nluLimit) {
                 if (typeof nluLimit === 'number') options.limit = nluLimit;
                 else if (typeof nluLimit === 'string') {
                    const parsed = parseInt(nluLimit, 10);
                    if (!isNaN(parsed)) options.limit = parsed;
                 }
            }
            if (customer_id && typeof customer_id === 'string') options.customerId = customer_id;
            // Note: QuickBooks skill currently doesn't filter by status in list. This is a placeholder.
            // if (status && typeof status === 'string') options.status = status;

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
                return `Error fetching QuickBooks invoices via NLU: ${response.error || 'Unknown error'}.`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "ListInvoices":`, error.message);
            return "Sorry, an error occurred while fetching QuickBooks invoices via NLU.";
        }

      case "GetInvoiceDetails":
        try {
            const { invoice_id } = nluResponse.entities;
            if (!invoice_id || typeof invoice_id !== 'string') {
                return "Invoice ID is required to get QuickBooks invoice details via NLU.";
            }
            const response: GetQuickBooksInvoiceDetailsResponse = await getQuickBooksInvoiceDetails(invoice_id);
            if (response.ok && response.invoice) {
                const inv = response.invoice;
                return `QuickBooks Invoice (ID: ${inv.Id}):\nDoc #: ${inv.DocNumber || 'N/A'}\nCustomer: ${inv.CustomerRef?.name || inv.CustomerRef?.value || 'N/A'}\nTotal: ${inv.TotalAmt !== undefined ? inv.TotalAmt.toFixed(2) : 'N/A'} ${inv.CurrencyRef?.value || ''}`;
            } else {
                return `Error fetching QuickBooks invoice via NLU: ${response.error || 'Unknown error'}.`;
            }
        } catch (error: any) {
            console.error(`Error in NLU Intent "GetInvoiceDetails":`, error.message);
            return "Sorry, an error occurred while fetching QuickBooks invoice details via NLU.";
        }

      default:
        // This case handles intents recognized by NLU but not yet implemented in the switch.
        if (nluResponse.error) { // NLU had an issue but still returned an intent somehow (less likely with current NLU error handling)
             console.log(`NLU processed with intent '${nluResponse.intent}' but also had an error: ${nluResponse.error}`);
        }
        return `I understood your intent as '${nluResponse.intent}' with entities ${JSON.stringify(nluResponse.entities)}, but I'm not fully set up to handle that specific request conversationally yet. You can try specific commands or 'help'.`;
    }
  } else { // NLU returned null intent (but no critical NLU service error)
    // Fallback to existing critical/simple command matching
    // The order of these specific commands is important.
    if (lowerCaseMessage.startsWith('create hubspot contact and dm me details')) {
    const userId = "mock_user_id_from_handler"; // This is assumed to be the Slack User ID for DM purposes.
    const commandPrefix = 'create hubspot contact and dm me details';
    const jsonDetailsString = message.substring(commandPrefix.length).trim();

    if (!jsonDetailsString) {
        return `Please provide contact details in JSON format after "${commandPrefix}". Usage: ${commandPrefix} {"email":"test@example.com","firstname":"Test"}`;
    }

    try {
      let contactDetails: HubSpotContactProperties;
      try {
        contactDetails = JSON.parse(jsonDetailsString);
      } catch (e: any) {
        console.error('Error parsing contact JSON for HubSpot creation (DM flow):', e.message);
        return `Invalid JSON format for contact details: ${e.message}. Please ensure you provide valid JSON.`;
      }

      if (!contactDetails.email) {
        return "The 'email' property is required in the JSON details to create a HubSpot contact.";
      }

      const hubspotResponse: CreateHubSpotContactResponse = await createHubSpotContact(userId, contactDetails);

      if (hubspotResponse.success && hubspotResponse.contactId && hubspotResponse.hubSpotContact) {
        const contact = hubspotResponse.hubSpotContact;
        let name = `${contact.properties.firstname || ''} ${contact.properties.lastname || ''}`.trim();
        if (!name) name = "N/A";

        let slackMessage = `🎉 HubSpot Contact Created!\n`;
        slackMessage += `ID: ${hubspotResponse.contactId}\n`;
        slackMessage += `Name: ${name}\n`;
        slackMessage += `Email: ${contact.properties.email || 'N/A'}\n`;
        if (contact.properties.company) {
          slackMessage += `Company: ${contact.properties.company}\n`;
        }
        if (ATOM_HUBSPOT_PORTAL_ID) {
          slackMessage += `View in HubSpot: https://app.hubspot.com/contacts/${ATOM_HUBSPOT_PORTAL_ID}/contact/${hubspotResponse.contactId}\n`;
        }

        try {
          const slackDmResponse = await sendSlackMessage(userId, userId, slackMessage);
          if (slackDmResponse.ok) {
            return `HubSpot contact created (ID: ${hubspotResponse.contactId}). I've sent the details to your Slack DM!`;
          } else {
            console.error('Failed to send Slack DM for new HubSpot contact:', slackDmResponse.error);
            return `HubSpot contact created (ID: ${hubspotResponse.contactId}), but I couldn't send details to your Slack DM. Slack error: ${slackDmResponse.error}`;
          }
        } catch (slackError: any) {
          console.error('Error sending Slack DM for new HubSpot contact:', slackError.message);
          return `HubSpot contact created (ID: ${hubspotResponse.contactId}), but there was an issue sending the confirmation to Slack: ${slackError.message}`;
        }
      } else {
        return `Failed to create HubSpot contact: ${hubspotResponse.message || 'Unknown HubSpot error. Please check HubSpot configuration and permissions.'}`;
      }
    } catch (error: any) {
      console.error('Error in "create hubspot contact and dm me details" handler:', error.message);
      return `An unexpected error occurred: ${error.message}`;
    }
  } else if (lowerCaseMessage.startsWith('create hubspot contact')) { // Basic channel notification version
    const userId = "mock_user_id_from_handler";
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
      if (!contactDetails.email) {
          return "The 'email' property is required in the JSON details to create a HubSpot contact.";
      }
      const hubspotResponse: CreateHubSpotContactResponse = await createHubSpotContact(userId, contactDetails);
      if (hubspotResponse.success && hubspotResponse.contactId && hubspotResponse.hubSpotContact) {
        const contact = hubspotResponse.hubSpotContact;
        userMessage = `HubSpot contact created successfully! ID: ${hubspotResponse.contactId}. Name: ${contact.properties.firstname || ''} ${contact.properties.lastname || ''}. Email: ${contact.properties.email}.`;
        if (ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID) {
          let slackMessageText = `🎉 New HubSpot Contact Created by Atom Agent! 🎉\n`;
          slackMessageText += `ID: ${hubspotResponse.contactId}\n`;
          // ... (rest of slack message construction as before)
           try {
            await sendSlackMessage(userId, ATOM_SLACK_HUBSPOT_NOTIFICATION_CHANNEL_ID, slackMessageText);
          } catch (slackError: any) { /* log but don't fail user message */ }
        }
      } else {
        userMessage = `Failed to create HubSpot contact: ${hubspotResponse.message || 'An unknown error occurred.'}`;
      }
      return userMessage;
    } catch (error: any) {
      console.error('Error in "create hubspot contact" handler:', error.message);
      return `An unexpected error occurred while creating the HubSpot contact: ${error.message}`;
    }
  } else if (lowerCaseMessage.startsWith('list events')) { // Simple fallback, NLU should catch "GetCalendarEvents"
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
  } else if (lowerCaseMessage.startsWith('list stripe payments')) {
    // const userId = "mock_user_id_from_handler"; // Not directly used by these Stripe skills
    const parts = lowerCaseMessage.split(' '); // e.g. "list stripe payments limit=5 customer=cus_123 starting_after=pi_abc"
    const options: { limit?: number; starting_after?: string; customer?: string } = {};

    parts.forEach(part => {
      if (part.startsWith('limit=')) {
        const limitVal = parseInt(part.split('=')[1], 10);
        if (!isNaN(limitVal)) options.limit = limitVal;
      } else if (part.startsWith('starting_after=')) {
        options.starting_after = part.split('=')[1];
      } else if (part.startsWith('customer=')) {
        options.customer = part.split('=')[1];
      }
    });
    if (options.limit === undefined) options.limit = 10; // Default limit

    try {
      const response: ListStripePaymentsResponse = await listStripePayments(options);
      if (response.ok && response.payments && response.payments.length > 0) {
        let output = "Stripe Payments:\n";
        for (const payment of response.payments) {
          output += `- ID: ${payment.id}, Amount: ${(payment.amount / 100).toFixed(2)} ${payment.currency.toUpperCase()}, Status: ${payment.status}, Created: ${new Date(payment.created * 1000).toLocaleDateString()}${payment.latest_charge?.receipt_url ? `, Receipt: ${payment.latest_charge.receipt_url}` : ''}\n`;
        }
        if (response.has_more && response.payments.length > 0) {
          output += `More payments available. For next page, use option: starting_after=${response.payments[response.payments.length - 1].id}\n`;
        }
        return output;
      } else if (response.ok) {
        return "No Stripe payments found matching your criteria.";
      } else {
        return `Error fetching Stripe payments: ${response.error || 'Unknown error'}`;
      }
    } catch (error: any) {
      console.error('Error in "list stripe payments" command:', error.message);
      return "Sorry, an unexpected error occurred while fetching Stripe payments.";
    }
  } else if (lowerCaseMessage.startsWith('get stripe payment')) {
    const parts = lowerCaseMessage.split(' '); // "get stripe payment <paymentIntentId>"
    if (parts.length < 4) {
      return "Please provide a Stripe PaymentIntent ID. Usage: get stripe payment <paymentIntentId>";
    }
    const paymentIntentId = parts[3];

    try {
      const response: GetStripePaymentDetailsResponse = await getStripePaymentDetails(paymentIntentId);
      if (response.ok && response.payment) {
        const p = response.payment;
        let output = `Stripe Payment Details (ID: ${p.id}):\nAmount: ${(p.amount / 100).toFixed(2)} ${p.currency.toUpperCase()}\nStatus: ${p.status}\nCreated: ${new Date(p.created * 1000).toLocaleString()}\nDescription: ${p.description || 'N/A'}`;
        if (p.customer) output += `\nCustomer ID: ${p.customer}`;
        if (p.latest_charge?.receipt_url) output += `\nReceipt URL: ${p.latest_charge.receipt_url}`;
        // You could add more details from p.latest_charge if needed
        return output;
      } else {
        return `Error fetching Stripe payment details: ${response.error || `PaymentIntent with ID ${paymentIntentId} not found or an unknown error occurred.`}`;
      }
    } catch (error: any) {
      console.error(`Error in "get stripe payment ${paymentIntentId}" command:`, error.message);
      return `Sorry, an unexpected error occurred while fetching Stripe payment details for ${paymentIntentId}.`;
    }
  } else if (lowerCaseMessage.startsWith('qb get auth url')) {
    try {
      const authUri = getQuickBooksAuthUri();
      if (authUri) {
        return `To authorize QuickBooks Online, please visit this URL in your browser: ${authUri}\nAfter authorization, the agent will need the resulting tokens and realmId to be stored in its configured token file path (${ATOM_QB_TOKEN_FILE_PATH}). This step typically requires manual intervention or a separate callback handler not part of this command.`;
      } else {
        return "Could not generate QuickBooks authorization URL. Please check server configuration and ensure QB Client ID, Secret, and Redirect URI are correctly set.";
      }
    } catch (error: any) {
      console.error('Error generating QuickBooks auth URL:', error.message);
      return "Sorry, an error occurred while generating the QuickBooks authorization URL.";
    }
  } else if (lowerCaseMessage.startsWith('list qb invoices')) {
    const parts = lowerCaseMessage.split(' '); // e.g. "list qb invoices limit=10 offset=1 customer=CUST_ID status=Paid"
    const options: { limit?: number; offset?: number; customerId?: string; /* status?: string; TODO: Add status filter if skill supports */ } = {};

    parts.forEach(part => {
      if (part.startsWith('limit=')) {
        const limitVal = parseInt(part.split('=')[1], 10);
        if (!isNaN(limitVal)) options.limit = limitVal;
      } else if (part.startsWith('offset=')) { // QBO uses 1-based offset (called StartPosition)
        const offsetVal = parseInt(part.split('=')[1], 10);
        if (!isNaN(offsetVal)) options.offset = offsetVal;
      } else if (part.startsWith('customer=')) {
        options.customerId = part.split('=')[1];
      }
      // TODO: Add status parsing if listQuickBooksInvoices supports filtering by it (e.g., Paid, Overdue, Open)
      // if (part.startsWith('status=')) options.status = part.split('=')[1];
    });
    if (options.limit === undefined) options.limit = 10;
    if (options.offset === undefined) options.offset = 1;


    try {
      const response: ListQuickBooksInvoicesResponse = await listQuickBooksInvoices(options);
      if (response.ok && response.invoices && response.invoices.length > 0) {
        let output = "QuickBooks Invoices:\n";
        for (const inv of response.invoices) {
          output += `- ID: ${inv.Id}, Num: ${inv.DocNumber || 'N/A'}, Cust: ${inv.CustomerRef?.name || inv.CustomerRef?.value || 'N/A'}, Total: ${inv.TotalAmt !== undefined ? inv.TotalAmt.toFixed(2) : 'N/A'} ${inv.CurrencyRef?.value || ''}, Due: ${inv.DueDate || 'N/A'}, Balance: ${inv.Balance !== undefined ? inv.Balance.toFixed(2) : 'N/A'}\n`;
        }
        if (response.queryResponse) {
          output += `Showing ${response.queryResponse.startPosition || options.offset}-${(response.queryResponse.startPosition || options.offset) + (response.invoices.length -1)} of ${response.queryResponse.totalCount || 'many'}. Max results per page: ${response.queryResponse.maxResults || options.limit}\n`;
        }
        return output;
      } else if (response.ok) {
        return "No QuickBooks invoices found matching your criteria.";
      } else {
        return `Error fetching QuickBooks invoices: ${response.error || 'Unknown error'}. Please ensure the agent is authorized with QuickBooks (use 'qb get auth url').`;
      }
    } catch (error: any) {
      console.error('Error in "list qb invoices" command:', error.message);
      return `An unexpected error occurred while creating the HubSpot contact: ${error.message}`;
    }
  } else if (lowerCaseMessage.startsWith('create hubspot contact and dm me details')) {
    const userId = "mock_user_id_from_handler"; // This is assumed to be the Slack User ID for DM purposes.
    const commandPrefix = 'create hubspot contact and dm me details';
    const jsonDetailsString = message.substring(commandPrefix.length).trim();

    if (!jsonDetailsString) {
        return `Please provide contact details in JSON format after "${commandPrefix}". Usage: ${commandPrefix} {"email":"test@example.com","firstname":"Test"}`;
    }

    try { // Outer try-catch for general errors like JSON parsing or unexpected issues
      let contactDetails: HubSpotContactProperties;
      try {
        contactDetails = JSON.parse(jsonDetailsString);
      } catch (e: any) {
        console.error('Error parsing contact JSON for HubSpot creation (DM flow):', e.message);
        return `Invalid JSON format for contact details: ${e.message}. Please ensure you provide valid JSON.`;
      }

      if (!contactDetails.email) { // Basic validation
        return "The 'email' property is required in the JSON details to create a HubSpot contact.";
      }

      const hubspotResponse: CreateHubSpotContactResponse = await createHubSpotContact(userId, contactDetails);

      if (hubspotResponse.success && hubspotResponse.contactId && hubspotResponse.hubSpotContact) {
        const contact = hubspotResponse.hubSpotContact;
        let name = `${contact.properties.firstname || ''} ${contact.properties.lastname || ''}`.trim();
        if (!name) name = "N/A";

        let slackMessage = `🎉 HubSpot Contact Created!\n`;
        slackMessage += `ID: ${hubspotResponse.contactId}\n`;
        slackMessage += `Name: ${name}\n`;
        slackMessage += `Email: ${contact.properties.email || 'N/A'}\n`;
        if (contact.properties.company) {
          slackMessage += `Company: ${contact.properties.company}\n`;
        }
        if (ATOM_HUBSPOT_PORTAL_ID) {
          slackMessage += `View in HubSpot: https://app.hubspot.com/contacts/${ATOM_HUBSPOT_PORTAL_ID}/contact/${hubspotResponse.contactId}\n`;
        }

        try { // Inner try-catch for the Slack DM part
          const slackDmResponse = await sendSlackMessage(userId, userId, slackMessage); // userId as channel for DM
          if (slackDmResponse.ok) {
            return `HubSpot contact created (ID: ${hubspotResponse.contactId}). I've sent the details to your Slack DM!`;
          } else {
            console.error('Failed to send Slack DM for new HubSpot contact:', slackDmResponse.error);
            return `HubSpot contact created (ID: ${hubspotResponse.contactId}), but I couldn't send details to your Slack DM. Slack error: ${slackDmResponse.error}`;
          }
        } catch (slackError: any) {
          console.error('Error sending Slack DM for new HubSpot contact:', slackError.message);
          return `HubSpot contact created (ID: ${hubspotResponse.contactId}), but there was an issue sending the confirmation to Slack: ${slackError.message}`;
        }
      } else { // HubSpot creation failed
        return `Failed to create HubSpot contact: ${hubspotResponse.message || 'Unknown HubSpot error. Please check HubSpot configuration and permissions.'}`;
      }
    } catch (error: any) { // Catch JSON parsing errors or other unexpected issues
      console.error('Error in "create hubspot contact and dm me details" handler:', error.message);
      return `An unexpected error occurred: ${error.message}`;
    }
  } else if (lowerCaseMessage.startsWith('get qb invoice')) {
    const parts = lowerCaseMessage.split(' '); // "get qb invoice <invoiceId>"
    if (parts.length < 4) {
      return "Please provide a QuickBooks Invoice ID. Usage: get qb invoice <invoiceId>";
    }
    const invoiceId = parts[3];

    try {
      const response: GetQuickBooksInvoiceDetailsResponse = await getQuickBooksInvoiceDetails(invoiceId);
      if (response.ok && response.invoice) {
        const inv = response.invoice;
        let output = `QuickBooks Invoice (ID: ${inv.Id}):\nDoc #: ${inv.DocNumber || 'N/A'}\nCustomer: ${inv.CustomerRef?.name || inv.CustomerRef?.value || 'N/A'}\nTotal: ${inv.TotalAmt !== undefined ? inv.TotalAmt.toFixed(2) : 'N/A'} ${inv.CurrencyRef?.value || ''}, Balance: ${inv.Balance !== undefined ? inv.Balance.toFixed(2) : 'N/A'}\nTxn Date: ${inv.TxnDate || 'N/A'}, Due Date: ${inv.DueDate || 'N/A'}\nEmail: ${inv.BillEmail?.Address || 'N/A'}\nStatus: ${inv.EmailStatus || 'N/A'}\nMemo: ${inv.CustomerMemo || 'N/A'}\nPrivate Note: ${inv.PrivateNote || 'N/A'}`;
        // Could add line item details if needed, but keep it concise for chat.
        // if (inv.Line && inv.Line.length > 0) {
        //   output += "\nLines:";
        //   inv.Line.forEach(line => output += `\n  - ${line.Description || 'Item'} Amount: ${line.Amount}`);
        // }
        return output;
      } else {
        return `Error fetching QuickBooks invoice: ${response.error || `Invoice with ID ${invoiceId} not found or an unknown error occurred.`}`;
      }
    } catch (error: any) {
      console.error(`Error in "get qb invoice ${invoiceId}" command:`, error.message);
    try {
      const parts = message.split(' ');
      const limit = parts.length > 2 && !isNaN(parseInt(parts[2])) ? parseInt(parts[2]) : 10;
      const events: CalendarEvent[] = await listUpcomingEvents(userId, limit);
      if (events.length === 0) {
        return "Could not retrieve calendar events (fallback).";
      }
      const eventList = events.map(event => `- ${event.summary} (${new Date(event.startTime).toLocaleString()})`).join('\n');
      return `Upcoming events (fallback):\n${eventList}`;
    } catch (error:any) { return "Error listing events (fallback)." }
  }
  // Add other very specific non-NLU commands here if necessary, or simple help
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
