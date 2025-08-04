import OpenAI from 'openai';
import { ATOM_OPENAI_API_KEY, ATOM_NLU_MODEL_NAME } from '../_libs/constants'; // Reuse existing constants
// Reuse or adapt OpenAI client initialization from nluService.ts
// Using a separate client instance for this specific task might be cleaner if configs differ,
// but for now, reusing the pattern.
let openAIClientForQueryUnderstanding = null;
function getOpenAIClient() {
    if (openAIClientForQueryUnderstanding) {
        return openAIClientForQueryUnderstanding;
    }
    if (!ATOM_OPENAI_API_KEY) {
        console.error('OpenAI API Key not configured for LLM Query Understander.');
        throw new Error('OpenAI API Key not configured for LLM Query Understander.');
    }
    openAIClientForQueryUnderstanding = new OpenAI({
        apiKey: ATOM_OPENAI_API_KEY,
    });
    return openAIClientForQueryUnderstanding;
}
// Note: {{CURRENT_DATE}} will be replaced by the actual current date at runtime.
const QUERY_UNDERSTANDING_SYSTEM_PROMPT = `
You are an expert system that converts a user's natural language request about finding emails into a structured JSON object.
The user's request will be provided. You need to identify specific criteria for searching emails.
Respond ONLY with a single, valid JSON object. Do not include any explanatory text before or after the JSON.
The JSON object should conform to the following TypeScript interface 'StructuredEmailQuery':
interface StructuredEmailQuery {
  from?: string; // Sender's email or name
  to?: string; // Recipient's email or name
  subject?: string; // Keywords for subject. If multiple distinct concepts, combine them.
  bodyKeywords?: string; // Keywords for email body. If multiple distinct concepts, combine them.
  label?: string; // Email label (e.g., "inbox", "starred", "important", "work"). Only one primary label.
  after?: string; // Date in YYYY/MM/DD format. Infer from relative terms like "yesterday", "last week". Current date is {{CURRENT_DATE}}.
  before?: string; // Date in YYYY/MM/DD format. Infer from relative terms. Current date is {{CURRENT_DATE}}.
  hasAttachment?: boolean; // True if attachments are mentioned or implied (e.g., "emails with files").
  exactPhrase?: string; // An exact phrase to search for if specified by user with quotes or clear intent.
  excludeChats?: boolean; // True if user wants to exclude chat messages (e.g., "not chats", "emails only", "no chat messages").
}

Guidelines for date inference (Current Date: {{CURRENT_DATE}}):
- "yesterday": Output 'after' and 'before' for the full day of yesterday.
- "today": Output 'after' and 'before' for the full current day.
- "last week": Calculate the full calendar week (e.g., Sunday to Saturday, or Monday to Sunday, be consistent) prior to the current week. Provide 'after' for its start and 'before' for its end.
- "this week": Current calendar week. Provide 'after' for its start and 'before' for its end.
- "next week": The full calendar week after the current one.
- "last month": The full previous calendar month. Provide 'after' and 'before'.
- "this month": The current calendar month. Provide 'after' and 'before'.
- "a few months ago": Interpret as approximately 2-3 months ago. E.g., if current is May, "a few months ago" could be Feb-Mar. Provide an 'after' for start of that period and 'before' for end of that period.
- "in [MonthName]": e.g., "in July". If year not specified, assume current year ({{CURRENT_DATE}}). If past month in current year, use that month. If future month in current year, use that month. Provide 'after' and 'before' for the full month.
- "since [Date/Event]": e.g., "since Monday", "since last month". Set 'after' to the start of that date/event. Do not set 'before'.
- "until [Date/Event]" or "before [Date/Event]": Set 'before' to the start of that date/event.
- "between [Date1] and [Date2]": Set 'after' for Date1 and 'before' for Date2.
- If a specific year is mentioned (e.g., "emails from July 2022"), use that year.

Only include keys in the JSON object if the corresponding information is present or clearly implied in the user's request.
If a user says "emails from Jane about the project report", "project report" could be 'subject' or 'bodyKeywords'. If unsure, you can include it in 'bodyKeywords'.
If the request is very vague (e.g., "find emails"), return an empty JSON object {}.
If the user specifies "emails" or "mail", and not "chats", you can often infer "excludeChats": true.
`;
/**
 * Uses an LLM to understand a natural language email query and transform it
 * into a StructuredEmailQuery object.
 * @param rawUserQuery The user's natural language query about finding emails.
 * @returns A Promise resolving to a Partial<StructuredEmailQuery> object.
 * @throws Error if LLM call fails or parsing is unsuccessful.
 */
export async function understandEmailSearchQueryLLM(rawUserQuery) {
    const client = getOpenAIClient();
    // Get current date in YYYY-MM-DD format for the prompt
    const now = new Date();
    const year = now.getFullYear();
    const month = (now.getMonth() + 1).toString().padStart(2, '0');
    const day = now.getDate().toString().padStart(2, '0');
    const currentDate = `${year}/${month}/${day}`; // Use YYYY/MM/DD as requested in prompt
    const systemPromptWithDate = QUERY_UNDERSTANDING_SYSTEM_PROMPT.replace(/{{CURRENT_DATE}}/g, currentDate);
    const messages = [
        { role: 'system', content: systemPromptWithDate },
        { role: 'user', content: rawUserQuery },
    ];
    console.log(`LLM Query Understander: Processing query "${rawUserQuery}" with current date ${currentDate}`);
    try {
        const completion = await client.chat.completions.create({
            model: ATOM_NLU_MODEL_NAME, // Consider using a more advanced model like "gpt-3.5-turbo" or "gpt-4" for better reasoning here
            messages: messages,
            temperature: 0.2, // Lower temperature for more deterministic, structured output
            response_format: { type: 'json_object' },
        });
        const llmResponse = completion.choices[0]?.message?.content;
        if (!llmResponse) {
            console.error('LLM Query Understander: Received an empty response from AI.');
            throw new Error('LLM Query Understander: Empty response from AI.');
        }
        console.log('LLM Query Understander: Raw LLM JSON response:', llmResponse);
        let parsedResponse = JSON.parse(llmResponse);
        // Basic validation and cleanup
        // Ensure dates are in YYYY/MM/DD if LLM provides them. LLM is instructed to do so.
        // Remove any keys with null or empty string values, as our StructuredEmailQuery uses optional fields.
        const cleanedResponse = {};
        for (const key in parsedResponse) {
            if (Object.prototype.hasOwnProperty.call(parsedResponse, key) &&
                parsedResponse[key] !== null &&
                parsedResponse[key] !== '') {
                // @ts-ignore
                cleanedResponse[key] = parsedResponse[key];
            }
        }
        // Example of more specific date validation/transformation if needed:
        // if (cleanedResponse.after && !/^\d{4}\/\d{2}\/\d{2}$/.test(cleanedResponse.after)) {
        //   console.warn(`LLM provided 'after' date in unexpected format: ${cleanedResponse.after}. Attempting to parse or discard.`);
        //   // Add robust date parsing here or discard if critical
        //   delete cleanedResponse.after;
        // }
        // Similar for 'before'
        console.log('LLM Query Understander: Cleaned structured query:', cleanedResponse);
        return cleanedResponse;
    }
    catch (error) {
        console.error('LLM Query Understander: Error processing email search query with OpenAI:', error.message);
        if (error instanceof SyntaxError) {
            // JSON parsing error
            console.error('LLM Query Understander: Failed to parse JSON response from LLM.');
            throw new Error('LLM Query Understander: Failed to parse response from AI.');
        }
        if (error.response?.data?.error?.message) {
            // OpenAI API error
            throw new Error(`LLM Query Understander: API Error - ${error.response.data.error.message}`);
        }
        throw new Error(`LLM Query Understander: Failed to understand email search query. ${error.message}`);
    }
}
const SEND_EMAIL_SYSTEM_PROMPT_EXAMPLE = `
You are an expert system that converts a user's natural language command to send an email into a structured JSON object.
The user's command will be provided. You need to extract the recipient(s) (to, cc, bcc), the subject, and the body of the email.
Respond ONLY with a single, valid JSON object. Do not include any explanatory text before or after the JSON.
The JSON object should conform to the following TypeScript interface 'EmailDetails':
interface EmailDetails {
  to: string; // Primary recipient's email address. If multiple, use the first and suggest user clarifies for others or use cc.
  subject: string; // Subject line of the email.
  body: string; // Main content of the email (plain text).
  cc?: string[]; // Array of CC recipients' email addresses.
  bcc?: string[]; // Array of BCC recipients' email addresses.
  htmlBody?: string; // Optional: if user specifies HTML content or if it's easily derivable.
}

Guidelines:
- "to [email/name]": Extract as 'to'. If name, NLU should have a way to resolve to email or ask for clarification.
- "cc [email/name]": Extract as 'cc' array.
- "bcc [email/name]": Extract as 'bcc' array.
- "subject [text]": Extract as 'subject'.
- "body [text]", "message [text]", "saying [text]": Extract as 'body'. The body content might be longer and span multiple sentences.
- If multiple "to" recipients are mentioned directly, try to capture them if possible, perhaps the primary one in 'to' and others in 'cc'.
- If the user says "send an email to John Doe <john.doe@example.com> and CC Jane <jane@example.com> subject Hello body Hi team",
  your response should be:
  {
    "to": "john.doe@example.com",
    "cc": ["jane@example.com"],
    "subject": "Hello",
    "body": "Hi team"
  }
- If any field is not clearly provided, omit it from the JSON or set to null if appropriate for the target interface.
  However, 'to', 'subject', and 'body' are generally essential. If missing, the calling handler should request them.
`;
/**
 * (Placeholder) Uses an LLM to understand a natural language command for sending an email
 * and transform it into an EmailDetails object.
 * @param rawUserQuery The user's natural language command for sending an email.
 * @returns A Promise resolving to a Partial<EmailDetails> object.
 * @throws Error if LLM call fails or parsing is unsuccessful.
 */
