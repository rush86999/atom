import OpenAI from 'openai';
import { ChatCompletionMessageParam } from 'openai/resources/chat/completions';
import { ATOM_OPENAI_API_KEY, ATOM_NLU_MODEL_NAME } from '../_libs/constants'; // Reuse existing constants
import { StructuredEmailQuery } from './nlu_email_helper'; // Import the target structure

// Reuse or adapt OpenAI client initialization from nluService.ts
// Using a separate client instance for this specific task might be cleaner if configs differ,
// but for now, reusing the pattern.
let openAIClientForQueryUnderstanding: OpenAI | null = null;

function getOpenAIClient(): OpenAI {
  if (openAIClientForQueryUnderstanding) {
    return openAIClientForQueryUnderstanding;
  }
  if (!ATOM_OPENAI_API_KEY) {
    console.error('OpenAI API Key not configured for LLM Query Understander.');
    throw new Error('OpenAI API Key not configured for LLM Query Understander.');
  }
  openAIClientForQueryUnderstanding = new OpenAI({ apiKey: ATOM_OPENAI_API_KEY });
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
export async function understandEmailSearchQueryLLM(rawUserQuery: string): Promise<Partial<StructuredEmailQuery>> {
  const client = getOpenAIClient();
  // Get current date in YYYY-MM-DD format for the prompt
  const now = new Date();
  const year = now.getFullYear();
  const month = (now.getMonth() + 1).toString().padStart(2, '0');
  const day = now.getDate().toString().padStart(2, '0');
  const currentDate = `${year}/${month}/${day}`; // Use YYYY/MM/DD as requested in prompt

  const systemPromptWithDate = QUERY_UNDERSTANDING_SYSTEM_PROMPT.replace(/{{CURRENT_DATE}}/g, currentDate);

  const messages: ChatCompletionMessageParam[] = [
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
    const cleanedResponse: Partial<StructuredEmailQuery> = {};
    for (const key in parsedResponse) {
      if (Object.prototype.hasOwnProperty.call(parsedResponse, key) &&
          parsedResponse[key] !== null &&
          parsedResponse[key] !== "") {
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

  } catch (error: any) {
    console.error('LLM Query Understander: Error processing email search query with OpenAI:', error.message);
    if (error instanceof SyntaxError) { // JSON parsing error
        console.error('LLM Query Understander: Failed to parse JSON response from LLM.');
        throw new Error('LLM Query Understander: Failed to parse response from AI.');
    }
    if (error.response?.data?.error?.message) { // OpenAI API error
        throw new Error(`LLM Query Understander: API Error - ${error.response.data.error.message}`);
    }
    throw new Error(`LLM Query Understander: Failed to understand email search query. ${error.message}`);
  }
}

/*
// Example Usage (conceptual, would be called by email_command_handler.ts)
async function testUnderstander() {
    try {
        const queries = [
            "Find emails from jane about the Q3 report sent last week, but not chats.",
            "emails with attachments regarding invoice INV-123 from two months ago",
            "show me messages from boss before yesterday",
            "any mail from 'support@example.com' since March 1st 2023 with 'ticket' in subject"
        ];

        for (const q of queries) {
            console.log(`\nTesting query: "${q}"`);
            const structuredQuery = await understandEmailSearchQueryLLM(q);
            console.log("Structured Query:", JSON.stringify(structuredQuery, null, 2));
        }
    } catch (e) {
        console.error("Understander Test failed:", e);
    }
}
// testUnderstander();
*/

// NLU for Sending Emails - Placeholder for future implementation

import { EmailDetails } from './emailSkills'; // Assuming EmailDetails is exported from emailSkills.ts

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
export async function understandEmailSendCommandLLM(rawUserQuery: string): Promise<Partial<EmailDetails>> {
  console.warn(
    'Placeholder function understandEmailSendCommandLLM called. ' +
    'This NLU capability needs to be fully implemented using an LLM with a proper prompt, ' +
    'intent classification, and entity extraction for sending emails.'
  );

  // --- ACTUAL LLM IMPLEMENTATION WOULD GO HERE ---
  // This would involve:
  // 1. Getting an OpenAI client.
  // 2. Using a system prompt like SEND_EMAIL_SYSTEM_PROMPT_EXAMPLE.
  // 3. Sending the rawUserQuery to the LLM.
  // 4. Parsing the LLM's JSON response into Partial<EmailDetails>.
  // 5. Performing validation and cleanup.

  // For now, returning a mock based on a very simple keyword parse for demonstration.
  // This is NOT robust NLU.
  if (rawUserQuery.toLowerCase().includes("email john subject test body hello")) {
    return {
      to: "john.doe@example.com",
      subject: "Test Email from Agent",
      body: "Hello John, this is a test email sent by the agent based on a command.",
    };
  }
  if (rawUserQuery.toLowerCase().includes("send to jane@example.com subject important body check this out")) {
    return {
      to: "jane@example.com",
      subject: "Important",
      body: "Check this out",
    };
  }

  // If no simple match, return empty or throw an error indicating NLU couldn't parse.
  // Throwing an error might be better to signal that the NLU part is missing.
  console.error(`understandEmailSendCommandLLM: Could not parse for sending: "${rawUserQuery}". Needs full NLU implementation.`);
  throw new Error(`Sorry, I couldn't understand the details for the email you want to send. Please try phrasing it clearly, for example: "Email user@example.com subject Your Subject body Your message."`);
}
