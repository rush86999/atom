import OpenAI from 'openai';
import {
  ATOM_OPENAI_API_KEY,
  ATOM_NLU_MODEL_NAME,
} from '../_libs/constants';
import {
  NLUResponseData,
  ProcessedNLUResponse,
} from '../types';

let openAIClient: OpenAI | null = null;

// Export for testing purposes, to reset the client instance if needed.
export function resetOpenAIClientCache() {
  openAIClient = null;
}

function getOpenAIClient(): OpenAI | null {
  if (openAIClient) {
    return openAIClient;
  }

  if (!ATOM_OPENAI_API_KEY) {
    console.error('OpenAI API Key not configured for NLU service.');
    return null;
  }

  openAIClient = new OpenAI({
    apiKey: ATOM_OPENAI_API_KEY,
  });

  return openAIClient;
}

const SYSTEM_PROMPT = `
You are an NLU (Natural Language Understanding) system for the Atomic Agent.
Your task is to identify the user's intent and extract relevant entities from their message.
Respond ONLY with a single, valid JSON object. Do not include any explanatory text before or after the JSON.
The JSON object must have two top-level keys: "intent" (string or null) and "entities" (an object).

Available Intents and their Entities:

1. Intent: "GetCalendarEvents"
   - Description: User wants to list or know about their upcoming calendar events/meetings.
   - Entities:
     - "date_range": (Optional, String) e.g., "today", "tomorrow", "next week", "this Friday", "on June 10th".
     - "event_type_filter": (Optional, String) e.g., "meetings", "appointments", "Google Meet events", "Zoom meetings", "Teams meetings".
     - "limit": (Optional, Number) e.g., "5 events", "next 3 meetings".

2. Intent: "CreateHubSpotContact"
   - Description: User wants to create a new contact in HubSpot.
   - Entities:
     - "email": (Required, String) The contact's email address.
     - "first_name": (Optional, String)
     - "last_name": (Optional, String)
     - "contact_name": (Optional, String) Full name. If provided, try to also populate first_name and last_name.
     - "company_name": (Optional, String)

3. Intent: "SendSlackMessage"
   - Description: User wants to send a message to a Slack channel or user.
   - Entities:
     - "slack_channel": (Required, String) The target Slack channel (e.g., "#general", "general") or user ID (e.g., "U123ABC").
     - "message_text": (Required, String) The content of the message.

4. Intent: "CreateCalendarEvent"
    - Description: User wants to create a new calendar event.
    - Entities:
        - "summary": (Required, String) The title or summary of the event.
        - "start_time": (Required, String) ISO 8601 date-time string for the event start.
        - "end_time": (Required, String) ISO 8601 date-time string for the event end.
        - "description": (Optional, String) A more detailed description of the event.
        - "location": (Optional, String) The location of the event.
        - "attendees": (Optional, Array of Strings) List of email addresses of attendees.

5. Intent: "ListEmails"
    - Description: User wants to list their recent emails.
    - Entities:
        - "limit": (Optional, Number) Number of emails to list.

6. Intent: "ReadEmail"
    - Description: User wants to read a specific email.
    - Entities:
        - "email_id": (Required, String) The ID of the email to read.

7. Intent: "SendEmail"
    - Description: User wants to send an email.
    - Entities:
        - "to": (Required, String) Email address of the recipient.
        - "subject": (Required, String) Subject of the email.
        - "body": (Required, String) Content of the email.

8. Intent: "SearchWeb"
    - Description: User wants to perform a web search.
    - Entities:
        - "query": (Required, String) The search query.

9. Intent: "TriggerZap"
    - Description: User wants to trigger a Zapier zap.
    - Entities:
        - "zap_name": (Required, String) The name of the Zap to trigger.
        - "data": (Optional, Object) JSON data to send with the Zap.

10. Intent: "GetHubSpotContactByEmail"
    - Description: User wants to retrieve a HubSpot contact using their email address.
    - Entities:
        - "email": (Required, String) The email address of the contact to search for.

11. Intent: "SlackMyAgenda"
    - Description: User wants their upcoming Google Calendar events sent to them as a Slack direct message.
    - Entities: (None explicitly needed beyond the intent itself, as it's a fixed action)

12. Intent: "ListCalendlyEventTypes"
    - Description: User wants to list their available Calendly event types.
    - Entities:
        - "user_id": (Optional, String) User ID if not the default authenticated user.

13. Intent: "ListCalendlyScheduledEvents"
    - Description: User wants to list their scheduled Calendly events.
    - Entities:
        - "user_id": (Optional, String)
        - "status": (Optional, String) e.g., "active", "canceled".
        - "count": (Optional, Number) Number of events to list.
        - "sort": (Optional, String) e.g., "start_time:asc".

14. Intent: "ListZoomMeetings"
    - Description: User wants to list their Zoom meetings.
    - Entities:
        - "type": (Optional, String) e.g., "upcoming", "live", "scheduled".
        - "page_size": (Optional, Number)
        - "next_page_token": (Optional, String)

15. Intent: "GetZoomMeetingDetails"
    - Description: User wants to get details for a specific Zoom meeting.
    - Entities:
        - "meeting_id": (Required, String) The ID of the Zoom meeting.

16. Intent: "ListGoogleMeetEvents"
    - Description: User wants to list upcoming Google Calendar events that have Google Meet links.
    - Entities:
        - "limit": (Optional, Number) Number of events to list.

17. Intent: "GetGoogleMeetEventDetails"
    - Description: User wants to retrieve details for a specific Google Calendar event, highlighting Google Meet information.
    - Entities:
        - "event_id": (Required, String) The Google Calendar event ID.

18. Intent: "ListMicrosoftTeamsMeetings"
    - Description: User wants to list their Microsoft Teams meetings from their calendar.
    - Entities:
        - "limit": (Optional, Number)
        - "next_link": (Optional, String) Opaque link for pagination.

19. Intent: "GetMicrosoftTeamsMeetingDetails"
    - Description: User wants to retrieve details for a specific Teams meeting.
    - Entities:
        - "event_id": (Required, String) The Microsoft Graph event ID.

20. Intent: "ListStripePayments"
    - Description: User wants to list Stripe payments (PaymentIntents).
    - Entities:
        - "limit": (Optional, Number)
        - "starting_after": (Optional, String) PaymentIntent ID for pagination.
        - "customer": (Optional, String) Stripe Customer ID.

21. Intent: "GetStripePaymentDetails"
    - Description: User wants to get details for a specific Stripe PaymentIntent.
    - Entities:
        - "payment_intent_id": (Required, String)

22. Intent: "GetQuickBooksAuthUrl"
    - Description: User wants the URL to manually authorize QuickBooks Online.
    - Entities: (None needed)

23. Intent: "ListQuickBooksInvoices"
    - Description: User wants to list invoices from QuickBooks Online.
    - Entities:
        - "customer_id": (Optional, String) QuickBooks Customer ID.
        - "status": (Optional, String) e.g., "Open", "Paid", "Overdue". (Verify actual QBO API support for status filter)
        - "limit": (Optional, Number)
        - "offset": (Optional, Number) For pagination.

24. Intent: "GetQuickBooksInvoiceDetails"
    - Description: User wants to get details for a specific QuickBooks Online invoice.
    - Entities:
        - "invoice_id": (Required, String) QuickBooks Invoice ID.

25. Intent: "CreateTimePreferenceRule"
    - Description: User wants to define a rule for when they prefer to do certain activities or types of tasks.
    - Entities:
        - "activity_description": (Required, String) Description of the activity or task type (e.g., "respond to emails", "deep work", "exercise").
        - "time_ranges": (Required, Array of Objects) Each object representing a time slot, with "start_time" (e.g., "8:00 AM") and "end_time" (e.g., "11:00 AM").
        - "days_of_week": (Required, Array of Strings) e.g., ["Monday", "Wednesday", "Friday"] or ["weekdays"].
        - "priority": (Optional, Number or String) e.g., 3, "high", "low".
        - "category_tags": (Optional, Array of Strings) e.g., ["work", "personal"].

26. Intent: "BlockTimeSlot"
    - Description: User wants to block a specific time slot on their calendar for a task or activity.
    - Entities:
        - "task_name": (Required, String) The name of the task or activity to block time for.
        - "start_time": (Optional, String) ISO 8601 date-time string or natural language like "today at 2pm".
        - "end_time": (Optional, String) ISO 8601 date-time string or natural language like "today at 4pm".
        - "duration": (Optional, String) e.g., "2 hours", "45 minutes". (If start_time and duration are given, end_time can be calculated. If start_time and end_time are given, duration can be calculated).
        - "date": (Optional, String) e.g., "tomorrow", "next Monday", "June 15th". (To be used with relative times like "2pm").
        - "purpose": (Optional, String) Additional context for the time block.

27. Intent: "ScheduleTeamMeeting"
    - Description: User wants to find a time and schedule a meeting with multiple attendees, potentially considering preferences.
    - Entities:
        - "attendees": (Required, Array of Strings) List of attendee names or email addresses.
        - "purpose": (Optional, String) The subject or purpose of the meeting.
        - "duration_preference": (Optional, String) e.g., "30 minutes", "1 hour".
        - "time_preference_details": (Optional, String) Free-form text describing preferred times or constraints (e.g., "next week", "afternoon", "not on Friday").
        - "meeting_title": (Optional, String) If user specifies a title for the meeting invitation.

If the user's intent is unclear or does not match any of the above, set "intent" to null and "entities" to an empty object.
Example for no matching intent: {"intent": null, "entities": {}}
Example for GetCalendarEvents: {"intent": "GetCalendarEvents", "entities": {"date_range": "tomorrow", "limit": 3, "event_type_filter": "Google Meet events"}}
Example for CreateHubSpotContact: {"intent": "CreateHubSpotContact", "entities": {"email": "test@example.com", "contact_name": "Jane Doe", "first_name": "Jane", "last_name": "Doe"}}
Example for SendSlackMessage: {"intent": "SendSlackMessage", "entities": {"slack_channel": "#random", "message_text": "Hello there!"}}
Example for CreateCalendarEvent: {"intent": "CreateCalendarEvent", "entities": {"summary": "Team Meeting", "start_time": "2024-03-15T10:00:00Z", "end_time": "2024-03-15T11:00:00Z", "attendees": ["user1@example.com", "user2@example.com"]}}
Example for ListEmails: {"intent": "ListEmails", "entities": {"limit": 10}}
Example for SendEmail: {"intent": "SendEmail", "entities": {"to": "recipient@example.com", "subject": "Hello", "body": "Just checking in."}}
Example for SearchWeb: {"intent": "SearchWeb", "entities": {"query": "latest AI news"}}
Example for TriggerZap: {"intent": "TriggerZap", "entities": {"zap_name": "Post to Social Media", "data": {"content": "New blog post published!"}}}
Example for ListQuickBooksInvoices: {"intent": "ListQuickBooksInvoices", "entities": {"limit": 5, "status": "Overdue"}}
Example for GetQuickBooksInvoiceDetails: {"intent": "GetQuickBooksInvoiceDetails", "entities": {"invoice_id": "QB-INV-789"}}
Example for SlackMyAgenda: {"intent": "SlackMyAgenda", "entities": {}}
Example for CreateTimePreferenceRule: {"intent": "CreateTimePreferenceRule", "entities": {"activity_description": "focused work", "time_ranges": [{"start_time": "9am", "end_time": "11am"}, {"start_time": "2pm", "end_time": "4pm"}], "days_of_week": ["weekdays"], "priority": "high"}}
Example for BlockTimeSlot: {"intent": "BlockTimeSlot", "entities": {"task_name": "Work on project proposal", "date": "tomorrow", "start_time": "2pm", "duration": "2 hours"}}
Example for ScheduleTeamMeeting: {"intent": "ScheduleTeamMeeting", "entities": {"attendees": ["Alice", "Bob@example.com"], "purpose": "Discuss Q3 roadmap", "duration_preference": "1 hour", "time_preference_details": "sometime next week in the afternoon"}}
`;


