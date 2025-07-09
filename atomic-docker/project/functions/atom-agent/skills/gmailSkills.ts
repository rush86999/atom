import {
  SkillResponse,
  Email,
  // NLU entity types for Gmail - will be defined or imported
} from '../types';
import { logger } from '../../_utils/logger';
import { understandEmailSearchQueryLLM } from './llm_email_query_understander';
import { buildGmailSearchQuery, StructuredEmailQuery, parseRelativeDateQuery } from './nlu_email_helper'; // Assuming nlu_email_helper.ts will export these
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
    let structuredQuery: Partial<StructuredEmailQuery> = await understandEmailSearchQueryLLM(rawUserQuery);
    logger.info(`[handleSearchGmail] LLM structured query: ${JSON.stringify(structuredQuery)}`);

    if (Object.keys(structuredQuery).length === 0 && rawUserQuery.length > 0) {
        logger.warn(`[handleSearchGmail] LLM returned empty structured query for input: "${rawUserQuery}". Using raw query as custom query for backend.`);
        // Fallback: if LLM gives nothing, use the raw query directly as a custom query part.
        // Gmail's search has some natural language capabilities.
        structuredQuery = { customQuery: rawUserQuery, excludeChats: true }; // Default to excluding chats for broad queries
    }

    const gmailApiQueryString = buildGmailSearchQuery(structuredQuery);
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

