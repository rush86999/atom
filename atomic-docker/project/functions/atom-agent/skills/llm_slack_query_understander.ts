import OpenAI from 'openai';
import { ChatCompletionMessageParam } from 'openai/resources/chat/completions';
import { ATOM_OPENAI_API_KEY, ATOM_NLU_MODEL_NAME } from '../_libs/constants';
import { logger } from '../../_utils/logger';

// Interface for structured Slack search queries
export interface StructuredSlackQuery {
  fromUser?: string;      // Slack user ID or display name. Resolve to ID if possible before API query.
  inChannel?: string;     // Slack channel ID or name. Resolve to ID if possible.
  mentionsUser?: string;  // Slack user ID or display name mentioned.
  hasFile?: boolean;
  hasLink?: boolean;
  hasReaction?: string;   // Emoji code for reaction (e.g., :thumbsup:)
  onDate?: string;        // Date in YYYY-MM-DD format.
  beforeDate?: string;    // Date in YYYY-MM-DD format.
  afterDate?: string;     // Date in YYYY-MM-DD format.
  textKeywords?: string;  // General keywords for message text.
  exactPhrase?: string;   // An exact phrase to search for.
}

let openAIClientForSlackQueryUnderstanding: OpenAI | null = null;

function getOpenAIClient(): OpenAI {
  if (openAIClientForSlackQueryUnderstanding) {
    return openAIClientForSlackQueryUnderstanding;
  }
  if (!ATOM_OPENAI_API_KEY) {
    logger.error('[LLMSlackQueryUnderstander] OpenAI API Key (ATOM_OPENAI_API_KEY) is not configured.');
    throw new Error('OpenAI API Key not configured for LLM Slack Query Understander.');
  }
  openAIClientForSlackQueryUnderstanding = new OpenAI({ apiKey: ATOM_OPENAI_API_KEY });
  logger.info('[LLMSlackQueryUnderstander] OpenAI client initialized.');
  return openAIClientForSlackQueryUnderstanding;
}

// System prompt for Slack query understanding. {{CURRENT_DATE}} will be replaced.
const SLACK_QUERY_UNDERSTANDING_SYSTEM_PROMPT = `
You are an expert system that converts a user's natural language request about finding Slack messages into a structured JSON object.
Respond ONLY with a single, valid JSON object. Do not include any explanatory text before or after the JSON.
The JSON object should conform to the 'StructuredSlackQuery' interface:
interface StructuredSlackQuery {
  fromUser?: string;      // User who sent the message (e.g., "John Doe", "@john").
  inChannel?: string;     // Channel where the message was posted (e.g., "#general", "project-alpha").
  mentionsUser?: string;  // User mentioned in the message (e.g., "mentioning @jane").
  hasFile?: boolean;      // True if files/attachments are mentioned (e.g., "messages with files", "shared a document").
  hasLink?: boolean;      // True if links are mentioned.
  hasReaction?: string;   // Emoji code if a reaction is specified (e.g., "with a :thumbsup:", "reacted with smile").
  onDate?: string;        // Specific date in YYYY-MM-DD. Current date is {{CURRENT_DATE}}.
  beforeDate?: string;    // Before this date (YYYY-MM-DD).
  afterDate?: string;     // After this date (YYYY-MM-DD).
  textKeywords?: string;  // Keywords for message text. Combine multiple concepts if appropriate.
  exactPhrase?: string;   // An exact phrase to search for (e.g., if user says "search for 'important update'").
}

Guidelines for date inference (Current Date: {{CURRENT_DATE}}):
- "yesterday": 'onDate' for yesterday's date.
- "today": 'onDate' for today's date.
- "last week": 'afterDate' for the start of the previous calendar week (e.g., Monday) and 'beforeDate' for the end of it (e.g., Sunday).
- "this week": 'afterDate' for the start of the current calendar week and 'beforeDate' for its end.
- "on [DayOfWeek]": e.g., "on Monday". If in the past, use the most recent Monday. If a future Monday, use that. Set 'onDate'.
- "in [MonthName]": e.g., "in July". If year not specified, assume current year. Set 'afterDate' for month start, 'beforeDate' for month end.
- "since [Date/Event]": e.g., "since last Tuesday". Set 'afterDate'.
- "until [Date/Event]" or "before [Date/Event]": Set 'beforeDate'.

Examples:
- "messages from @bob about the Q1 report in #marketing yesterday"
  -> {"fromUser": "@bob", "textKeywords": "Q1 report", "inChannel": "#marketing", "onDate": "YYYY-MM-DD (yesterday's date)"}
- "find messages with a PDF sent by Jane last month"
  -> {"hasFile": true, "fromUser": "Jane", "afterDate": "YYYY-MM-DD (start of last month)", "beforeDate": "YYYY-MM-DD (end of last month)", "textKeywords": "PDF"}
- "search for 'project deadline' in DMs with @alice"
  -> {"exactPhrase": "project deadline", "inChannel": "@alice"} (DMs can be treated as channels with user names)
- "messages that have a :party_popper: reaction"
  -> {"hasReaction": ":party_popper:"}

Only include keys in the JSON if the information is present or clearly implied.
If a user mentions a name for 'fromUser', 'inChannel' (for DMs), or 'mentionsUser', keep it as the name. The system will try to resolve it to an ID later.
If the request is very vague (e.g., "find messages"), return an empty JSON object {}.
`;