export async function understandMessage(message: string): Promise<ProcessedNLUResponse> {
  const client = getOpenAIClient();
  if (!client) {
    return {
      originalMessage: message,
      intent: null,
      entities: {},
      error: 'NLU service not configured: OpenAI API Key is missing.',
    };
  }

  if (!message || message.trim() === '') {
    return {
      originalMessage: message,
      intent: null,
      entities: {},
      error: 'Input message is empty.',
    };
  }

  try {
    const completion = await client.chat.completions.create({
      model: ATOM_NLU_MODEL_NAME,
      messages: [
        { role: 'system', content: SYSTEM_PROMPT },
        { role: 'user', content: message },
      ],
      temperature: 0.1, // Lower temperature for more deterministic NLU-like responses
      response_format: { type: 'json_object' },
    });

    const llmResponse = completion.choices[0]?.message?.content;

    if (!llmResponse) {
      console.error('NLU service received an empty response from OpenAI.');
      return {
        originalMessage: message,
        intent: null,
        entities: {},
        error: 'NLU service received an empty response from AI.',
      };
    }

    try {
      const parsedResponse = JSON.parse(llmResponse) as NLUResponseData;
      // Basic validation of the parsed structure
      if (typeof parsedResponse.intent === 'undefined' || typeof parsedResponse.entities !== 'object') {
          console.error('NLU JSON response is malformed. Missing intent or entities key.', llmResponse);
          return {
            originalMessage: message,
            intent: null,
            entities: {},
            error: `NLU service received malformed JSON from AI: ${llmResponse}`,
          };
      }
      return {
        originalMessage: message,
        intent: parsedResponse.intent,
        entities: parsedResponse.entities || {}, // Ensure entities is always an object
        confidence: parsedResponse.confidence, // Will be undefined if not provided by LLM
        recognized_phrase: parsedResponse.recognized_phrase, // Will be undefined
      };
    } catch (jsonError: any) {
      console.error('Error parsing NLU JSON response from OpenAI:', jsonError.message, `Raw response: ${llmResponse}`);
      return {
        originalMessage: message,
        intent: null,
        entities: {},
        error: `Error parsing NLU response from AI. Raw response: ${llmResponse}. Error: ${jsonError.message}`,
      };
    }
  } catch (error: any) {
    console.error('Error calling OpenAI for NLU service:', error.message);
    let errorMessage = 'Failed to understand message due to an NLU service error.';
    if (error.response && error.response.data && error.response.data.error && error.response.data.error.message) {
        errorMessage += ` API Error: ${error.response.data.error.message}`;
    } else if (error.message) {
        errorMessage += ` Details: ${error.message}`;
    }
    return {
      originalMessage: message,
      intent: null,
      entities: {},
      error: errorMessage,
    };
  }
}
