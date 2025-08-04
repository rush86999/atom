import OpenAI from 'openai';
import { ATOM_OPENAI_API_KEY, ATOM_NLU_MODEL_NAME } from '../_libs/constants';
import { logger } from '../../_utils/logger';
let openAIClientForSlackQueryUnderstanding = null;
function getOpenAIClient() {
    if (openAIClientForSlackQueryUnderstanding) {
        return openAIClientForSlackQueryUnderstanding;
    }
    if (!ATOM_OPENAI_API_KEY) {
        logger.error('[LLMSlackQueryUnderstander] OpenAI API Key (ATOM_OPENAI_API_KEY) is not configured.');
        throw new Error('OpenAI API Key not configured for LLM Slack Query Understander.');
    }
    openAIClientForSlackQueryUnderstanding = new OpenAI({
        apiKey: ATOM_OPENAI_API_KEY,
    });
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
export async function understandSlackSearchQueryLLM(rawUserQuery) {
    const client = getOpenAIClient();
    const now = new Date();
    const year = now.getFullYear();
    const month = (now.getMonth() + 1).toString().padStart(2, '0');
    const day = now.getDate().toString().padStart(2, '0');
    const currentDate = `${year}-${month}-${day}`; // YYYY-MM-DD
    const systemPromptWithDate = SLACK_QUERY_UNDERSTANDING_SYSTEM_PROMPT.replace(/{{CURRENT_DATE}}/g, currentDate);
    const messages = [
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
        const cleanedResponse = {};
        for (const key in parsedResponse) {
            if (Object.prototype.hasOwnProperty.call(parsedResponse, key) &&
                parsedResponse[key] !== null &&
                parsedResponse[key] !== '') {
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
        if (cleanedResponse.beforeDate &&
            !dateRegex.test(cleanedResponse.beforeDate)) {
            logger.warn(`[LLMSlackQueryUnderstander] LLM provided 'beforeDate' in unexpected format: ${cleanedResponse.beforeDate}. Discarding.`);
            delete cleanedResponse.beforeDate;
        }
        if (cleanedResponse.afterDate &&
            !dateRegex.test(cleanedResponse.afterDate)) {
            logger.warn(`[LLMSlackQueryUnderstander] LLM provided 'afterDate' in unexpected format: ${cleanedResponse.afterDate}. Discarding.`);
            delete cleanedResponse.afterDate;
        }
        logger.info('[LLMSlackQueryUnderstander] Cleaned structured Slack query:', cleanedResponse);
        return cleanedResponse;
    }
    catch (error) {
        logger.error('[LLMSlackQueryUnderstander] Error processing Slack search query with OpenAI:', error.message);
        if (error instanceof SyntaxError) {
            logger.error('[LLMSlackQueryUnderstander] Failed to parse JSON response from LLM:', llmResponse);
            throw new Error('LLM Slack Query Understander: Failed to parse response from AI.');
        }
        if (error.response?.data?.error?.message) {
            // Axios-style error
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGxtX3NsYWNrX3F1ZXJ5X3VuZGVyc3RhbmRlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImxsbV9zbGFja19xdWVyeV91bmRlcnN0YW5kZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxNQUFNLE1BQU0sUUFBUSxDQUFDO0FBRTVCLE9BQU8sRUFBRSxtQkFBbUIsRUFBRSxtQkFBbUIsRUFBRSxNQUFNLG9CQUFvQixDQUFDO0FBQzlFLE9BQU8sRUFBRSxNQUFNLEVBQUUsTUFBTSxxQkFBcUIsQ0FBQztBQWlCN0MsSUFBSSxzQ0FBc0MsR0FBa0IsSUFBSSxDQUFDO0FBRWpFLFNBQVMsZUFBZTtJQUN0QixJQUFJLHNDQUFzQyxFQUFFLENBQUM7UUFDM0MsT0FBTyxzQ0FBc0MsQ0FBQztJQUNoRCxDQUFDO0lBQ0QsSUFBSSxDQUFDLG1CQUFtQixFQUFFLENBQUM7UUFDekIsTUFBTSxDQUFDLEtBQUssQ0FDVixxRkFBcUYsQ0FDdEYsQ0FBQztRQUNGLE1BQU0sSUFBSSxLQUFLLENBQ2IsaUVBQWlFLENBQ2xFLENBQUM7SUFDSixDQUFDO0lBQ0Qsc0NBQXNDLEdBQUcsSUFBSSxNQUFNLENBQUM7UUFDbEQsTUFBTSxFQUFFLG1CQUFtQjtLQUM1QixDQUFDLENBQUM7SUFDSCxNQUFNLENBQUMsSUFBSSxDQUFDLHdEQUF3RCxDQUFDLENBQUM7SUFDdEUsT0FBTyxzQ0FBc0MsQ0FBQztBQUNoRCxDQUFDO0FBRUQsa0ZBQWtGO0FBQ2xGLE1BQU0sdUNBQXVDLEdBQUc7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBeUMvQyxDQUFDO0FBRUY7Ozs7O0dBS0c7QUFDSCxNQUFNLENBQUMsS0FBSyxVQUFVLDZCQUE2QixDQUNqRCxZQUFvQjtJQUVwQixNQUFNLE1BQU0sR0FBRyxlQUFlLEVBQUUsQ0FBQztJQUNqQyxNQUFNLEdBQUcsR0FBRyxJQUFJLElBQUksRUFBRSxDQUFDO0lBQ3ZCLE1BQU0sSUFBSSxHQUFH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cGVuQUkgZnJvbSAnb3BlbmFpJztcbmltcG9ydCB7IENoYXRDb21wbGV0aW9uTWVzc2FnZVBhcmFtIH0gZnJvbSAnb3BlbmFpL3Jlc291cmNlcy9jaGF0L2NvbXBsZXRpb25zJztcbmltcG9ydCB7IEFUT01fT1BFTkFJX0FQSV9LRVksIEFUT01fTkxVX01PREVMX05BTUUgfSBmcm9tICcuLi9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IHsgbG9nZ2VyIH0gZnJvbSAnLi4vLi4vX3V0aWxzL2xvZ2dlcic7XG5cbi8vIEludGVyZmFjZSBmb3Igc3RydWN0dXJlZCBTbGFjayBzZWFyY2ggcXVlcmllc1xuZXhwb3J0IGludGVyZmFjZSBTdHJ1Y3R1cmVkU2xhY2tRdWVyeSB7XG4gIGZyb21Vc2VyPzogc3RyaW5nOyAvLyBTbGFjayB1c2VyIElEIG9yIGRpc3BsYXkgbmFtZS4gUmVzb2x2ZSB0byBJRCBpZiBwb3NzaWJsZSBiZWZvcmUgQVBJIHF1ZXJ5LlxuICBpbkNoYW5uZWw/OiBzdHJpbmc7IC8vIFNsYWNrIGNoYW5uZWwgSUQgb3IgbmFtZS4gUmVzb2x2ZSB0byBJRCBpZiBwb3NzaWJsZS5cbiAgbWVudGlvbnNVc2VyPzogc3RyaW5nOyAvLyBTbGFjayB1c2VyIElEIG9yIGRpc3BsYXkgbmFtZSBtZW50aW9uZWQuXG4gIGhhc0ZpbGU/OiBib29sZWFuO1xuICBoYXNMaW5rPzogYm9vbGVhbjtcbiAgaGFzUmVhY3Rpb24/OiBzdHJpbmc7IC8vIEVtb2ppIGNvZGUgZm9yIHJlYWN0aW9uIChlLmcuLCA6dGh1bWJzdXA6KVxuICBvbkRhdGU/OiBzdHJpbmc7IC8vIERhdGUgaW4gWVlZWS1NTS1ERCBmb3JtYXQuXG4gIGJlZm9yZURhdGU/OiBzdHJpbmc7IC8vIERhdGUgaW4gWVlZWS1NTS1ERCBmb3JtYXQuXG4gIGFmdGVyRGF0ZT86IHN0cmluZzsgLy8gRGF0ZSBpbiBZWVlZLU1NLUREIGZvcm1hdC5cbiAgdGV4dEtleXdvcmRzPzogc3RyaW5nOyAvLyBHZW5lcmFsIGtleXdvcmRzIGZvciBtZXNzYWdlIHRleHQuXG4gIGV4YWN0UGhyYXNlPzogc3RyaW5nOyAvLyBBbiBleGFjdCBwaHJhc2UgdG8gc2VhcmNoIGZvci5cbn1cblxubGV0IG9wZW5BSUNsaWVudEZvclNsYWNrUXVlcnlVbmRlcnN0YW5kaW5nOiBPcGVuQUkgfCBudWxsID0gbnVsbDtcblxuZnVuY3Rpb24gZ2V0T3BlbkFJQ2xpZW50KCk6IE9wZW5BSSB7XG4gIGlmIChvcGVuQUlDbGllbnRGb3JTbGFja1F1ZXJ5VW5kZXJzdGFuZGluZykge1xuICAgIHJldHVybiBvcGVuQUlDbGllbnRGb3JTbGFja1F1ZXJ5VW5kZXJzdGFuZGluZztcbiAgfVxuICBpZiAoIUFUT01fT1BFTkFJX0FQSV9LRVkpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAnW0xMTVNsYWNrUXVlcnlVbmRlcnN0YW5kZXJdIE9wZW5BSSBBUEkgS2V5IChBVE9NX09QRU5BSV9BUElfS0VZKSBpcyBub3QgY29uZmlndXJlZC4nXG4gICAgKTtcbiAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAnT3BlbkFJIEFQSSBLZXkgbm90IGNvbmZpZ3VyZWQgZm9yIExMTSBTbGFjayBRdWVyeSBVbmRlcnN0YW5kZXIuJ1xuICAgICk7XG4gIH1cbiAgb3BlbkFJQ2xpZW50Rm9yU2xhY2tRdWVyeVVuZGVyc3RhbmRpbmcgPSBuZXcgT3BlbkFJKHtcbiAgICBhcGlLZXk6IEFUT01fT1BFTkFJX0FQSV9LRVksXG4gIH0pO1xuICBsb2dnZXIuaW5mbygnW0xMTVNsYWNrUXVlcnlVbmRlcnN0YW5kZXJdIE9wZW5BSSBjbGllbnQgaW5pdGlhbGl6ZWQuJyk7XG4gIHJldHVybiBvcGVuQUlDbGllbnRGb3JTbGFja1F1ZXJ5VW5kZXJzdGFuZGluZztcbn1cblxuLy8gU3lzdGVtIHByb21wdCBmb3IgU2xhY2sgcXVlcnkgdW5kZXJzdGFuZGluZy4ge3tDVVJSRU5UX0RBVEV9fSB3aWxsIGJlIHJlcGxhY2VkLlxuY29uc3QgU0xBQ0tfUVVFUllfVU5ERVJTVEFORElOR19TWVNURU1fUFJPTVBUID0gYFxuWW91IGFyZSBhbiBleHBlcnQgc3lzdGVtIHRoYXQgY29udmVydHMgYSB1c2VyJ3MgbmF0dXJhbCBsYW5ndWFnZSByZXF1ZXN0IGFib3V0IGZpbmRpbmcgU2xhY2sgbWVzc2FnZXMgaW50byBhIHN0cnVjdHVyZWQgSlNPTiBvYmplY3QuXG5SZXNwb25kIE9OTFkgd2l0aCBhIHNpbmdsZSwgdmFsaWQgSlNPTiBvYmplY3QuIERvIG5vdCBpbmNsdWRlIGFueSBleHBsYW5hdG9yeSB0ZXh0IGJlZm9yZSBvciBhZnRlciB0aGUgSlNPTi5cblRoZSBKU09OIG9iamVjdCBzaG91bGQgY29uZm9ybSB0byB0aGUgJ1N0cnVjdHVyZWRTbGFja1F1ZXJ5JyBpbnRlcmZhY2U6XG5pbnRlcmZhY2UgU3RydWN0dXJlZFNsYWNrUXVlcnkge1xuICBmcm9tVXNlcj86IHN0cmluZzsgICAgICAvLyBVc2VyIHdobyBzZW50IHRoZSBtZXNzYWdlIChlLmcuLCBcIkpvaG4gRG9lXCIsIFwiQGpvaG5cIikuXG4gIGluQ2hhbm5lbD86IHN0cmluZzsgICAgIC8vIENoYW5uZWwgd2hlcmUgdGhlIG1lc3NhZ2Ugd2FzIHBvc3RlZCAoZS5nLiwgXCIjZ2VuZXJhbFwiLCBcInByb2plY3QtYWxwaGFcIikuXG4gIG1lbnRpb25zVXNlcj86IHN0cmluZzsgIC8vIFVzZXIgbWVudGlvbmVkIGluIHRoZSBtZXNzYWdlIChlLmcuLCBcIm1lbnRpb25pbmcgQGphbmVcIikuXG4gIGhhc0ZpbGU/OiBib29sZWFuOyAgICAgIC8vIFRydWUgaWYgZmlsZXMvYXR0YWNobWVudHMgYXJlIG1lbnRpb25lZCAoZS5nLiwgXCJtZXNzYWdlcyB3aXRoIGZpbGVzXCIsIFwic2hhcmVkIGEgZG9jdW1lbnRcIikuXG4gIGhhc0xpbms/OiBib29sZWFuOyAgICAgIC8vIFRydWUgaWYgbGlua3MgYXJlIG1lbnRpb25lZC5cbiAgaGFzUmVhY3Rpb24/OiBzdHJpbmc7ICAgLy8gRW1vamkgY29kZSBpZiBhIHJlYWN0aW9uIGlzIHNwZWNpZmllZCAoZS5nLiwgXCJ3aXRoIGEgOnRodW1ic3VwOlwiLCBcInJlYWN0ZWQgd2l0aCBzbWlsZVwiKS5cbiAgb25EYXRlPzogc3RyaW5nOyAgICAgICAgLy8gU3BlY2lmaWMgZGF0ZSBpbiBZWVlZLU1NLURELiBDdXJyZW50IGRhdGUgaXMge3tDVVJSRU5UX0RBVEV9fS5cbiAgYmVmb3JlRGF0ZT86IHN0cmluZzsgICAgLy8gQmVmb3JlIHRoaXMgZGF0ZSAoWVlZWS1NTS1ERCkuXG4gIGFmdGVyRGF0ZT86IHN0cmluZzsgICAgIC8vIEFmdGVyIHRoaXMgZGF0ZSAoWVlZWS1NTS1ERCkuXG4gIHRleHRLZXl3b3Jkcz86IHN0cmluZzsgIC8vIEtleXdvcmRzIGZvciBtZXNzYWdlIHRleHQuIENvbWJpbmUgbXVsdGlwbGUgY29uY2VwdHMgaWYgYXBwcm9wcmlhdGUuXG4gIGV4YWN0UGhyYXNlPzogc3RyaW5nOyAgIC8vIEFuIGV4YWN0IHBocmFzZSB0byBzZWFyY2ggZm9yIChlLmcuLCBpZiB1c2VyIHNheXMgXCJzZWFyY2ggZm9yICdpbXBvcnRhbnQgdXBkYXRlJ1wiKS5cbn1cblxuR3VpZGVsaW5lcyBmb3IgZGF0ZSBpbmZlcmVuY2UgKEN1cnJlbnQgRGF0ZToge3tDVVJSRU5UX0RBVEV9fSk6XG4tIFwieWVzdGVyZGF5XCI6ICdvbkRhdGUnIGZvciB5ZXN0ZXJkYXkncyBkYXRlLlxuLSBcInRvZGF5XCI6ICdvbkRhdGUnIGZvciB0b2RheSdzIGRhdGUuXG4tIFwibGFzdCB3ZWVrXCI6ICdhZnRlckRhdGUnIGZvciB0aGUgc3RhcnQgb2YgdGhlIHByZXZpb3VzIGNhbGVuZGFyIHdlZWsgKGUuZy4sIE1vbmRheSkgYW5kICdiZWZvcmVEYXRlJyBmb3IgdGhlIGVuZCBvZiBpdCAoZS5nLiwgU3VuZGF5KS5cbi0gXCJ0aGlzIHdlZWtcIjogJ2FmdGVyRGF0ZScgZm9yIHRoZSBzdGFydCBvZiB0aGUgY3VycmVudCBjYWxlbmRhciB3ZWVrIGFuZCAnYmVmb3JlRGF0ZScgZm9yIGl0cyBlbmQuXG4tIFwib24gW0RheU9mV2Vla11cIjogZS5nLiwgXCJvbiBNb25kYXlcIi4gSWYgaW4gdGhlIHBhc3QsIHVzZSB0aGUgbW9zdCByZWNlbnQgTW9uZGF5LiBJZiBhIGZ1dHVyZSBNb25kYXksIHVzZSB0aGF0LiBTZXQgJ29uRGF0ZScuXG4tIFwiaW4gW01vbnRoTmFtZV1cIjogZS5nLiwgXCJpbiBKdWx5XCIuIElmIHllYXIgbm90IHNwZWNpZmllZCwgYXNzdW1lIGN1cnJlbnQgeWVhci4gU2V0ICdhZnRlckRhdGUnIGZvciBtb250aCBzdGFydCwgJ2JlZm9yZURhdGUnIGZvciBtb250aCBlbmQuXG4tIFwic2luY2UgW0RhdGUvRXZlbnRdXCI6IGUuZy4sIFwic2luY2UgbGFzdCBUdWVzZGF5XCIuIFNldCAnYWZ0ZXJEYXRlJy5cbi0gXCJ1bnRpbCBbRGF0ZS9FdmVudF1cIiBvciBcImJlZm9yZSBbRGF0ZS9FdmVudF1cIjogU2V0ICdiZWZvcmVEYXRlJy5cblxuRXhhbXBsZXM6XG4tIFwibWVzc2FnZXMgZnJvbSBAYm9iIGFib3V0IHRoZSBRMSByZXBvcnQgaW4gI21hcmtldGluZyB5ZXN0ZXJkYXlcIlxuICAtPiB7XCJmcm9tVXNlclwiOiBcIkBib2JcIiwgXCJ0ZXh0S2V5d29yZHNcIjogXCJRMSByZXBvcnRcIiwgXCJpbkNoYW5uZWxcIjogXCIjbWFya2V0aW5nXCIsIFwib25EYXRlXCI6IFwiWVlZWS1NTS1ERCAoeWVzdGVyZGF5J3MgZGF0ZSlcIn1cbi0gXCJmaW5kIG1lc3NhZ2VzIHdpdGggYSBQREYgc2VudCBieSBKYW5lIGxhc3QgbW9udGhcIlxuICAtPiB7XCJoYXNGaWxlXCI6IHRydWUsIFwiZnJvbVVzZXJcIjogXCJKYW5lXCIsIFwiYWZ0ZXJEYXRlXCI6IFwiWVlZWS1NTS1ERCAoc3RhcnQgb2YgbGFzdCBtb250aClcIiwgXCJiZWZvcmVEYXRlXCI6IFwiWVlZWS1NTS1ERCAoZW5kIG9mIGxhc3QgbW9udGgpXCIsIFwidGV4dEtleXdvcmRzXCI6IFwiUERGXCJ9XG4tIFwic2VhcmNoIGZvciAncHJvamVjdCBkZWFkbGluZScgaW4gRE1zIHdpdGggQGFsaWNlXCJcbiAgLT4ge1wiZXhhY3RQaHJhc2VcIjogXCJwcm9qZWN0IGRlYWRsaW5lXCIsIFwiaW5DaGFubmVsXCI6IFwiQGFsaWNlXCJ9IChETXMgY2FuIGJlIHRyZWF0ZWQgYXMgY2hhbm5lbHMgd2l0aCB1c2VyIG5hbWVzKVxuLSBcIm1lc3NhZ2VzIHRoYXQgaGF2ZSBhIDpwYXJ0eV9wb3BwZXI6IHJlYWN0aW9uXCJcbiAgLT4ge1wiaGFzUmVhY3Rpb25cIjogXCI6cGFydHlfcG9wcGVyOlwifVxuXG5Pbmx5IGluY2x1ZGUga2V5cyBpbiB0aGUgSlNPTiBpZiB0aGUgaW5mb3JtYXRpb24gaXMgcHJlc2VudCBvciBjbGVhcmx5IGltcGxpZWQuXG5JZiBhIHVzZXIgbWVudGlvbnMgYSBuYW1lIGZvciAnZnJvbVVzZXInLCAnaW5DaGFubmVsJyAoZm9yIERNcyksIG9yICdtZW50aW9uc1VzZXInLCBrZWVwIGl0IGFzIHRoZSBuYW1lLiBUaGUgc3lzdGVtIHdpbGwgdHJ5IHRvIHJlc29sdmUgaXQgdG8gYW4gSUQgbGF0ZXIuXG5JZiB0aGUgcmVxdWVzdCBpcyB2ZXJ5IHZhZ3VlIChlLmcuLCBcImZpbmQgbWVzc2FnZXNcIiksIHJldHVybiBhbiBlbXB0eSBKU09OIG9iamVjdCB7fS5cbmA7XG5cbi8qKlxuICogVXNlcyBhbiBMTE0gdG8gdW5kZXJzdGFuZCBhIG5hdHVyYWwgbGFuZ3VhZ2UgU2xhY2sgcXVlcnkgYW5kIHRyYW5zZm9ybSBpdFxuICogaW50byBhIFN0cnVjdHVyZWRTbGFja1F1ZXJ5IG9iamVjdC5cbiAqIEBwYXJhbSByYXdVc2VyUXVlcnkgVGhlIHVzZXIncyBuYXR1cmFsIGxhbmd1YWdlIHF1ZXJ5IGFib3V0IGZpbmRpbmcgU2xhY2sgbWVzc2FnZXMuXG4gKiBAcmV0dXJucyBBIFByb21pc2UgcmVzb2x2aW5nIHRvIGEgUGFydGlhbDxTdHJ1Y3R1cmVkU2xhY2tRdWVyeT4gb2JqZWN0LlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gdW5kZXJzdGFuZFNsYWNrU2VhcmNoUXVlcnlMTE0oXG4gIHJhd1VzZXJRdWVyeTogc3RyaW5nXG4pOiBQcm9taXNlPFBhcnRpYWw8U3RydWN0dXJlZFNsYWNrUXVlcnk+PiB7XG4gIGNvbnN0IGNsaWVudCA9IGdldE9wZW5BSUNsaWVudCgpO1xuICBjb25zdCBub3cgPSBuZXcgRGF0ZSgpO1xuICBjb25zdCB5ZWFyID0gbm93LmdldEZ1bGxZZWFyKCk7XG4gIGNvbnN0IG1vbnRoID0gKG5vdy5nZXRNb250aCgpICsgMSkudG9TdHJpbmcoKS5wYWRTdGFydCgyLCAnMCcpO1xuICBjb25zdCBkYXkgPSBub3cuZ2V0RGF0ZSgpLnRvU3RyaW5nKCkucGFkU3RhcnQoMiwgJzAnKTtcbiAgY29uc3QgY3VycmVudERhdGUgPSBgJHt5ZWFyfS0ke21vbnRofS0ke2RheX1gOyAvLyBZWVlZLU1NLUREXG5cbiAgY29uc3Qgc3lzdGVtUHJvbXB0V2l0aERhdGUgPSBTTEFDS19RVUVSWV9VTkRFUlNUQU5ESU5HX1NZU1RFTV9QUk9NUFQucmVwbGFjZShcbiAgICAve3tDVVJSRU5UX0RBVEV9fS9nLFxuICAgIGN1cnJlbnREYXRlXG4gICk7XG5cbiAgY29uc3QgbWVzc2FnZXM6IENoYXRDb21wbGV0aW9uTWVzc2FnZVBhcmFtW10gPSBbXG4gICAgeyByb2xlOiAnc3lzdGVtJywgY29udGVudDogc3lzdGVtUHJvbXB0V2l0aERhdGUgfSxcbiAgICB7IHJvbGU6ICd1c2VyJywgY29udGVudDogcmF3VXNlclF1ZXJ5IH0sXG4gIF07XG5cbiAgbG9nZ2VyLmRlYnVnKFxuICAgIGBbTExNU2xhY2tRdWVyeVVuZGVyc3RhbmRlcl0gUHJvY2Vzc2luZyBxdWVyeTogXCIke3Jhd1VzZXJRdWVyeX1cIiB3aXRoIGN1cnJlbnQgZGF0ZSAke2N1cnJlbnREYXRlfWBcbiAgKTtcblxuICB0cnkge1xuICAgIGNvbnN0IGNvbXBsZXRpb24gPSBhd2FpdCBjbGllbnQuY2hhdC5jb21wbGV0aW9ucy5jcmVhdGUoe1xuICAgICAgbW9kZWw6IEFUT01fTkxVX01PREVMX05BTUUsIC8vIE9yIGEgbW9yZSBjYXBhYmxlIG1vZGVsIGxpa2UgXCJncHQtMy41LXR1cmJvLTExMDZcIiBvciBcImdwdC00XCIgZm9yIGJldHRlciBKU09OXG4gICAgICBtZXNzYWdlczogbWVzc2FnZXMsXG4gICAgICB0ZW1wZXJhdHVyZTogMC4xLFxuICAgICAgcmVzcG9uc2VfZm9ybWF0OiB7IHR5cGU6ICdqc29uX29iamVjdCcgfSxcbiAgICB9KTtcblxuICAgIGNvbnN0IGxsbVJlc3BvbnNlID0gY29tcGxldGlvbi5jaG9pY2VzWzBdPy5tZXNzYWdlPy5jb250ZW50O1xuICAgIGlmICghbGxtUmVzcG9uc2UpIHtcbiAgICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICAgJ1tMTE1TbGFja1F1ZXJ5VW5kZXJzdGFuZGVyXSBSZWNlaXZlZCBhbiBlbXB0eSByZXNwb25zZSBmcm9tIEFJLidcbiAgICAgICk7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ0xMTSBTbGFjayBRdWVyeSBVbmRlcnN0YW5kZXI6IEVtcHR5IHJlc3BvbnNlIGZyb20gQUkuJyk7XG4gICAgfVxuXG4gICAgbG9nZ2VyLmRlYnVnKFxuICAgICAgJ1tMTE1TbGFja1F1ZXJ5VW5kZXJzdGFuZGVyXSBSYXcgTExNIEpTT04gcmVzcG9uc2U6JyxcbiAgICAgIGxsbVJlc3BvbnNlXG4gICAgKTtcbiAgICBsZXQgcGFyc2VkUmVzcG9uc2UgPSBKU09OLnBhcnNlKGxsbVJlc3BvbnNlKTtcblxuICAgIC8vIENsZWFuIHVwIG51bGwvZW1wdHkgdmFsdWVzXG4gICAgY29uc3QgY2xlYW5lZFJlc3BvbnNlOiBQYXJ0aWFsPFN0cnVjdHVyZWRTbGFja1F1ZXJ5PiA9IHt9O1xuICAgIGZvciAoY29uc3Qga2V5IGluIHBhcnNlZFJlc3BvbnNlKSB7XG4gICAgICBpZiAoXG4gICAgICAgIE9iamVjdC5wcm90b3R5cGUuaGFzT3duUHJvcGVydHkuY2FsbChwYXJzZWRSZXNwb25zZSwga2V5KSAmJlxuICAgICAgICBwYXJzZWRSZXNwb25zZVtrZXldICE9PSBudWxsICYmXG4gICAgICAgIHBhcnNlZFJlc3BvbnNlW2tleV0gIT09ICcnXG4gICAgICApIHtcbiAgICAgICAgLy8gQHRzLWlnbm9yZSAtIGFzc2lnbmluZyB0byBwb3RlbnRpYWxseSBkaWZmZXJlbnQgdHlwZXMsIGJ1dCBrZXlzIHNob3VsZCBtYXRjaFxuICAgICAgICBjbGVhbmVkUmVzcG9uc2Vba2V5XSA9IHBhcnNlZFJlc3BvbnNlW2tleV07XG4gICAgICB9XG4gICAgfVxuICAgIC8vIFZhbGlkYXRlIGRhdGUgZm9ybWF0cyBpZiBMTE0gZG9lc24ndCBzdHJpY3RseSBhZGhlcmVcbiAgICBjb25zdCBkYXRlUmVnZXggPSAvXlxcZHs0fS1cXGR7Mn0tXFxkezJ9JC87XG4gICAgaWYgKGNsZWFuZWRSZXNwb25zZS5vbkRhdGUgJiYgIWRhdGVSZWdleC50ZXN0KGNsZWFuZWRSZXNwb25zZS5vbkRhdGUpKSB7XG4gICAgICBsb2dnZXIud2FybihcbiAgICAgICAgYFtMTE1TbGFja1F1ZXJ5VW5kZXJzdGFuZGVyXSBMTE0gcHJvdmlkZWQgJ29uRGF0ZScgaW4gdW5leHBlY3RlZCBmb3JtYXQ6ICR7Y2xlYW5lZFJlc3BvbnNlLm9uRGF0ZX0uIERpc2NhcmRpbmcuYFxuICAgICAgKTtcbiAgICAgIGRlbGV0ZSBjbGVhbmVkUmVzcG9uc2Uub25EYXRlO1xuICAgIH1cbiAgICBpZiAoXG4gICAgICBjbGVhbmVkUmVzcG9uc2UuYmVmb3JlRGF0ZSAmJlxuICAgICAgIWRhdGVSZWdleC50ZXN0KGNsZWFuZWRSZXNwb25zZS5iZWZvcmVEYXRlKVxuICAgICkge1xuICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgIGBbTExNU2xhY2tRdWVyeVVuZGVyc3RhbmRlcl0gTExNIHByb3ZpZGVkICdiZWZvcmVEYXRlJyBpbiB1bmV4cGVjdGVkIGZvcm1hdDogJHtjbGVhbmVkUmVzcG9uc2UuYmVmb3JlRGF0ZX0uIERpc2NhcmRpbmcuYFxuICAgICAgKTtcbiAgICAgIGRlbGV0ZSBjbGVhbmVkUmVzcG9uc2UuYmVmb3JlRGF0ZTtcbiAgICB9XG4gICAgaWYgKFxuICAgICAgY2xlYW5lZFJlc3BvbnNlLmFmdGVyRGF0ZSAmJlxuICAgICAgIWRhdGVSZWdleC50ZXN0KGNsZWFuZWRSZXNwb25zZS5hZnRlckRhdGUpXG4gICAgKSB7XG4gICAgICBsb2dnZXIud2FybihcbiAgICAgICAgYFtMTE1TbGFja1F1ZXJ5VW5kZXJzdGFuZGVyXSBMTE0gcHJvdmlkZWQgJ2FmdGVyRGF0ZScgaW4gdW5leHBlY3RlZCBmb3JtYXQ6ICR7Y2xlYW5lZFJlc3BvbnNlLmFmdGVyRGF0ZX0uIERpc2NhcmRpbmcuYFxuICAgICAgKTtcbiAgICAgIGRlbGV0ZSBjbGVhbmVkUmVzcG9uc2UuYWZ0ZXJEYXRlO1xuICAgIH1cblxuICAgIGxvZ2dlci5pbmZvKFxuICAgICAgJ1tMTE1TbGFja1F1ZXJ5VW5kZXJzdGFuZGVyXSBDbGVhbmVkIHN0cnVjdHVyZWQgU2xhY2sgcXVlcnk6JyxcbiAgICAgIGNsZWFuZWRSZXNwb25zZVxuICAgICk7XG4gICAgcmV0dXJuIGNsZWFuZWRSZXNwb25zZTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICdbTExNU2xhY2tRdWVyeVVuZGVyc3RhbmRlcl0gRXJyb3IgcHJvY2Vzc2luZyBTbGFjayBzZWFyY2ggcXVlcnkgd2l0aCBPcGVuQUk6JyxcbiAgICAgIGVycm9yLm1lc3NhZ2VcbiAgICApO1xuICAgIGlmIChlcnJvciBpbnN0YW5jZW9mIFN5bnRheEVycm9yKSB7XG4gICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgICdbTExNU2xhY2tRdWVyeVVuZGVyc3RhbmRlcl0gRmFpbGVkIHRvIHBhcnNlIEpTT04gcmVzcG9uc2UgZnJvbSBMTE06JyxcbiAgICAgICAgbGxtUmVzcG9uc2VcbiAgICAgICk7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgICdMTE0gU2xhY2sgUXVlcnkgVW5kZXJzdGFuZGVyOiBGYWlsZWQgdG8gcGFyc2UgcmVzcG9uc2UgZnJvbSBBSS4nXG4gICAgICApO1xuICAgIH1cbiAgICBpZiAoZXJyb3IucmVzcG9uc2U/LmRhdGE/LmVycm9yPy5tZXNzYWdlKSB7XG4gICAgICAvLyBBeGlvcy1zdHlsZSBlcnJvclxuICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICBgTExNIFNsYWNrIFF1ZXJ5IFVuZGVyc3RhbmRlcjogQVBJIEVycm9yIC0gJHtlcnJvci5yZXNwb25zZS5kYXRhLmVycm9yLm1lc3NhZ2V9YFxuICAgICAgKTtcbiAgICB9XG4gICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgYExMTSBTbGFjayBRdWVyeSBVbmRlcnN0YW5kZXI6IEZhaWxlZCB0byB1bmRlcnN0YW5kIFNsYWNrIHNlYXJjaCBxdWVyeS4gJHtlcnJvci5tZXNzYWdlfWBcbiAgICApO1xuICB9XG59XG5cbi8qXG4vLyBFeGFtcGxlIFVzYWdlIChjb25jZXB0dWFsKVxuYXN5bmMgZnVuY3Rpb24gdGVzdFNsYWNrVW5kZXJzdGFuZGVyKCkge1xuICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IHF1ZXJpZXMgPSBbXG4gICAgICAgICAgICBcIm1lc3NhZ2VzIGZyb20gSm9obiBhYm91dCBwcm9qZWN0IGFscGhhIGluICNnZW5lcmFsIHllc3RlcmRheVwiLFxuICAgICAgICAgICAgXCJzbGFjayBtZXNzYWdlcyB3aXRoIGEgUERGIGZyb20gamFuZSBsYXN0IHdlZWtcIixcbiAgICAgICAgICAgIFwic2VhcmNoIGZvciAnaW1wb3J0YW50IGFubm91bmNlbWVudCcgaW4gRE1zIHdpdGggQHNhcmFcIixcbiAgICAgICAgICAgIFwibWVzc2FnZXMgd2l0aCBhIDp0YWRhOiByZWFjdGlvbiBzZW50IHRvZGF5XCJcbiAgICAgICAgXTtcblxuICAgICAgICBmb3IgKGNvbnN0IHEgb2YgcXVlcmllcykge1xuICAgICAgICAgICAgY29uc29sZS5sb2coYFxcblRlc3RpbmcgU2xhY2sgcXVlcnk6IFwiJHtxfVwiYCk7XG4gICAgICAgICAgICBjb25zdCBzdHJ1Y3R1cmVkUXVlcnkgPSBhd2FpdCB1bmRlcnN0YW5kU2xhY2tTZWFyY2hRdWVyeUxMTShxKTtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKFwiU3RydWN0dXJlZCBTbGFjayBRdWVyeTpcIiwgSlNPTi5zdHJpbmdpZnkoc3RydWN0dXJlZFF1ZXJ5LCBudWxsLCAyKSk7XG4gICAgICAgIH1cbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoXCJTbGFjayBVbmRlcnN0YW5kZXIgVGVzdCBmYWlsZWQ6XCIsIGUpO1xuICAgIH1cbn1cbi8vIHRlc3RTbGFja1VuZGVyc3RhbmRlcigpO1xuKi9cbiJdfQ==