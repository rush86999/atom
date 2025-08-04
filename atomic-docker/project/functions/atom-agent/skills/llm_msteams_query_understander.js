import OpenAI from 'openai';
import { ATOM_OPENAI_API_KEY, ATOM_NLU_MODEL_NAME } from '../_libs/constants';
import { logger } from '../../_utils/logger';
let openAIClientForMSTeamsQueryUnderstanding = null;
function getOpenAIClient() {
    if (openAIClientForMSTeamsQueryUnderstanding) {
        return openAIClientForMSTeamsQueryUnderstanding;
    }
    if (!ATOM_OPENAI_API_KEY) {
        logger.error('[LLMMSTeamsQueryUnderstander] OpenAI API Key (ATOM_OPENAI_API_KEY) is not configured.');
        throw new Error('OpenAI API Key not configured for LLM MS Teams Query Understander.');
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
export async function understandMSTeamsSearchQueryLLM(rawUserQuery) {
    const client = getOpenAIClient();
    const now = new Date();
    const year = now.getFullYear();
    const month = (now.getMonth() + 1).toString().padStart(2, '0');
    const day = now.getDate().toString().padStart(2, '0');
    const currentDate = `${year}-${month}-${day}`; // YYYY-MM-DD
    const systemPromptWithDate = MSTEAMS_QUERY_UNDERSTANDING_SYSTEM_PROMPT.replace(/{{CURRENT_DATE}}/g, currentDate);
    const messages = [
        { role: 'system', content: systemPromptWithDate },
        { role: 'user', content: rawUserQuery },
    ];
    logger.debug(`[LLMMSTeamsQueryUnderstander] Processing query: "${rawUserQuery}" with current date ${currentDate}`);
    try {
        const completion = await client.chat.completions.create({
            model: ATOM_NLU_MODEL_NAME,
            messages: messages,
            temperature: 0.1,
            response_format: { type: 'json_object' },
        });
        const llmResponse = completion.choices[0]?.message?.content;
        if (!llmResponse) {
            logger.error('[LLMMSTeamsQueryUnderstander] Received an empty response from AI.');
            throw new Error('LLM MS Teams Query Understander: Empty response from AI.');
        }
        logger.debug('[LLMMSTeamsQueryUnderstander] Raw LLM JSON response:', llmResponse);
        let parsedResponse = JSON.parse(llmResponse);
        const cleanedResponse = {};
        for (const key in parsedResponse) {
            if (Object.prototype.hasOwnProperty.call(parsedResponse, key) &&
                parsedResponse[key] !== null &&
                parsedResponse[key] !== '') {
                // @ts-ignore
                cleanedResponse[key] = parsedResponse[key];
            }
        }
        const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
        if (cleanedResponse.onDate && !dateRegex.test(cleanedResponse.onDate)) {
            logger.warn(`[LLMMSTeamsQueryUnderstander] LLM provided 'onDate' in unexpected format: ${cleanedResponse.onDate}. Discarding.`);
            delete cleanedResponse.onDate;
        }
        if (cleanedResponse.beforeDate &&
            !dateRegex.test(cleanedResponse.beforeDate)) {
            logger.warn(`[LLMMSTeamsQueryUnderstander] LLM provided 'beforeDate' in unexpected format: ${cleanedResponse.beforeDate}. Discarding.`);
            delete cleanedResponse.beforeDate;
        }
        if (cleanedResponse.afterDate &&
            !dateRegex.test(cleanedResponse.afterDate)) {
            logger.warn(`[LLMMSTeamsQueryUnderstander] LLM provided 'afterDate' in unexpected format: ${cleanedResponse.afterDate}. Discarding.`);
            delete cleanedResponse.afterDate;
        }
        logger.info('[LLMMSTeamsQueryUnderstander] Cleaned structured MS Teams query:', cleanedResponse);
        return cleanedResponse;
    }
    catch (error) {
        logger.error('[LLMMSTeamsQueryUnderstander] Error processing MS Teams search query with OpenAI:', error.message);
        if (error instanceof SyntaxError) {
            logger.error('[LLMMSTeamsQueryUnderstander] Failed to parse JSON response from LLM:', llmResponse);
            throw new Error('LLM MS Teams Query Understander: Failed to parse response from AI.');
        }
        if (error.response?.data?.error?.message) {
            throw new Error(`LLM MS Teams Query Understander: API Error - ${error.response.data.error.message}`);
        }
        throw new Error(`LLM MS Teams Query Understander: Failed to understand MS Teams search query. ${error.message}`);
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGxtX21zdGVhbXNfcXVlcnlfdW5kZXJzdGFuZGVyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibGxtX21zdGVhbXNfcXVlcnlfdW5kZXJzdGFuZGVyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sTUFBTSxNQUFNLFFBQVEsQ0FBQztBQUU1QixPQUFPLEVBQUUsbUJBQW1CLEVBQUUsbUJBQW1CLEVBQUUsTUFBTSxvQkFBb0IsQ0FBQztBQUM5RSxPQUFPLEVBQUUsTUFBTSxFQUFFLE1BQU0scUJBQXFCLENBQUM7QUFpQjdDLElBQUksd0NBQXdDLEdBQWtCLElBQUksQ0FBQztBQUVuRSxTQUFTLGVBQWU7SUFDdEIsSUFBSSx3Q0FBd0MsRUFBRSxDQUFDO1FBQzdDLE9BQU8sd0NBQXdDLENBQUM7SUFDbEQsQ0FBQztJQUNELElBQUksQ0FBQyxtQkFBbUIsRUFBRSxDQUFDO1FBQ3pCLE1BQU0sQ0FBQyxLQUFLLENBQ1YsdUZBQXVGLENBQ3hGLENBQUM7UUFDRixNQUFNLElBQUksS0FBSyxDQUNiLG9FQUFvRSxDQUNyRSxDQUFDO0lBQ0osQ0FBQztJQUNELHdDQUF3QyxHQUFHLElBQUksTUFBTSxDQUFDO1FBQ3BELE1BQU0sRUFBRSxtQkFBbUI7S0FDNUIsQ0FBQyxDQUFDO0lBQ0gsTUFBTSxDQUFDLElBQUksQ0FBQywwREFBMEQsQ0FBQyxDQUFDO0lBQ3hFLE9BQU8sd0NBQXdDLENBQUM7QUFDbEQsQ0FBQztBQUVELHFGQUFxRjtBQUNyRiw0RkFBNEY7QUFDNUYsd0hBQXdIO0FBQ3hILE1BQU0seUNBQXlDLEdBQUc7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBeUNqRCxDQUFDO0FBRUY7Ozs7O0dBS0c7QUFDSCxNQUFNLENBQUMsS0FBSyxVQUFVLCtCQUErQixDQUNuRCxZQUFvQjtJQUVwQixNQUFNLE1BQU0sR0FBRyxlQUFlLEVBQUUsQ0FBQztJQUNqQyxNQUFNLEdBQUcsR0FBRyxJQUFJLElBQUks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VSxlQUFlLENBQzNILENBQUM7WUFDRixPQUFPLGVBQWUsQ0FBQyxVQUFVLENBQUM7UUFDcEMsQ0FBQztRQUNELElBQ0UsZUFBZSxDQUFDLFNBQVM7WUFDekIsQ0FBQyxTQUFTLENBQUMsSUFBSSxDQUFDLGVBQWUsQ0FBQyxTQUFTLENBQUMsRUFDMUMsQ0FBQztZQUNELE1BQU0sQ0FBQyxJQUFJLENBQ1QsZ0ZBQWdGLGVBQWUsQ0FBQyxTQUFTLGVBQWUsQ0FDekgsQ0FBQztZQUNGLE9BQU8sZUFBZSxDQUFDLFNBQVMsQ0FBQztRQUNuQyxDQUFDO1FBRUQsTUFBTSxDQUFDLElBQUksQ0FDVCxrRUFBa0UsRUFDbEUsZUFBZSxDQUNoQixDQUFDO1FBQ0YsT0FBTyxlQUFlLENBQUM7SUFDekIsQ0FBQztJQUFDLE9BQU8sS0FBVSxFQUFFLENBQUM7UUFDcEIsTUFBTSxDQUFDLEtBQUssQ0FDVixtRkFBbUYsRUFDbkYsS0FBSyxDQUFDLE9BQU8sQ0FDZCxDQUFDO1FBQ0YsSUFBSSxLQUFLLFlBQVksV0FBVyxFQUFFLENBQUM7WUFDakMsTUFBTSxDQUFDLEtBQUssQ0FDVix1RUFBdUUsRUFDdkUsV0FBVyxDQUNaLENBQUM7WUFDRixNQUFNLElBQUksS0FBSyxDQUNiLG9FQUFvRSxDQUNyRSxDQUFDO1FBQ0osQ0FBQztRQUNELElBQUksS0FBSyxDQUFDLFFBQVEsRUFBRSxJQUFJLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxDQUFDO1lBQ3pDLE1BQU0sSUFBSSxLQUFLLENBQ2IsZ0RBQWdELEtBQUssQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDLEtBQUssQ0FBQyxPQUFPLEVBQUUsQ0FDcEYsQ0FBQztRQUNKLENBQUM7UUFDRCxNQUFNLElBQUksS0FBSyxDQUNiLGdGQUFnRixLQUFLLENBQUMsT0FBTyxFQUFFLENBQ2hHLENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBPcGVuQUkgZnJvbSAnb3BlbmFpJztcbmltcG9ydCB7IENoYXRDb21wbGV0aW9uTWVzc2FnZVBhcmFtIH0gZnJvbSAnb3BlbmFpL3Jlc291cmNlcy9jaGF0L2NvbXBsZXRpb25zJztcbmltcG9ydCB7IEFUT01fT1BFTkFJX0FQSV9LRVksIEFUT01fTkxVX01PREVMX05BTUUgfSBmcm9tICcuLi9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IHsgbG9nZ2VyIH0gZnJvbSAnLi4vLi4vX3V0aWxzL2xvZ2dlcic7XG5cbi8vIEludGVyZmFjZSBmb3Igc3RydWN0dXJlZCBNaWNyb3NvZnQgVGVhbXMgc2VhcmNoIHF1ZXJpZXNcbmV4cG9ydCBpbnRlcmZhY2UgU3RydWN0dXJlZE1TVGVhbXNRdWVyeSB7XG4gIGZyb21Vc2VyPzogc3RyaW5nOyAvLyBTZW5kZXIncyBuYW1lIG9yIGVtYWlsIChHcmFwaCBzZWFyY2ggY2FuIG9mdGVuIHJlc29sdmUgbmFtZXMpXG4gIGluQ2hhdE9yQ2hhbm5lbD86IHN0cmluZzsgLy8gQ2hhdCBJRCwgQ2hhbm5lbCBJRCwgb3IgbmFtZSAoZS5nLiwgXCJHZW5lcmFsXCIsIFwiUHJvamVjdCBBbHBoYSBDaGF0IHdpdGggQm9iXCIpXG4gIG1lbnRpb25zVXNlcj86IHN0cmluZzsgLy8gVXNlciBtZW50aW9uZWQgKG5hbWUgb3IgZW1haWwpXG4gIGhhc0ZpbGU/OiBib29sZWFuOyAvLyBUcnVlIGlmIGZpbGVzL2F0dGFjaG1lbnRzIGFyZSBtZW50aW9uZWRcbiAgaGFzTGluaz86IGJvb2xlYW47IC8vIFRydWUgaWYgbGlua3MgYXJlIG1lbnRpb25lZCAobGVzcyBjb21tb24gYXMgZGlyZWN0IEtRTCwgbWlnaHQgYmUgcGFydCBvZiB0ZXh0S2V5d29yZHMpXG4gIG9uRGF0ZT86IHN0cmluZzsgLy8gU3BlY2lmaWMgZGF0ZSBpbiBZWVlZLU1NLUREIGZvcm1hdC5cbiAgYmVmb3JlRGF0ZT86IHN0cmluZzsgLy8gQmVmb3JlIHRoaXMgZGF0ZSAoWVlZWS1NTS1ERCkuXG4gIGFmdGVyRGF0ZT86IHN0cmluZzsgLy8gQWZ0ZXIgdGhpcyBkYXRlIChZWVlZLU1NLUREKS5cbiAgdGV4dEtleXdvcmRzPzogc3RyaW5nOyAvLyBHZW5lcmFsIGtleXdvcmRzIGZvciBtZXNzYWdlIGNvbnRlbnQuXG4gIHN1YmplY3RDb250YWlucz86IHN0cmluZzsgLy8gRm9yIGNoYW5uZWwgbWVzc2FnZXMgdGhhdCBtaWdodCBoYXZlIGEgc3ViamVjdC5cbiAgZXhhY3RQaHJhc2U/OiBzdHJpbmc7IC8vIEFuIGV4YWN0IHBocmFzZSB0byBzZWFyY2ggZm9yLlxufVxuXG5sZXQgb3BlbkFJQ2xpZW50Rm9yTVNUZWFtc1F1ZXJ5VW5kZXJzdGFuZGluZzogT3BlbkFJIHwgbnVsbCA9IG51bGw7XG5cbmZ1bmN0aW9uIGdldE9wZW5BSUNsaWVudCgpOiBPcGVuQUkge1xuICBpZiAob3BlbkFJQ2xpZW50Rm9yTVNUZWFtc1F1ZXJ5VW5kZXJzdGFuZGluZykge1xuICAgIHJldHVybiBvcGVuQUlDbGllbnRGb3JNU1RlYW1zUXVlcnlVbmRlcnN0YW5kaW5nO1xuICB9XG4gIGlmICghQVRPTV9PUEVOQUlfQVBJX0tFWSkge1xuICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICdbTExNTVNUZWFtc1F1ZXJ5VW5kZXJzdGFuZGVyXSBPcGVuQUkgQVBJIEtleSAoQVRPTV9PUEVOQUlfQVBJX0tFWSkgaXMgbm90IGNvbmZpZ3VyZWQuJ1xuICAgICk7XG4gICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgJ09wZW5BSSBBUEkgS2V5IG5vdCBjb25maWd1cmVkIGZvciBMTE0gTVMgVGVhbXMgUXVlcnkgVW5kZXJzdGFuZGVyLidcbiAgICApO1xuICB9XG4gIG9wZW5BSUNsaWVudEZvck1TVGVhbXNRdWVyeVVuZGVyc3RhbmRpbmcgPSBuZXcgT3BlbkFJKHtcbiAgICBhcGlLZXk6IEFUT01fT1BFTkFJX0FQSV9LRVksXG4gIH0pO1xuICBsb2dnZXIuaW5mbygnW0xMTU1TVGVhbXNRdWVyeVVuZGVyc3RhbmRlcl0gT3BlbkFJIGNsaWVudCBpbml0aWFsaXplZC4nKTtcbiAgcmV0dXJuIG9wZW5BSUNsaWVudEZvck1TVGVhbXNRdWVyeVVuZGVyc3RhbmRpbmc7XG59XG5cbi8vIFN5c3RlbSBwcm9tcHQgZm9yIE1TIFRlYW1zIHF1ZXJ5IHVuZGVyc3RhbmRpbmcuIHt7Q1VSUkVOVF9EQVRFfX0gd2lsbCBiZSByZXBsYWNlZC5cbi8vIE1pY3Jvc29mdCBHcmFwaCBTZWFyY2ggQVBJIHVzZXMgS2V5d29yZCBRdWVyeSBMYW5ndWFnZSAoS1FMKSBvciBuYXR1cmFsIGxhbmd1YWdlIHF1ZXJpZXMuXG4vLyBUaGlzIHByb21wdCBhaW1zIGZvciBzdHJ1Y3R1cmVkIG91dHB1dCB0aGF0IGNhbiB0aGVuIGJlIGVhc2lseSBjb252ZXJ0ZWQgdG8gYSBLUUwgcXVlcnkgb3IgcGFydHMgb2YgYSBzZWFyY2ggcmVxdWVzdC5cbmNvbnN0IE1TVEVBTVNfUVVFUllfVU5ERVJTVEFORElOR19TWVNURU1fUFJPTVBUID0gYFxuWW91IGFyZSBhbiBleHBlcnQgc3lzdGVtIHRoYXQgY29udmVydHMgYSB1c2VyJ3MgbmF0dXJhbCBsYW5ndWFnZSByZXF1ZXN0IGFib3V0IGZpbmRpbmcgTWljcm9zb2Z0IFRlYW1zIG1lc3NhZ2VzIGludG8gYSBzdHJ1Y3R1cmVkIEpTT04gb2JqZWN0LlxuUmVzcG9uZCBPTkxZIHdpdGggYSBzaW5nbGUsIHZhbGlkIEpTT04gb2JqZWN0LiBEbyBub3QgaW5jbHVkZSBhbnkgZXhwbGFuYXRvcnkgdGV4dCBiZWZvcmUgb3IgYWZ0ZXIgdGhlIEpTT04uXG5UaGUgSlNPTiBvYmplY3Qgc2hvdWxkIGNvbmZvcm0gdG8gdGhlICdTdHJ1Y3R1cmVkTVNUZWFtc1F1ZXJ5JyBpbnRlcmZhY2U6XG5pbnRlcmZhY2UgU3RydWN0dXJlZE1TVGVhbXNRdWVyeSB7XG4gIGZyb21Vc2VyPzogc3RyaW5nOyAgICAgICAgICAvLyBTZW5kZXIncyBuYW1lIG9yIGVtYWlsIChlLmcuLCBcIkpvaG4gRG9lXCIsIFwiam9obi5kb2VAZXhhbXBsZS5jb21cIikuXG4gIGluQ2hhdE9yQ2hhbm5lbD86IHN0cmluZzsgICAvLyBOYW1lIG9mIHRoZSBjaGF0IChlLmcuLCBcIkNoYXQgd2l0aCBKYW5lXCIsIFwiUHJvamVjdCBEaXNjdXNzaW9uXCIpIG9yIGNoYW5uZWwgKGUuZy4sIFwiR2VuZXJhbFwiLCBcIlE0IFBsYW5uaW5nXCIpLlxuICBtZW50aW9uc1VzZXI/OiBzdHJpbmc7ICAgICAgLy8gVXNlciBtZW50aW9uZWQgaW4gdGhlIG1lc3NhZ2UgKG5hbWUgb3IgZW1haWwpLlxuICBoYXNGaWxlPzogYm9vbGVhbjsgICAgICAgICAgLy8gVHJ1ZSBpZiBmaWxlcy9hdHRhY2htZW50cyBhcmUgbWVudGlvbmVkLlxuICBoYXNMaW5rPzogYm9vbGVhbjsgICAgICAgICAgLy8gVHJ1ZSBpZiBsaW5rcyBhcmUgbWVudGlvbmVkLlxuICBvbkRhdGU/OiBzdHJpbmc7ICAgICAgICAgICAgLy8gU3BlY2lmaWMgZGF0ZSBpbiBZWVlZLU1NLURELiBDdXJyZW50IGRhdGUgaXMge3tDVVJSRU5UX0RBVEV9fS5cbiAgYmVmb3JlRGF0ZT86IHN0cmluZzsgICAgICAgIC8vIEJlZm9yZSB0aGlzIGRhdGUgKFlZWVktTU0tREQpLlxuICBhZnRlckRhdGU/OiBzdHJpbmc7ICAgICAgICAgLy8gQWZ0ZXIgdGhpcyBkYXRlIChZWVlZLU1NLUREKS5cbiAgdGV4dEtleXdvcmRzPzogc3RyaW5nOyAgICAgIC8vIEtleXdvcmRzIGZvciBtZXNzYWdlIGNvbnRlbnQuIENvbWJpbmUgbXVsdGlwbGUgY29uY2VwdHMgaWYgYXBwcm9wcmlhdGUuXG4gIHN1YmplY3RDb250YWlucz86IHN0cmluZzsgICAvLyBLZXl3b3JkcyBmb3IgdGhlIHN1YmplY3Qgb2YgYSBjaGFubmVsIG1lc3NhZ2UuXG4gIGV4YWN0UGhyYXNlPzogc3RyaW5nOyAgICAgICAvLyBBbiBleGFjdCBwaHJhc2UgaWYgc3BlY2lmaWVkIChlLmcuLCBcInNlYXJjaCBmb3IgJ3VyZ2VudCByZXZpZXcgbmVlZGVkJ1wiKS5cbn1cblxuR3VpZGVsaW5lcyBmb3IgZGF0ZSBpbmZlcmVuY2UgKEN1cnJlbnQgRGF0ZToge3tDVVJSRU5UX0RBVEV9fSk6XG4tIFwieWVzdGVyZGF5XCI6ICdvbkRhdGUnIGZvciB5ZXN0ZXJkYXkncyBkYXRlLlxuLSBcInRvZGF5XCI6ICdvbkRhdGUnIGZvciB0b2RheSdzIGRhdGUuXG4tIFwibGFzdCB3ZWVrXCI6ICdhZnRlckRhdGUnIGZvciB0aGUgc3RhcnQgb2YgdGhlIHByZXZpb3VzIGNhbGVuZGFyIHdlZWsgKGUuZy4sIE1vbmRheSkgYW5kICdiZWZvcmVEYXRlJyBmb3IgaXRzIGVuZCAoZS5nLiwgU3VuZGF5KS5cbi0gXCJ0aGlzIHdlZWtcIjogJ2FmdGVyRGF0ZScgZm9yIHRoZSBzdGFydCBvZiB0aGUgY3VycmVudCBjYWxlbmRhciB3ZWVrIGFuZCAnYmVmb3JlRGF0ZScgZm9yIGl0cyBlbmQuXG4tIFwib24gW0RheU9mV2Vla11cIjogZS5nLiwgXCJvbiBNb25kYXlcIi4gSWYgaW4gdGhlIHBhc3QsIHVzZSB0aGUgbW9zdCByZWNlbnQgTW9uZGF5LiBJZiBhIGZ1dHVyZSBNb25kYXksIHVzZSB0aGF0LiBTZXQgJ29uRGF0ZScuXG4tIFwiaW4gW01vbnRoTmFtZV1cIjogZS5nLiwgXCJpbiBKdWx5XCIuIElmIHllYXIgbm90IHNwZWNpZmllZCwgYXNzdW1lIGN1cnJlbnQgeWVhci4gU2V0ICdhZnRlckRhdGUnIGZvciBtb250aCBzdGFydCwgJ2JlZm9yZURhdGUnIGZvciBtb250aCBlbmQuXG4tIFwic2luY2UgW0RhdGUvRXZlbnRdXCI6IGUuZy4sIFwic2luY2UgbGFzdCBUdWVzZGF5XCIuIFNldCAnYWZ0ZXJEYXRlJy5cbi0gXCJ1bnRpbCBbRGF0ZS9FdmVudF1cIiBvciBcImJlZm9yZSBbRGF0ZS9FdmVudF1cIjogU2V0ICdiZWZvcmVEYXRlJy5cblxuRXhhbXBsZXM6XG4tIFwiVGVhbXMgbWVzc2FnZXMgZnJvbSBCb2IgYWJvdXQgdGhlIGJ1ZGdldCBpbiAnTWFya2V0aW5nIENhbXBhaWduIENoYXQnIGxhc3QgTW9uZGF5XCJcbiAgLT4ge1wiZnJvbVVzZXJcIjogXCJCb2JcIiwgXCJ0ZXh0S2V5d29yZHNcIjogXCJidWRnZXRcIiwgXCJpbkNoYXRPckNoYW5uZWxcIjogXCJNYXJrZXRpbmcgQ2FtcGFpZ24gQ2hhdFwiLCBcIm9uRGF0ZVwiOiBcIllZWVktTU0tREQgKGxhc3QgTW9uZGF5J3MgZGF0ZSlcIn1cbi0gXCJmaW5kIG1lc3NhZ2VzIHdpdGggYW4gRXhjZWwgZmlsZSBzaGFyZWQgYnkgYWxpY2VAY29udG9zby5jb20gdHdvIHdlZWtzIGFnb1wiXG4gIC0+IHtcImhhc0ZpbGVcIjogdHJ1ZSwgXCJmcm9tVXNlclwiOiBcImFsaWNlQGNvbnRvc28uY29tXCIsIFwidGV4dEtleXdvcmRzXCI6IFwiRXhjZWxcIiwgXCJhZnRlckRhdGVcIjogXCJZWVlZLU1NLUREIChzdGFydCBvZiAyIHdlZWtzIGFnbylcIiwgXCJiZWZvcmVEYXRlXCI6IFwiWVlZWS1NTS1ERCAoZW5kIG9mIDIgd2Vla3MgYWdvKVwifVxuLSBcInNlYXJjaCBmb3IgJ2NsaWVudCBmZWVkYmFjaycgaW4gdGhlIEdlbmVyYWwgY2hhbm5lbCBvZiBQcm9qZWN0IFggdGVhbVwiXG4gIC0+IHtcImV4YWN0UGhyYXNlXCI6IFwiY2xpZW50IGZlZWRiYWNrXCIsIFwiaW5DaGF0T3JDaGFubmVsXCI6IFwiUHJvamVjdCBYIEdlbmVyYWxcIn0gKEFzc3VtZSBjaGFubmVsIG5hbWUgaW1wbGllcyB0ZWFtIGlmIHNwZWNpZmljIGVub3VnaClcbi0gXCJtZXNzYWdlcyBtZW50aW9uaW5nIG1lIHdpdGggYSBsaW5rXCJcbiAgLT4ge1wibWVudGlvbnNVc2VyXCI6IFwibWVcIiwgXCJoYXNMaW5rXCI6IHRydWV9XG5cbk9ubHkgaW5jbHVkZSBrZXlzIGluIHRoZSBKU09OIGlmIHRoZSBpbmZvcm1hdGlvbiBpcyBwcmVzZW50IG9yIGNsZWFybHkgaW1wbGllZC5cbklmIHRoZSByZXF1ZXN0IGlzIHZlcnkgdmFndWUgKGUuZy4sIFwiZmluZCBUZWFtcyBtZXNzYWdlc1wiKSwgcmV0dXJuIGFuIGVtcHR5IEpTT04gb2JqZWN0IHt9LlxuSWYgdXNlciBzYXlzIFwibWVudGlvbmluZyBtZVwiLCB1c2UgXCJtZVwiIGZvciBtZW50aW9uc1VzZXIuIFRoZSBzeXN0ZW0gd2lsbCByZXNvbHZlIFwibWVcIiB0byB0aGUgYWN0dWFsIHVzZXIgSUQuXG5gO1xuXG4vKipcbiAqIFVzZXMgYW4gTExNIHRvIHVuZGVyc3RhbmQgYSBuYXR1cmFsIGxhbmd1YWdlIE1TIFRlYW1zIHF1ZXJ5IGFuZCB0cmFuc2Zvcm0gaXRcbiAqIGludG8gYSBTdHJ1Y3R1cmVkTVNUZWFtc1F1ZXJ5IG9iamVjdC5cbiAqIEBwYXJhbSByYXdVc2VyUXVlcnkgVGhlIHVzZXIncyBuYXR1cmFsIGxhbmd1YWdlIHF1ZXJ5IGFib3V0IGZpbmRpbmcgVGVhbXMgbWVzc2FnZXMuXG4gKiBAcmV0dXJucyBBIFByb21pc2UgcmVzb2x2aW5nIHRvIGEgUGFydGlhbDxTdHJ1Y3R1cmVkTVNUZWFtc1F1ZXJ5PiBvYmplY3QuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiB1bmRlcnN0YW5kTVNUZWFtc1NlYXJjaFF1ZXJ5TExNKFxuICByYXdVc2VyUXVlcnk6IHN0cmluZ1xuKTogUHJvbWlzZTxQYXJ0aWFsPFN0cnVjdHVyZWRNU1RlYW1zUXVlcnk+PiB7XG4gIGNvbnN0IGNsaWVudCA9IGdldE9wZW5BSUNsaWVudCgpO1xuICBjb25zdCBub3cgPSBuZXcgRGF0ZSgpO1xuICBjb25zdCB5ZWFyID0gbm93LmdldEZ1bGxZZWFyKCk7XG4gIGNvbnN0IG1vbnRoID0gKG5vdy5nZXRNb250aCgpICsgMSkudG9TdHJpbmcoKS5wYWRTdGFydCgyLCAnMCcpO1xuICBjb25zdCBkYXkgPSBub3cuZ2V0RGF0ZSgpLnRvU3RyaW5nKCkucGFkU3RhcnQoMiwgJzAnKTtcbiAgY29uc3QgY3VycmVudERhdGUgPSBgJHt5ZWFyfS0ke21vbnRofS0ke2RheX1gOyAvLyBZWVlZLU1NLUREXG5cbiAgY29uc3Qgc3lzdGVtUHJvbXB0V2l0aERhdGUgPVxuICAgIE1TVEVBTVNfUVVFUllfVU5ERVJTVEFORElOR19TWVNURU1fUFJPTVBULnJlcGxhY2UoXG4gICAgICAve3tDVVJSRU5UX0RBVEV9fS9nLFxuICAgICAgY3VycmVudERhdGVcbiAgICApO1xuXG4gIGNvbnN0IG1lc3NhZ2VzOiBDaGF0Q29tcGxldGlvbk1lc3NhZ2VQYXJhbVtdID0gW1xuICAgIHsgcm9sZTogJ3N5c3RlbScsIGNvbnRlbnQ6IHN5c3RlbVByb21wdFdpdGhEYXRlIH0sXG4gICAgeyByb2xlOiAndXNlcicsIGNvbnRlbnQ6IHJhd1VzZXJRdWVyeSB9LFxuICBdO1xuXG4gIGxvZ2dlci5kZWJ1ZyhcbiAgICBgW0xMTU1TVGVhbXNRdWVyeVVuZGVyc3RhbmRlcl0gUHJvY2Vzc2luZyBxdWVyeTogXCIke3Jhd1VzZXJRdWVyeX1cIiB3aXRoIGN1cnJlbnQgZGF0ZSAke2N1cnJlbnREYXRlfWBcbiAgKTtcblxuICB0cnkge1xuICAgIGNvbnN0IGNvbXBsZXRpb24gPSBhd2FpdCBjbGllbnQuY2hhdC5jb21wbGV0aW9ucy5jcmVhdGUoe1xuICAgICAgbW9kZWw6IEFUT01fTkxVX01PREVMX05BTUUsXG4gICAgICBtZXNzYWdlczogbWVzc2FnZXMsXG4gICAgICB0ZW1wZXJhdHVyZTogMC4xLFxuICAgICAgcmVzcG9uc2VfZm9ybWF0OiB7IHR5cGU6ICdqc29uX29iamVjdCcgfSxcbiAgICB9KTtcblxuICAgIGNvbnN0IGxsbVJlc3BvbnNlID0gY29tcGxldGlvbi5jaG9pY2VzWzBdPy5tZXNzYWdlPy5jb250ZW50O1xuICAgIGlmICghbGxtUmVzcG9uc2UpIHtcbiAgICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICAgJ1tMTE1NU1RlYW1zUXVlcnlVbmRlcnN0YW5kZXJdIFJlY2VpdmVkIGFuIGVtcHR5IHJlc3BvbnNlIGZyb20gQUkuJ1xuICAgICAgKTtcbiAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgJ0xMTSBNUyBUZWFtcyBRdWVyeSBVbmRlcnN0YW5kZXI6IEVtcHR5IHJlc3BvbnNlIGZyb20gQUkuJ1xuICAgICAgKTtcbiAgICB9XG5cbiAgICBsb2dnZXIuZGVidWcoXG4gICAgICAnW0xMTU1TVGVhbXNRdWVyeVVuZGVyc3RhbmRlcl0gUmF3IExMTSBKU09OIHJlc3BvbnNlOicsXG4gICAgICBsbG1SZXNwb25zZVxuICAgICk7XG4gICAgbGV0IHBhcnNlZFJlc3BvbnNlID0gSlNPTi5wYXJzZShsbG1SZXNwb25zZSk7XG5cbiAgICBjb25zdCBjbGVhbmVkUmVzcG9uc2U6IFBhcnRpYWw8U3RydWN0dXJlZE1TVGVhbXNRdWVyeT4gPSB7fTtcbiAgICBmb3IgKGNvbnN0IGtleSBpbiBwYXJzZWRSZXNwb25zZSkge1xuICAgICAgaWYgKFxuICAgICAgICBPYmplY3QucHJvdG90eXBlLmhhc093blByb3BlcnR5LmNhbGwocGFyc2VkUmVzcG9uc2UsIGtleSkgJiZcbiAgICAgICAgcGFyc2VkUmVzcG9uc2Vba2V5XSAhPT0gbnVsbCAmJlxuICAgICAgICBwYXJzZWRSZXNwb25zZVtrZXldICE9PSAnJ1xuICAgICAgKSB7XG4gICAgICAgIC8vIEB0cy1pZ25vcmVcbiAgICAgICAgY2xlYW5lZFJlc3BvbnNlW2tleV0gPSBwYXJzZWRSZXNwb25zZVtrZXldO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IGRhdGVSZWdleCA9IC9eXFxkezR9LVxcZHsyfS1cXGR7Mn0kLztcbiAgICBpZiAoY2xlYW5lZFJlc3BvbnNlLm9uRGF0ZSAmJiAhZGF0ZVJlZ2V4LnRlc3QoY2xlYW5lZFJlc3BvbnNlLm9uRGF0ZSkpIHtcbiAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICBgW0xMTU1TVGVhbXNRdWVyeVVuZGVyc3RhbmRlcl0gTExNIHByb3ZpZGVkICdvbkRhdGUnIGluIHVuZXhwZWN0ZWQgZm9ybWF0OiAke2NsZWFuZWRSZXNwb25zZS5vbkRhdGV9LiBEaXNjYXJkaW5nLmBcbiAgICAgICk7XG4gICAgICBkZWxldGUgY2xlYW5lZFJlc3BvbnNlLm9uRGF0ZTtcbiAgICB9XG4gICAgaWYgKFxuICAgICAgY2xlYW5lZFJlc3BvbnNlLmJlZm9yZURhdGUgJiZcbiAgICAgICFkYXRlUmVnZXgudGVzdChjbGVhbmVkUmVzcG9uc2UuYmVmb3JlRGF0ZSlcbiAgICApIHtcbiAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICBgW0xMTU1TVGVhbXNRdWVyeVVuZGVyc3RhbmRlcl0gTExNIHByb3ZpZGVkICdiZWZvcmVEYXRlJyBpbiB1bmV4cGVjdGVkIGZvcm1hdDogJHtjbGVhbmVkUmVzcG9uc2UuYmVmb3JlRGF0ZX0uIERpc2NhcmRpbmcuYFxuICAgICAgKTtcbiAgICAgIGRlbGV0ZSBjbGVhbmVkUmVzcG9uc2UuYmVmb3JlRGF0ZTtcbiAgICB9XG4gICAgaWYgKFxuICAgICAgY2xlYW5lZFJlc3BvbnNlLmFmdGVyRGF0ZSAmJlxuICAgICAgIWRhdGVSZWdleC50ZXN0KGNsZWFuZWRSZXNwb25zZS5hZnRlckRhdGUpXG4gICAgKSB7XG4gICAgICBsb2dnZXIud2FybihcbiAgICAgICAgYFtMTE1NU1RlYW1zUXVlcnlVbmRlcnN0YW5kZXJdIExMTSBwcm92aWRlZCAnYWZ0ZXJEYXRlJyBpbiB1bmV4cGVjdGVkIGZvcm1hdDogJHtjbGVhbmVkUmVzcG9uc2UuYWZ0ZXJEYXRlfS4gRGlzY2FyZGluZy5gXG4gICAgICApO1xuICAgICAgZGVsZXRlIGNsZWFuZWRSZXNwb25zZS5hZnRlckRhdGU7XG4gICAgfVxuXG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICAnW0xMTU1TVGVhbXNRdWVyeVVuZGVyc3RhbmRlcl0gQ2xlYW5lZCBzdHJ1Y3R1cmVkIE1TIFRlYW1zIHF1ZXJ5OicsXG4gICAgICBjbGVhbmVkUmVzcG9uc2VcbiAgICApO1xuICAgIHJldHVybiBjbGVhbmVkUmVzcG9uc2U7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAnW0xMTU1TVGVhbXNRdWVyeVVuZGVyc3RhbmRlcl0gRXJyb3IgcHJvY2Vzc2luZyBNUyBUZWFtcyBzZWFyY2ggcXVlcnkgd2l0aCBPcGVuQUk6JyxcbiAgICAgIGVycm9yLm1lc3NhZ2VcbiAgICApO1xuICAgIGlmIChlcnJvciBpbnN0YW5jZW9mIFN5bnRheEVycm9yKSB7XG4gICAgICBsb2dnZXIuZXJyb3IoXG4gICAgICAgICdbTExNTVNUZWFtc1F1ZXJ5VW5kZXJzdGFuZGVyXSBGYWlsZWQgdG8gcGFyc2UgSlNPTiByZXNwb25zZSBmcm9tIExMTTonLFxuICAgICAgICBsbG1SZXNwb25zZVxuICAgICAgKTtcbiAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgJ0xMTSBNUyBUZWFtcyBRdWVyeSBVbmRlcnN0YW5kZXI6IEZhaWxlZCB0byBwYXJzZSByZXNwb25zZSBmcm9tIEFJLidcbiAgICAgICk7XG4gICAgfVxuICAgIGlmIChlcnJvci5yZXNwb25zZT8uZGF0YT8uZXJyb3I/Lm1lc3NhZ2UpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgYExMTSBNUyBUZWFtcyBRdWVyeSBVbmRlcnN0YW5kZXI6IEFQSSBFcnJvciAtICR7ZXJyb3IucmVzcG9uc2UuZGF0YS5lcnJvci5tZXNzYWdlfWBcbiAgICAgICk7XG4gICAgfVxuICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgIGBMTE0gTVMgVGVhbXMgUXVlcnkgVW5kZXJzdGFuZGVyOiBGYWlsZWQgdG8gdW5kZXJzdGFuZCBNUyBUZWFtcyBzZWFyY2ggcXVlcnkuICR7ZXJyb3IubWVzc2FnZX1gXG4gICAgKTtcbiAgfVxufVxuIl19