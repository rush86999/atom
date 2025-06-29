import {
  SkillResponse,
  Email,
  // NLU entity types for Gmail - will be defined or imported
} from '../types';
import { logger } from '../../_utils/logger';
import { understandEmailSearchQueryLLM } from './llm_email_query_understander';
import { buildGmailQueryString, StructuredEmailQuery } from './nlu_email_helper'; // Assuming nlu_email_helper.ts will export these
import { searchMyEmails as searchMyEmailsBackend, readEmail as readEmailBackend, extractInformationFromEmailBody } from './emailSkills';

// --- NLU Entity Interfaces (Conceptual - for documentation and type safety if NLU provides them directly) ---
// These would align with the inputs expected by the LLM parser or a direct NLU service.
export interface SearchGmailNluEntities {
  raw_query_text: string; // The full natural language query from the user
  // Optional: NLU might pre-extract some common entities, but LLM parser is primary
  from_sender?: string;
  subject_keywords?: string;
  date_filter?: string; // e.g., "last week"
  limit_number?: number;
}

export interface ExtractInfoFromGmailNluEntities {
  email_id?: string; // Specific ID of the email
  email_reference_context?: string; // e.g., "last email from support", "the email about project X"
  information_keywords: string[]; // Array of what to extract, e.g., ["invoice number", "due date"]
}


// --- Skill Implementations ---

export async function handleSearchGmail(
  userId: string,
  rawUserQuery: string,
  limit: number = 10, // Default limit
): Promise<SkillResponse<{ emails: Email[], userMessage: string }>> {
  logger.info(`[handleSearchGmail] User: ${userId}, Query: "${rawUserQuery}", Limit: ${limit}`);

  try {
    const structuredQuery: Partial<StructuredEmailQuery> = await understandEmailSearchQueryLLM(rawUserQuery);
    logger.info(`[handleSearchGmail] LLM structured query: ${JSON.stringify(structuredQuery)}`);

    if (Object.keys(structuredQuery).length === 0 && rawUserQuery.length > 30) { // Vague query but long enough that user expected something
        logger.warn(`[handleSearchGmail] LLM returned empty structured query for a non-trivial input: "${rawUserQuery}". Passing raw query to backend.`);
        // Fallback: if LLM gives nothing, but query is substantial, try passing raw query.
        // Or, decide if this should be an error/clarification request.
        // For now, let's try to use raw query directly with Gmail's search, which has some NL capabilities.
    }

    const gmailApiQueryString = buildGmailQueryString(structuredQuery, rawUserQuery); // Pass raw for potential fallback
    logger.info(`[handleSearchGmail] Constructed Gmail API query string: "${gmailApiQueryString}"`);

    if (!gmailApiQueryString || gmailApiQueryString.trim() === "") {
        return {
            ok: true, // Or false, depending on how to treat "empty effective query"
            data: { emails: [], userMessage: "I couldn't determine specific search criteria from your request. Please try rephrasing." }
        };
    }

    const emails: Email[] = await searchMyEmailsBackend(userId, gmailApiQueryString, limit);

    let userMessage = "";
    if (emails.length === 0) {
      userMessage = "I couldn't find any emails matching your search criteria.";
    } else {
      userMessage = `I found ${emails.length} email(s) matching your criteria:\n`;
      emails.forEach((email, index) => {
        userMessage += `${index + 1}. Subject: "${email.subject}" (From: ${email.sender}, Date: ${new Date(email.timestamp).toLocaleDateString()})\n   Snippet: ${email.body.substring(0,100)}...\n   (ID: ${email.id})\n`;
      });
    }
    return { ok: true, data: { emails, userMessage } };

  } catch (error: any) {
    logger.error(`[handleSearchGmail] Error: ${error.message}`, error);
    return {
        ok: false,
        error: { code: 'GMAIL_SEARCH_FAILED', message: error.message || "Failed to search Gmail." },
        data: { emails: [], userMessage: `Sorry, I encountered an error while searching your emails: ${error.message}` }
    };
  }
}


export async function handleExtractInfoFromGmail(
  userId: string,
  emailIdOrReference: string, // Could be an email ID or a reference like "last email from ..."
  informationKeywords: string[],
  // Optional: if NLU provides the email body directly from context to avoid re-fetch
  emailBodyContext?: string
): Promise<SkillResponse<{ extractedInfo: Record<string, string | null>, userMessage: string }>> {
  logger.info(`[handleExtractInfoFromGmail] User: ${userId}, EmailRef: "${emailIdOrReference}", Keywords: [${informationKeywords.join(', ')}]`);

  if (!informationKeywords || informationKeywords.length === 0) {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Please specify what information you want to extract.'} };
  }

  let emailBody: string | null = emailBodyContext || null;
  let emailSubject = "the email"; // Default subject for messages

  try {
    if (!emailBody) {
      // TODO: Implement email_id resolution if emailIdOrReference is not a direct ID.
      // This might involve:
      // 1. Checking if emailIdOrReference looks like a Gmail ID.
      // 2. If it's a reference (e.g., "last email from support"), call handleSearchGmail
      //    with a query constructed from the reference, get the top result's ID.
      //    This part can be complex and might require user clarification if ambiguous.
      // For V1, assume emailIdOrReference IS the email ID for simplicity if no body context.
      logger.info(`[handleExtractInfoFromGmail] Attempting to fetch email ID: ${emailIdOrReference}`);
      const emailResult = await readEmailBackend(userId, emailIdOrReference);
      if (emailResult.success && emailResult.email) {
        emailBody = emailResult.email.body;
        emailSubject = emailResult.email.subject || emailSubject;
      } else {
        throw new Error(emailResult.message || `Could not find or read email with reference: ${emailIdOrReference}`);
      }
    }

    if (!emailBody || emailBody.trim() === "") {
        return {
            ok: false,
            error: { code: 'EMAIL_CONTENT_EMPTY', message: `The email body for "${emailSubject}" is empty or could not be retrieved.`},
            data: { extractedInfo: {}, userMessage: `The email body for "${emailSubject}" is empty, so I couldn't extract information.`}
        };
    }

    const extractedInfo = await extractInformationFromEmailBody(emailBody, informationKeywords);

    let foundCount = 0;
    let messageParts: string[] = [`From my review of "${emailSubject}":`];
    informationKeywords.forEach(keyword => {
      if (extractedInfo[keyword] !== null && extractedInfo[keyword] !== undefined) {
        messageParts.push(`- For "${keyword}": ${extractedInfo[keyword]}`);
        foundCount++;
      } else {
        messageParts.push(`- I couldn't find information about "${keyword}".`);
      }
    });

    const userMessage = foundCount > 0 ? messageParts.join('\n') : `I reviewed "${emailSubject}" but couldn't find the specific information you asked for (${informationKeywords.join(', ')}).`;

    return { ok: true, data: { extractedInfo, userMessage } };

  } catch (error: any) {
    logger.error(`[handleExtractInfoFromGmail] Error: ${error.message}`, error);
     return {
        ok: false,
        error: { code: 'GMAIL_EXTRACT_FAILED', message: error.message || "Failed to extract information from Gmail." },
        data: { extractedInfo: {}, userMessage: `Sorry, I encountered an error while extracting information: ${error.message}` }
    };
  }
}
