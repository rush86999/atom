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

import {
    GmailSearchParameters,
    CalendarEventSummary,
    GmailMessageSnippet,
} from '../types'; // Added for searchEmailsForPrep

export async function searchEmailsForPrep(
  userId: string,
  params: GmailSearchParameters,
  meetingContext?: CalendarEventSummary | null, // Optional meeting context
  limit: number = 5 // Default limit for prep results
): Promise<SkillResponse<{ results: GmailMessageSnippet[], query_executed?: string }>> {
  logger.info(`[searchEmailsForPrep] User: ${userId}, Params: ${JSON.stringify(params)}, MeetingContext: ${meetingContext?.summary}`);

  try {
    let structuredQuery: Partial<StructuredEmailQuery> = {};

    // 1. Populate structuredQuery from params
    if (params.from_sender) structuredQuery.from = params.from_sender;
    if (params.subject_keywords) structuredQuery.subject = params.subject_keywords;
    if (params.body_keywords) structuredQuery.body = params.body_keywords; // Direct mapping
    if (params.has_attachment_only) structuredQuery.hasAttachment = true;

    // Date query handling - needs robust parsing or direct use if formatted for Gmail
    // For simplicity, if params.date_query is like "after:YYYY/MM/DD before:YYYY/MM/DD", buildGmailQueryString might use it.
    // Otherwise, this part needs more sophisticated date parsing logic.
    // For now, we'll assume buildGmailQueryString handles what it can from date_query or meeting context.

    // 2. Enhance structuredQuery with meetingContext
    if (meetingContext) {
      const eventKeywordsArray: string[] = [];
      if (meetingContext.summary) {
        // Add event title keywords to subject/body search
        // Simple split, could be improved (e.g. remove common words)
        eventKeywordsArray.push(...meetingContext.summary.toLowerCase().split(' ').filter(kw => kw.length > 2));
      }

      // Add attendees to a general keyword pool for now, simpler than complex OR logic in from/to
      if (meetingContext.attendees && meetingContext.attendees.length > 0) {
        meetingContext.attendees.forEach(a => {
          if (a.email && a.email !== userId) { // Exclude self
            eventKeywordsArray.push(a.email);
            if (a.displayName) { // Add display name parts if available
                eventKeywordsArray.push(...a.displayName.toLowerCase().split(' ').filter(kw => kw.length > 2));
            }
          }
        });
      }

      // Combine all event-related keywords and add to body search.
      // This is a simplified approach. More advanced would be targeted field searches.
      if (eventKeywordsArray.length > 0) {
        const uniqueEventKeywords = Array.from(new Set(eventKeywordsArray)); // Remove duplicates
        const eventKeywordString = uniqueEventKeywords.join(' '); // Join with space for Gmail query
        structuredQuery.body = structuredQuery.body ? `${structuredQuery.body} ${eventKeywordString}` : eventKeywordString;
      }

      // Refine date range based on meeting start time if params.date_query is not specific (e.g. "recent", or not set)
      if (meetingContext.start && (!params.date_query || params.date_query.toLowerCase() === "recent" || params.date_query.trim() === "")) {
        const meetingDate = new Date(meetingContext.start);
        const sevenDaysBefore = new Date(meetingDate);
        sevenDaysBefore.setDate(meetingDate.getDate() - 7);

        const afterDate = `${sevenDaysBefore.getFullYear()}/${(sevenDaysBefore.getMonth() + 1).toString().padStart(2, '0')}/${sevenDaysBefore.getDate().toString().padStart(2, '0')}`;
        // Search up to and including the meeting day
        const beforeMeetingDay = new Date(meetingDate);
        beforeMeetingDay.setDate(meetingDate.getDate() + 1); // Search until the end of the meeting day
        const beforeDate = `${beforeMeetingDay.getFullYear()}/${(beforeMeetingDay.getMonth() + 1).toString().padStart(2, '0')}/${beforeMeetingDay.getDate().toString().padStart(2, '0')}`;

        structuredQuery.after = afterDate;
        structuredQuery.before = beforeDate;
        logger.info(`[searchEmailsForPrep] Date range from meeting context: after:${afterDate} before:${beforeDate}`);
      }
    }

    // Pass params.date_query directly to buildGmailQueryString if it wasn't overridden by meeting context.
    // buildGmailQueryString will need to be robust enough to handle it or ignore if not in expected format.
    const rawDateQueryForBuild = (structuredQuery.after || structuredQuery.before) ? "" : params.date_query || "";

    const gmailApiQueryString = buildGmailQueryString(structuredQuery, rawDateQueryForBuild);
    logger.info(`[searchEmailsForPrep] Constructed Gmail API query string: "${gmailApiQueryString}"`);

    if (!gmailApiQueryString || gmailApiQueryString.trim() === "") {
      logger.warn("[searchEmailsForPrep] Empty Gmail API query string generated. Returning no results.");
      return { ok: true, data: { results: [], query_executed: gmailApiQueryString } };
    }

    const backendResults: Email[] = await searchMyEmailsBackend(userId, gmailApiQueryString, limit);

    const results: GmailMessageSnippet[] = backendResults.map(email => ({
      id: email.id,
      threadId: email.threadId,
      subject: email.subject,
      from: email.sender,
      date: email.timestamp,
      snippet: email.body?.substring(0, 200), // Truncate snippet
      link: email.id ? `https://mail.google.com/mail/u/0/#inbox/${email.id}` : undefined
    }));

    logger.info(`[searchEmailsForPrep] Found ${results.length} emails.`);
    return { ok: true, data: { results, query_executed: gmailApiQueryString } };

  } catch (error: any) {
    logger.error(`[searchEmailsForPrep] Error: ${error.message}`, error);
    return {
        ok: false,
        error: { code: 'GMAIL_PREP_SEARCH_FAILED', message: error.message || "Failed to search Gmail for meeting prep." }
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
