import OpenAI from 'openai';
import { ChatCompletionMessageParam } from 'openai/resources/chat/completions';
import { ATOM_OPENAI_API_KEY, ATOM_NLU_MODEL_NAME } from '../_libs/constants';
import { logger } from '../../_utils/logger';

// Interface for structured Microsoft Teams search queries
export interface StructuredMSTeamsQuery {
  fromUser?: string; // Sender's name or email (Graph search can often resolve names)
  inChatOrChannel?: string; // Chat ID, Channel ID, or name (e.g., "General", "Project Alpha Chat with Bob")
  mentionsUser?: string; // User mentioned (name or email)
  hasFile?: boolean; // True if files/attachments are mentioned
  hasLink?: boolean; // True if links are mentioned (less common as direct KQL, might be part of textKeywords)
  onDate?: string; // Specific date in YYYY-MM-DD format.
  beforeDate?: string; // Before this date (YYYY-MM-DD).
  afterDate?: string; // After this date (YYYY-MM-DD).
  textKeywords?: string; // General keywords for message content.
  subjectContains?: string; // For channel messages that might have a subject.
  exactPhrase?: string; // An exact phrase to search for.
}

let openAIClientForMSTeamsQueryUnderstanding: OpenAI | null = null;

function getOpenAIClient(): OpenAI {
  if (openAIClientForMSTeamsQueryUnderstanding) {
    return openAIClientForMSTeamsQueryUnderstanding;
  }
  if (!ATOM_OPENAI_API_KEY) {
    logger.error(
      '[LLMMSTeamsQueryUnderstander] OpenAI API Key (ATOM_OPENAI_API_KEY) is not configured.'
    );
    throw new Error(
      'OpenAI API Key not configured for LLM MS Teams Query Understander.'
    );
  }
  openAIClientForMSTeamsQueryUnderstanding = new OpenAI({
    apiKey: ATOM_OPENAI_API_KEY,
  });
  logger.info('[LLMMSTeamsQueryUnderstander] OpenAI client initialized.');
  return openAIClientForMSTeamsQueryUnderstanding;
}

// System prompt for MS Teams query understanding. {{CURRENT_DATE}} will be replaced.
// Microsoft Graph Search API uses Keyword Query Language (KQL) or natural language queries.
// This prompt aims for structured output that can then be easily converted to a KQL query or parts of a search request.
const MSTEAMS_QUERY_UNDERSTANDING_SYSTEM_PROMPT = `
You are an expert system that converts a user's natural language request about finding Microsoft Teams messages into a structured JSON object.
Respond ONLY with a single, valid JSON object. Do not include any explanatory text before or after the JSON.
The JSON object should conform to the 'StructuredMSTeamsQuery' interface:
interface StructuredMSTeamsQuery {
  fromUser?: string;          // Sender's name or email (e.g., "John Doe", "john.doe@example.com").
  inChatOrChannel?: string;   // Name of the chat (e.g., "Chat with Jane", "Project Discussion") or channel (e.g., "General", "Q4 Planning").
  mentionsUser?: string;      // User mentioned in the message (name or email).
  hasFile?: boolean;          // True if files/attachments are mentioned.
  hasLink?: boolean;          // True if links are mentioned.
  onDate?: string;            // Specific date in YYYY-MM-DD. Current date is {{CURRENT_DATE}}.
  beforeDate?: string;        // Before this date (YYYY-MM-DD).
  afterDate?: string;         // After this date (YYYY-MM-DD).
  textKeywords?: string;      // Keywords for message content. Combine multiple concepts if appropriate.
  subjectContains?: string;   // Keywords for the subject of a channel message.
  exactPhrase?: string;       // An exact phrase if specified (e.g., "search for 'urgent review needed'").
}

Guidelines for date inference (Current Date: {{CURRENT_DATE}}):
- "yesterday": 'onDate' for yesterday's date.
- "today": 'onDate' for today's date.
- "last week": 'afterDate' for the start of the previous calendar week (e.g., Monday) and 'beforeDate' for its end (e.g., Sunday).
- "this week": 'afterDate' for the start of the current calendar week and 'beforeDate' for its end.
- "on [DayOfWeek]": e.g., "on Monday". If in the past, use the most recent Monday. If a future Monday, use that. Set 'onDate'.
- "in [MonthName]": e.g., "in July". If year not specified, assume current year. Set 'afterDate' for month start, 'beforeDate' for month end.
- "since [Date/Event]": e.g., "since last Tuesday". Set 'afterDate'.
- "until [Date/Event]" or "before [Date/Event]": Set 'beforeDate'.

Examples:
- "Teams messages from Bob about the budget in 'Marketing Campaign Chat' last Monday"
  -> {"fromUser": "Bob", "textKeywords": "budget", "inChatOrChannel": "Marketing Campaign Chat", "onDate": "YYYY-MM-DD (last Monday's date)"}
- "find messages with an Excel file shared by alice@contoso.com two weeks ago"
  -> {"hasFile": true, "fromUser": "alice@contoso.com", "textKeywords": "Excel", "afterDate": "YYYY-MM-DD (start of 2 weeks ago)", "beforeDate": "YYYY-MM-DD (end of 2 weeks ago)"}
- "search for 'client feedback' in the General channel of Project X team"
  -> {"exactPhrase": "client feedback", "inChatOrChannel": "Project X General"} (Assume channel name implies team if specific enough)
- "messages mentioning me with a link"
  -> {"mentionsUser": "me", "hasLink": true}

Only include keys in the JSON if the information is present or clearly implied.
If the request is very vague (e.g., "find Teams messages"), return an empty JSON object {}.
If user says "mentioning me", use "me" for mentionsUser. The system will resolve "me" to the actual user ID.
`;