/**
 * Uses an LLM to understand a natural language Slack query and transform it
 * into a StructuredSlackQuery object.
 * @param rawUserQuery The user's natural language query about finding Slack messages.
 * @returns A Promise resolving to a Partial<StructuredSlackQuery> object.
 */
export async function understandSlackSearchQueryLLM(rawUserQuery: string): Promise<Partial<StructuredSlackQuery>> {
  const client = getOpenAIClient();
  const now = new Date();
  const year = now.getFullYear();
  const month = (now.getMonth() + 1).toString().padStart(2, '0');
  const day = now.getDate().toString().padStart(2, '0');
  const currentDate = `${year}-${month}-${day}`; // YYYY-MM-DD

  const systemPromptWithDate = SLACK_QUERY_UNDERSTANDING_SYSTEM_PROMPT.replace(/{{CURRENT_DATE}}/g, currentDate);

  const messages: ChatCompletionMessageParam[] = [
    { role: 'system', content: systemPromptWithDate },
    { role: 'user', content: rawUserQuery },
  ];

  logger.debug(`[LLMSlackQueryUnderstander] Processing query: "${rawUserQuery}" with current date ${currentDate}`);

  try {
    const completion = await client.chat.completions.create({
      model: ATOM_NLU_MODEL_NAME, // Or a more capable model like "gpt-3.5-turbo-1106" or "gpt-4" for better JSON
      messages: messages,
      temperature: 0.1,
      response_format: { type: 'json_object' },
    });

    const llmResponse = completion.choices[0]?.message?.content;
    if (!llmResponse) {
      logger.error('[LLMSlackQueryUnderstander] Received an empty response from AI.');
      throw new Error('LLM Slack Query Understander: Empty response from AI.');
    }

    logger.debug('[LLMSlackQueryUnderstander] Raw LLM JSON response:', llmResponse);
    let parsedResponse = JSON.parse(llmResponse);

    // Clean up null/empty values
    const cleanedResponse: Partial<StructuredSlackQuery> = {};
    for (const key in parsedResponse) {
      if (Object.prototype.hasOwnProperty.call(parsedResponse, key) &&
          parsedResponse[key] !== null &&
          parsedResponse[key] !== "") {
        // @ts-ignore - assigning to potentially different types, but keys should match
        cleanedResponse[key] = parsedResponse[key];
      }
    }
    // Validate date formats if LLM doesn't strictly adhere
    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    if (cleanedResponse.onDate && !dateRegex.test(cleanedResponse.onDate)) {
        logger.warn(`[LLMSlackQueryUnderstander] LLM provided 'onDate' in unexpected format: ${cleanedResponse.onDate}. Discarding.`);
        delete cleanedResponse.onDate;
    }
    if (cleanedResponse.beforeDate && !dateRegex.test(cleanedResponse.beforeDate)) {
        logger.warn(`[LLMSlackQueryUnderstander] LLM provided 'beforeDate' in unexpected format: ${cleanedResponse.beforeDate}. Discarding.`);
        delete cleanedResponse.beforeDate;
    }
    if (cleanedResponse.afterDate && !dateRegex.test(cleanedResponse.afterDate)) {
        logger.warn(`[LLMSlackQueryUnderstander] LLM provided 'afterDate' in unexpected format: ${cleanedResponse.afterDate}. Discarding.`);
        delete cleanedResponse.afterDate;
    }


    logger.info('[LLMSlackQueryUnderstander] Cleaned structured Slack query:', cleanedResponse);
    return cleanedResponse;

  } catch (error: any) {
    logger.error('[LLMSlackQueryUnderstander] Error processing Slack search query with OpenAI:', error.message);
    if (error instanceof SyntaxError) {
        logger.error('[LLMSlackQueryUnderstander] Failed to parse JSON response from LLM:', llmResponse);
        throw new Error('LLM Slack Query Understander: Failed to parse response from AI.');
    }
    if (error.response?.data?.error?.message) { // Axios-style error
        throw new Error(`LLM Slack Query Understander: API Error - ${error.response.data.error.message}`);
    }
    throw new Error(`LLM Slack Query Understander: Failed to understand Slack search query. ${error.message}`);
  }
}

/*
// Example Usage (conceptual)
async function testSlackUnderstander() {
    try {
        const queries = [
            "messages from John about project alpha in #general yesterday",
            "slack messages with a PDF from jane last week",
            "search for 'important announcement' in DMs with @sara",
            "messages with a :tada: reaction sent today"
        ];

        for (const q of queries) {
            console.log(`\nTesting Slack query: "${q}"`);
            const structuredQuery = await understandSlackSearchQueryLLM(q);
            console.log("Structured Slack Query:", JSON.stringify(structuredQuery, null, 2));
        }
    } catch (e) {
        console.error("Slack Understander Test failed:", e);
    }
}
// testSlackUnderstander();
*/
