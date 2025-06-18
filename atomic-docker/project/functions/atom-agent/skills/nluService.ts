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

4. Intent: "ListInvoices"
    - Description: User wants to list invoices, potentially from QuickBooks.
    - Entities:
        - "customer_id": (Optional, String) e.g., "customer 123", "for John Doe's account".
        - "status": (Optional, String) e.g., "open", "paid", "overdue".
        - "limit": (Optional, Number) e.g., "last 10 invoices".

5. Intent: "GetInvoiceDetails"
    - Description: User wants to get details for a specific invoice.
    - Entities:
        - "invoice_id": (Required, String) e.g., "invoice 456", "for INV-003".

If the user's intent is unclear or does not match any of the above, set "intent" to null and "entities" to an empty object.
Example for no matching intent: {"intent": null, "entities": {}}
Example for GetCalendarEvents: {"intent": "GetCalendarEvents", "entities": {"date_range": "tomorrow", "limit": 3, "event_type_filter": "Google Meet events"}}
Example for CreateHubSpotContact: {"intent": "CreateHubSpotContact", "entities": {"email": "test@example.com", "contact_name": "Jane Doe", "first_name": "Jane", "last_name": "Doe"}}
Example for SendSlackMessage: {"intent": "SendSlackMessage", "entities": {"slack_channel": "#random", "message_text": "Hello there!"}}
Example for ListInvoices: {"intent": "ListInvoices", "entities": {"limit": 5, "status": "overdue"}}
Example for GetInvoiceDetails: {"intent": "GetInvoiceDetails", "entities": {"invoice_id": "QB-INV-789"}}
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