/**
 * Uses an LLM to understand a natural language MS Teams query and transform it
 * into a StructuredMSTeamsQuery object.
 * @param rawUserQuery The user's natural language query about finding Teams messages.
 * @returns A Promise resolving to a Partial<StructuredMSTeamsQuery> object.
 */
export async function understandMSTeamsSearchQueryLLM(
  rawUserQuery: string
): Promise<Partial<StructuredMSTeamsQuery>> {
  const client = getOpenAIClient();
  const now = new Date();
  const year = now.getFullYear();
  const month = (now.getMonth() + 1).toString().padStart(2, '0');
  const day = now.getDate().toString().padStart(2, '0');
  const currentDate = `${year}-${month}-${day}`; // YYYY-MM-DD

  const systemPromptWithDate =
    MSTEAMS_QUERY_UNDERSTANDING_SYSTEM_PROMPT.replace(
      /{{CURRENT_DATE}}/g,
      currentDate
    );

  const messages: ChatCompletionMessageParam[] = [
    { role: 'system', content: systemPromptWithDate },
    { role: 'user', content: rawUserQuery },
  ];

  logger.debug(
    `[LLMMSTeamsQueryUnderstander] Processing query: "${rawUserQuery}" with current date ${currentDate}`
  );

  try {
    const completion = await client.chat.completions.create({
      model: ATOM_NLU_MODEL_NAME,
      messages: messages,
      temperature: 0.1,
      response_format: { type: 'json_object' },
    });

    const llmResponse = completion.choices[0]?.message?.content;
    if (!llmResponse) {
      logger.error(
        '[LLMMSTeamsQueryUnderstander] Received an empty response from AI.'
      );
      throw new Error(
        'LLM MS Teams Query Understander: Empty response from AI.'
      );
    }

    logger.debug(
      '[LLMMSTeamsQueryUnderstander] Raw LLM JSON response:',
      llmResponse
    );
    let parsedResponse = JSON.parse(llmResponse);

    const cleanedResponse: Partial<StructuredMSTeamsQuery> = {};
    for (const key in parsedResponse) {
      if (
        Object.prototype.hasOwnProperty.call(parsedResponse, key) &&
        parsedResponse[key] !== null &&
        parsedResponse[key] !== ''
      ) {
        // @ts-ignore
        cleanedResponse[key] = parsedResponse[key];
      }
    }

    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    if (cleanedResponse.onDate && !dateRegex.test(cleanedResponse.onDate)) {
      logger.warn(
        `[LLMMSTeamsQueryUnderstander] LLM provided 'onDate' in unexpected format: ${cleanedResponse.onDate}. Discarding.`
      );
      delete cleanedResponse.onDate;
    }
    if (
      cleanedResponse.beforeDate &&
      !dateRegex.test(cleanedResponse.beforeDate)
    ) {
      logger.warn(
        `[LLMMSTeamsQueryUnderstander] LLM provided 'beforeDate' in unexpected format: ${cleanedResponse.beforeDate}. Discarding.`
      );
      delete cleanedResponse.beforeDate;
    }
    if (
      cleanedResponse.afterDate &&
      !dateRegex.test(cleanedResponse.afterDate)
    ) {
      logger.warn(
        `[LLMMSTeamsQueryUnderstander] LLM provided 'afterDate' in unexpected format: ${cleanedResponse.afterDate}. Discarding.`
      );
      delete cleanedResponse.afterDate;
    }

    logger.info(
      '[LLMMSTeamsQueryUnderstander] Cleaned structured MS Teams query:',
      cleanedResponse
    );
    return cleanedResponse;
  } catch (error: any) {
    logger.error(
      '[LLMMSTeamsQueryUnderstander] Error processing MS Teams search query with OpenAI:',
      error.message
    );
    if (error instanceof SyntaxError) {
      logger.error(
        '[LLMMSTeamsQueryUnderstander] Failed to parse JSON response from LLM:',
        llmResponse
      );
      throw new Error(
        'LLM MS Teams Query Understander: Failed to parse response from AI.'
      );
    }
    if (error.response?.data?.error?.message) {
      throw new Error(
        `LLM MS Teams Query Understander: API Error - ${error.response.data.error.message}`
      );
    }
    throw new Error(
      `LLM MS Teams Query Understander: Failed to understand MS Teams search query. ${error.message}`
    );
  }
}
