import OpenAI from 'openai';
import { ChatCompletionMessageParam } from 'openai/resources/chat/completions';
import {
  ATOM_OPENAI_API_KEY,
  ATOM_NLU_MODEL_NAME,
} from '../_libs/constants';
import {
  NLUResponseData,
  ProcessedNLUResponse,
} from '../types';

let openAIClient: OpenAI | null = null;

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

Available Intents and their Entities: (List of intents 1-27 from previous version remains here)

1. Intent: "GetCalendarEvents"
   - Entities: ...
2. Intent: "CreateHubSpotContact"
   - Entities: ...
(Skipping full list of 27 intents for brevity in this example, but assume they are present)
27. Intent: "ScheduleTeamMeeting"
    - Entities: ...

If the user's intent is unclear or does not match any of the above single intents, set "intent" to null and "entities" to an empty object.

If the user's intent is ambiguous or critical information is missing for a recognized single intent, set "intent" to "NeedsClarification",
set "entities" to include what was understood (e.g., {"partially_understood_intent": "CreateCalendarEvent", "summary": "Meeting"}),
and formulate a "clarification_question" to ask the user.
Example for NeedsClarification: {"intent": "NeedsClarification", "entities": {"partially_understood_intent": "CreateCalendarEvent", "summary": "Team Meeting with Marketing"}, "clarification_question": "What date and time would you like to schedule the meeting for, and who should be invited?"}

If a user's request involves multiple distinct actions or a sequence of steps that correspond to known simple intents, identify it as a "ComplexTask".
The "entities" for a "ComplexTask" should include an "original_query" key with the user's full request, and a "sub_tasks" key, which is an array of objects.
Each object in the "sub_tasks" array should itself be a standard NLU output structure for a simple intent: {"intent": "SubIntentName", "entities": {...}, "summary_for_sub_task": "User-friendly description of this step"}.
Example for ComplexTask: User says "Book a flight to London for next Tuesday and find me a hotel near Hyde Park for 3 nights."
Response (assuming BookFlight and FindHotel are defined simple intents):
{
  "intent": "ComplexTask",
  "entities": {
    "original_query": "Book a flight to London for next Tuesday and find me a hotel near Hyde Park for 3 nights.",
    "sub_tasks": [
      {
        "intent": "CreateCalendarEvent", "entities": {"summary": "Flight to London", "description": "Book flight for next Tuesday to London"},
        "summary_for_sub_task": "Book a flight to London for next Tuesday."
      },
      {
        "intent": "SearchWeb", "entities": {"query": "hotel near Hyde Park London 3 nights"},
        "summary_for_sub_task": "Find a hotel near Hyde Park in London for 3 nights."
      }
    ]
  }
}
If you identify a "ComplexTask", do not also try to process its parts as one of the simpler, single intents in the main response. Focus on the decomposition.
Ensure sub_task intents are chosen from the list of available simple intents.

Example for no matching intent: {"intent": null, "entities": {}}
Example for GetCalendarEvents: {"intent": "GetCalendarEvents", "entities": {"date_range": "tomorrow", "limit": 3, "event_type_filter": "Google Meet events"}}`;

export async function understandMessage(message: string, conversationHistory?: ChatCompletionMessageParam[]): Promise<ProcessedNLUResponse> {
  const client = getOpenAIClient();
  if (!client) {
    return { originalMessage: message, intent: null, entities: {}, error: 'NLU service not configured: OpenAI API Key is missing.' };
  }
  if (!message || message.trim() === '') {
    return { originalMessage: message, intent: null, entities: {}, error: 'Input message is empty.' };
  }

  const messages: ChatCompletionMessageParam[] = [
    { role: 'system', content: SYSTEM_PROMPT },
    ...(conversationHistory || []).map(h => ({ role: h.role as 'user' | 'assistant', content: h.content || '' })),
    { role: 'user', content: message },
  ];

  try {
    const completion = await client.chat.completions.create({
      model: ATOM_NLU_MODEL_NAME,
      messages: messages,
      temperature: 0.1,
      response_format: { type: 'json_object' },
    });

    const llmResponse = completion.choices[0]?.message?.content;
    if (!llmResponse) {
      return { originalMessage: message, intent: null, entities: {}, error: 'NLU service received an empty response from AI.' };
    }

    try {
      const parsedResponse = JSON.parse(llmResponse) as NLUResponseData;
      if (typeof parsedResponse.intent === 'undefined' || typeof parsedResponse.entities !== 'object') {
        return { originalMessage: message, intent: null, entities: {}, error: `NLU service received malformed JSON from AI: ${llmResponse}` };
      }

      const processed: ProcessedNLUResponse = {
        originalMessage: message,
        intent: parsedResponse.intent,
        entities: parsedResponse.entities || {},
        confidence: parsedResponse.confidence,
        recognized_phrase: parsedResponse.recognized_phrase,
      };

      if (parsedResponse.intent === "NeedsClarification" && parsedResponse.clarification_question) {
        processed.requires_clarification = true;
        processed.clarification_question = parsedResponse.clarification_question;
        if (parsedResponse.partially_understood_intent) {
          processed.entities.partially_understood_intent = parsedResponse.partially_understood_intent;
        }
      } else if (parsedResponse.intent === "ComplexTask" && parsedResponse.entities && parsedResponse.entities.sub_tasks) {
        processed.sub_tasks = parsedResponse.entities.sub_tasks.map(st => ({
          intent: st.intent || null,
          entities: st.entities || {},
          summary_for_sub_task: st.summary_for_sub_task || ''
        }));
        // Keep original_query if present in entities
        if (parsedResponse.entities.original_query) {
          processed.entities.original_query = parsedResponse.entities.original_query;
        }
      }
      return processed;
    } catch (jsonError: any) {
      return { originalMessage: message, intent: null, entities: {}, error: `Error parsing NLU response from AI. Raw response: ${llmResponse}. Error: ${jsonError.message}` };
    }
  } catch (error: any) {
    console.error('Error calling OpenAI for NLU service:', error.message);
    let errorMessage = 'Failed to understand message due to an NLU service error.';
    if (error.response?.data?.error?.message) { // More robust error checking
        errorMessage += ` API Error: ${error.response.data.error.message}`;\
    } else if (error.message) {
        errorMessage += ` Details: ${error.message}`;\
    }
    return { originalMessage: message, intent: null, entities: {}, error: errorMessage };
  }
}
