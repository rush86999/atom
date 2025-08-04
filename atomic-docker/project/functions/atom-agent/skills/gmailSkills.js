import { logger } from '../../_utils/logger';
import { understandEmailSearchQueryLLM } from './llm_email_query_understander';
import { buildGmailSearchQuery, parseRelativeDateQuery, } from './nlu_email_helper'; // Assuming nlu_email_helper.ts will export these
import { searchMyEmails as searchMyEmailsBackend, readEmail as readEmailBackend, extractInformationFromEmailBody, } from './emailSkills';
// --- Skill Implementations ---
export async function handleSearchGmail(userId, rawUserQuery, limit = 10 // Default limit
) {
    logger.info(`[handleSearchGmail] User: ${userId}, Query: "${rawUserQuery}", Limit: ${limit}`);
    try {
        let structuredQuery = await understandEmailSearchQueryLLM(rawUserQuery);
        logger.info(`[handleSearchGmail] LLM structured query: ${JSON.stringify(structuredQuery)}`);
        if (Object.keys(structuredQuery).length === 0 && rawUserQuery.length > 0) {
            logger.warn(`[handleSearchGmail] LLM returned empty structured query for input: "${rawUserQuery}". Using raw query as custom query for backend.`);
            // Fallback: if LLM gives nothing, use the raw query directly as a custom query part.
            // Gmail's search has some natural language capabilities.
            structuredQuery = { customQuery: rawUserQuery, excludeChats: true }; // Default to excluding chats for broad queries
        }
        const gmailApiQueryString = buildGmailSearchQuery(structuredQuery);
        logger.info(`[handleSearchGmail] Constructed Gmail API query string: "${gmailApiQueryString}"`);
        if (!gmailApiQueryString || gmailApiQueryString.trim() === '') {
            return {
                ok: true, // Or false, depending on how to treat "empty effective query"
                data: {
                    emails: [],
                    userMessage: "I couldn't determine specific search criteria from your request. Please try rephrasing.",
                },
            };
        }
        const emails = await searchMyEmailsBackend(userId, gmailApiQueryString, limit);
        let userMessage = '';
        if (emails.length === 0) {
            userMessage = "I couldn't find any emails matching your search criteria.";
        }
        else {
            userMessage = `I found ${emails.length} email(s) matching your criteria:\n`;
            emails.forEach((email, index) => {
                userMessage += `${index + 1}. Subject: "${email.subject}" (From: ${email.sender}, Date: ${new Date(email.timestamp).toLocaleDateString()})\n   Snippet: ${email.body.substring(0, 100)}...\n   (ID: ${email.id})\n`;
            });
        }
        return { ok: true, data: { emails, userMessage } };
    }
    catch (error) {
        logger.error(`[handleSearchGmail] Error: ${error.message}`, error);
        return {
            ok: false,
            error: {
                code: 'GMAIL_SEARCH_FAILED',
                message: error.message || 'Failed to search Gmail.',
            },
            data: {
                emails: [],
                userMessage: `Sorry, I encountered an error while searching your emails: ${error.message}`,
            },
        };
    }
}
export async function getRecentUnreadEmailsForBriefing(userId, targetDate, // The specific date for which to get emails
count = 3 // Default to 3 emails
) {
    logger.info(`[getRecentUnreadEmailsForBriefing] User: ${userId}, TargetDate: ${targetDate.toISOString().split('T')[0]}, Count: ${count}`);
    try {
        const formatDateForGmail = (date) => {
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
            `before:${formatDateForGmail(beforeDate)}`,
        ];
        const gmailApiQueryString = queryParts.join(' ');
        logger.info(`[getRecentUnreadEmailsForBriefing] Constructed Gmail API query string: "${gmailApiQueryString}"`);
        // searchMyEmailsBackend expects a raw query string and returns Email[]
        const backendResults = await searchMyEmailsBackend(userId, gmailApiQueryString, count);
        const results = backendResults.map((email) => ({
            id: email.id,
            threadId: email.threadId, // Assuming Email type from emailSkills has threadId
            subject: email.subject,
            from: email.sender, // Assuming Email type from emailSkills has sender
            date: email.timestamp, // Assuming Email type from emailSkills has timestamp (ISO string)
            snippet: email.body?.substring(0, 200), // Use body as snippet, truncate
            link: email.id
                ? `https://mail.google.com/mail/u/0/#inbox/${email.id}`
                : undefined,
        }));
        logger.info(`[getRecentUnreadEmailsForBriefing] Found ${results.length} unread emails for the target date.`);
        return { ok: true, data: { results, query_executed: gmailApiQueryString } };
    }
    catch (error) {
        logger.error(`[getRecentUnreadEmailsForBriefing] Error: ${error.message}`, error);
        return {
            ok: false,
            error: {
                code: 'GMAIL_BRIEFING_FETCH_FAILED',
                message: error.message || 'Failed to fetch recent unread emails for briefing.',
            },
        };
    }
}
export async function searchEmailsForPrep(userId, params, meetingContext, // Optional meeting context
limit = 5 // Default limit for prep results
) {
    logger.info(`[searchEmailsForPrep] User: ${userId}, Params: ${JSON.stringify(params)}, MeetingContext: ${meetingContext?.summary}`);
    try {
        let structuredQuery = {};
        // 1. Populate structuredQuery from params
        if (params.from_sender)
            structuredQuery.from = params.from_sender;
        if (params.subject_keywords)
            structuredQuery.subject = params.subject_keywords;
        if (params.body_keywords)
            structuredQuery.body = params.body_keywords; // Direct mapping
        if (params.has_attachment_only)
            structuredQuery.hasAttachment = true;
        // Date query handling - needs robust parsing or direct use if formatted for Gmail
        // For simplicity, if params.date_query is like "after:YYYY/MM/DD before:YYYY/MM/DD", buildGmailQueryString might use it.
        // Otherwise, this part needs more sophisticated date parsing logic.
        // For now, we'll assume buildGmailQueryString handles what it can from date_query or meeting context.
        // 2. Enhance structuredQuery with meetingContext
        if (meetingContext) {
            const eventKeywordsArray = [];
            if (meetingContext.summary) {
                // Add event title keywords to subject/body search
                // Simple split, could be improved (e.g. remove common words)
                eventKeywordsArray.push(...meetingContext.summary
                    .toLowerCase()
                    .split(' ')
                    .filter((kw) => kw.length > 2));
            }
            // Handle attendees by building a specific (from:X OR to:X OR from:Y OR to:Y) query part.
            if (meetingContext.attendees && meetingContext.attendees.length > 0) {
                const attendeeEmailQueries = [];
                // Extract email from attendee string (e.g., "Display Name <email@example.com>" or just "email@example.com")
                const emailRegex = /<([^>]+)>/;
                meetingContext.attendees.forEach((attendeeString) => {
                    let email = undefined;
                    const match = attendeeString.match(emailRegex);
                    if (match && match[1]) {
                        email = match[1].trim();
                    }
                    else if (attendeeString.includes('@') &&
                        !attendeeString.startsWith('<') &&
                        !attendeeString.endsWith('>')) {
                        // If it contains '@' and is not already caught by regex (e.g. just "user@example.com")
                        // Also ensure it's not part of a malformed string like "<user@example.com"
                        const potentialEmail = attendeeString
                            .split(/\s+/)
                            .find((part) => part.includes('@'));
                        if (potentialEmail) {
                            email = potentialEmail.trim();
                        }
                    }
                    // Note: We are not attempting to extract emails from display names if no explicit email is provided.
                    // This focuses the search on actual email addresses involved.
                    if (email && email.toLowerCase() !== userId.toLowerCase()) {
                        // Exclude self, case-insensitive
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
                structuredQuery.body = structuredQuery.body
                    ? `${structuredQuery.body} ${eventKeywordString}`
                    : eventKeywordString;
            }
            // Refine date range based on meeting start time if params.date_query is not specific or not provided.
            // The goal is to establish a sensible default window around the meeting.
            const isDateQueryGeneric = !params.date_query ||
                params.date_query.toLowerCase() === 'recent' ||
                params.date_query.trim() === '';
            if (meetingContext.start && isDateQueryGeneric) {
                const meetingStartDate = new Date(meetingContext.start);
                meetingStartDate.setHours(0, 0, 0, 0); // Normalize to start of day for 'after'
                // Default: 7 days before the meeting start day
                // TODO: Make this window (7 days) configurable or more dynamic based on meeting proximity.
                const afterDateObj = new Date(meetingStartDate);
                afterDateObj.setDate(meetingStartDate.getDate() - 7);
                // Determine 'before' date: day after meeting end, or day after meeting start if end is not available/valid
                let meetingEndDateForQuery;
                if (meetingContext.end) {
                    try {
                        meetingEndDateForQuery = new Date(meetingContext.end);
                        // Check if meetingContext.end was a valid date string
                        if (isNaN(meetingEndDateForQuery.getTime())) {
                            logger.warn(`[searchEmailsForPrep] Invalid meetingContext.end date: ${meetingContext.end}. Falling back to start date.`);
                            meetingEndDateForQuery = new Date(meetingContext.start);
                        }
                    }
                    catch (e) {
                        logger.warn(`[searchEmailsForPrep] Error parsing meetingContext.end date: ${meetingContext.end}. Falling back to start date.`, e);
                        meetingEndDateForQuery = new Date(meetingContext.start);
                    }
                }
                else {
                    meetingEndDateForQuery = new Date(meetingContext.start);
                }
                meetingEndDateForQuery.setHours(0, 0, 0, 0); // Normalize
                const beforeDateObj = new Date(meetingEndDateForQuery);
                beforeDateObj.setDate(meetingEndDateForQuery.getDate() + 1); // Day after the meeting (exclusive end for query)
                const formatDate = (date) => {
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
        if (!(structuredQuery.after || structuredQuery.before) &&
            params.date_query) {
            logger.info(`[searchEmailsForPrep] Attempting to parse params.date_query: "${params.date_query}"`);
            const parsedDates = parseRelativeDateQuery(params.date_query);
            if (parsedDates) {
                if (parsedDates.after)
                    structuredQuery.after = parsedDates.after;
                if (parsedDates.before)
                    structuredQuery.before = parsedDates.before;
                logger.info(`[searchEmailsForPrep] Parsed date query to: after:${parsedDates.after}, before:${parsedDates.before}`);
            }
            else {
                // If parseRelativeDateQuery couldn't understand it, and it looks like a raw Gmail query part, add it to customQuery.
                // This is a fallback for queries like "older_than:7d" or specific "after:YYYY/MM/DD" if not caught by parseRelativeDateQuery's own check.
                if (params.date_query.includes(':') &&
                    (params.date_query.includes('older_than') ||
                        params.date_query.includes('newer_than') ||
                        params.date_query.match(/(after|before):\d{4}\/\d{2}\/\d{2}/))) {
                    structuredQuery.customQuery = structuredQuery.customQuery
                        ? `${structuredQuery.customQuery} ${params.date_query}`
                        : params.date_query;
                    logger.info(`[searchEmailsForPrep] Using params.date_query as custom query part: "${params.date_query}"`);
                }
                else {
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
        if (!gmailApiQueryString || gmailApiQueryString.trim() === '') {
            logger.warn('[searchEmailsForPrep] Empty Gmail API query string generated. Returning no results.');
            return {
                ok: true,
                data: { results: [], query_executed: gmailApiQueryString },
            };
        }
        const backendResults = await searchMyEmailsBackend(userId, gmailApiQueryString, limit);
        const results = backendResults.map((email) => ({
            id: email.id,
            threadId: email.threadId,
            subject: email.subject,
            from: email.sender,
            date: email.timestamp,
            snippet: email.body?.substring(0, 200), // Truncate snippet
            link: email.id
                ? `https://mail.google.com/mail/u/0/#inbox/${email.id}`
                : undefined,
        }));
        logger.info(`[searchEmailsForPrep] Found ${results.length} emails.`);
        return { ok: true, data: { results, query_executed: gmailApiQueryString } };
    }
    catch (error) {
        logger.error(`[searchEmailsForPrep] Error: ${error.message}`, error);
        return {
            ok: false,
            error: {
                code: 'GMAIL_PREP_SEARCH_FAILED',
                message: error.message || 'Failed to search Gmail for meeting prep.',
            },
        };
    }
}
export async function handleExtractInfoFromGmail(userId, emailIdOrReference, // Could be an email ID or a reference like "last email from ..."
informationKeywords, 
// Optional: if NLU provides the email body directly from context to avoid re-fetch
emailBodyContext) {
    logger.info(`[handleExtractInfoFromGmail] User: ${userId}, EmailRef: "${emailIdOrReference}", Keywords: [${informationKeywords.join(', ')}]`);
    if (!informationKeywords || informationKeywords.length === 0) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Please specify what information you want to extract.',
            },
        };
    }
    let emailBody = emailBodyContext || null;
    let emailSubject = 'the email'; // Default subject for messages
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
            }
            else {
                throw new Error(emailResult.message ||
                    `Could not find or read email with reference: ${emailIdOrReference}`);
            }
        }
        if (!emailBody || emailBody.trim() === '') {
            return {
                ok: false,
                error: {
                    code: 'EMAIL_CONTENT_EMPTY',
                    message: `The email body for "${emailSubject}" is empty or could not be retrieved.`,
                },
                data: {
                    extractedInfo: {},
                    userMessage: `The email body for "${emailSubject}" is empty, so I couldn't extract information.`,
                },
            };
        }
        const extractedInfo = await extractInformationFromEmailBody(emailBody, informationKeywords);
        let foundCount = 0;
        let messageParts = [`From my review of "${emailSubject}":`];
        informationKeywords.forEach((keyword) => {
            if (extractedInfo[keyword] !== null &&
                extractedInfo[keyword] !== undefined) {
                messageParts.push(`- For "${keyword}": ${extractedInfo[keyword]}`);
                foundCount++;
            }
            else {
                messageParts.push(`- I couldn't find information about "${keyword}".`);
            }
        });
        const userMessage = foundCount > 0
            ? messageParts.join('\n')
            : `I reviewed "${emailSubject}" but couldn't find the specific information you asked for (${informationKeywords.join(', ')}).`;
        return { ok: true, data: { extractedInfo, userMessage } };
    }
    catch (error) {
        logger.error(`[handleExtractInfoFromGmail] Error: ${error.message}`, error);
        return {
            ok: false,
            error: {
                code: 'GMAIL_EXTRACT_FAILED',
                message: error.message || 'Failed to extract information from Gmail.',
            },
            data: {
                extractedInfo: {},
                userMessage: `Sorry, I encountered an error while extracting information: ${error.message}`,
            },
        };
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ21haWxTa2lsbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJnbWFpbFNraWxscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFLQSxPQUFPLEVBQUUsTUFBTSxFQUFFLE1BQU0scUJBQXFCLENBQUM7QUFDN0MsT0FBTyxFQUFFLDZCQUE2QixFQUFFLE1BQU0sZ0NBQWdDLENBQUM7QUFDL0UsT0FBTyxFQUNMLHFCQUFxQixFQUVyQixzQkFBc0IsR0FDdkIsTUFBTSxvQkFBb0IsQ0FBQyxDQUFDLGlEQUFpRDtBQUM5RSxPQUFPLEVBQ0wsY0FBYyxJQUFJLHFCQUFxQixFQUN2QyxTQUFTLElBQUksZ0JBQWdCLEVBQzdCLCtCQUErQixHQUNoQyxNQUFNLGVBQWUsQ0FBQztBQW1CdkIsZ0NBQWdDO0FBRWhDLE1BQU0sQ0FBQyxLQUFLLFVBQVUsaUJBQWlCLENBQ3JDLE1BQWMsRUFDZCxZQUFvQixFQUNwQixRQUFnQixFQUFFLENBQUMsZ0JBQWdCOztJQUVuQyxNQUFNLENBQUMsSUFBSSxDQUNULDZCQUE2QixNQUFNLGFBQWEsWUFBWSxhQUFhLEtBQUssRUFBRSxDQUNqRixDQUFDO0lBRUYsSUFBSSxDQUFDO1FBQ0gsSUFBSSxlQUFlLEdBQ2pCLE1BQU0sNkJBQTZCLENBQUMsWUFBWSxDQUFDLENBQUM7UUFDcEQsTUFBTSxDQUFDLElBQUksQ0FDVCw2Q0FBNkMsSUFBSSxDQUFDLFNBQVMsQ0FBQyxlQUFlLENBQUMsRUFBRSxDQUMvRSxDQUFDO1FBRUYsSUFBSSxNQUFNLENBQUMsSUFBSSxDQUFDLGVBQWUsQ0FBQyxDQUFDLE1BQU0sS0FBSyxDQUFDLElBQUksWUFBWSxDQUFDLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztZQUN6RSxNQUFNLENBQUMsSUFBSSxDQUNULHVFQUF1RSxZQUFZLGlEQUFpRCxDQUNySSxDQUFDO1lBQ0YscUZBQXFGO1lBQ3JGLHlEQUF5RDtZQUN6RCxlQUFlLEdBQUcsRUFBRSxXQUFXLEVBQUUsWUFBWSxFQUFFLFlBQVks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QUFXLEVBQUUsRUFBRSxDQUFDO0lBQzVELENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLE1BQU0sQ0FBQyxLQUFLLENBQUMsdUNBQXVDLEtBQUssQ0FBQyxPQUFPLEVBQUUsRUFBRSxLQUFLLENBQUMsQ0FBQztRQUM1RSxPQUFPO1lBQ0wsRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLHNCQUFzQjtnQkFDNUIsT0FBTyxFQUFFLEtBQUssQ0FBQyxPQUFPLElBQUksMkNBQTJDO2FBQ3RFO1lBQ0QsSUFBSSxFQUFFO2dCQUNKLGFBQWEsRUFBRSxFQUFFO2dCQUNqQixXQUFXLEVBQUUsK0RBQStELEtBQUssQ0FBQyxPQUFPLEVBQUU7YUFDNUY7U0FDRixDQUFDO0lBQ0osQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQge1xuICBTa2lsbFJlc3BvbnNlLFxuICBFbWFpbCxcbiAgLy8gTkxVIGVudGl0eSB0eXBlcyBmb3IgR21haWwgLSB3aWxsIGJlIGRlZmluZWQgb3IgaW1wb3J0ZWRcbn0gZnJvbSAnLi4vdHlwZXMnO1xuaW1wb3J0IHsgbG9nZ2VyIH0gZnJvbSAnLi4vLi4vX3V0aWxzL2xvZ2dlcic7XG5pbXBvcnQgeyB1bmRlcnN0YW5kRW1haWxTZWFyY2hRdWVyeUxMTSB9IGZyb20gJy4vbGxtX2VtYWlsX3F1ZXJ5X3VuZGVyc3RhbmRlcic7XG5pbXBvcnQge1xuICBidWlsZEdtYWlsU2VhcmNoUXVlcnksXG4gIFN0cnVjdHVyZWRFbWFpbFF1ZXJ5LFxuICBwYXJzZVJlbGF0aXZlRGF0ZVF1ZXJ5LFxufSBmcm9tICcuL25sdV9lbWFpbF9oZWxwZXInOyAvLyBBc3N1bWluZyBubHVfZW1haWxfaGVscGVyLnRzIHdpbGwgZXhwb3J0IHRoZXNlXG5pbXBvcnQge1xuICBzZWFyY2hNeUVtYWlscyBhcyBzZWFyY2hNeUVtYWlsc0JhY2tlbmQsXG4gIHJlYWRFbWFpbCBhcyByZWFkRW1haWxCYWNrZW5kLFxuICBleHRyYWN0SW5mb3JtYXRpb25Gcm9tRW1haWxCb2R5LFxufSBmcm9tICcuL2VtYWlsU2tpbGxzJztcblxuLy8gLS0tIE5MVSBFbnRpdHkgSW50ZXJmYWNlcyAoQ29uY2VwdHVhbCAtIGZvciBkb2N1bWVudGF0aW9uIGFuZCB0eXBlIHNhZmV0eSBpZiBOTFUgcHJvdmlkZXMgdGhlbSBkaXJlY3RseSkgLS0tXG4vLyBUaGVzZSB3b3VsZCBhbGlnbiB3aXRoIHRoZSBpbnB1dHMgZXhwZWN0ZWQgYnkgdGhlIExMTSBwYXJzZXIgb3IgYSBkaXJlY3QgTkxVIHNlcnZpY2UuXG5leHBvcnQgaW50ZXJmYWNlIFNlYXJjaEdtYWlsTmx1RW50aXRpZXMge1xuICByYXdfcXVlcnlfdGV4dDogc3RyaW5nOyAvLyBUaGUgZnVsbCBuYXR1cmFsIGxhbmd1YWdlIHF1ZXJ5IGZyb20gdGhlIHVzZXJcbiAgLy8gT3B0aW9uYWw6IE5MVSBtaWdodCBwcmUtZXh0cmFjdCBzb21lIGNvbW1vbiBlbnRpdGllcywgYnV0IExMTSBwYXJzZXIgaXMgcHJpbWFyeVxuICBmcm9tX3NlbmRlcj86IHN0cmluZztcbiAgc3ViamVjdF9rZXl3b3Jkcz86IHN0cmluZztcbiAgZGF0ZV9maWx0ZXI/OiBzdHJpbmc7IC8vIGUuZy4sIFwibGFzdCB3ZWVrXCJcbiAgbGltaXRfbnVtYmVyPzogbnVtYmVyO1xufVxuXG5leHBvcnQgaW50ZXJmYWNlIEV4dHJhY3RJbmZvRnJvbUdtYWlsTmx1RW50aXRpZXMge1xuICBlbWFpbF9pZD86IHN0cmluZzsgLy8gU3BlY2lmaWMgSUQgb2YgdGhlIGVtYWlsXG4gIGVtYWlsX3JlZmVyZW5jZV9jb250ZXh0Pzogc3RyaW5nOyAvLyBlLmcuLCBcImxhc3QgZW1haWwgZnJvbSBzdXBwb3J0XCIsIFwidGhlIGVtYWlsIGFib3V0IHByb2plY3QgWFwiXG4gIGluZm9ybWF0aW9uX2tleXdvcmRzOiBzdHJpbmdbXTsgLy8gQXJyYXkgb2Ygd2hhdCB0byBleHRyYWN0LCBlLmcuLCBbXCJpbnZvaWNlIG51bWJlclwiLCBcImR1ZSBkYXRlXCJdXG59XG5cbi8vIC0tLSBTa2lsbCBJbXBsZW1lbnRhdGlvbnMgLS0tXG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBoYW5kbGVTZWFyY2hHbWFpbChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHJhd1VzZXJRdWVyeTogc3RyaW5nLFxuICBsaW1pdDogbnVtYmVyID0gMTAgLy8gRGVmYXVsdCBsaW1pdFxuKTogUHJvbWlzZTxTa2lsbFJlc3BvbnNlPHsgZW1haWxzOiBFbWFpbFtdOyB1c2VyTWVzc2FnZTogc3RyaW5nIH0+PiB7XG4gIGxvZ2dlci5pbmZvKFxuICAgIGBbaGFuZGxlU2VhcmNoR21haWxdIFVzZXI6ICR7dXNlcklkfSwgUXVlcnk6IFwiJHtyYXdVc2VyUXVlcnl9XCIsIExpbWl0OiAke2xpbWl0fWBcbiAgKTtcblxuICB0cnkge1xuICAgIGxldCBzdHJ1Y3R1cmVkUXVlcnk6IFBhcnRpYWw8U3RydWN0dXJlZEVtYWlsUXVlcnk+ID1cbiAgICAgIGF3YWl0IHVuZGVyc3RhbmRFbWFpbFNlYXJjaFF1ZXJ5TExNKHJhd1VzZXJRdWVyeSk7XG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICBgW2hhbmRsZVNlYXJjaEdtYWlsXSBMTE0gc3RydWN0dXJlZCBxdWVyeTogJHtKU09OLnN0cmluZ2lmeShzdHJ1Y3R1cmVkUXVlcnkpfWBcbiAgICApO1xuXG4gICAgaWYgKE9iamVjdC5rZXlzKHN0cnVjdHVyZWRRdWVyeSkubGVuZ3RoID09PSAwICYmIHJhd1VzZXJRdWVyeS5sZW5ndGggPiAwKSB7XG4gICAgICBsb2dnZXIud2FybihcbiAgICAgICAgYFtoYW5kbGVTZWFyY2hHbWFpbF0gTExNIHJldHVybmVkIGVtcHR5IHN0cnVjdHVyZWQgcXVlcnkgZm9yIGlucHV0OiBcIiR7cmF3VXNlclF1ZXJ5fVwiLiBVc2luZyByYXcgcXVlcnkgYXMgY3VzdG9tIHF1ZXJ5IGZvciBiYWNrZW5kLmBcbiAgICAgICk7XG4gICAgICAvLyBGYWxsYmFjazogaWYgTExNIGdpdmVzIG5vdGhpbmcsIHVzZSB0aGUgcmF3IHF1ZXJ5IGRpcmVjdGx5IGFzIGEgY3VzdG9tIHF1ZXJ5IHBhcnQuXG4gICAgICAvLyBHbWFpbCdzIHNlYXJjaCBoYXMgc29tZSBuYXR1cmFsIGxhbmd1YWdlIGNhcGFiaWxpdGllcy5cbiAgICAgIHN0cnVjdHVyZWRRdWVyeSA9IHsgY3VzdG9tUXVlcnk6IHJhd1VzZXJRdWVyeSwgZXhjbHVkZUNoYXRzOiB0cnVlIH07IC8vIERlZmF1bHQgdG8gZXhjbHVkaW5nIGNoYXRzIGZvciBicm9hZCBxdWVyaWVzXG4gICAgfVxuXG4gICAgY29uc3QgZ21haWxBcGlRdWVyeVN0cmluZyA9IGJ1aWxkR21haWxTZWFyY2hRdWVyeShzdHJ1Y3R1cmVkUXVlcnkpO1xuICAgIGxvZ2dlci5pbmZvKFxuICAgICAgYFtoYW5kbGVTZWFyY2hHbWFpbF0gQ29uc3RydWN0ZWQgR21haWwgQVBJIHF1ZXJ5IHN0cmluZzogXCIke2dtYWlsQXBpUXVlcnlTdHJpbmd9XCJgXG4gICAgKTtcblxuICAgIGlmICghZ21haWxBcGlRdWVyeVN0cmluZyB8fCBnbWFpbEFwaVF1ZXJ5U3RyaW5nLnRyaW0oKSA9PT0gJycpIHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiB0cnVlLCAvLyBPciBmYWxzZSwgZGVwZW5kaW5nIG9uIGhvdyB0byB0cmVhdCBcImVtcHR5IGVmZmVjdGl2ZSBxdWVyeVwiXG4gICAgICAgIGRhdGE6IHtcbiAgICAgICAgICBlbWFpbHM6IFtdLFxuICAgICAgICAgIHVzZXJNZXNzYWdlOlxuICAgICAgICAgICAgXCJJIGNvdWxkbid0IGRldGVybWluZSBzcGVjaWZpYyBzZWFyY2ggY3JpdGVyaWEgZnJvbSB5b3VyIHJlcXVlc3QuIFBsZWFzZSB0cnkgcmVwaHJhc2luZy5cIixcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgY29uc3QgZW1haWxzOiBFbWFpbFtdID0gYXdhaXQgc2VhcmNoTXlFbWFpbHNCYWNrZW5kKFxuICAgICAgdXNlcklkLFxuICAgICAgZ21haWxBcGlRdWVyeVN0cmluZyxcbiAgICAgIGxpbWl0XG4gICAgKTtcblxuICAgIGxldCB1c2VyTWVzc2FnZSA9ICcnO1xuICAgIGlmIChlbWFpbHMubGVuZ3RoID09PSAwKSB7XG4gICAgICB1c2VyTWVzc2FnZSA9IFwiSSBjb3VsZG4ndCBmaW5kIGFueSBlbWFpbHMgbWF0Y2hpbmcgeW91ciBzZWFyY2ggY3JpdGVyaWEuXCI7XG4gICAgfSBlbHNlIHtcbiAgICAgIHVzZXJNZXNzYWdlID0gYEkgZm91bmQgJHtlbWFpbHMubGVuZ3RofSBlbWFpbChzKSBtYXRjaGluZyB5b3VyIGNyaXRlcmlhOlxcbmA7XG4gICAgICBlbWFpbHMuZm9yRWFjaCgoZW1haWwsIGluZGV4KSA9PiB7XG4gICAgICAgIHVzZXJNZXNzYWdlICs9IGAke2luZGV4ICsgMX0uIFN1YmplY3Q6IFwiJHtlbWFpbC5zdWJqZWN0fVwiIChGcm9tOiAke2VtYWlsLnNlbmRlcn0sIERhdGU6ICR7bmV3IERhdGUoZW1haWwudGltZXN0YW1wKS50b0xvY2FsZURhdGVTdHJpbmcoKX0pXFxuICAgU25pcHBldDogJHtlbWFpbC5ib2R5LnN1YnN0cmluZygwLCAxMDApfS4uLlxcbiAgIChJRDogJHtlbWFpbC5pZH0pXFxuYDtcbiAgICAgIH0pO1xuICAgIH1cbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogeyBlbWFpbHMsIHVzZXJNZXNzYWdlIH0gfTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGxvZ2dlci5lcnJvcihgW2hhbmRsZVNlYXJjaEdtYWlsXSBFcnJvcjogJHtlcnJvci5tZXNzYWdlfWAsIGVycm9yKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0dNQUlMX1NFQVJDSF9GQUlMRUQnLFxuICAgICAgICBtZXNzYWdlOiBlcnJvci5tZXNzYWdlIHx8ICdGYWlsZWQgdG8gc2VhcmNoIEdtYWlsLicsXG4gICAgICB9LFxuICAgICAgZGF0YToge1xuICAgICAgICBlbWFpbHM6IFtdLFxuICAgICAgICB1c2VyTWVzc2FnZTogYFNvcnJ5LCBJIGVuY291bnRlcmVkIGFuIGVycm9yIHdoaWxlIHNlYXJjaGluZyB5b3VyIGVtYWlsczogJHtlcnJvci5tZXNzYWdlfWAsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFJlY2VudFVucmVhZEVtYWlsc0ZvckJyaWVmaW5nKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGFyZ2V0RGF0ZTogRGF0ZSwgLy8gVGhlIHNwZWNpZmljIGRhdGUgZm9yIHdoaWNoIHRvIGdldCBlbWFpbHNcbiAgY291bnQ6IG51bWJlciA9IDMgLy8gRGVmYXVsdCB0byAzIGVtYWlsc1xuKTogUHJvbWlzZTxcbiAgU2tpbGxSZXNwb25zZTx7IHJlc3VsdHM6IEdtYWlsTWVzc2FnZVNuaXBwZXRbXTsgcXVlcnlfZXhlY3V0ZWQ/OiBzdHJpbmcgfT5cbj4ge1xuICBsb2dnZXIuaW5mbyhcbiAgICBgW2dldFJlY2VudFVucmVhZEVtYWlsc0ZvckJyaWVmaW5nXSBVc2VyOiAke3VzZXJJZH0sIFRhcmdldERhdGU6ICR7dGFyZ2V0RGF0ZS50b0lTT1N0cmluZygpLnNwbGl0KCdUJylbMF19LCBDb3VudDogJHtjb3VudH1gXG4gICk7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCBmb3JtYXREYXRlRm9yR21haWwgPSAoZGF0ZTogRGF0ZSk6IHN0cmluZyA9PiB7XG4gICAgICBjb25zdCB5ZWFyID0gZGF0ZS5nZXRVVENGdWxsWWVhcigpO1xuICAgICAgY29uc3QgbW9udGggPSAoZGF0ZS5nZXRVVENNb250aCgpICsgMSkudG9TdHJpbmcoKS5wYWRTdGFydCgyLCAnMCcpO1xuICAgICAgY29uc3QgZGF5ID0gZGF0ZS5nZXRVVENEYXRlKCkudG9TdHJpbmcoKS5wYWRTdGFydCgyLCAnMCcpO1xuICAgICAgcmV0dXJuIGAke3llYXJ9LyR7bW9udGh9LyR7ZGF5fWA7XG4gICAgfTtcblxuICAgIGNvbnN0IGFmdGVyRGF0ZSA9IG5ldyBEYXRlKHRhcmdldERhdGUpO1xuICAgIGFmdGVyRGF0ZS5zZXRVVENIb3VycygwLCAwLCAwLCAwKTsgLy8gU3RhcnQgb2YgdGFyZ2V0RGF0ZSBpbiBVVENcblxuICAgIGNvbnN0IGJlZm9yZURhdGUgPSBuZXcgRGF0ZSh0YXJnZXREYXRlKTtcbiAgICBiZWZvcmVEYXRlLnNldFVUQ0hvdXJzKDAsIDAsIDAsIDApO1xuICAgIGJlZm9yZURhdGUuc2V0VVRDRGF0ZSh0YXJnZXREYXRlLmdldFVUQ0RhdGUoKSArIDEpOyAvLyBTdGFydCBvZiB0aGUgZGF5ICphZnRlciogdGFyZ2V0RGF0ZSBmb3IgZXhjbHVzaXZlICdiZWZvcmUnXG5cbiAgICBjb25zdCBxdWVyeVBhcnRzID0gW1xuICAgICAgJ2lzOnVucmVhZCcsXG4gICAgICAnaW46aW5ib3gnLCAvLyBTdGFuZGFyZCBpbmJveFxuICAgICAgLy8gQ29uc2lkZXIgJ2NhdGVnb3J5OnByaW1hcnknIGlmIHdhbnRpbmcgdG8gZmlsdGVyIHByb21vdGlvbnMvc29jaWFsLCBidXQgJ2luOmluYm94JyBpcyBicm9hZGVyLlxuICAgICAgYGFmdGVyOiR7Zm9ybWF0RGF0ZUZvckdtYWlsKGFmdGVyRGF0ZSl9YCxcbiAgICAgIGBiZWZvcmU6JHtmb3JtYXREYXRlRm9yR21haWwoYmVmb3JlRGF0ZSl9YCxcbiAgICBdO1xuXG4gICAgY29uc3QgZ21haWxBcGlRdWVyeVN0cmluZyA9IHF1ZXJ5UGFydHMuam9pbignICcpO1xuICAgIGxvZ2dlci5pbmZvKFxuICAgICAgYFtnZXRSZWNlbnRVbnJlYWRFbWFpbHNGb3JCcmllZmluZ10gQ29uc3RydWN0ZWQgR21haWwgQVBJIHF1ZXJ5IHN0cmluZzogXCIke2dtYWlsQXBpUXVlcnlTdHJpbmd9XCJgXG4gICAgKTtcblxuICAgIC8vIHNlYXJjaE15RW1haWxzQmFja2VuZCBleHBlY3RzIGEgcmF3IHF1ZXJ5IHN0cmluZyBhbmQgcmV0dXJucyBFbWFpbFtdXG4gICAgY29uc3QgYmFja2VuZFJlc3VsdHM6IEVtYWlsW10gPSBhd2FpdCBzZWFyY2hNeUVtYWlsc0JhY2tlbmQoXG4gICAgICB1c2VySWQsXG4gICAgICBnbWFpbEFwaVF1ZXJ5U3RyaW5nLFxuICAgICAgY291bnRcbiAgICApO1xuXG4gICAgY29uc3QgcmVzdWx0czogR21haWxNZXNzYWdlU25pcHBldFtdID0gYmFja2VuZFJlc3VsdHMubWFwKChlbWFpbCkgPT4gKHtcbiAgICAgIGlkOiBlbWFpbC5pZCxcbiAgICAgIHRocmVhZElkOiBlbWFpbC50aHJlYWRJZCwgLy8gQXNzdW1pbmcgRW1haWwgdHlwZSBmcm9tIGVtYWlsU2tpbGxzIGhhcyB0aHJlYWRJZFxuICAgICAgc3ViamVjdDogZW1haWwuc3ViamVjdCxcbiAgICAgIGZyb206IGVtYWlsLnNlbmRlciwgLy8gQXNzdW1pbmcgRW1haWwgdHlwZSBmcm9tIGVtYWlsU2tpbGxzIGhhcyBzZW5kZXJcbiAgICAgIGRhdGU6IGVtYWlsLnRpbWVzdGFtcCwgLy8gQXNzdW1pbmcgRW1haWwgdHlwZSBmcm9tIGVtYWlsU2tpbGxzIGhhcyB0aW1lc3RhbXAgKElTTyBzdHJpbmcpXG4gICAgICBzbmlwcGV0OiBlbWFpbC5ib2R5Py5zdWJzdHJpbmcoMCwgMjAwKSwgLy8gVXNlIGJvZHkgYXMgc25pcHBldCwgdHJ1bmNhdGVcbiAgICAgIGxpbms6IGVtYWlsLmlkXG4gICAgICAgID8gYGh0dHBzOi8vbWFpbC5nb29nbGUuY29tL21haWwvdS8wLyNpbmJveC8ke2VtYWlsLmlkfWBcbiAgICAgICAgOiB1bmRlZmluZWQsXG4gICAgfSkpO1xuXG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICBgW2dldFJlY2VudFVucmVhZEVtYWlsc0ZvckJyaWVmaW5nXSBGb3VuZCAke3Jlc3VsdHMubGVuZ3RofSB1bnJlYWQgZW1haWxzIGZvciB0aGUgdGFyZ2V0IGRhdGUuYFxuICAgICk7XG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHsgcmVzdWx0cywgcXVlcnlfZXhlY3V0ZWQ6IGdtYWlsQXBpUXVlcnlTdHJpbmcgfSB9O1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgYFtnZXRSZWNlbnRVbnJlYWRFbWFpbHNGb3JCcmllZmluZ10gRXJyb3I6ICR7ZXJyb3IubWVzc2FnZX1gLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnR01BSUxfQlJJRUZJTkdfRkVUQ0hfRkFJTEVEJyxcbiAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICBlcnJvci5tZXNzYWdlIHx8ICdGYWlsZWQgdG8gZmV0Y2ggcmVjZW50IHVucmVhZCBlbWFpbHMgZm9yIGJyaWVmaW5nLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn1cblxuaW1wb3J0IHtcbiAgR21haWxTZWFyY2hQYXJhbWV0ZXJzLFxuICBDYWxlbmRhckV2ZW50U3VtbWFyeSxcbiAgR21haWxNZXNzYWdlU25pcHBldCxcbn0gZnJvbSAnLi4vdHlwZXMnOyAvLyBBZGRlZCBmb3Igc2VhcmNoRW1haWxzRm9yUHJlcFxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gc2VhcmNoRW1haWxzRm9yUHJlcChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHBhcmFtczogR21haWxTZWFyY2hQYXJhbWV0ZXJzLFxuICBtZWV0aW5nQ29udGV4dD86IENhbGVuZGFyRXZlbnRTdW1tYXJ5IHwgbnVsbCwgLy8gT3B0aW9uYWwgbWVldGluZyBjb250ZXh0XG4gIGxpbWl0OiBudW1iZXIgPSA1IC8vIERlZmF1bHQgbGltaXQgZm9yIHByZXAgcmVzdWx0c1xuKTogUHJvbWlzZTxcbiAgU2tpbGxSZXNwb25zZTx7IHJlc3VsdHM6IEdtYWlsTWVzc2FnZVNuaXBwZXRbXTsgcXVlcnlfZXhlY3V0ZWQ/OiBzdHJpbmcgfT5cbj4ge1xuICBsb2dnZXIuaW5mbyhcbiAgICBgW3NlYXJjaEVtYWlsc0ZvclByZXBdIFVzZXI6ICR7dXNlcklkfSwgUGFyYW1zOiAke0pTT04uc3RyaW5naWZ5KHBhcmFtcyl9LCBNZWV0aW5nQ29udGV4dDogJHttZWV0aW5nQ29udGV4dD8uc3VtbWFyeX1gXG4gICk7XG5cbiAgdHJ5IHtcbiAgICBsZXQgc3RydWN0dXJlZFF1ZXJ5OiBQYXJ0aWFsPFN0cnVjdHVyZWRFbWFpbFF1ZXJ5PiA9IHt9O1xuXG4gICAgLy8gMS4gUG9wdWxhdGUgc3RydWN0dXJlZFF1ZXJ5IGZyb20gcGFyYW1zXG4gICAgaWYgKHBhcmFtcy5mcm9tX3NlbmRlcikgc3RydWN0dXJlZFF1ZXJ5LmZyb20gPSBwYXJhbXMuZnJvbV9zZW5kZXI7XG4gICAgaWYgKHBhcmFtcy5zdWJqZWN0X2tleXdvcmRzKVxuICAgICAgc3RydWN0dXJlZFF1ZXJ5LnN1YmplY3QgPSBwYXJhbXMuc3ViamVjdF9rZXl3b3JkcztcbiAgICBpZiAocGFyYW1zLmJvZHlfa2V5d29yZHMpIHN0cnVjdHVyZWRRdWVyeS5ib2R5ID0gcGFyYW1zLmJvZHlfa2V5d29yZHM7IC8vIERpcmVjdCBtYXBwaW5nXG4gICAgaWYgKHBhcmFtcy5oYXNfYXR0YWNobWVudF9vbmx5KSBzdHJ1Y3R1cmVkUXVlcnkuaGFzQXR0YWNobWVudCA9IHRydWU7XG5cbiAgICAvLyBEYXRlIHF1ZXJ5IGhhbmRsaW5nIC0gbmVlZHMgcm9idXN0IHBhcnNpbmcgb3IgZGlyZWN0IHVzZSBpZiBmb3JtYXR0ZWQgZm9yIEdtYWlsXG4gICAgLy8gRm9yIHNpbXBsaWNpdHksIGlmIHBhcmFtcy5kYXRlX3F1ZXJ5IGlzIGxpa2UgXCJhZnRlcjpZWVlZL01NL0REIGJlZm9yZTpZWVlZL01NL0REXCIsIGJ1aWxkR21haWxRdWVyeVN0cmluZyBtaWdodCB1c2UgaXQuXG4gICAgLy8gT3RoZXJ3aXNlLCB0aGlzIHBhcnQgbmVlZHMgbW9yZSBzb3BoaXN0aWNhdGVkIGRhdGUgcGFyc2luZyBsb2dpYy5cbiAgICAvLyBGb3Igbm93LCB3ZSdsbCBhc3N1bWUgYnVpbGRHbWFpbFF1ZXJ5U3RyaW5nIGhhbmRsZXMgd2hhdCBpdCBjYW4gZnJvbSBkYXRlX3F1ZXJ5IG9yIG1lZXRpbmcgY29udGV4dC5cblxuICAgIC8vIDIuIEVuaGFuY2Ugc3RydWN0dXJlZFF1ZXJ5IHdpdGggbWVldGluZ0NvbnRleHRcbiAgICBpZiAobWVldGluZ0NvbnRleHQpIHtcbiAgICAgIGNvbnN0IGV2ZW50S2V5d29yZHNBcnJheTogc3RyaW5nW10gPSBbXTtcbiAgICAgIGlmIChtZWV0aW5nQ29udGV4dC5zdW1tYXJ5KSB7XG4gICAgICAgIC8vIEFkZCBldmVudCB0aXRsZSBrZXl3b3JkcyB0byBzdWJqZWN0L2JvZHkgc2VhcmNoXG4gICAgICAgIC8vIFNpbXBsZSBzcGxpdCwgY291bGQgYmUgaW1wcm92ZWQgKGUuZy4gcmVtb3ZlIGNvbW1vbiB3b3JkcylcbiAgICAgICAgZXZlbnRLZXl3b3Jkc0FycmF5LnB1c2goXG4gICAgICAgICAgLi4ubWVldGluZ0NvbnRleHQuc3VtbWFyeVxuICAgICAgICAgICAgLnRvTG93ZXJDYXNlKClcbiAgICAgICAgICAgIC5zcGxpdCgnICcpXG4gICAgICAgICAgICAuZmlsdGVyKChrdykgPT4ga3cubGVuZ3RoID4gMilcbiAgICAgICAgKTtcbiAgICAgIH1cblxuICAgICAgLy8gSGFuZGxlIGF0dGVuZGVlcyBieSBidWlsZGluZyBhIHNwZWNpZmljIChmcm9tOlggT1IgdG86WCBPUiBmcm9tOlkgT1IgdG86WSkgcXVlcnkgcGFydC5cbiAgICAgIGlmIChtZWV0aW5nQ29udGV4dC5hdHRlbmRlZXMgJiYgbWVldGluZ0NvbnRleHQuYXR0ZW5kZWVzLmxlbmd0aCA+IDApIHtcbiAgICAgICAgY29uc3QgYXR0ZW5kZWVFbWFpbFF1ZXJpZXM6IHN0cmluZ1tdID0gW107XG4gICAgICAgIC8vIEV4dHJhY3QgZW1haWwgZnJvbSBhdHRlbmRlZSBzdHJpbmcgKGUuZy4sIFwiRGlzcGxheSBOYW1lIDxlbWFpbEBleGFtcGxlLmNvbT5cIiBvciBqdXN0IFwiZW1haWxAZXhhbXBsZS5jb21cIilcbiAgICAgICAgY29uc3QgZW1haWxSZWdleCA9IC88KFtePl0rKT4vO1xuXG4gICAgICAgIG1lZXRpbmdDb250ZXh0LmF0dGVuZGVlcy5mb3JFYWNoKChhdHRlbmRlZVN0cmluZykgPT4ge1xuICAgICAgICAgIGxldCBlbWFpbDogc3RyaW5nIHwgdW5kZWZpbmVkID0gdW5kZWZpbmVkO1xuICAgICAgICAgIGNvbnN0IG1hdGNoID0gYXR0ZW5kZWVTdHJpbmcubWF0Y2goZW1haWxSZWdleCk7XG4gICAgICAgICAgaWYgKG1hdGNoICYmIG1hdGNoWzFdKSB7XG4gICAgICAgICAgICBlbWFpbCA9IG1hdGNoWzFdLnRyaW0oKTtcbiAgICAgICAgICB9IGVsc2UgaWYgKFxuICAgICAgICAgICAgYXR0ZW5kZWVTdHJpbmcuaW5jbHVkZXMoJ0AnKSAmJlxuICAgICAgICAgICAgIWF0dGVuZGVlU3RyaW5nLnN0YXJ0c1dpdGgoJzwnKSAmJlxuICAgICAgICAgICAgIWF0dGVuZGVlU3RyaW5nLmVuZHNXaXRoKCc+JylcbiAgICAgICAgICApIHtcbiAgICAgICAgICAgIC8vIElmIGl0IGNvbnRhaW5zICdAJyBhbmQgaXMgbm90IGFscmVhZHkgY2F1Z2h0IGJ5IHJlZ2V4IChlLmcuIGp1c3QgXCJ1c2VyQGV4YW1wbGUuY29tXCIpXG4gICAgICAgICAgICAvLyBBbHNvIGVuc3VyZSBpdCdzIG5vdCBwYXJ0IG9mIGEgbWFsZm9ybWVkIHN0cmluZyBsaWtlIFwiPHVzZXJAZXhhbXBsZS5jb21cIlxuICAgICAgICAgICAgY29uc3QgcG90ZW50aWFsRW1haWwgPSBhdHRlbmRlZVN0cmluZ1xuICAgICAgICAgICAgICAuc3BsaXQoL1xccysvKVxuICAgICAgICAgICAgICAuZmluZCgocGFydCkgPT4gcGFydC5pbmNsdWRlcygnQCcpKTtcbiAgICAgICAgICAgIGlmIChwb3RlbnRpYWxFbWFpbCkge1xuICAgICAgICAgICAgICBlbWFpbCA9IHBvdGVudGlhbEVtYWlsLnRyaW0oKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgICAgLy8gTm90ZTogV2UgYXJlIG5vdCBhdHRlbXB0aW5nIHRvIGV4dHJhY3QgZW1haWxzIGZyb20gZGlzcGxheSBuYW1lcyBpZiBubyBleHBsaWNpdCBlbWFpbCBpcyBwcm92aWRlZC5cbiAgICAgICAgICAvLyBUaGlzIGZvY3VzZXMgdGhlIHNlYXJjaCBvbiBhY3R1YWwgZW1haWwgYWRkcmVzc2VzIGludm9sdmVkLlxuXG4gICAgICAgICAgaWYgKGVtYWlsICYmIGVtYWlsLnRvTG93ZXJDYXNlKCkgIT09IHVzZXJJZC50b0xvd2VyQ2FzZSgpKSB7XG4gICAgICAgICAgICAvLyBFeGNsdWRlIHNlbGYsIGNhc2UtaW5zZW5zaXRpdmVcbiAgICAgICAgICAgIGNvbnN0IHNhbml0aXplZEVtYWlsID0gZW1haWw7IC8vIEFscmVhZHkgdHJpbW1lZCBpZiBleHRyYWN0ZWRcbiAgICAgICAgICAgIGF0dGVuZGVlRW1haWxRdWVyaWVzLnB1c2goYGZyb206JHtzYW5pdGl6ZWRFbWFpbH1gKTtcbiAgICAgICAgICAgIGF0dGVuZGVlRW1haWxRdWVyaWVzLnB1c2goYHRvOiR7c2FuaXRpemVkRW1haWx9YCk7XG4gICAgICAgICAgfVxuICAgICAgICB9KTtcblxuICAgICAgICBpZiAoYXR0ZW5kZWVFbWFpbFF1ZXJpZXMubGVuZ3RoID4gMCkge1xuICAgICAgICAgIGNvbnN0IGF0dGVuZGVlUXVlcnlQYXJ0ID0gYCgke2F0dGVuZGVlRW1haWxRdWVyaWVzLmpvaW4oJyBPUiAnKX0pYDtcbiAgICAgICAgICBzdHJ1Y3R1cmVkUXVlcnkuY3VzdG9tUXVlcnkgPSBzdHJ1Y3R1cmVkUXVlcnkuY3VzdG9tUXVlcnlcbiAgICAgICAgICAgID8gYCR7c3RydWN0dXJlZFF1ZXJ5LmN1c3RvbVF1ZXJ5fSAke2F0dGVuZGVlUXVlcnlQYXJ0fWBcbiAgICAgICAgICAgIDogYXR0ZW5kZWVRdWVyeVBhcnQ7XG4gICAgICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgICAgICBgW3NlYXJjaEVtYWlsc0ZvclByZXBdIEFkZGVkIGF0dGVuZGVlIHF1ZXJ5IHBhcnQ6ICR7YXR0ZW5kZWVRdWVyeVBhcnR9YFxuICAgICAgICAgICk7XG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgICAgLy8gQ29tYmluZSBldmVudCBzdW1tYXJ5IGtleXdvcmRzIGFuZCBhZGQgdG8gYm9keSBzZWFyY2guXG4gICAgICBpZiAoZXZlbnRLZXl3b3Jkc0FycmF5Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgY29uc3QgdW5pcXVlRXZlbnRLZXl3b3JkcyA9IEFycmF5LmZyb20obmV3IFNldChldmVudEtleXdvcmRzQXJyYXkpKTtcbiAgICAgICAgY29uc3QgZXZlbnRLZXl3b3JkU3RyaW5nID0gdW5pcXVlRXZlbnRLZXl3b3Jkcy5qb2luKCcgJyk7XG4gICAgICAgIHN0cnVjdHVyZWRRdWVyeS5ib2R5ID0gc3RydWN0dXJlZFF1ZXJ5LmJvZHlcbiAgICAgICAgICA/IGAke3N0cnVjdHVyZWRRdWVyeS5ib2R5fSAke2V2ZW50S2V5d29yZFN0cmluZ31gXG4gICAgICAgICAgOiBldmVudEtleXdvcmRTdHJpbmc7XG4gICAgICB9XG5cbiAgICAgIC8vIFJlZmluZSBkYXRlIHJhbmdlIGJhc2VkIG9uIG1lZXRpbmcgc3RhcnQgdGltZSBpZiBwYXJhbXMuZGF0ZV9xdWVyeSBpcyBub3Qgc3BlY2lmaWMgb3Igbm90IHByb3ZpZGVkLlxuICAgICAgLy8gVGhlIGdvYWwgaXMgdG8gZXN0YWJsaXNoIGEgc2Vuc2libGUgZGVmYXVsdCB3aW5kb3cgYXJvdW5kIHRoZSBtZWV0aW5nLlxuICAgICAgY29uc3QgaXNEYXRlUXVlcnlHZW5lcmljID1cbiAgICAgICAgIXBhcmFtcy5kYXRlX3F1ZXJ5IHx8XG4gICAgICAgIHBhcmFtcy5kYXRlX3F1ZXJ5LnRvTG93ZXJDYXNlKCkgPT09ICdyZWNlbnQnIHx8XG4gICAgICAgIHBhcmFtcy5kYXRlX3F1ZXJ5LnRyaW0oKSA9PT0gJyc7XG4gICAgICBpZiAobWVldGluZ0NvbnRleHQuc3RhcnQgJiYgaXNEYXRlUXVlcnlHZW5lcmljKSB7XG4gICAgICAgIGNvbnN0IG1lZXRpbmdTdGFydERhdGUgPSBuZXcgRGF0ZShtZWV0aW5nQ29udGV4dC5zdGFydCk7XG4gICAgICAgIG1lZXRpbmdTdGFydERhdGUuc2V0SG91cnMoMCwgMCwgMCwgMCk7IC8vIE5vcm1hbGl6ZSB0byBzdGFydCBvZiBkYXkgZm9yICdhZnRlcidcblxuICAgICAgICAvLyBEZWZhdWx0OiA3IGRheXMgYmVmb3JlIHRoZSBtZWV0aW5nIHN0YXJ0IGRheVxuICAgICAgICAvLyBUT0RPOiBNYWtlIHRoaXMgd2luZG93ICg3IGRheXMpIGNvbmZpZ3VyYWJsZSBvciBtb3JlIGR5bmFtaWMgYmFzZWQgb24gbWVldGluZyBwcm94aW1pdHkuXG4gICAgICAgIGNvbnN0IGFmdGVyRGF0ZU9iaiA9IG5ldyBEYXRlKG1lZXRpbmdTdGFydERhdGUpO1xuICAgICAgICBhZnRlckRhdGVPYmouc2V0RGF0ZShtZWV0aW5nU3RhcnREYXRlLmdldERhdGUoKSAtIDcpO1xuXG4gICAgICAgIC8vIERldGVybWluZSAnYmVmb3JlJyBkYXRlOiBkYXkgYWZ0ZXIgbWVldGluZyBlbmQsIG9yIGRheSBhZnRlciBtZWV0aW5nIHN0YXJ0IGlmIGVuZCBpcyBub3QgYXZhaWxhYmxlL3ZhbGlkXG4gICAgICAgIGxldCBtZWV0aW5nRW5kRGF0ZUZvclF1ZXJ5OiBEYXRlO1xuICAgICAgICBpZiAobWVldGluZ0NvbnRleHQuZW5kKSB7XG4gICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgIG1lZXRpbmdFbmREYXRlRm9yUXVlcnkgPSBuZXcgRGF0ZShtZWV0aW5nQ29udGV4dC5lbmQpO1xuICAgICAgICAgICAgLy8gQ2hlY2sgaWYgbWVldGluZ0NvbnRleHQuZW5kIHdhcyBhIHZhbGlkIGRhdGUgc3RyaW5nXG4gICAgICAgICAgICBpZiAoaXNOYU4obWVldGluZ0VuZERhdGVGb3JRdWVyeS5nZXRUaW1lKCkpKSB7XG4gICAgICAgICAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICAgICAgICAgIGBbc2VhcmNoRW1haWxzRm9yUHJlcF0gSW52YWxpZCBtZWV0aW5nQ29udGV4dC5lbmQgZGF0ZTogJHttZWV0aW5nQ29udGV4dC5lbmR9LiBGYWxsaW5nIGJhY2sgdG8gc3RhcnQgZGF0ZS5gXG4gICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgIG1lZXRpbmdFbmREYXRlRm9yUXVlcnkgPSBuZXcgRGF0ZShtZWV0aW5nQ29udGV4dC5zdGFydCk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfSBjYXRjaCAoZSkge1xuICAgICAgICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgICAgICAgIGBbc2VhcmNoRW1haWxzRm9yUHJlcF0gRXJyb3IgcGFyc2luZyBtZWV0aW5nQ29udGV4dC5lbmQgZGF0ZTogJHttZWV0aW5nQ29udGV4dC5lbmR9LiBGYWxsaW5nIGJhY2sgdG8gc3RhcnQgZGF0ZS5gLFxuICAgICAgICAgICAgICBlXG4gICAgICAgICAgICApO1xuICAgICAgICAgICAgbWVldGluZ0VuZERhdGVGb3JRdWVyeSA9IG5ldyBEYXRlKG1lZXRpbmdDb250ZXh0LnN0YXJ0KTtcbiAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgbWVldGluZ0VuZERhdGVGb3JRdWVyeSA9IG5ldyBEYXRlKG1lZXRpbmdDb250ZXh0LnN0YXJ0KTtcbiAgICAgICAgfVxuICAgICAgICBtZWV0aW5nRW5kRGF0ZUZvclF1ZXJ5LnNldEhvdXJzKDAsIDAsIDAsIDApOyAvLyBOb3JtYWxpemVcblxuICAgICAgICBjb25zdCBiZWZvcmVEYXRlT2JqID0gbmV3IERhdGUobWVldGluZ0VuZERhdGVGb3JRdWVyeSk7XG4gICAgICAgIGJlZm9yZURhdGVPYmouc2V0RGF0ZShtZWV0aW5nRW5kRGF0ZUZvclF1ZXJ5LmdldERhdGUoKSArIDEpOyAvLyBEYXkgYWZ0ZXIgdGhlIG1lZXRpbmcgKGV4Y2x1c2l2ZSBlbmQgZm9yIHF1ZXJ5KVxuXG4gICAgICAgIGNvbnN0IGZvcm1hdERhdGUgPSAoZGF0ZTogRGF0ZSk6IHN0cmluZyA9PiB7XG4gICAgICAgICAgY29uc3QgeWVhciA9IGRhdGUuZ2V0RnVsbFllYXIoKTtcbiAgICAgICAgICBjb25zdCBtb250aCA9IChkYXRlLmdldE1vbnRoKCkgKyAxKS50b1N0cmluZygpLnBhZFN0YXJ0KDIsICcwJyk7XG4gICAgICAgICAgY29uc3QgZGF5ID0gZGF0ZS5nZXREYXRlKCkudG9TdHJpbmcoKS5wYWRTdGFydCgyLCAnMCcpO1xuICAgICAgICAgIHJldHVybiBgJHt5ZWFyfS8ke21vbnRofS8ke2RheX1gO1xuICAgICAgICB9O1xuXG4gICAgICAgIHN0cnVjdHVyZWRRdWVyeS5hZnRlciA9IGZvcm1hdERhdGUoYWZ0ZXJEYXRlT2JqKTtcbiAgICAgICAgc3RydWN0dXJlZFF1ZXJ5LmJlZm9yZSA9IGZvcm1hdERhdGUoYmVmb3JlRGF0ZU9iaik7XG4gICAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICAgIGBbc2VhcmNoRW1haWxzRm9yUHJlcF0gRGF0ZSByYW5nZSBmcm9tIG1lZXRpbmcgY29udGV4dDogYWZ0ZXI6JHtzdHJ1Y3R1cmVkUXVlcnkuYWZ0ZXJ9IGJlZm9yZToke3N0cnVjdHVyZWRRdWVyeS5iZWZvcmV9YFxuICAgICAgICApO1xuICAgICAgfVxuICAgIH1cblxuICAgIC8vIElmIG5vIGRhdGUgcmFuZ2Ugd2FzIHNldCBieSBtZWV0aW5nQ29udGV4dCwgdHJ5IHRvIHBhcnNlIHBhcmFtcy5kYXRlX3F1ZXJ5XG4gICAgaWYgKFxuICAgICAgIShzdHJ1Y3R1cmVkUXVlcnkuYWZ0ZXIgfHwgc3RydWN0dXJlZFF1ZXJ5LmJlZm9yZSkgJiZcbiAgICAgIHBhcmFtcy5kYXRlX3F1ZXJ5XG4gICAgKSB7XG4gICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgYFtzZWFyY2hFbWFpbHNGb3JQcmVwXSBBdHRlbXB0aW5nIHRvIHBhcnNlIHBhcmFtcy5kYXRlX3F1ZXJ5OiBcIiR7cGFyYW1zLmRhdGVfcXVlcnl9XCJgXG4gICAgICApO1xuICAgICAgY29uc3QgcGFyc2VkRGF0ZXMgPSBwYXJzZVJlbGF0aXZlRGF0ZVF1ZXJ5KHBhcmFtcy5kYXRlX3F1ZXJ5KTtcbiAgICAgIGlmIChwYXJzZWREYXRlcykge1xuICAgICAgICBpZiAocGFyc2VkRGF0ZXMuYWZ0ZXIpIHN0cnVjdHVyZWRRdWVyeS5hZnRlciA9IHBhcnNlZERhdGVzLmFmdGVyO1xuICAgICAgICBpZiAocGFyc2VkRGF0ZXMuYmVmb3JlKSBzdHJ1Y3R1cmVkUXVlcnkuYmVmb3JlID0gcGFyc2VkRGF0ZXMuYmVmb3JlO1xuICAgICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgICBgW3NlYXJjaEVtYWlsc0ZvclByZXBdIFBhcnNlZCBkYXRlIHF1ZXJ5IHRvOiBhZnRlcjoke3BhcnNlZERhdGVzLmFmdGVyfSwgYmVmb3JlOiR7cGFyc2VkRGF0ZXMuYmVmb3JlfWBcbiAgICAgICAgKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIC8vIElmIHBhcnNlUmVsYXRpdmVEYXRlUXVlcnkgY291bGRuJ3QgdW5kZXJzdGFuZCBpdCwgYW5kIGl0IGxvb2tzIGxpa2UgYSByYXcgR21haWwgcXVlcnkgcGFydCwgYWRkIGl0IHRvIGN1c3RvbVF1ZXJ5LlxuICAgICAgICAvLyBUaGlzIGlzIGEgZmFsbGJhY2sgZm9yIHF1ZXJpZXMgbGlrZSBcIm9sZGVyX3RoYW46N2RcIiBvciBzcGVjaWZpYyBcImFmdGVyOllZWVkvTU0vRERcIiBpZiBub3QgY2F1Z2h0IGJ5IHBhcnNlUmVsYXRpdmVEYXRlUXVlcnkncyBvd24gY2hlY2suXG4gICAgICAgIGlmIChcbiAgICAgICAgICBwYXJhbXMuZGF0ZV9xdWVyeS5pbmNsdWRlcygnOicpICYmXG4gICAgICAgICAgKHBhcmFtcy5kYXRlX3F1ZXJ5LmluY2x1ZGVzKCdvbGRlcl90aGFuJykgfHxcbiAgICAgICAgICAgIHBhcmFtcy5kYXRlX3F1ZXJ5LmluY2x1ZGVzKCduZXdlcl90aGFuJykgfHxcbiAgICAgICAgICAgIHBhcmFtcy5kYXRlX3F1ZXJ5Lm1hdGNoKC8oYWZ0ZXJ8YmVmb3JlKTpcXGR7NH1cXC9cXGR7Mn1cXC9cXGR7Mn0vKSlcbiAgICAgICAgKSB7XG4gICAgICAgICAgc3RydWN0dXJlZFF1ZXJ5LmN1c3RvbVF1ZXJ5ID0gc3RydWN0dXJlZFF1ZXJ5LmN1c3RvbVF1ZXJ5XG4gICAgICAgICAgICA/IGAke3N0cnVjdHVyZWRRdWVyeS5jdXN0b21RdWVyeX0gJHtwYXJhbXMuZGF0ZV9xdWVyeX1gXG4gICAgICAgICAgICA6IHBhcmFtcy5kYXRlX3F1ZXJ5O1xuICAgICAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICAgICAgYFtzZWFyY2hFbWFpbHNGb3JQcmVwXSBVc2luZyBwYXJhbXMuZGF0ZV9xdWVyeSBhcyBjdXN0b20gcXVlcnkgcGFydDogXCIke3BhcmFtcy5kYXRlX3F1ZXJ5fVwiYFxuICAgICAgICAgICk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgbG9nZ2VyLndhcm4oXG4gICAgICAgICAgICBgW3NlYXJjaEVtYWlsc0ZvclByZXBdIENvdWxkIG5vdCBwYXJzZSBkYXRlX3F1ZXJ5OiBcIiR7cGFyYW1zLmRhdGVfcXVlcnl9XCIgYW5kIGl0IGRvZXNuJ3QgbG9vayBsaWtlIGEgZGlyZWN0IEdtYWlsIGRhdGUgdGVybS5gXG4gICAgICAgICAgKTtcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cblxuICAgIC8vIERlZmF1bHQgdG8gZXhjbHVkaW5nIGNoYXRzIGlmIG5vdCBvdGhlcndpc2Ugc3BlY2lmaWVkLlxuICAgIGlmIChzdHJ1Y3R1cmVkUXVlcnkuZXhjbHVkZUNoYXRzID09PSB1bmRlZmluZWQpIHtcbiAgICAgIHN0cnVjdHVyZWRRdWVyeS5leGNsdWRlQ2hhdHMgPSB0cnVlO1xuICAgIH1cblxuICAgIGNvbnN0IGdtYWlsQXBpUXVlcnlTdHJpbmcgPSBidWlsZEdtYWlsU2VhcmNoUXVlcnkoc3RydWN0dXJlZFF1ZXJ5KTtcbiAgICBsb2dnZXIuaW5mbyhcbiAgICAgIGBbc2VhcmNoRW1haWxzRm9yUHJlcF0gQ29uc3RydWN0ZWQgR21haWwgQVBJIHF1ZXJ5IHN0cmluZzogXCIke2dtYWlsQXBpUXVlcnlTdHJpbmd9XCJgXG4gICAgKTtcblxuICAgIGlmICghZ21haWxBcGlRdWVyeVN0cmluZyB8fCBnbWFpbEFwaVF1ZXJ5U3RyaW5nLnRyaW0oKSA9PT0gJycpIHtcbiAgICAgIGxvZ2dlci53YXJuKFxuICAgICAgICAnW3NlYXJjaEVtYWlsc0ZvclByZXBdIEVtcHR5IEdtYWlsIEFQSSBxdWVyeSBzdHJpbmcgZ2VuZXJhdGVkLiBSZXR1cm5pbmcgbm8gcmVzdWx0cy4nXG4gICAgICApO1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgb2s6IHRydWUsXG4gICAgICAgIGRhdGE6IHsgcmVzdWx0czogW10sIHF1ZXJ5X2V4ZWN1dGVkOiBnbWFpbEFwaVF1ZXJ5U3RyaW5nIH0sXG4gICAgICB9O1xuICAgIH1cblxuICAgIGNvbnN0IGJhY2tlbmRSZXN1bHRzOiBFbWFpbFtdID0gYXdhaXQgc2VhcmNoTXlFbWFpbHNCYWNrZW5kKFxuICAgICAgdXNlcklkLFxuICAgICAgZ21haWxBcGlRdWVyeVN0cmluZyxcbiAgICAgIGxpbWl0XG4gICAgKTtcblxuICAgIGNvbnN0IHJlc3VsdHM6IEdtYWlsTWVzc2FnZVNuaXBwZXRbXSA9IGJhY2tlbmRSZXN1bHRzLm1hcCgoZW1haWwpID0+ICh7XG4gICAgICBpZDogZW1haWwuaWQsXG4gICAgICB0aHJlYWRJZDogZW1haWwudGhyZWFkSWQsXG4gICAgICBzdWJqZWN0OiBlbWFpbC5zdWJqZWN0LFxuICAgICAgZnJvbTogZW1haWwuc2VuZGVyLFxuICAgICAgZGF0ZTogZW1haWwudGltZXN0YW1wLFxuICAgICAgc25pcHBldDogZW1haWwuYm9keT8uc3Vic3RyaW5nKDAsIDIwMCksIC8vIFRydW5jYXRlIHNuaXBwZXRcbiAgICAgIGxpbms6IGVtYWlsLmlkXG4gICAgICAgID8gYGh0dHBzOi8vbWFpbC5nb29nbGUuY29tL21haWwvdS8wLyNpbmJveC8ke2VtYWlsLmlkfWBcbiAgICAgICAgOiB1bmRlZmluZWQsXG4gICAgfSkpO1xuXG4gICAgbG9nZ2VyLmluZm8oYFtzZWFyY2hFbWFpbHNGb3JQcmVwXSBGb3VuZCAke3Jlc3VsdHMubGVuZ3RofSBlbWFpbHMuYCk7XG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHsgcmVzdWx0cywgcXVlcnlfZXhlY3V0ZWQ6IGdtYWlsQXBpUXVlcnlTdHJpbmcgfSB9O1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nZ2VyLmVycm9yKGBbc2VhcmNoRW1haWxzRm9yUHJlcF0gRXJyb3I6ICR7ZXJyb3IubWVzc2FnZX1gLCBlcnJvcik7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdHTUFJTF9QUkVQX1NFQVJDSF9GQUlMRUQnLFxuICAgICAgICBtZXNzYWdlOiBlcnJvci5tZXNzYWdlIHx8ICdGYWlsZWQgdG8gc2VhcmNoIEdtYWlsIGZvciBtZWV0aW5nIHByZXAuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlRXh0cmFjdEluZm9Gcm9tR21haWwoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBlbWFpbElkT3JSZWZlcmVuY2U6IHN0cmluZywgLy8gQ291bGQgYmUgYW4gZW1haWwgSUQgb3IgYSByZWZlcmVuY2UgbGlrZSBcImxhc3QgZW1haWwgZnJvbSAuLi5cIlxuICBpbmZvcm1hdGlvbktleXdvcmRzOiBzdHJpbmdbXSxcbiAgLy8gT3B0aW9uYWw6IGlmIE5MVSBwcm92aWRlcyB0aGUgZW1haWwgYm9keSBkaXJlY3RseSBmcm9tIGNvbnRleHQgdG8gYXZvaWQgcmUtZmV0Y2hcbiAgZW1haWxCb2R5Q29udGV4dD86IHN0cmluZ1xuKTogUHJvbWlzZTxcbiAgU2tpbGxSZXNwb25zZTx7XG4gICAgZXh0cmFjdGVkSW5mbzogUmVjb3JkPHN0cmluZywgc3RyaW5nIHwgbnVsbD47XG4gICAgdXNlck1lc3NhZ2U6IHN0cmluZztcbiAgfT5cbj4ge1xuICBsb2dnZXIuaW5mbyhcbiAgICBgW2hhbmRsZUV4dHJhY3RJbmZvRnJvbUdtYWlsXSBVc2VyOiAke3VzZXJJZH0sIEVtYWlsUmVmOiBcIiR7ZW1haWxJZE9yUmVmZXJlbmNlfVwiLCBLZXl3b3JkczogWyR7aW5mb3JtYXRpb25LZXl3b3Jkcy5qb2luKCcsICcpfV1gXG4gICk7XG5cbiAgaWYgKCFpbmZvcm1hdGlvbktleXdvcmRzIHx8IGluZm9ybWF0aW9uS2V5d29yZHMubGVuZ3RoID09PSAwKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1BsZWFzZSBzcGVjaWZ5IHdoYXQgaW5mb3JtYXRpb24geW91IHdhbnQgdG8gZXh0cmFjdC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgbGV0IGVtYWlsQm9keTogc3RyaW5nIHwgbnVsbCA9IGVtYWlsQm9keUNvbnRleHQgfHwgbnVsbDtcbiAgbGV0IGVtYWlsU3ViamVjdCA9ICd0aGUgZW1haWwnOyAvLyBEZWZhdWx0IHN1YmplY3QgZm9yIG1lc3NhZ2VzXG5cbiAgdHJ5IHtcbiAgICBpZiAoIWVtYWlsQm9keSkge1xuICAgICAgLy8gVE9ETzogSW1wbGVtZW50IGVtYWlsX2lkIHJlc29sdXRpb24gaWYgZW1haWxJZE9yUmVmZXJlbmNlIGlzIG5vdCBhIGRpcmVjdCBJRC5cbiAgICAgIC8vIFRoaXMgbWlnaHQgaW52b2x2ZTpcbiAgICAgIC8vIDEuIENoZWNraW5nIGlmIGVtYWlsSWRPclJlZmVyZW5jZSBsb29rcyBsaWtlIGEgR21haWwgSUQuXG4gICAgICAvLyAyLiBJZiBpdCdzIGEgcmVmZXJlbmNlIChlLmcuLCBcImxhc3QgZW1haWwgZnJvbSBzdXBwb3J0XCIpLCBjYWxsIGhhbmRsZVNlYXJjaEdtYWlsXG4gICAgICAvLyAgICB3aXRoIGEgcXVlcnkgY29uc3RydWN0ZWQgZnJvbSB0aGUgcmVmZXJlbmNlLCBnZXQgdGhlIHRvcCByZXN1bHQncyBJRC5cbiAgICAgIC8vICAgIFRoaXMgcGFydCBjYW4gYmUgY29tcGxleCBhbmQgbWlnaHQgcmVxdWlyZSB1c2VyIGNsYXJpZmljYXRpb24gaWYgYW1iaWd1b3VzLlxuICAgICAgLy8gRm9yIFYxLCBhc3N1bWUgZW1haWxJZE9yUmVmZXJlbmNlIElTIHRoZSBlbWFpbCBJRCBmb3Igc2ltcGxpY2l0eSBpZiBubyBib2R5IGNvbnRleHQuXG4gICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgYFtoYW5kbGVFeHRyYWN0SW5mb0Zyb21HbWFpbF0gQXR0ZW1wdGluZyB0byBmZXRjaCBlbWFpbCBJRDogJHtlbWFpbElkT3JSZWZlcmVuY2V9YFxuICAgICAgKTtcbiAgICAgIGNvbnN0IGVtYWlsUmVzdWx0ID0gYXdhaXQgcmVhZEVtYWlsQmFja2VuZCh1c2VySWQsIGVtYWlsSWRPclJlZmVyZW5jZSk7XG4gICAgICBpZiAoZW1haWxSZXN1bHQuc3VjY2VzcyAmJiBlbWFpbFJlc3VsdC5lbWFpbCkge1xuICAgICAgICBlbWFpbEJvZHkgPSBlbWFpbFJlc3VsdC5lbWFpbC5ib2R5O1xuICAgICAgICBlbWFpbFN1YmplY3QgPSBlbWFpbFJlc3VsdC5lbWFpbC5zdWJqZWN0IHx8IGVtYWlsU3ViamVjdDtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgICBlbWFpbFJlc3VsdC5tZXNzYWdlIHx8XG4gICAgICAgICAgICBgQ291bGQgbm90IGZpbmQgb3IgcmVhZCBlbWFpbCB3aXRoIHJlZmVyZW5jZTogJHtlbWFpbElkT3JSZWZlcmVuY2V9YFxuICAgICAgICApO1xuICAgICAgfVxuICAgIH1cblxuICAgIGlmICghZW1haWxCb2R5IHx8IGVtYWlsQm9keS50cmltKCkgPT09ICcnKSB7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ0VNQUlMX0NPTlRFTlRfRU1QVFknLFxuICAgICAgICAgIG1lc3NhZ2U6IGBUaGUgZW1haWwgYm9keSBmb3IgXCIke2VtYWlsU3ViamVjdH1cIiBpcyBlbXB0eSBvciBjb3VsZCBub3QgYmUgcmV0cmlldmVkLmAsXG4gICAgICAgIH0sXG4gICAgICAgIGRhdGE6IHtcbiAgICAgICAgICBleHRyYWN0ZWRJbmZvOiB7fSxcbiAgICAgICAgICB1c2VyTWVzc2FnZTogYFRoZSBlbWFpbCBib2R5IGZvciBcIiR7ZW1haWxTdWJqZWN0fVwiIGlzIGVtcHR5LCBzbyBJIGNvdWxkbid0IGV4dHJhY3QgaW5mb3JtYXRpb24uYCxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgY29uc3QgZXh0cmFjdGVkSW5mbyA9IGF3YWl0IGV4dHJhY3RJbmZvcm1hdGlvbkZyb21FbWFpbEJvZHkoXG4gICAgICBlbWFpbEJvZHksXG4gICAgICBpbmZvcm1hdGlvbktleXdvcmRzXG4gICAgKTtcblxuICAgIGxldCBmb3VuZENvdW50ID0gMDtcbiAgICBsZXQgbWVzc2FnZVBhcnRzOiBzdHJpbmdbXSA9IFtgRnJvbSBteSByZXZpZXcgb2YgXCIke2VtYWlsU3ViamVjdH1cIjpgXTtcbiAgICBpbmZvcm1hdGlvbktleXdvcmRzLmZvckVhY2goKGtleXdvcmQpID0+IHtcbiAgICAgIGlmIChcbiAgICAgICAgZXh0cmFjdGVkSW5mb1trZXl3b3JkXSAhPT0gbnVsbCAmJlxuICAgICAgICBleHRyYWN0ZWRJbmZvW2tleXdvcmRdICE9PSB1bmRlZmluZWRcbiAgICAgICkge1xuICAgICAgICBtZXNzYWdlUGFydHMucHVzaChgLSBGb3IgXCIke2tleXdvcmR9XCI6ICR7ZXh0cmFjdGVkSW5mb1trZXl3b3JkXX1gKTtcbiAgICAgICAgZm91bmRDb3VudCsrO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgbWVzc2FnZVBhcnRzLnB1c2goYC0gSSBjb3VsZG4ndCBmaW5kIGluZm9ybWF0aW9uIGFib3V0IFwiJHtrZXl3b3JkfVwiLmApO1xuICAgICAgfVxuICAgIH0pO1xuXG4gICAgY29uc3QgdXNlck1lc3NhZ2UgPVxuICAgICAgZm91bmRDb3VudCA+IDBcbiAgICAgICAgPyBtZXNzYWdlUGFydHMuam9pbignXFxuJylcbiAgICAgICAgOiBgSSByZXZpZXdlZCBcIiR7ZW1haWxTdWJqZWN0fVwiIGJ1dCBjb3VsZG4ndCBmaW5kIHRoZSBzcGVjaWZpYyBpbmZvcm1hdGlvbiB5b3UgYXNrZWQgZm9yICgke2luZm9ybWF0aW9uS2V5d29yZHMuam9pbignLCAnKX0pLmA7XG5cbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogeyBleHRyYWN0ZWRJbmZvLCB1c2VyTWVzc2FnZSB9IH07XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBsb2dnZXIuZXJyb3IoYFtoYW5kbGVFeHRyYWN0SW5mb0Zyb21HbWFpbF0gRXJyb3I6ICR7ZXJyb3IubWVzc2FnZX1gLCBlcnJvcik7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdHTUFJTF9FWFRSQUNUX0ZBSUxFRCcsXG4gICAgICAgIG1lc3NhZ2U6IGVycm9yLm1lc3NhZ2UgfHwgJ0ZhaWxlZCB0byBleHRyYWN0IGluZm9ybWF0aW9uIGZyb20gR21haWwuJyxcbiAgICAgIH0sXG4gICAgICBkYXRhOiB7XG4gICAgICAgIGV4dHJhY3RlZEluZm86IHt9LFxuICAgICAgICB1c2VyTWVzc2FnZTogYFNvcnJ5LCBJIGVuY291bnRlcmVkIGFuIGVycm9yIHdoaWxlIGV4dHJhY3RpbmcgaW5mb3JtYXRpb246ICR7ZXJyb3IubWVzc2FnZX1gLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59XG4iXX0=