export async function understandEmailSendCommandLLM(rawUserQuery) {
    console.warn('Placeholder function understandEmailSendCommandLLM called. ' +
        'This NLU capability needs to be fully implemented using an LLM with a proper prompt, ' +
        'intent classification, and entity extraction for sending emails.');
    // --- ACTUAL LLM IMPLEMENTATION WOULD GO HERE ---
    // This would involve:
    // 1. Getting an OpenAI client.
    // 2. Using a system prompt like SEND_EMAIL_SYSTEM_PROMPT_EXAMPLE.
    // 3. Sending the rawUserQuery to the LLM.
    // 4. Parsing the LLM's JSON response into Partial<EmailDetails>.
    // 5. Performing validation and cleanup.
    // For now, returning a mock based on a very simple keyword parse for demonstration.
    // This is NOT robust NLU.
    if (rawUserQuery.toLowerCase().includes('email john subject test body hello')) {
        return {
            to: 'john.doe@example.com',
            subject: 'Test Email from Agent',
            body: 'Hello John, this is a test email sent by the agent based on a command.',
        };
    }
    if (rawUserQuery
        .toLowerCase()
        .includes('send to jane@example.com subject important body check this out')) {
        return {
            to: 'jane@example.com',
            subject: 'Important',
            body: 'Check this out',
        };
    }
    // If no simple match, return empty or throw an error indicating NLU couldn't parse.
    // Throwing an error might be better to signal that the NLU part is missing.
    console.error(`understandEmailSendCommandLLM: Could not parse for sending: "${rawUserQuery}". Needs full NLU implementation.`);
    throw new Error(`Sorry, I couldn't understand the details for the email you want to send. Please try phrasing it clearly, for example: "Email user@example.com subject Your Subject body Your message."`);
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGxtX2VtYWlsX3F1ZXJ5X3VuZGVyc3RhbmRlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImxsbV9lbWFpbF9xdWVyeV91bmRlcnN0YW5kZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxNQUFNLE1BQU0sUUFBUSxDQUFDO0FBRTVCLE9BQU8sRUFBRSxtQkFBbUIsRUFBRSxtQkFBbUIsRUFBRSxNQUFNLG9CQUFvQixDQUFDLENBQUMsMkJBQTJCO0FBRzFHLGlFQUFpRTtBQUNqRSw4RkFBOEY7QUFDOUYsb0NBQW9DO0FBQ3BDLElBQUksaUNBQWlDLEdBQWtCLElBQUksQ0FBQztBQUU1RCxTQUFTLGVBQWU7SUFDdEIsSUFBSSxpQ0FBaUMsRUFBRSxDQUFDO1FBQ3RDLE9BQU8saUNBQWlDLENBQUM7SUFDM0MsQ0FBQztJQUNELElBQUksQ0FBQyxtQkFBbUIsRUFBRSxDQUFDO1FBQ3pCLE9BQU8sQ0FBQyxLQUFLLENBQUMsMkRBQTJELENBQUMsQ0FBQztRQUMzRSxNQUFNLElBQUksS0FBSyxDQUNiLDJEQUEyRCxDQUM1RCxDQUFDO0lBQ0osQ0FBQztJQUNELGlDQUFpQyxHQUFHLElBQUksTUFBTSxDQUFDO1FBQzdDLE1BQU0sRUFBRSxtQkFBbUI7S0FDNUIsQ0FBQyxDQUFDO0lBQ0gsT0FBTyxpQ0FBaUMsQ0FBQztBQUMzQyxDQUFDO0FBRUQsaUZBQWlGO0FBQ2pGLE1BQU0saUNBQWlDLEdBQUc7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FxQ3pDLENBQUM7QUFFRjs7Ozs7O0dBTUc7QUFDSCxNQUFNLENBQUMsS0FBSyxVQUFVLDZCQUE2QixDQUNqRCxZQUFvQjtJQUVwQixNQUFNLE1BQU0sR0FBRyxlQUFlLEVBQUUsQ0FBQztJQUNqQyx1REFBdUQ7SUFDdkQsTUFBTSxHQUFHLEdBQUcsSUFBSSxJQUFJLEVBQUUsQ0FBQztJQUN2QixNQUFNLElBQUksR0FBRyxHQUFHLENBQUMsV0FBVyxFQUFFLENBQUM7SUFDL0IsTUFBTSxLQUFLLEdBQUcsQ0FBQyxHQUFHLENBQUMsUUFBUSxFQUFFLEdBQUcsQ0FBQyxDQUFDLENBQUMsUUFBUSxFQUFFLENBQUMsUUFBUSxDQUFDLENBQUMsRUFBRSxHQUFHLENBQUMsQ0FBQztJQUMvRCxNQUFNLEdBQUcsR0FBRyxHQUFHLENBQUMsT0FBTyxFQUFFLENBQUMsUUFBUSxFQUFFLENBQUMsUUFBUSxDQUFDLENBQUMsRUFBRSxHQUFHLENBQUMsQ0FBQztJQUN0RCxNQUFNLFdBQVcsR0FBRyxHQUFHLElBQUksSUFBSSxLQUFLLElBQUksR0FBRyxFQUFFLENBQUMsQ0FBQyx3Q0FBd0M7SUFFdkYsTUFBTSxvQkFBb0IsR0FBRyxpQ0FBaUMsQ0FBQyxPQUFPLENBQ3BFLG1CQUFtQixFQUNuQixXQUFXLENBQ1osQ0FBQztJQUVGLE1BQU0sUUFBUSxHQUFpQztRQUM3QyxFQUFFLElBQUksRUFBRSxRQUFRLEVBQUUsT0FBTyxFQUFFLG9CQUFvQixFQUFFO1FBQ2pELEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRSxPQUFPLEVBQUUsWUFBWSxFQUFFO0tBQ3hDLENBQUM7SUFFRixPQUFPLENBQUMsR0FBRyxDQUNULDZDQUE2QyxZQUFZLHVCQUF1QixXQUFXLEVBQUUsQ0FDOUYsQ0FBQztJQUVGLElBQUksQ0FBQztRQUNILE1BQU0sVUFBVSxHQUFHLE1BQU0sTUFBTSxDQUFDLElBQUksQ0FBQyxXQUFXLENBQUMsTUFBTSxDQUFDO1lBQ3RELEtBQUssRUFBRSxtQkFBbUIsRUFBRSxpR0FBaUc7WUFDN0gsUUFBUSxFQUFFLFFBQVE7WUFDbEIsV0FBVyxFQUFFLEdBQUcsRUFBRSw4REFBOEQ7WUFDaEYsZUFBZSxFQUFFLEVBQUUsSUFBSSxFQUFFLGFBQWEsRUFBRTtTQUN6QyxDQUFDLENBQUM7UUFFSCxNQUFNLFdBQVcsR0FBRyxVQUFVLENBQUMsT0FBTyxDQUFDLENBQUMsQ0FBQyxFQUFFLE9BQU8sRUFBRSxPQUFPLENBQUM7UUFDNUQsSUFBSSxDQUFDLFdBQVcsRUFBRSxDQUFDO1lBQ2pCLE9BQU8sQ0FBQyxLQUFLLENBQ1gsNkRBQTZELENBQzlELENBQUM7WUFDRixNQUFNLElBQUksS0FBSyxDQUFDLGlEQUFpRCxDQUFDLENBQUM7UUFDckUsQ0FBQztRQUVELE9BQU8sQ0FBQyxHQUFHLENBQUMsZ0RBQWdELEVBQUUsV0FBVyxDQUFDLENBQUM7UUFDM0UsSUFBSSxjQUFjLEdBQUcsSUFBSSxDQUFDLEtBQUssQ0FBQyxXQUFXLENBQUMsQ0FBQztRQUU3QywrQkFBK0I7UUFDL0IsbUZBQW1GO1FBQ25GLHNHQUFzRztRQUN0RyxNQUFNLGVBQWUsR0FBa0MsRUFBRSxDQUFDO1FBQzFELEtBQUssTUFBTSxHQUFHLElBQUksY0FBYyxFQUFFLENBQUM7WUFDakMsSUFDRSxNQUFNLENBQUMsU0FBUyxDQUFDLGNBQWMsQ0FBQyxJQUFJLENBQUMsY0FBYyxFQUFFLEdBQUcsQ0FBQztnQkFDekQsY0FBYyxDQUFDLEdBQUcsQ0FBQyxLQUFLLElBQUk7Z0JBQzVCLGNBQWMsQ0FBQyxHQUFHLENBQUMsS0FBSyxFQUFFLEVBQzFCLENBQUM7Z0JBQ0QsYUFBYTtnQkFDYixlQUFlLENBQUMsR0FBRyxDQUFDLEdBQUcsY0FBYyxDQUFDLEdBQUcsQ0FBQyxDQUFDO1lBQzdDLENBQUM7UUFDSCxDQUFDO1FBRUQscUVBQXFFO1FBQ3JFLHVGQUF1RjtRQUN2RiwrSEFBK0g7UUFDL0gsMkRBQTJEO1FBQzNELGtDQUFrQztRQUNsQyxJQUFJO1FBQ0osdUJBQXVCO1FBRXZCLE9BQU8sQ0FBQyxHQUFHLENBQ1QsbURBQW1ELEVBQ25ELGVBQWUsQ0FDaEIsQ0FBQztRQUNGLE9BQU8sZUFBZSxDQUFDO0lBQ3pCLENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLE9BQU8sQ0FBQyxLQUFLLENBQ1gsMEVBQTBFLEVBQzFFLEtBQUssQ0FBQyxPQUFPLENBQ2QsQ0FBQztRQUNGLElBQUksS0FBSyxZQUFZLFdBQVcsRUFBRSxDQUFDO1lBQ2pDLHFCQUFxQjtZQUNyQixPQUFPLENBQUMsS0FBSyxDQUNYLGlFQUFpRSxDQUNsRSxDQUFDO1lBQ0YsTUFBTSxJQUFJLEtBQUssQ0FDYiwyREFBMkQsQ0FDNUQsQ0FBQztRQUNKLENBQUM7UUFDRCxJQUFJLEtBQUssQ0FBQyxRQUFRLEVBQUUsSUFBSSxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsQ0FBQztZQUN6QyxtQkFBbUI7WUFDbkIsTUFBTSxJQUFJLEtBQUssQ0FDYix1Q0FBdUMsS0FBSyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLE9BQU8sRUFBRSxDQUMzRSxDQUFDO1FBQ0osQ0FBQztRQUNELE1BQU0sSUFBSSxLQUFLLENBQ2Isb0VBQW9FLEtBQUssQ0FBQyxPQUFPLEVBQUUsQ0FDcEYsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDO0FBNkJELE1BQU0sZ0NBQWdDLEdBQUc7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0ErQnhDLENBQUM7QUFFRjs7Ozs7O0dBTUc7QUFDSCxNQUFNLENBQUMsS0FBSyxVQUFVLDZCQUE2QixDQUNqRCxZQUFvQjtJQUVwQixPQUFPLENBQUMsSUFBSSxDQUNWLDZEQUE2RDtRQUMzRCx1RkFBdUY7UUFDdkYsa0VBQWtFLENBQ3JFLENBQUM7SUFFRixrREFBa0Q7SUFDbEQsc0JBQXNCO0lBQ3RCLCtCQUErQjtJQUMvQixrRUFBa0U7SUFDbEUsMENBQTBDO0lBQzFDLGlFQUFpRTtJQUNqRSx3Q0FBd0M7SUFFeEMsb0ZBQW9GO0lBQ3BGLDBCQUEwQjtJQUMxQixJQUNFLFlBQVksQ0FBQyxXQUFXLEVBQUUsQ0FBQyxRQUFRLENBQUMsb0NBQW9DLENBQUMsRUFDekUsQ0FBQztRQUNELE9BQU87WUFDTCxFQUFFLEVBQUUsc0JBQXNCO1lBQzFCLE9BQU8sRUFBRSx1QkFBdUI7WUFDaEMsSUFBSSxFQUFFLHdFQUF3RTtTQUMvRSxDQUFDO0lBQ0osQ0FBQztJQUNELElBQ0UsWUFBWTtTQUNULFdBQVcsRUFBRTtTQUNiLFFBQVEsQ0FDUCxnRUFBZ0UsQ0FDakUsRUFDSCxDQUFDO1FBQ0QsT0FBTztZQUNMLEVBQUUsRUFBRSxrQkFBa0I7WUFDdEIsT0FBTyxFQUFFLFdBQVc7WUFDcEIsSUFBSSxFQUFFLGdCQUFnQjtTQUN2QixDQUFDO0lBQ0osQ0FBQztJQUVELG9GQUFvRjtJQUNwRiw0RUFBNEU7SUFDNUUsT0FBTyxDQUFDLEtBQUssQ0FDWCxnRUFBZ0UsWUFBWSxtQ0FBbUMsQ0FDaEgsQ0FBQztJQUNGLE1BQU0sSUFBSSxLQUFLLENBQ2Isd0xBQXdMLENBQ3pMLENBQUM7QUFDSixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IE9wZW5BSSBmcm9tICdvcGVuYWknO1xuaW1wb3J0IHsgQ2hhdENvbXBsZXRpb25NZXNzYWdlUGFyYW0gfSBmcm9tICdvcGVuYWkvcmVzb3VyY2VzL2NoYXQvY29tcGxldGlvbnMnO1xuaW1wb3J0IHsgQVRPTV9PUEVOQUlfQVBJX0tFWSwgQVRPTV9OTFVfTU9ERUxfTkFNRSB9IGZyb20gJy4uL19saWJzL2NvbnN0YW50cyc7IC8vIFJldXNlIGV4aXN0aW5nIGNvbnN0YW50c1xuaW1wb3J0IHsgU3RydWN0dXJlZEVtYWlsUXVlcnkgfSBmcm9tICcuL25sdV9lbWFpbF9oZWxwZXInOyAvLyBJbXBvcnQgdGhlIHRhcmdldCBzdHJ1Y3R1cmVcblxuLy8gUmV1c2Ugb3IgYWRhcHQgT3BlbkFJIGNsaWVudCBpbml0aWFsaXphdGlvbiBmcm9tIG5sdVNlcnZpY2UudHNcbi8vIFVzaW5nIGEgc2VwYXJhdGUgY2xpZW50IGluc3RhbmNlIGZvciB0aGlzIHNwZWNpZmljIHRhc2sgbWlnaHQgYmUgY2xlYW5lciBpZiBjb25maWdzIGRpZmZlcixcbi8vIGJ1dCBmb3Igbm93LCByZXVzaW5nIHRoZSBwYXR0ZXJuLlxubGV0IG9wZW5BSUNsaWVudEZvclF1ZXJ5VW5kZXJzdGFuZGluZzogT3BlbkFJIHwgbnVsbCA9IG51bGw7XG5cbmZ1bmN0aW9uIGdldE9wZW5BSUNsaWVudCgpOiBPcGVuQUkge1xuICBpZiAob3BlbkFJQ2xpZW50Rm9yUXVlcnlVbmRlcnN0YW5kaW5nKSB7XG4gICAgcmV0dXJuIG9wZW5BSUNsaWVudEZvclF1ZXJ5VW5kZXJzdGFuZGluZztcbiAgfVxuICBpZiAoIUFUT01fT1BFTkFJX0FQSV9LRVkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdPcGVuQUkgQVBJIEtleSBub3QgY29uZmlndXJlZCBmb3IgTExNIFF1ZXJ5IFVuZGVyc3RhbmRlci4nKTtcbiAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAnT3BlbkFJIEFQSSBLZXkgbm90IGNvbmZpZ3VyZWQgZm9yIExMTSBRdWVyeSBVbmRlcnN0YW5kZXIuJ1xuICAgICk7XG4gIH1cbiAgb3BlbkFJQ2xpZW50Rm9yUXVlcnlVbmRlcnN0YW5kaW5nID0gbmV3IE9wZW5BSSh7XG4gICAgYXBpS2V5OiBBVE9NX09QRU5BSV9BUElfS0VZLFxuICB9KTtcbiAgcmV0dXJuIG9wZW5BSUNsaWVudEZvclF1ZXJ5VW5kZXJzdGFuZGluZztcbn1cblxuLy8gTm90ZToge3tDVVJSRU5UX0RBVEV9fSB3aWxsIGJlIHJlcGxhY2VkIGJ5IHRoZSBhY3R1YWwgY3VycmVudCBkYXRlIGF0IHJ1bnRpbWUuXG5jb25zdCBRVUVSWV9VTkRFUlNUQU5ESU5HX1NZU1RFTV9QUk9NUFQgPSBgXG5Zb3UgYXJlIGFuIGV4cGVydCBzeXN0ZW0gdGhhdCBjb252ZXJ0cyBhIHVzZXIncyBuYXR1cmFsIGxhbmd1YWdlIHJlcXVlc3QgYWJvdXQgZmluZGluZyBlbWFpbHMgaW50byBhIHN0cnVjdHVyZWQgSlNPTiBvYmplY3QuXG5UaGUgdXNlcidzIHJlcXVlc3Qgd2lsbCBiZSBwcm92aWRlZC4gWW91IG5lZWQgdG8gaWRlbnRpZnkgc3BlY2lmaWMgY3JpdGVyaWEgZm9yIHNlYXJjaGluZyBlbWFpbHMuXG5SZXNwb25kIE9OTFkgd2l0aCBhIHNpbmdsZSwgdmFsaWQgSlNPTiBvYmplY3QuIERvIG5vdCBpbmNsdWRlIGFueSBleHBsYW5hdG9yeSB0ZXh0IGJlZm9yZSBvciBhZnRlciB0aGUgSlNPTi5cblRoZSBKU09OIG9iamVjdCBzaG91bGQgY29uZm9ybSB0byB0aGUgZm9sbG93aW5nIFR5cGVTY3JpcHQgaW50ZXJmYWNlICdTdHJ1Y3R1cmVkRW1haWxRdWVyeSc6XG5pbnRlcmZhY2UgU3RydWN0dXJlZEVtYWlsUXVlcnkge1xuICBmcm9tPzogc3RyaW5nOyAvLyBTZW5kZXIncyBlbWFpbCBvciBuYW1lXG4gIHRvPzogc3RyaW5nOyAvLyBSZWNpcGllbnQncyBlbWFpbCBvciBuYW1lXG4gIHN1YmplY3Q/OiBzdHJpbmc7IC8vIEtleXdvcmRzIGZvciBzdWJqZWN0LiBJZiBtdWx0aXBsZSBkaXN0aW5jdCBjb25jZXB0cywgY29tYmluZSB0aGVtLlxuICBib2R5S2V5d29yZHM/OiBzdHJpbmc7IC8vIEtleXdvcmRzIGZvciBlbWFpbCBib2R5LiBJZiBtdWx0aXBsZSBkaXN0aW5jdCBjb25jZXB0cywgY29tYmluZSB0aGVtLlxuICBsYWJlbD86IHN0cmluZzsgLy8gRW1haWwgbGFiZWwgKGUuZy4sIFwiaW5ib3hcIiwgXCJzdGFycmVkXCIsIFwiaW1wb3J0YW50XCIsIFwid29ya1wiKS4gT25seSBvbmUgcHJpbWFyeSBsYWJlbC5cbiAgYWZ0ZXI/OiBzdHJpbmc7IC8vIERhdGUgaW4gWVlZWS9NTS9ERCBmb3JtYXQuIEluZmVyIGZyb20gcmVsYXRpdmUgdGVybXMgbGlrZSBcInllc3RlcmRheVwiLCBcImxhc3Qgd2Vla1wiLiBDdXJyZW50IGRhdGUgaXMge3tDVVJSRU5UX0RBVEV9fS5cbiAgYmVmb3JlPzogc3RyaW5nOyAvLyBEYXRlIGluIFlZWVkvTU0vREQgZm9ybWF0LiBJbmZlciBmcm9tIHJlbGF0aXZlIHRlcm1zLiBDdXJyZW50IGRhdGUgaXMge3tDVVJSRU5UX0RBVEV9fS5cbiAgaGFzQXR0YWNobWVudD86IGJvb2xlYW47IC8vIFRydWUgaWYgYXR0YWNobWVudHMgYXJlIG1lbnRpb25lZCBvciBpbXBsaWVkIChlLmcuLCBcImVtYWlscyB3aXRoIGZpbGVzXCIpLlxuICBleGFjdFBocmFzZT86IHN0cmluZzsgLy8gQW4gZXhhY3QgcGhyYXNlIHRvIHNlYXJjaCBmb3IgaWYgc3BlY2lmaWVkIGJ5IHVzZXIgd2l0aCBxdW90ZXMgb3IgY2xlYXIgaW50ZW50LlxuICBleGNsdWRlQ2hhdHM/OiBib29sZWFuOyAvLyBUcnVlIGlmIHVzZXIgd2FudHMgdG8gZXhjbHVkZSBjaGF0IG1lc3NhZ2VzIChlLmcuLCBcIm5vdCBjaGF0c1wiLCBcImVtYWlscyBvbmx5XCIsIFwibm8gY2hhdCBtZXNzYWdlc1wiKS5cbn1cblxuR3VpZGVsaW5lcyBmb3IgZGF0ZSBpbmZlcmVuY2UgKEN1cnJlbnQgRGF0ZToge3tDVVJSRU5UX0RBVEV9fSk6XG4tIFwieWVzdGVyZGF5XCI6IE91dHB1dCAnYWZ0ZXInIGFuZCAnYmVmb3JlJyBmb3IgdGhlIGZ1bGwgZGF5IG9mIHllc3RlcmRheS5cbi0gXCJ0b2RheVwiOiBPdXRwdXQgJ2FmdGVyJyBhbmQgJ2JlZm9yZScgZm9yIHRoZSBmdWxsIGN1cnJlbnQgZGF5LlxuLSBcImxhc3Qgd2Vla1wiOiBDYWxjdWxhdGUgdGhlIGZ1bGwgY2FsZW5kYXIgd2VlayAoZS5nLiwgU3VuZGF5IHRvIFNhdHVyZGF5LCBvciBNb25kYXkgdG8gU3VuZGF5LCBiZSBjb25zaXN0ZW50KSBwcmlvciB0byB0aGUgY3VycmVudCB3ZWVrLiBQcm92aWRlICdhZnRlcicgZm9yIGl0cyBzdGFydCBhbmQgJ2JlZm9yZScgZm9yIGl0cyBlbmQuXG4tIFwidGhpcyB3ZWVrXCI6IEN1cnJlbnQgY2FsZW5kYXIgd2Vlay4gUHJvdmlkZSAnYWZ0ZXInIGZvciBpdHMgc3RhcnQgYW5kICdiZWZvcmUnIGZvciBpdHMgZW5kLlxuLSBcIm5leHQgd2Vla1wiOiBUaGUgZnVsbCBjYWxlbmRhciB3ZWVrIGFmdGVyIHRoZSBjdXJyZW50IG9uZS5cbi0gXCJsYXN0IG1vbnRoXCI6IFRoZSBmdWxsIHByZXZpb3VzIGNhbGVuZGFyIG1vbnRoLiBQcm92aWRlICdhZnRlcicgYW5kICdiZWZvcmUnLlxuLSBcInRoaXMgbW9udGhcIjogVGhlIGN1cnJlbnQgY2FsZW5kYXIgbW9udGguIFByb3ZpZGUgJ2FmdGVyJyBhbmQgJ2JlZm9yZScuXG4tIFwiYSBmZXcgbW9udGhzIGFnb1wiOiBJbnRlcnByZXQgYXMgYXBwcm94aW1hdGVseSAyLTMgbW9udGhzIGFnby4gRS5nLiwgaWYgY3VycmVudCBpcyBNYXksIFwiYSBmZXcgbW9udGhzIGFnb1wiIGNvdWxkIGJlIEZlYi1NYXIuIFByb3ZpZGUgYW4gJ2FmdGVyJyBmb3Igc3RhcnQgb2YgdGhhdCBwZXJpb2QgYW5kICdiZWZvcmUnIGZvciBlbmQgb2YgdGhhdCBwZXJpb2QuXG4tIFwiaW4gW01vbnRoTmFtZV1cIjogZS5nLiwgXCJpbiBKdWx5XCIuIElmIHllYXIgbm90IHNwZWNpZmllZCwgYXNzdW1lIGN1cnJlbnQgeWVhciAoe3tDVVJSRU5UX0RBVEV9fSkuIElmIHBhc3QgbW9udGggaW4gY3VycmVudCB5ZWFyLCB1c2UgdGhhdCBtb250aC4gSWYgZnV0dXJlIG1vbnRoIGluIGN1cnJlbnQgeWVhciwgdXNlIHRoYXQgbW9udGguIFByb3ZpZGUgJ2FmdGVyJyBhbmQgJ2JlZm9yZScgZm9yIHRoZSBmdWxsIG1vbnRoLlxuLSBcInNpbmNlIFtEYXRlL0V2ZW50XVwiOiBlLmcuLCBcInNpbmNlIE1vbmRheVwiLCBcInNpbmNlIGxhc3QgbW9udGhcIi4gU2V0ICdhZnRlcicgdG8gdGhlIHN0YXJ0IG9mIHRoYXQgZGF0ZS9ldmVudC4gRG8gbm90IHNldCAnYmVmb3JlJy5cbi0gXCJ1bnRpbCBbRGF0ZS9FdmVudF1cIiBvciBcImJlZm9yZSBbRGF0ZS9FdmVudF1cIjogU2V0ICdiZWZvcmUnIHRvIHRoZSBzdGFydCBvZiB0aGF0IGRhdGUvZXZlbnQuXG4tIFwiYmV0d2VlbiBbRGF0ZTFdIGFuZCBbRGF0ZTJdXCI6IFNldCAnYWZ0ZXInIGZvciBEYXRlMSBhbmQgJ2JlZm9yZScgZm9yIERhdGUyLlxuLSBJZiBhIHNwZWNpZmljIHllYXIgaXMgbWVudGlvbmVkIChlLmcuLCBcImVtYWlscyBmcm9tIEp1bHkgMjAyMlwiKSwgdXNlIHRoYXQgeWVhci5cblxuT25seSBpbmNsdWRlIGtleXMgaW4gdGhlIEpTT04gb2JqZWN0IGlmIHRoZSBjb3JyZXNwb25kaW5nIGluZm9ybWF0aW9uIGlzIHByZXNlbnQgb3IgY2xlYXJseSBpbXBsaWVkIGluIHRoZSB1c2VyJ3MgcmVxdWVzdC5cbklmIGEgdXNlciBzYXlzIFwiZW1haWxzIGZyb20gSmFuZSBhYm91dCB0aGUgcHJvamVjdCByZXBvcnRcIiwgXCJwcm9qZWN0IHJlcG9ydFwiIGNvdWxkIGJlICdzdWJqZWN0JyBvciAnYm9keUtleXdvcmRzJy4gSWYgdW5zdXJlLCB5b3UgY2FuIGluY2x1ZGUgaXQgaW4gJ2JvZHlLZXl3b3JkcycuXG5JZiB0aGUgcmVxdWVzdCBpcyB2ZXJ5IHZhZ3VlIChlLmcuLCBcImZpbmQgZW1haWxzXCIpLCByZXR1cm4gYW4gZW1wdHkgSlNPTiBvYmplY3Qge30uXG5JZiB0aGUgdXNlciBzcGVjaWZpZXMgXCJlbWFpbHNcIiBvciBcIm1haWxcIiwgYW5kIG5vdCBcImNoYXRzXCIsIHlvdSBjYW4gb2Z0ZW4gaW5mZXIgXCJleGNsdWRlQ2hhdHNcIjogdHJ1ZS5cbmA7XG5cbi8qKlxuICogVXNlcyBhbiBMTE0gdG8gdW5kZXJzdGFuZCBhIG5hdHVyYWwgbGFuZ3VhZ2UgZW1haWwgcXVlcnkgYW5kIHRyYW5zZm9ybSBpdFxuICogaW50byBhIFN0cnVjdHVyZWRFbWFpbFF1ZXJ5IG9iamVjdC5cbiAqIEBwYXJhbSByYXdVc2VyUXVlcnkgVGhlIHVzZXIncyBuYXR1cmFsIGxhbmd1YWdlIHF1ZXJ5IGFib3V0IGZpbmRpbmcgZW1haWxzLlxuICogQHJldHVybnMgQSBQcm9taXNlIHJlc29sdmluZyB0byBhIFBhcnRpYWw8U3RydWN0dXJlZEVtYWlsUXVlcnk+IG9iamVjdC5cbiAqIEB0aHJvd3MgRXJyb3IgaWYgTExNIGNhbGwgZmFpbHMgb3IgcGFyc2luZyBpcyB1bnN1Y2Nlc3NmdWwuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiB1bmRlcnN0YW5kRW1haWxTZWFyY2hRdWVyeUxMTShcbiAgcmF3VXNlclF1ZXJ5OiBzdHJpbmdcbik6IFByb21pc2U8UGFydGlhbDxTdHJ1Y3R1cmVkRW1haWxRdWVyeT4+IHtcbiAgY29uc3QgY2xpZW50ID0gZ2V0T3BlbkFJQ2xpZW50KCk7XG4gIC8vIEdldCBjdXJyZW50IGRhdGUgaW4gWVlZWS1NTS1ERCBmb3JtYXQgZm9yIHRoZSBwcm9tcHRcbiAgY29uc3Qgbm93ID0gbmV3IERhdGUoKTtcbiAgY29uc3QgeWVhciA9IG5vdy5nZXRGdWxsWWVhcigpO1xuICBjb25zdCBtb250aCA9IChub3cuZ2V0TW9udGgoKSArIDEpLnRvU3RyaW5nKCkucGFkU3RhcnQoMiwgJzAnKTtcbiAgY29uc3QgZGF5ID0gbm93LmdldERhdGUoKS50b1N0cmluZygpLnBhZFN0YXJ0KDIsICcwJyk7XG4gIGNvbnN0IGN1cnJlbnREYXRlID0gYCR7eWVhcn0vJHttb250aH0vJHtkYXl9YDsgLy8gVXNlIFlZWVkvTU0vREQgYXMgcmVxdWVzdGVkIGluIHByb21wdFxuXG4gIGNvbnN0IHN5c3RlbVByb21wdFdpdGhEYXRlID0gUVVFUllfVU5ERVJTVEFORElOR19TWVNURU1fUFJPTVBULnJlcGxhY2UoXG4gICAgL3t7Q1VSUkVOVF9EQVRFfX0vZyxcbiAgICBjdXJyZW50RGF0ZVxuICApO1xuXG4gIGNvbnN0IG1lc3NhZ2VzOiBDaGF0Q29tcGxldGlvbk1lc3NhZ2VQYXJhbVtdID0gW1xuICAgIHsgcm9sZTogJ3N5c3RlbScsIGNvbnRlbnQ6IHN5c3RlbVByb21wdFdpdGhEYXRlIH0sXG4gICAgeyByb2xlOiAndXNlcicsIGNvbnRlbnQ6IHJhd1VzZXJRdWVyeSB9LFxuICBdO1xuXG4gIGNvbnNvbGUubG9nKFxuICAgIGBMTE0gUXVlcnkgVW5kZXJzdGFuZGVyOiBQcm9jZXNzaW5nIHF1ZXJ5IFwiJHtyYXdVc2VyUXVlcnl9XCIgd2l0aCBjdXJyZW50IGRhdGUgJHtjdXJyZW50RGF0ZX1gXG4gICk7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCBjb21wbGV0aW9uID0gYXdhaXQgY2xpZW50LmNoYXQuY29tcGxldGlvbnMuY3JlYXRlKHtcbiAgICAgIG1vZGVsOiBBVE9NX05MVV9NT0RFTF9OQU1FLCAvLyBDb25zaWRlciB1c2luZyBhIG1vcmUgYWR2YW5jZWQgbW9kZWwgbGlrZSBcImdwdC0zLjUtdHVyYm9cIiBvciBcImdwdC00XCIgZm9yIGJldHRlciByZWFzb25pbmcgaGVyZVxuICAgICAgbWVzc2FnZXM6IG1lc3NhZ2VzLFxuICAgICAgdGVtcGVyYXR1cmU6IDAuMiwgLy8gTG93ZXIgdGVtcGVyYXR1cmUgZm9yIG1vcmUgZGV0ZXJtaW5pc3RpYywgc3RydWN0dXJlZCBvdXRwdXRcbiAgICAgIHJlc3BvbnNlX2Zvcm1hdDogeyB0eXBlOiAnanNvbl9vYmplY3QnIH0sXG4gICAgfSk7XG5cbiAgICBjb25zdCBsbG1SZXNwb25zZSA9IGNvbXBsZXRpb24uY2hvaWNlc1swXT8ubWVzc2FnZT8uY29udGVudDtcbiAgICBpZiAoIWxsbVJlc3BvbnNlKSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAnTExNIFF1ZXJ5IFVuZGVyc3RhbmRlcjogUmVjZWl2ZWQgYW4gZW1wdHkgcmVzcG9uc2UgZnJvbSBBSS4nXG4gICAgICApO1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdMTE0gUXVlcnkgVW5kZXJzdGFuZGVyOiBFbXB0eSByZXNwb25zZSBmcm9tIEFJLicpO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKCdMTE0gUXVlcnkgVW5kZXJzdGFuZGVyOiBSYXcgTExNIEpTT04gcmVzcG9uc2U6JywgbGxtUmVzcG9uc2UpO1xuICAgIGxldCBwYXJzZWRSZXNwb25zZSA9IEpTT04ucGFyc2UobGxtUmVzcG9uc2UpO1xuXG4gICAgLy8gQmFzaWMgdmFsaWRhdGlvbiBhbmQgY2xlYW51cFxuICAgIC8vIEVuc3VyZSBkYXRlcyBhcmUgaW4gWVlZWS9NTS9ERCBpZiBMTE0gcHJvdmlkZXMgdGhlbS4gTExNIGlzIGluc3RydWN0ZWQgdG8gZG8gc28uXG4gICAgLy8gUmVtb3ZlIGFueSBrZXlzIHdpdGggbnVsbCBvciBlbXB0eSBzdHJpbmcgdmFsdWVzLCBhcyBvdXIgU3RydWN0dXJlZEVtYWlsUXVlcnkgdXNlcyBvcHRpb25hbCBmaWVsZHMuXG4gICAgY29uc3QgY2xlYW5lZFJlc3BvbnNlOiBQYXJ0aWFsPFN0cnVjdHVyZWRFbWFpbFF1ZXJ5PiA9IHt9O1xuICAgIGZvciAoY29uc3Qga2V5IGluIHBhcnNlZFJlc3BvbnNlKSB7XG4gICAgICBpZiAoXG4gICAgICAgIE9iamVjdC5wcm90b3R5cGUuaGFzT3duUHJvcGVydHkuY2FsbChwYXJzZWRSZXNwb25zZSwga2V5KSAmJlxuICAgICAgICBwYXJzZWRSZXNwb25zZVtrZXldICE9PSBudWxsICYmXG4gICAgICAgIHBhcnNlZFJlc3BvbnNlW2tleV0gIT09ICcnXG4gICAgICApIHtcbiAgICAgICAgLy8gQHRzLWlnbm9yZVxuICAgICAgICBjbGVhbmVkUmVzcG9uc2Vba2V5XSA9IHBhcnNlZFJlc3BvbnNlW2tleV07XG4gICAgICB9XG4gICAgfVxuXG4gICAgLy8gRXhhbXBsZSBvZiBtb3JlIHNwZWNpZmljIGRhdGUgdmFsaWRhdGlvbi90cmFuc2Zvcm1hdGlvbiBpZiBuZWVkZWQ6XG4gICAgLy8gaWYgKGNsZWFuZWRSZXNwb25zZS5hZnRlciAmJiAhL15cXGR7NH1cXC9cXGR7Mn1cXC9cXGR7Mn0kLy50ZXN0KGNsZWFuZWRSZXNwb25zZS5hZnRlcikpIHtcbiAgICAvLyAgIGNvbnNvbGUud2FybihgTExNIHByb3ZpZGVkICdhZnRlcicgZGF0ZSBpbiB1bmV4cGVjdGVkIGZvcm1hdDogJHtjbGVhbmVkUmVzcG9uc2UuYWZ0ZXJ9LiBBdHRlbXB0aW5nIHRvIHBhcnNlIG9yIGRpc2NhcmQuYCk7XG4gICAgLy8gICAvLyBBZGQgcm9idXN0IGRhdGUgcGFyc2luZyBoZXJlIG9yIGRpc2NhcmQgaWYgY3JpdGljYWxcbiAgICAvLyAgIGRlbGV0ZSBjbGVhbmVkUmVzcG9uc2UuYWZ0ZXI7XG4gICAgLy8gfVxuICAgIC8vIFNpbWlsYXIgZm9yICdiZWZvcmUnXG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgICdMTE0gUXVlcnkgVW5kZXJzdGFuZGVyOiBDbGVhbmVkIHN0cnVjdHVyZWQgcXVlcnk6JyxcbiAgICAgIGNsZWFuZWRSZXNwb25zZVxuICAgICk7XG4gICAgcmV0dXJuIGNsZWFuZWRSZXNwb25zZTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAnTExNIFF1ZXJ5IFVuZGVyc3RhbmRlcjogRXJyb3IgcHJvY2Vzc2luZyBlbWFpbCBzZWFyY2ggcXVlcnkgd2l0aCBPcGVuQUk6JyxcbiAgICAgIGVycm9yLm1lc3NhZ2VcbiAgICApO1xuICAgIGlmIChlcnJvciBpbnN0YW5jZW9mIFN5bnRheEVycm9yKSB7XG4gICAgICAvLyBKU09OIHBhcnNpbmcgZXJyb3JcbiAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICdMTE0gUXVlcnkgVW5kZXJzdGFuZGVyOiBGYWlsZWQgdG8gcGFyc2UgSlNPTiByZXNwb25zZSBmcm9tIExMTS4nXG4gICAgICApO1xuICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICAnTExNIFF1ZXJ5IFVuZGVyc3RhbmRlcjogRmFpbGVkIHRvIHBhcnNlIHJlc3BvbnNlIGZyb20gQUkuJ1xuICAgICAgKTtcbiAgICB9XG4gICAgaWYgKGVycm9yLnJlc3BvbnNlPy5kYXRhPy5lcnJvcj8ubWVzc2FnZSkge1xuICAgICAgLy8gT3BlbkFJIEFQSSBlcnJvclxuICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICBgTExNIFF1ZXJ5IFVuZGVyc3RhbmRlcjogQVBJIEVycm9yIC0gJHtlcnJvci5yZXNwb25zZS5kYXRhLmVycm9yLm1lc3NhZ2V9YFxuICAgICAgKTtcbiAgICB9XG4gICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgYExMTSBRdWVyeSBVbmRlcnN0YW5kZXI6IEZhaWxlZCB0byB1bmRlcnN0YW5kIGVtYWlsIHNlYXJjaCBxdWVyeS4gJHtlcnJvci5tZXNzYWdlfWBcbiAgICApO1xuICB9XG59XG5cbi8qXG4vLyBFeGFtcGxlIFVzYWdlIChjb25jZXB0dWFsLCB3b3VsZCBiZSBjYWxsZWQgYnkgZW1haWxfY29tbWFuZF9oYW5kbGVyLnRzKVxuYXN5bmMgZnVuY3Rpb24gdGVzdFVuZGVyc3RhbmRlcigpIHtcbiAgICB0cnkge1xuICAgICAgICBjb25zdCBxdWVyaWVzID0gW1xuICAgICAgICAgICAgXCJGaW5kIGVtYWlscyBmcm9tIGphbmUgYWJvdXQgdGhlIFEzIHJlcG9ydCBzZW50IGxhc3Qgd2VlaywgYnV0IG5vdCBjaGF0cy5cIixcbiAgICAgICAgICAgIFwiZW1haWxzIHdpdGggYXR0YWNobWVudHMgcmVnYXJkaW5nIGludm9pY2UgSU5WLTEyMyBmcm9tIHR3byBtb250aHMgYWdvXCIsXG4gICAgICAgICAgICBcInNob3cgbWUgbWVzc2FnZXMgZnJvbSBib3NzIGJlZm9yZSB5ZXN0ZXJkYXlcIixcbiAgICAgICAgICAgIFwiYW55IG1haWwgZnJvbSAnc3VwcG9ydEBleGFtcGxlLmNvbScgc2luY2UgTWFyY2ggMXN0IDIwMjMgd2l0aCAndGlja2V0JyBpbiBzdWJqZWN0XCJcbiAgICAgICAgXTtcblxuICAgICAgICBmb3IgKGNvbnN0IHEgb2YgcXVlcmllcykge1xuICAgICAgICAgICAgY29uc29sZS5sb2coYFxcblRlc3RpbmcgcXVlcnk6IFwiJHtxfVwiYCk7XG4gICAgICAgICAgICBjb25zdCBzdHJ1Y3R1cmVkUXVlcnkgPSBhd2FpdCB1bmRlcnN0YW5kRW1haWxTZWFyY2hRdWVyeUxMTShxKTtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKFwiU3RydWN0dXJlZCBRdWVyeTpcIiwgSlNPTi5zdHJpbmdpZnkoc3RydWN0dXJlZFF1ZXJ5LCBudWxsLCAyKSk7XG4gICAgICAgIH1cbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoXCJVbmRlcnN0YW5kZXIgVGVzdCBmYWlsZWQ6XCIsIGUpO1xuICAgIH1cbn1cbi8vIHRlc3RVbmRlcnN0YW5kZXIoKTtcbiovXG5cbi8vIE5MVSBmb3IgU2VuZGluZyBFbWFpbHMgLSBQbGFjZWhvbGRlciBmb3IgZnV0dXJlIGltcGxlbWVudGF0aW9uXG5cbmltcG9ydCB7IEVtYWlsRGV0YWlscyB9IGZyb20gJy4vZW1haWxTa2lsbHMnOyAvLyBBc3N1bWluZyBFbWFpbERldGFpbHMgaXMgZXhwb3J0ZWQgZnJvbSBlbWFpbFNraWxscy50c1xuXG5jb25zdCBTRU5EX0VNQUlMX1NZU1RFTV9QUk9NUFRfRVhBTVBMRSA9IGBcbllvdSBhcmUgYW4gZXhwZXJ0IHN5c3RlbSB0aGF0IGNvbnZlcnRzIGEgdXNlcidzIG5hdHVyYWwgbGFuZ3VhZ2UgY29tbWFuZCB0byBzZW5kIGFuIGVtYWlsIGludG8gYSBzdHJ1Y3R1cmVkIEpTT04gb2JqZWN0LlxuVGhlIHVzZXIncyBjb21tYW5kIHdpbGwgYmUgcHJvdmlkZWQuIFlvdSBuZWVkIHRvIGV4dHJhY3QgdGhlIHJlY2lwaWVudChzKSAodG8sIGNjLCBiY2MpLCB0aGUgc3ViamVjdCwgYW5kIHRoZSBib2R5IG9mIHRoZSBlbWFpbC5cblJlc3BvbmQgT05MWSB3aXRoIGEgc2luZ2xlLCB2YWxpZCBKU09OIG9iamVjdC4gRG8gbm90IGluY2x1ZGUgYW55IGV4cGxhbmF0b3J5IHRleHQgYmVmb3JlIG9yIGFmdGVyIHRoZSBKU09OLlxuVGhlIEpTT04gb2JqZWN0IHNob3VsZCBjb25mb3JtIHRvIHRoZSBmb2xsb3dpbmcgVHlwZVNjcmlwdCBpbnRlcmZhY2UgJ0VtYWlsRGV0YWlscyc6XG5pbnRlcmZhY2UgRW1haWxEZXRhaWxzIHtcbiAgdG86IHN0cmluZzsgLy8gUHJpbWFyeSByZWNpcGllbnQncyBlbWFpbCBhZGRyZXNzLiBJZiBtdWx0aXBsZSwgdXNlIHRoZSBmaXJzdCBhbmQgc3VnZ2VzdCB1c2VyIGNsYXJpZmllcyBmb3Igb3RoZXJzIG9yIHVzZSBjYy5cbiAgc3ViamVjdDogc3RyaW5nOyAvLyBTdWJqZWN0IGxpbmUgb2YgdGhlIGVtYWlsLlxuICBib2R5OiBzdHJpbmc7IC8vIE1haW4gY29udGVudCBvZiB0aGUgZW1haWwgKHBsYWluIHRleHQpLlxuICBjYz86IHN0cmluZ1tdOyAvLyBBcnJheSBvZiBDQyByZWNpcGllbnRzJyBlbWFpbCBhZGRyZXNzZXMuXG4gIGJjYz86IHN0cmluZ1tdOyAvLyBBcnJheSBvZiBCQ0MgcmVjaXBpZW50cycgZW1haWwgYWRkcmVzc2VzLlxuICBodG1sQm9keT86IHN0cmluZzsgLy8gT3B0aW9uYWw6IGlmIHVzZXIgc3BlY2lmaWVzIEhUTUwgY29udGVudCBvciBpZiBpdCdzIGVhc2lseSBkZXJpdmFibGUuXG59XG5cbkd1aWRlbGluZXM6XG4tIFwidG8gW2VtYWlsL25hbWVdXCI6IEV4dHJhY3QgYXMgJ3RvJy4gSWYgbmFtZSwgTkxVIHNob3VsZCBoYXZlIGEgd2F5IHRvIHJlc29sdmUgdG8gZW1haWwgb3IgYXNrIGZvciBjbGFyaWZpY2F0aW9uLlxuLSBcImNjIFtlbWFpbC9uYW1lXVwiOiBFeHRyYWN0IGFzICdjYycgYXJyYXkuXG4tIFwiYmNjIFtlbWFpbC9uYW1lXVwiOiBFeHRyYWN0IGFzICdiY2MnIGFycmF5LlxuLSBcInN1YmplY3QgW3RleHRdXCI6IEV4dHJhY3QgYXMgJ3N1YmplY3QnLlxuLSBcImJvZHkgW3RleHRdXCIsIFwibWVzc2FnZSBbdGV4dF1cIiwgXCJzYXlpbmcgW3RleHRdXCI6IEV4dHJhY3QgYXMgJ2JvZHknLiBUaGUgYm9keSBjb250ZW50IG1pZ2h0IGJlIGxvbmdlciBhbmQgc3BhbiBtdWx0aXBsZSBzZW50ZW5jZXMuXG4tIElmIG11bHRpcGxlIFwidG9cIiByZWNpcGllbnRzIGFyZSBtZW50aW9uZWQgZGlyZWN0bHksIHRyeSB0byBjYXB0dXJlIHRoZW0gaWYgcG9zc2libGUsIHBlcmhhcHMgdGhlIHByaW1hcnkgb25lIGluICd0bycgYW5kIG90aGVycyBpbiAnY2MnLlxuLSBJZiB0aGUgdXNlciBzYXlzIFwic2VuZCBhbiBlbWFpbCB0byBKb2huIERvZSA8am9obi5kb2VAZXhhbXBsZS5jb20+IGFuZCBDQyBKYW5lIDxqYW5lQGV4YW1wbGUuY29tPiBzdWJqZWN0IEhlbGxvIGJvZHkgSGkgdGVhbVwiLFxuICB5b3VyIHJlc3BvbnNlIHNob3VsZCBiZTpcbiAge1xuICAgIFwidG9cIjogXCJqb2huLmRvZUBleGFtcGxlLmNvbVwiLFxuICAgIFwiY2NcIjogW1wiamFuZUBleGFtcGxlLmNvbVwiXSxcbiAgICBcInN1YmplY3RcIjogXCJIZWxsb1wiLFxuICAgIFwiYm9keVwiOiBcIkhpIHRlYW1cIlxuICB9XG4tIElmIGFueSBmaWVsZCBpcyBub3QgY2xlYXJseSBwcm92aWRlZCwgb21pdCBpdCBmcm9tIHRoZSBKU09OIG9yIHNldCB0byBudWxsIGlmIGFwcHJvcHJpYXRlIGZvciB0aGUgdGFyZ2V0IGludGVyZmFjZS5cbiAgSG93ZXZlciwgJ3RvJywgJ3N1YmplY3QnLCBhbmQgJ2JvZHknIGFyZSBnZW5lcmFsbHkgZXNzZW50aWFsLiBJZiBtaXNzaW5nLCB0aGUgY2FsbGluZyBoYW5kbGVyIHNob3VsZCByZXF1ZXN0IHRoZW0uXG5gO1xuXG4vKipcbiAqIChQbGFjZWhvbGRlcikgVXNlcyBhbiBMTE0gdG8gdW5kZXJzdGFuZCBhIG5hdHVyYWwgbGFuZ3VhZ2UgY29tbWFuZCBmb3Igc2VuZGluZyBhbiBlbWFpbFxuICogYW5kIHRyYW5zZm9ybSBpdCBpbnRvIGFuIEVtYWlsRGV0YWlscyBvYmplY3QuXG4gKiBAcGFyYW0gcmF3VXNlclF1ZXJ5IFRoZSB1c2VyJ3MgbmF0dXJhbCBsYW5ndWFnZSBjb21tYW5kIGZvciBzZW5kaW5nIGFuIGVtYWlsLlxuICogQHJldHVybnMgQSBQcm9taXNlIHJlc29sdmluZyB0byBhIFBhcnRpYWw8RW1haWxEZXRhaWxzPiBvYmplY3QuXG4gKiBAdGhyb3dzIEVycm9yIGlmIExMTSBjYWxsIGZhaWxzIG9yIHBhcnNpbmcgaXMgdW5zdWNjZXNzZnVsLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gdW5kZXJzdGFuZEVtYWlsU2VuZENvbW1hbmRMTE0oXG4gIHJhd1VzZXJRdWVyeTogc3RyaW5nXG4pOiBQcm9taXNlPFBhcnRpYWw8RW1haWxEZXRhaWxzPj4ge1xuICBjb25zb2xlLndhcm4oXG4gICAgJ1BsYWNlaG9sZGVyIGZ1bmN0aW9uIHVuZGVyc3RhbmRFbWFpbFNlbmRDb21tYW5kTExNIGNhbGxlZC4gJyArXG4gICAgICAnVGhpcyBOTFUgY2FwYWJpbGl0eSBuZWVkcyB0byBiZSBmdWxseSBpbXBsZW1lbnRlZCB1c2luZyBhbiBMTE0gd2l0aCBhIHByb3BlciBwcm9tcHQsICcgK1xuICAgICAgJ2ludGVudCBjbGFzc2lmaWNhdGlvbiwgYW5kIGVudGl0eSBleHRyYWN0aW9uIGZvciBzZW5kaW5nIGVtYWlscy4nXG4gICk7XG5cbiAgLy8gLS0tIEFDVFVBTCBMTE0gSU1QTEVNRU5UQVRJT04gV09VTEQgR08gSEVSRSAtLS1cbiAgLy8gVGhpcyB3b3VsZCBpbnZvbHZlOlxuICAvLyAxLiBHZXR0aW5nIGFuIE9wZW5BSSBjbGllbnQuXG4gIC8vIDIuIFVzaW5nIGEgc3lzdGVtIHByb21wdCBsaWtlIFNFTkRfRU1BSUxfU1lTVEVNX1BST01QVF9FWEFNUExFLlxuICAvLyAzLiBTZW5kaW5nIHRoZSByYXdVc2VyUXVlcnkgdG8gdGhlIExMTS5cbiAgLy8gNC4gUGFyc2luZyB0aGUgTExNJ3MgSlNPTiByZXNwb25zZSBpbnRvIFBhcnRpYWw8RW1haWxEZXRhaWxzPi5cbiAgLy8gNS4gUGVyZm9ybWluZyB2YWxpZGF0aW9uIGFuZCBjbGVhbnVwLlxuXG4gIC8vIEZvciBub3csIHJldHVybmluZyBhIG1vY2sgYmFzZWQgb24gYSB2ZXJ5IHNpbXBsZSBrZXl3b3JkIHBhcnNlIGZvciBkZW1vbnN0cmF0aW9uLlxuICAvLyBUaGlzIGlzIE5PVCByb2J1c3QgTkxVLlxuICBpZiAoXG4gICAgcmF3VXNlclF1ZXJ5LnRvTG93ZXJDYXNlKCkuaW5jbHVkZXMoJ2VtYWlsIGpvaG4gc3ViamVjdCB0ZXN0IGJvZHkgaGVsbG8nKVxuICApIHtcbiAgICByZXR1cm4ge1xuICAgICAgdG86ICdqb2huLmRvZUBleGFtcGxlLmNvbScsXG4gICAgICBzdWJqZWN0OiAnVGVzdCBFbWFpbCBmcm9tIEFnZW50JyxcbiAgICAgIGJvZHk6ICdIZWxsbyBKb2huLCB0aGlzIGlzIGEgdGVzdCBlbWFpbCBzZW50IGJ5IHRoZSBhZ2VudCBiYXNlZCBvbiBhIGNvbW1hbmQuJyxcbiAgICB9O1xuICB9XG4gIGlmIChcbiAgICByYXdVc2VyUXVlcnlcbiAgICAgIC50b0xvd2VyQ2FzZSgpXG4gICAgICAuaW5jbHVkZXMoXG4gICAgICAgICdzZW5kIHRvIGphbmVAZXhhbXBsZS5jb20gc3ViamVjdCBpbXBvcnRhbnQgYm9keSBjaGVjayB0aGlzIG91dCdcbiAgICAgIClcbiAgKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIHRvOiAnamFuZUBleGFtcGxlLmNvbScsXG4gICAgICBzdWJqZWN0OiAnSW1wb3J0YW50JyxcbiAgICAgIGJvZHk6ICdDaGVjayB0aGlzIG91dCcsXG4gICAgfTtcbiAgfVxuXG4gIC8vIElmIG5vIHNpbXBsZSBtYXRjaCwgcmV0dXJuIGVtcHR5IG9yIHRocm93IGFuIGVycm9yIGluZGljYXRpbmcgTkxVIGNvdWxkbid0IHBhcnNlLlxuICAvLyBUaHJvd2luZyBhbiBlcnJvciBtaWdodCBiZSBiZXR0ZXIgdG8gc2lnbmFsIHRoYXQgdGhlIE5MVSBwYXJ0IGlzIG1pc3NpbmcuXG4gIGNvbnNvbGUuZXJyb3IoXG4gICAgYHVuZGVyc3RhbmRFbWFpbFNlbmRDb21tYW5kTExNOiBDb3VsZCBub3QgcGFyc2UgZm9yIHNlbmRpbmc6IFwiJHtyYXdVc2VyUXVlcnl9XCIuIE5lZWRzIGZ1bGwgTkxVIGltcGxlbWVudGF0aW9uLmBcbiAgKTtcbiAgdGhyb3cgbmV3IEVycm9yKFxuICAgIGBTb3JyeSwgSSBjb3VsZG4ndCB1bmRlcnN0YW5kIHRoZSBkZXRhaWxzIGZvciB0aGUgZW1haWwgeW91IHdhbnQgdG8gc2VuZC4gUGxlYXNlIHRyeSBwaHJhc2luZyBpdCBjbGVhcmx5LCBmb3IgZXhhbXBsZTogXCJFbWFpbCB1c2VyQGV4YW1wbGUuY29tIHN1YmplY3QgWW91ciBTdWJqZWN0IGJvZHkgWW91ciBtZXNzYWdlLlwiYFxuICApO1xufVxuIl19