export async function getRecentUnreadEmailsForBriefing(
  userId: string,
  targetDate: Date, // The specific date for which to get emails
  count: number = 3 // Default to 3 emails
): Promise<SkillResponse<{ results: GmailMessageSnippet[], query_executed?: string }>> {
  logger.info(`[getRecentUnreadEmailsForBriefing] User: ${userId}, TargetDate: ${targetDate.toISOString().split('T')[0]}, Count: ${count}`);

  try {
    const formatDateForGmail = (date: Date): string => {
      const year = date.getUTCFullYear();
      const month = (date.getUTCMonth() + 1).toString().padStart(2, '0');
      const day = date.getUTCDate().toString().padStart(2, '0');
      return `${year}/${month}/${day}`;
    };

    const afterDate = new Date(targetDate);
    afterDate.setUTCHours(0, 0, 0, 0); // Start of targetDate in UTC

    const beforeDate = new Date(targetDate);
    beforeDate.setUTCHours(0, 0, 0, 0);
    beforeDate.setUTCDate(targetDate.getUTCDate() + 1); // Start of the day *after* targetDate for exclusive 'before'

    const queryParts = [
      'is:unread',
      'in:inbox', // Standard inbox
      // Consider 'category:primary' if wanting to filter promotions/social, but 'in:inbox' is broader.
      `after:${formatDateForGmail(afterDate)}`,
      `before:${formatDateForGmail(beforeDate)}`
    ];

    const gmailApiQueryString = queryParts.join(' ');
    logger.info(`[getRecentUnreadEmailsForBriefing] Constructed Gmail API query string: "${gmailApiQueryString}"`);

    // searchMyEmailsBackend expects a raw query string and returns Email[]
    const backendResults: Email[] = await searchMyEmailsBackend(userId, gmailApiQueryString, count);

    const results: GmailMessageSnippet[] = backendResults.map(email => ({
      id: email.id,
      threadId: email.threadId, // Assuming Email type from emailSkills has threadId
      subject: email.subject,
      from: email.sender, // Assuming Email type from emailSkills has sender
      date: email.timestamp, // Assuming Email type from emailSkills has timestamp (ISO string)
      snippet: email.body?.substring(0, 200), // Use body as snippet, truncate
      link: email.id ? `https://mail.google.com/mail/u/0/#inbox/${email.id}` : undefined
    }));

    logger.info(`[getRecentUnreadEmailsForBriefing] Found ${results.length} unread emails for the target date.`);
    return { ok: true, data: { results, query_executed: gmailApiQueryString } };

  } catch (error: any) {
    logger.error(`[getRecentUnreadEmailsForBriefing] Error: ${error.message}`, error);
    return {
        ok: false,
        error: { code: 'GMAIL_BRIEFING_FETCH_FAILED', message: error.message || "Failed to fetch recent unread emails for briefing." }
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

      // Handle attendees by building a specific (from:X OR to:X OR from:Y OR to:Y) query part.
      if (meetingContext.attendees && meetingContext.attendees.length > 0) {
        const attendeeEmailQueries: string[] = [];
        // Extract email from attendee string (e.g., "Display Name <email@example.com>" or just "email@example.com")
        const emailRegex = /<([^>]+)>/;

        meetingContext.attendees.forEach(attendeeString => {
          let email: string | undefined = undefined;
          const match = attendeeString.match(emailRegex);
          if (match && match[1]) {
            email = match[1].trim();
          } else if (attendeeString.includes('@') && !attendeeString.startsWith('<') && !attendeeString.endsWith('>')) {
            // If it contains '@' and is not already caught by regex (e.g. just "user@example.com")
            // Also ensure it's not part of a malformed string like "<user@example.com"
            const potentialEmail = attendeeString.split(/\s+/).find(part => part.includes('@'));
            if (potentialEmail) {
                 email = potentialEmail.trim();
            }
          }
          // Note: We are not attempting to extract emails from display names if no explicit email is provided.
          // This focuses the search on actual email addresses involved.

          if (email && email.toLowerCase() !== userId.toLowerCase()) { // Exclude self, case-insensitive
            const sanitizedEmail = email; // Already trimmed if extracted
            attendeeEmailQueries.push(`from:${sanitizedEmail}`);
            attendeeEmailQueries.push(`to:${sanitizedEmail}`);
          }
        });

        if (attendeeEmailQueries.length > 0) {
          const attendeeQueryPart = `(${attendeeEmailQueries.join(' OR ')})`;
          structuredQuery.customQuery = structuredQuery.customQuery
            ? `${structuredQuery.customQuery} ${attendeeQueryPart}`
            : attendeeQueryPart;
          logger.info(`[searchEmailsForPrep] Added attendee query part: ${attendeeQueryPart}`);
        }
      }

      // Combine event summary keywords and add to body search.
      if (eventKeywordsArray.length > 0) {
        const uniqueEventKeywords = Array.from(new Set(eventKeywordsArray));
        const eventKeywordString = uniqueEventKeywords.join(' ');
        structuredQuery.body = structuredQuery.body ? `${structuredQuery.body} ${eventKeywordString}` : eventKeywordString;
      }

      // Refine date range based on meeting start time if params.date_query is not specific or not provided.
      // The goal is to establish a sensible default window around the meeting.
      const isDateQueryGeneric = !params.date_query || params.date_query.toLowerCase() === "recent" || params.date_query.trim() === "";
      if (meetingContext.start && isDateQueryGeneric) {
        const meetingStartDate = new Date(meetingContext.start);
        meetingStartDate.setHours(0,0,0,0); // Normalize to start of day for 'after'

        // Default: 7 days before the meeting start day
        // TODO: Make this window (7 days) configurable or more dynamic based on meeting proximity.
        const afterDateObj = new Date(meetingStartDate);
        afterDateObj.setDate(meetingStartDate.getDate() - 7);

        // Determine 'before' date: day after meeting end, or day after meeting start if end is not available/valid
        let meetingEndDateForQuery: Date;
        if (meetingContext.end) {
            try {
                meetingEndDateForQuery = new Date(meetingContext.end);
                // Check if meetingContext.end was a valid date string
                if (isNaN(meetingEndDateForQuery.getTime())) {
                    logger.warn(`[searchEmailsForPrep] Invalid meetingContext.end date: ${meetingContext.end}. Falling back to start date.`);
                    meetingEndDateForQuery = new Date(meetingContext.start);
                }
            } catch (e) {
                logger.warn(`[searchEmailsForPrep] Error parsing meetingContext.end date: ${meetingContext.end}. Falling back to start date.`, e);
                meetingEndDateForQuery = new Date(meetingContext.start);
            }
        } else {
            meetingEndDateForQuery = new Date(meetingContext.start);
        }
        meetingEndDateForQuery.setHours(0,0,0,0); // Normalize

        const beforeDateObj = new Date(meetingEndDateForQuery);
        beforeDateObj.setDate(meetingEndDateForQuery.getDate() + 1); // Day after the meeting (exclusive end for query)

        const formatDate = (date: Date): string => {
            const year = date.getFullYear();
            const month = (date.getMonth() + 1).toString().padStart(2, '0');
            const day = date.getDate().toString().padStart(2, '0');
            return `${year}/${month}/${day}`;
        };

        structuredQuery.after = formatDate(afterDateObj);
        structuredQuery.before = formatDate(beforeDateObj);
        logger.info(`[searchEmailsForPrep] Date range from meeting context: after:${structuredQuery.after} before:${structuredQuery.before}`);
      }
    }

    // If no date range was set by meetingContext, try to parse params.date_query
    if (!(structuredQuery.after || structuredQuery.before) && params.date_query) {
      logger.info(`[searchEmailsForPrep] Attempting to parse params.date_query: "${params.date_query}"`);
      const parsedDates = parseRelativeDateQuery(params.date_query);
      if (parsedDates) {
        if (parsedDates.after) structuredQuery.after = parsedDates.after;
        if (parsedDates.before) structuredQuery.before = parsedDates.before;
        logger.info(`[searchEmailsForPrep] Parsed date query to: after:${parsedDates.after}, before:${parsedDates.before}`);
      } else {
        // If parseRelativeDateQuery couldn't understand it, and it looks like a raw Gmail query part, add it to customQuery.
        // This is a fallback for queries like "older_than:7d" or specific "after:YYYY/MM/DD" if not caught by parseRelativeDateQuery's own check.
        if (params.date_query.includes(":") && (params.date_query.includes("older_than") || params.date_query.includes("newer_than") || params.date_query.match(/(after|before):\d{4}\/\d{2}\/\d{2}/))) {
            structuredQuery.customQuery = structuredQuery.customQuery
                ? `${structuredQuery.customQuery} ${params.date_query}`
                : params.date_query;
            logger.info(`[searchEmailsForPrep] Using params.date_query as custom query part: "${params.date_query}"`);
        } else {
            logger.warn(`[searchEmailsForPrep] Could not parse date_query: "${params.date_query}" and it doesn't look like a direct Gmail date term.`);
        }
      }
    }

    // Default to excluding chats if not otherwise specified.
    if (structuredQuery.excludeChats === undefined) {
        structuredQuery.excludeChats = true;
    }

    const gmailApiQueryString = buildGmailSearchQuery(structuredQuery);
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
