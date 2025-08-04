import { buildGmailSearchQuery, } from '../skills/nlu_email_helper';
import { searchMyEmails, readEmail, } from '../skills/emailSkills';
// Assume a way to send messages back to the user, e.g., through a chat interface.
// This is a placeholder for the actual messaging function.
// import { sendAgentResponse } from '../agentResponse';
import { extractInformationFromEmailBody } from '../skills/emailSkills';
import { understandEmailSearchQueryLLM } from '../skills/llm_email_query_understander'; // Import LLM query understander
import { sendEmail as sendEmailSkill, } from '../skills/emailSkills'; // Added sendEmailSkill, EmailDetails, SendEmailResponse
import { logger } from '../../_utils/logger'; // Assuming logger is available
/**
 * Handles a generic email inquiry: understands the search query using an LLM,
 * finds an email, and performs an action on it (e.g., extracts info, gets metadata).
 */
export async function handleEmailInquiry(request) {
    const { userId, rawEmailSearchQuery, actionRequested, targetEmailId } = request;
    let messageToUser = '';
    try {
        let targetEmail = null;
        // Step 1: Obtain the target email (either by ID or by searching)
        if (targetEmailId) {
            console.log(`Agent: Attempting to read specified email ID ${targetEmailId} for user ${userId}.`);
            const emailDetailsResponse = await readEmail(userId, targetEmailId);
            if (emailDetailsResponse.success && emailDetailsResponse.email) {
                targetEmail = emailDetailsResponse.email;
            }
            else {
                messageToUser = `Sorry, I couldn't read the details for email ID ${targetEmailId}. ${emailDetailsResponse.message}`;
                console.log('Agent response: ', messageToUser);
                return messageToUser;
            }
        }
        else {
            // Use LLM to understand the raw search query and convert to StructuredEmailQuery
            console.log(`Agent: Understanding email search query: "${rawEmailSearchQuery}" for user ${userId}`);
            const structuredSearchParams = await understandEmailSearchQueryLLM(rawEmailSearchQuery);
            const gmailQueryString = buildGmailSearchQuery(structuredSearchParams);
            if (!gmailQueryString) {
                // This might happen if LLM returns empty object for a vague query.
                messageToUser =
                    "I couldn't determine specific search criteria from your request. Could you be more precise?";
                console.log('Agent response: ', messageToUser);
                return messageToUser;
            }
            console.log(`Agent: Searching emails for user ${userId} with LLM-derived query: ${gmailQueryString}`);
            const emailsFound = await searchMyEmails(userId, gmailQueryString, 5);
            if (!emailsFound || emailsFound.length === 0) {
                messageToUser =
                    "I couldn't find any emails matching your criteria based on my understanding of your request.";
                console.log('Agent response: ', messageToUser);
                return messageToUser;
            }
            if (emailsFound.length > 1) {
                // Multiple emails found, ask for clarification.
                messageToUser = 'I found a few emails matching your criteria:\n';
                emailsFound.slice(0, 3).forEach((email, index) => {
                    // Show up to 3
                    messageToUser += `${index + 1}. Subject: "${email.subject || 'No Subject'}" (ID: ...${email.id.slice(-6)})\n`;
                });
                if (emailsFound.length > 3) {
                    messageToUser += `And ${emailsFound.length - 3} more.\n`;
                }
                messageToUser +=
                    'Which one are you interested in? You can tell me the number or provide more details to narrow it down.';
                console.log('Agent needs clarification: ', messageToUser);
                // In a full dialogue system, the agent would set a state expecting clarification.
                // For now, returning this message means the current interaction path stops here.
                return messageToUser;
            }
            // Only one email found, or clarification has led to one.
            const singleEmailSummary = emailsFound[0];
            console.log(`Agent: Found email ID ${singleEmailSummary.id}. Subject: "${singleEmailSummary.subject}". Fetching details...`);
            // Voice-friendly update:
            // console.log(`Agent: Found email ID ${singleEmailSummary.id}. Subject: "${singleEmailSummary.subject}". Fetching details...`);
            // Consider a spoken confirmation: sendAgentResponse(userId, `Okay, I found an email titled "${singleEmailSummary.subject}". Let me get the details.`);
            const emailDetailsResponse = await readEmail(userId, singleEmailSummary.id);
            if (emailDetailsResponse.success && emailDetailsResponse.email) {
                targetEmail = emailDetailsResponse.email;
            }
            else {
                messageToUser = `I found an email titled "${singleEmailSummary.subject}", but I'm having trouble loading its full content right now. The error was: ${emailDetailsResponse.message || 'Unknown error'}.`;
                console.log('Agent response: ', messageToUser);
                return messageToUser;
            }
        }
        if (!targetEmail) {
            messageToUser =
                "I couldn't identify a specific email to process with the information provided. Could you try searching again with different terms?";
            console.log('Agent response: ', messageToUser);
            return messageToUser;
        }
        // Step 2: Perform the requested action on the targetEmail
        const emailSubjectForResponse = targetEmail.subject || 'this email'; // Use "this email" if subject is empty for more natural response
        const emailIdShortForResponse = targetEmail.id.slice(-6); // For concise ID reference if needed
        switch (actionRequested.actionType) {
            case 'GET_FULL_CONTENT':
                const bodyPreview = targetEmail.body
                    ? targetEmail.body.length > 200
                        ? targetEmail.body.substring(0, 200) + '...'
                        : targetEmail.body
                    : 'it appears to have no readable body content.';
                messageToUser = `The email titled "${emailSubjectForResponse}" begins with: "${bodyPreview}". Is there a specific part you're interested in, or would you like me to try and find something particular in it?`;
                break;
            case 'GET_SENDER':
                messageToUser = `The sender of "${emailSubjectForResponse}" is: ${targetEmail.sender || 'not specified'}.`;
                break;
            case 'GET_SUBJECT':
                messageToUser = `The subject of the email (ID ending in ...${emailIdShortForResponse}) is: "${targetEmail.subject || 'No Subject'}".`;
                break;
            case 'GET_DATE':
                const dateOptions = {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                    hour: 'numeric',
                    minute: '2-digit',
                };
                const formattedDate = targetEmail.timestamp
                    ? new Date(targetEmail.timestamp).toLocaleDateString(undefined, dateOptions)
                    : 'an unknown date';
                messageToUser = `The email "${emailSubjectForResponse}" was received on ${formattedDate}.`;
                break;
            case 'FIND_SPECIFIC_INFO':
                if (!targetEmail.body) {
                    messageToUser = `The email "${emailSubjectForResponse}" doesn't seem to have any text content for me to analyze for that.`;
                    break;
                }
                const keywordsToExtract = actionRequested.infoKeywords || [];
                const nlQuestion = actionRequested.naturalLanguageQuestion;
                if (keywordsToExtract.length === 0 && !nlQuestion) {
                    messageToUser = `You asked me to find specific information in "${emailSubjectForResponse}", but didn't specify what to look for.`;
                    break;
                }
                // Prefer natural language question if provided to the LLM extractor, otherwise use keywords.
                // The current LLM extractor is designed for keywords, so we'll pass keywords.
                // If a naturalLanguageQuestion was provided, the NLU service should ideally convert it to infoKeywords.
                // For this example, we'll assume infoKeywords is populated correctly by the NLU layer.
                const extractionInputKeywords = keywordsToExtract.length > 0
                    ? keywordsToExtract
                    : nlQuestion
                        ? [nlQuestion]
                        : [];
                if (extractionInputKeywords.length === 0) {
                    messageToUser = `You asked me to find specific information in "${emailSubjectForResponse}", but didn't specify what to look for.`;
                    break;
                }
                const extractedInfo = await extractInformationFromEmailBody(targetEmail.body, extractionInputKeywords);
                let foundAny = false;
                let responseParts = [];
                // Construct a more conversational response
                if (extractionInputKeywords.length === 1) {
                    // Single piece of info requested
                    const singleKeyword = extractionInputKeywords[0];
                    const resultValue = extractedInfo[singleKeyword];
                    if (resultValue) {
                        if (resultValue.startsWith('Keyword "') &&
                            resultValue.endsWith('" found. (Further analysis needed for specific value).')) {
                            messageToUser = `The email "${emailSubjectForResponse}" mentions "${singleKeyword}".`;
                        }
                        else {
                            messageToUser = `Regarding "${singleKeyword}" in the email "${emailSubjectForResponse}", I found: ${resultValue}.`;
                        }
                        foundAny = true;
                    }
                    else {
                        messageToUser = `I checked the email "${emailSubjectForResponse}" for "${singleKeyword}", but I couldn't find that specific information.`;
                    }
                }
                else {
                    // Multiple pieces of info requested
                    responseParts.push(`In the email "${emailSubjectForResponse}":`);
                    for (const keyword of extractionInputKeywords) {
                        const resultValue = extractedInfo[keyword];
                        if (resultValue) {
                            if (resultValue.startsWith('Keyword "') &&
                                resultValue.endsWith('" found. (Further analysis needed for specific value).')) {
                                responseParts.push(`- It mentions "${keyword}".`);
                            }
                            else {
                                responseParts.push(`- For "${keyword}", I found: ${resultValue}.`);
                            }
                            foundAny = true;
                        }
                        else {
                            responseParts.push(`- I couldn't find specific information about "${keyword}".`);
                        }
                    }
                    if (!foundAny) {
                        messageToUser = `I scanned "${emailSubjectForResponse}" for information related to "${extractionInputKeywords.join(', ')}", but couldn't find those specific details.`;
                    }
                    else {
                        messageToUser = responseParts.join('\n');
                    }
                }
                break;
            case 'SUMMARIZE_EMAIL':
                // TODO: Implement LLM-based summarization skill call
                messageToUser = `I can't summarize emails yet, but I found the one titled "${emailSubjectForResponse}".`;
                break;
            default:
                messageToUser = `I found the email "${emailSubjectForResponse}". I'm not sure how to handle the action: ${actionRequested.actionType}.`;
        }
        console.log('Agent final voice-friendlier response: ', messageToUser);
        return messageToUser;
    }
    catch (error) {
        console.error(`Agent: Error in handleFindEmailAndExtractInfo for user ${userId}:`, error);
        messageToUser = `I encountered an issue while processing your request: ${error.message || 'Unknown error'}`;
        // await sendAgentResponse(userId, messageToUser);
        console.log('Agent error response: ', messageToUser);
        return messageToUser;
    }
}
/*
// Example of how this handler might be invoked by the main agent orchestrator
// after NLU processing provides a ParsedNluEmailRequest object.

async function mainAgentLogic(userId: string, parsedNluResult: any) {
    if (parsedNluResult.intent === 'FIND_EMAIL_AND_EXTRACT_CONTRACT_END_DATE') {
        const request: ParsedNluEmailRequest = {
            userId: userId,
            searchParameters: {
                from: parsedNluResult.entities.sender,
                subject: parsedNluResult.entities.subjectKeywords,
                bodyKeywords: parsedNluResult.entities.bodyKeywords,
                // NLU needs to convert "a few months ago" to after/before dates
                after: parsedNluResult.entities.dateRange?.after,
                before: parsedNluResult.entities.dateRange?.before,
            },
            informationToExtract: 'contractEndDate'
        };
        await handleFindEmailAndExtractInfo(request);
    }
}
*/
/**
 * Handles a request to send an email.
 */
export async function handleSendEmailRequest(request) {
    const { userId, emailDetails } = request;
    let messageToUser = '';
    logger.info(`Agent: Attempting to send email for user ${userId} with details:`, emailDetails);
    if (!emailDetails.to ||
        !emailDetails.subject ||
        (!emailDetails.body && !emailDetails.htmlBody)) {
        messageToUser =
            "I'm sorry, but I'm missing some crucial information to send the email. I need at least a recipient, a subject, and a body content.";
        logger.warn(`Agent: Missing details for send email request for user ${userId}. Details:`, emailDetails);
        return messageToUser;
    }
    try {
        const sendResponse = await sendEmailSkill(emailDetails);
        if (sendResponse.success) {
            messageToUser = `Okay, I've sent the email to ${emailDetails.to} with the subject "${emailDetails.subject}".`;
            if (sendResponse.emailId) {
                messageToUser += ` (Message ID: ${sendResponse.emailId})`;
            }
            logger.info(`Agent: Email sent successfully for user ${userId}. Response:`, sendResponse);
        }
        else {
            messageToUser = `I tried to send the email, but something went wrong. ${sendResponse.message || 'An unknown error occurred.'}`;
            logger.error(`Agent: Failed to send email for user ${userId}. Response:`, sendResponse);
        }
    }
    catch (error) {
        logger.error(`Agent: Critical error in handleSendEmailRequest for user ${userId}:`, error);
        messageToUser = `I encountered a critical error while trying to send the email: ${error.message || 'Unknown error'}`;
    }
    return messageToUser;
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZW1haWxfY29tbWFuZF9oYW5kbGVyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZW1haWxfY29tbWFuZF9oYW5kbGVyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sRUFFTCxxQkFBcUIsR0FDdEIsTUFBTSw0QkFBNEIsQ0FBQztBQUNwQyxPQUFPLEVBQ0wsY0FBYyxFQUNkLFNBQVMsR0FHVixNQUFNLHVCQUF1QixDQUFDO0FBQy9CLGtGQUFrRjtBQUNsRiwyREFBMkQ7QUFDM0Qsd0RBQXdEO0FBQ3hELE9BQU8sRUFBRSwrQkFBK0IsRUFBRSxNQUFNLHVCQUF1QixDQUFDO0FBQ3hFLE9BQU8sRUFBRSw2QkFBNkIsRUFBRSxNQUFNLHdDQUF3QyxDQUFDLENBQUMsZ0NBQWdDO0FBRXhILE9BQU8sRUFJTCxTQUFTLElBQUksY0FBYyxHQUc1QixNQUFNLHVCQUF1QixDQUFDLENBQUMsd0RBQXdEO0FBQ3hGLE9BQU8sRUFBRSxNQUFNLEVBQUUsTUFBTSxxQkFBcUIsQ0FBQyxDQUFDLCtCQUErQjtBQWtDN0U7OztHQUdHO0FBQ0gsTUFBTSxDQUFDLEtBQUssVUFBVSxrQkFBa0IsQ0FDdEMsT0FBOEI7SUFFOUIsTUFBTSxFQUFFLE1BQU0sRUFBRSxtQkFBbUIsRUFBRSxlQUFlLEVBQUUsYUFBYSxFQUFFLEdBQ25FLE9BQU8sQ0FBQztJQUNWLElBQUksYUFBYSxHQUFHLEVBQUUsQ0FBQztJQUV2QixJQUFJLENBQUM7UUFDSCxJQUFJLFdBQVcsR0FBaUIsSUFBSSxDQUFDO1FBRXJDLGlFQUFpRTtRQUNqRSxJQUFJLGFBQWEsRUFBRSxDQUFDO1lBQ2xCLE9BQU8sQ0FBQyxHQUFHLENBQ1QsZ0RBQWdELGFBQWEsYUFBYSxNQUFNLEdBQUcsQ0FDcEYsQ0FBQztZQUNGLE1BQU0sb0JBQW9CLEdBQUcsTUFBTSxTQUFTLENBQUMsTUFBTSxFQUFFLGFBQWEsQ0FBQyxDQUFDO1lBQ3BFLElBQUksb0JBQW9CLENBQUMsT0FBTyxJQUFJLG9CQUFvQixDQUFDLEtBQUssRUFBRSxDQUFDO2dCQUMvRCxXQUFXLEdBQUcsb0JBQW9CLENBQUMsS0FBSyxDQUFDO1lBQzNDLENBQUM7aUJBQU0sQ0FBQztnQkFDTixhQUFhLEdBQUcsbURBQW1ELGFBQWEsS0FBSyxvQkFBb0IsQ0FBQyxPQUFPLEVBQUUsQ0FBQztnQkFDcEgsT0FBTyxDQUFDLEdBQUcsQ0FBQyxrQkFBa0IsRUFBRSxhQUFhLENBQUMsQ0FBQztnQkFDL0MsT0FBTyxhQUFhLENBQUM7WUFDdkIsQ0FBQztRQUNILENBQUM7YUFBTSxDQUFDO1lBQ04saUZBQWlGO1lBQ2pGLE9BQU8sQ0FBQyxHQUFHLENBQ1QsNkNBQTZDLG1CQUFtQixjQUFjLE1BQU0sRUFBRSxDQUN2RixDQUFDO1lBQ0YsTUFBTSxzQkFBc0IsR0FDMUIsTUFBTSw2QkFBNkIsQ0FBQyxtQkFBbUIsQ0FBQyxDQUFDO1lBRTNELE1BQU0sZ0JBQWdCLEdBQUcscUJBQXFCLENBQUMsc0JBQXNCLENBQUMsQ0FBQztZQUN2RSxJQUFJLENBQUMsZ0JBQWdCLEVBQUUsQ0FBQztnQkFDdEIsbUVBQW1FO2dCQUNuRSxhQUFhO29CQUNYLDZGQUE2RixDQUFDO2dCQUNoRyxPQUFPLENBQUMsR0FBRyxDQUFDLGtCQUFrQixFQUFFLGFBQWEsQ0FBQyxDQUFDO2dCQUMvQyxPQUFPLGFBQWEsQ0FBQztZQUN2QixDQUFDO1lBQ0QsT0FBTyxDQUFDLEdBQUcsQ0FDVCxvQ0FBb0MsTUFBTSw0QkFBNEIsZ0JBQWdCLEVBQUUsQ0FDekYsQ0FBQztZQUNGLE1BQU0sV0FBVyxHQUFHLE1BQU0sY0FBYyxDQUFDLE1BQU0sRUFBRSxnQkFBZ0IsRUFBRSxDQUFDLENBQUMsQ0FBQztZQUV0RSxJQUFJLENBQUMsV0FBVyxJQUFJLFdBQVcsQ0FBQyxNQUFNLEtBQUssQ0FBQyxFQUFFLENBQUM7Z0JBQzdDLGFBQWE7b0JBQ1gsOEZBQThGLENBQUM7Z0JBQ2pHLE9BQU8sQ0FBQyxHQUFHLENBQUMsa0JBQWtCLEVBQUUsYUFBYSxDQUFDLENBQUM7Z0JBQy9DLE9BQU8sYUFBYSxDQUFDO1lBQ3ZCLENBQUM7WUFFRCxJQUFJLFdBQVcsQ0FBQyxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7Z0JBQzNCLGdEQUFnRDtnQkFDaEQsYUFBYSxHQUFHLGdEQUFnRCxDQUFDO2dCQUNqRSxXQUFXLENBQUMsS0FBSyxDQUFDLENBQUMsRUFBRSxDQUFDLENBQUMsQ0FBQyxPQUFPLENBQUMsQ0FBQyxLQUFLLEVBQUUsS0FBSyxFQUFFLEVBQUU7b0JBQy9DLGVBQWU7b0JBQ2YsYUFBYSxJQUFJLEdBQUcsS0FBSyxHQUFHLENBQUMsZUFBZSxLQUFLLENBQUMsT0FBTyxJQUFJLFlBQVksYUFBYSxLQUFLLENBQUMsRUFBRSxDQUFDLEtBQUssQ0FBQyxDQUFDLENBQUMsQ0FBQyxLQUFLLENBQUM7Z0JBQ2hILENBQUMsQ0FBQyxDQUFDO2dCQUNILElBQUksV0FBVyxDQUFDLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztvQkFDM0IsYUFBYSxJQUFJLE9BQU8sV0FBVyxDQUFDLE1BQU0sR0FBRyxDQUFDLFVBQVUsQ0FBQztnQkFDM0QsQ0FBQztnQkFDRCxhQUFhO29CQUNYLHdHQUF3RyxDQUFDO2dCQUMzRyxPQUFPLENBQUMsR0FBRyxDQUFDLDZCQUE2QixFQUFFLGFBQWEsQ0FBQyxDQUFDO2dCQUMxRCxrRkFBa0Y7Z0JBQ2xGLGlGQUFpRjtnQkFDakYsT0FBTyxhQUFhLENBQUM7WUFDdkIsQ0FBQztZQUVELHlEQUF5RDtZQUN6RCxNQUFNLGtCQUFrQixHQUFHLFdBQVcsQ0FBQyxDQUFDLENBQUMsQ0FBQztZQUMxQyxPQUFPLENBQUMsR0FBRyxDQUNULHlCQUF5QixrQkFBa0IsQ0FBQyxFQUFFLGVBQWUsa0JBQWtCLENBQUMsT0FBTyx3QkFBd0IsQ0FDaEgsQ0FBQztZQUVGLHlCQUF5QjtZQUN6QixnSUFBZ0k7WUFDaEksdUpBQXVKO1lBRXZKLE1BQU0sb0JBQW9CLEdBQUcsTUFBTSxTQUFTLENBQzFDLE1BQU0sRUFDTixrQkFBa0IsQ0FBQyxFQUFFLENBQ3RCLENBQUM7WUFDRixJQUFJLG9CQUFvQixDQUFDLE9BQU8sSUFBSSxvQkFBb0IsQ0FBQyxLQUFLLEVBQUUsQ0FBQztnQkFDL0QsV0FBVyxHQUFHLG9CQUFvQixDQUFDLEtBQUssQ0FBQztZQUMzQyxDQUFDO2lCQUFNLENBQUM7Z0JBQ04sYUFBYSxHQUFHLDRCQUE0QixrQkFBa0IsQ0FBQyxPQUFPLGdGQUFnRixvQkFBb0IsQ0FBQyxPQUFPLElBQUksZUFBZSxHQUFHLENBQUM7Z0JBQ3pNLE9BQU8sQ0FBQyxHQUFHLENBQUMsa0JBQWtCLEVBQUUsYUFBYSxDQUFDLENBQUM7Z0JBQy9DLE9BQU8sYUFBYSxDQUFDO1lBQ3ZCLENBQUM7UUFDSCxDQUFDO1FBRUQsSUFBSSxDQUFDLFdBQVcsRUFBRSxDQUFDO1lBQ2pCLGFBQWE7Z0JBQ1gsb0lBQW9JLENBQUM7WUFDdkksT0FBTyxDQUFDLEdBQUcsQ0FBQyxrQkFBa0IsRUFBRSxhQUFhLENBQUMsQ0FBQztZQUMvQyxPQUFPLGFBQWEsQ0FBQztRQUN2QixDQUFDO1FBRUQsMERBQTBEO1FBQzFELE1BQU0sdUJBQXVCLEdBQUcsV0FBVyxDQUFDLE9BQU8sSUFBSSxZQUFZLENBQUMsQ0FBQyxpRUFBaUU7UUFDdEksTUFBTSx1QkFBdUIsR0FBRyxXQUFXLENBQUMsRUFBRSxDQUFDLEtBQUssQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMscUNBQXFDO1FBRS9GLFFBQVEsZUFBZSxDQUFDLFVBQVUsRUFBRSxDQUFDO1lBQ25DLEtBQUssa0JBQWtCO2dCQUNyQixNQUFNLFdBQVcsR0FBRyxXQUFXLENBQUMsSUFBSTtvQkFDbEMsQ0FBQyxDQUFDLFdBQVcsQ0FBQyxJQUFJLENBQUMsTUFBTSxHQUFHLEdBQUc7d0JBQzdCLENBQUMsQ0FBQyxXQUFXLENBQUMsSUFBSSxDQUFDLFNBQVMsQ0FBQyxDQUFDLEVBQUUsR0FBRyxDQUFDLEdBQUcsS0FBSzt3QkFDNUMsQ0FBQyxDQUFDLFdBQVcsQ0FBQyxJQUFJO29CQUNwQixDQUFDLENBQUMsOENBQThDLENBQUM7Z0JBQ25ELGFBQWEsR0FBRyxxQkFBcUIsdUJBQXVCLG1CQUFtQixXQUFXLG9IQUFvSCxDQUFDO2dCQUMvTSxNQUFNO1lBQ1IsS0FBSyxZQUFZO2dCQUNmLGFBQWEsR0FBRyxrQkFBa0IsdUJBQXVCLFNBQVMsV0FBVyxDQUFDLE1BQU0sSUFBSSxlQUFlLEdBQUcsQ0FBQztnQkFDM0csTUFBTTtZQUNSLEtBQUssYUFBYTtnQkFDaEIsYUFBYSxHQUFHLDZDQUE2Qyx1QkFBdUIsVUFBVSxXQUFXLENBQUMsT0FBTyxJQUFJLFlBQVksSUFBSSxDQUFDO2dCQUN0SSxNQUFNO1lBQ1IsS0FBSyxVQUFVO2dCQUNiLE1BQU0sV0FBVyxHQUErQjtvQkFDOUMsSUFBSSxFQUFFLFNBQVM7b0JBQ2YsS0FBSyxFQUFFLE1BQU07b0JBQ2IsR0FBRyxFQUFFLFNBQVM7b0JBQ2QsSUFBSSxFQUFFLFNBQVM7b0JBQ2YsTUFBTSxFQUFFLFNBQVM7aUJBQ2xCLENBQUM7Z0JBQ0YsTUFBTSxhQUFhLEdBQUcsV0FBVyxDQUFDLFNBQVM7b0JBQ3pDLENBQUMsQ0FBQyxJQUFJLElBQUksQ0FBQyxXQUFXLENBQUMsU0FBUyxDQUFDLENBQUMsa0JBQWtCLENBQ2hELFNBQVMsRUFDVCxXQUFXLENBQ1o7b0JBQ0gsQ0FBQyxDQUFDLGlCQUFpQixDQUFDO2dCQUN0QixhQUFhLEdBQUcsY0FBYyx1QkFBdUIscUJBQXFCLGFBQWEsR0FBRyxDQUFDO2dCQUMzRixNQUFNO1lBQ1IsS0FBSyxvQkFBb0I7Z0JBQ3ZCLElBQUksQ0FBQyxXQUFXLENBQUMsSUFBSSxFQUFFLENBQUM7b0JBQ3RCLGFBQWEsR0FBRyxjQUFjLHVCQUF1QixxRUFBcUUsQ0FBQztvQkFDM0gsTUFBTTtnQkFDUixDQUFDO2dCQUNELE1BQU0saUJBQWlCLEdBQUcsZUFBZSxDQUFDLFlBQVksSUFBSSxFQUFFLENBQUM7Z0JBQzdELE1BQU0sVUFBVSxHQUFHLGVBQWUsQ0FBQyx1QkFBdUIsQ0FBQztnQkFFM0QsSUFBSSxpQkFBaUIsQ0FBQyxNQUFNLEtBQUssQ0FBQyxJQUFJLENBQUMsVUFBVSxFQUFFLENBQUM7b0JBQ2xELGFBQWEsR0FBRyxpREFBaUQsdUJBQXVCLHlDQUF5QyxDQUFDO29CQUNsSSxNQUFNO2dCQUNSLENBQUM7Z0JBRUQsNkZBQTZGO2dCQUM3Riw4RUFBOEU7Z0JBQzlFLHdHQUF3RztnQkFDeEcsdUZBQXVGO2dCQUV2RixNQUFNLHVCQUF1QixHQUMzQixpQkFBaUIsQ0FBQyxNQUFNLEdBQUcsQ0FBQztvQkFDMUIsQ0FBQyxDQUFDLGlCQUFpQjtvQkFDbkIsQ0FBQyxDQUFDLFVBQVU7d0JBQ1YsQ0FBQyxDQUFDLENBQUMsVUFBVSxDQUFDO3dCQUNkLENBQUMsQ0FBQyxFQUFFLENBQUM7Z0JBRVgsSUFBSSx1QkFBdUIsQ0FBQyxNQUFNLEtBQUssQ0FBQyxFQUFFLENBQUM7b0JBQ3pDLGFBQWEsR0FBRyxpREFBaUQsdUJBQXVCLHlDQUF5QyxDQUFDO29CQUNsSSxNQUFNO2dCQUNSLENBQUM7Z0JBRUQsTUFBTSxhQUFhLEdBQUcsTUFBTSwrQkFBK0IsQ0FDekQsV0FBVyxDQUFDLElBQUksRUFDaEIsdUJBQXVCLENBQ3hCLENBQUM7Z0JBQ0YsSUFBSSxRQUFRLEdBQUcsS0FBSyxDQUFDO2dCQUNyQixJQUFJLGFBQWEsR0FBYSxFQUFFLENBQUM7Z0JBRWpDLDJDQUEyQztnQkFDM0MsSUFBSSx1QkFBdUIsQ0FBQyxNQUFNLEtBQUssQ0FBQyxFQUFFLENBQUM7b0JBQ3pDLGlDQUFpQztvQkFDakMsTUFBTSxhQUFhLEdBQUcsdUJBQXVCLENBQUMsQ0FBQyxDQUFDLENBQUM7b0JBQ2pELE1BQU0sV0FBVyxHQUFHLGFBQWEsQ0FBQyxhQUFhLENBQUMsQ0FBQztvQkFDakQsSUFBSSxXQUFXLEVBQUUsQ0FBQzt3QkFDaEIsSUFDRSxXQUFXLENBQUMsVUFBVSxDQUFDLFdBQVcsQ0FBQzs0QkFDbkMsV0FBVyxDQUFDLFFBQVEsQ0FDbEIsd0RBQXdELENBQ3pELEVBQ0QsQ0FBQzs0QkFDRCxhQUFhLEdBQUcsY0FBYyx1QkFBdUIsZUFBZSxhQUFhLElBQUksQ0FBQzt3QkFDeEYsQ0FBQzs2QkFBTSxDQUFDOzRCQUNOLGFBQWEsR0FBRyxjQUFjLGFBQWEsbUJBQW1CLHVCQUF1QixlQUFlLFdBQVcsR0FBRyxDQUFDO3dCQUNySCxDQUFDO3dCQUNELFFBQVEsR0FBRyxJQUFJLENBQUM7b0JBQ2xCLENBQUM7eUJBQU0sQ0FBQzt3QkFDTixhQUFhLEdBQUcsd0JBQXdCLHVCQUF1QixVQUFVLGFBQWEsbURBQW1ELENBQUM7b0JBQzVJLENBQUM7Z0JBQ0gsQ0FBQztxQkFBTSxDQUFDO29CQUNOLG9DQUFvQztvQkFDcEMsYUFBYSxDQUFDLElBQUksQ0FBQyxpQkFBaUIsdUJBQXVCLElBQUksQ0FBQyxDQUFDO29CQUNqRSxLQUFLLE1BQU0sT0FBTyxJQUFJLHVCQUF1QixFQUFFLENBQUM7d0JBQzlDLE1BQU0sV0FBVyxHQUFHLGFBQWEsQ0FBQyxPQUFPLENBQUMsQ0FBQzt3QkFDM0MsSUFBSSxXQUFXLEVBQUUsQ0FBQzs0QkFDaEIsSUFDRSxXQUFXLENBQUMsVUFBVSxDQUFDLFdBQVcsQ0FBQztnQ0FDbkMsV0FBVyxDQUFDLFFBQVEsQ0FDbEIsd0RBQXdELENBQ3pELEVBQ0QsQ0FBQztnQ0FDRCxhQUFhLENBQUMsSUFBSSxDQUFDLGtCQUFrQixPQUFPLElBQUksQ0FBQyxDQUFDOzRCQUNwRCxDQUFDO2lDQUFNLENBQUM7Z0NBQ04sYUFBYSxDQUFDLElBQUksQ0FDaEIsVUFBVSxPQUFPLGVBQWUsV0FBVyxHQUFHLENBQy9DLENBQUM7NEJBQ0osQ0FBQzs0QkFDRCxRQUFRLEdBQUcsSUFBSSxDQUFDO3dCQUNsQixDQUFDOzZCQUFNLENBQUM7NEJBQ04sYUFBYSxDQUFDLElBQUksQ0FDaEIsaURBQWlELE9BQU8sSUFBSSxDQUM3RCxDQUFDO3dCQUNKLENBQUM7b0JBQ0gsQ0FBQztvQkFDRCxJQUFJLENBQUMsUUFBUSxFQUFFLENBQUM7d0JBQ2QsYUFBYSxHQUFHLGNBQWMsdUJBQXVCLGlDQUFpQyx1QkFBdUIsQ0FBQyxJQUFJLENBQUMsSUFBSSxDQUFDLDhDQUE4QyxDQUFDO29CQUN6SyxDQUFDO3lCQUFNLENBQUM7d0JBQ04sYUFBYSxHQUFHLGFBQWEsQ0FBQyxJQUFJLENBQUMsSUFBSSxDQUFDLENBQUM7b0JBQzNDLENBQUM7Z0JBQ0gsQ0FBQztnQkFDRCxNQUFNO1lBQ1IsS0FBSyxpQkFBaUI7Z0JBQ3BCLHFEQUFxRDtnQkFDckQsYUFBYSxHQUFHLDZEQUE2RCx1QkFBdUIsSUFBSSxDQUFDO2dCQUN6RyxNQUFNO1lBQ1I7Z0JBQ0UsYUFBYSxHQUFHLHNCQUFzQix1QkFBdUIsNkNBQTZDLGVBQWUsQ0FBQyxVQUFVLEdBQUcsQ0FBQztRQUM1SSxDQUFDO1FBRUQsT0FBTyxDQUFDLEdBQUcsQ0FBQyx5Q0FBeUMsRUFBRSxhQUFhLENBQUMsQ0FBQztRQUN0RSxPQUFPLGFBQWEsQ0FBQztJQUN2QixDQUFDO0lBQUMsT0FBTyxLQUFVLEVBQUUsQ0FBQztRQUNwQixPQUFPLENBQUMsS0FBSyxDQUNYLDBEQUEwRCxNQUFNLEdBQUcsRUFDbkUsS0FBSyxDQUNOLENBQUM7UUFDRixhQUFhLEdBQUcseURBQXlELEtBQUssQ0FBQyxPQUFPLElBQUksZUFBZSxFQUFFLENBQUM7UUFDNUcsa0RBQWtEO1FBQ2xELE9BQU8sQ0FBQyxHQUFHLENBQUMsd0JBQXdCLEVBQUUsYUFBYSxDQUFDLENBQUM7UUFDckQsT0FBTyxhQUFhLENBQUM7SUFDdkIsQ0FBQztBQUNILENBQUM7QUFFRDs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0VBcUJFO0FBRUY7O0dBRUc7QUFDSCxNQUFNLENBQUMsS0FBSyxVQUFVLHNCQUFzQixDQUMxQyxPQUFrQztJQUVsQyxNQUFNLEVBQUUsTUFBTSxFQUFFLFlBQVksRUFBRSxHQUFHLE9BQU8sQ0FBQztJQUN6QyxJQUFJLGFBQWEsR0FBRyxFQUFFLENBQUM7SUFFdkIsTUFBTSxDQUFDLElBQUksQ0FDVCw0Q0FBNEMsTUFBTSxnQkFBZ0IsRUFDbEUsWUFBWSxDQUNiLENBQUM7SUFFRixJQUNFLENBQUMsWUFBWSxDQUFDLEVBQUU7UUFDaEIsQ0FBQyxZQUFZLENBQUMsT0FBTztRQUNyQixDQUFDLENBQUMsWUFBWSxDQUFDLElBQUksSUFBSSxDQUFDLFlBQVksQ0FBQyxRQUFRLENBQUMsRUFDOUMsQ0FBQztRQUNELGFBQWE7WUFDWCxvSUFBb0ksQ0FBQztRQUN2SSxNQUFNLENBQUMsSUFBSSxDQUNULDBEQUEwRCxNQUFNLFlBQVksRUFDNUUsWUFBWSxDQUNiLENBQUM7UUFDRixPQUFPLGFBQWEsQ0FBQztJQUN2QixDQUFDO0lBRUQsSUFBSSxDQUFDO1FBQ0gsTUFBTSxZQUFZLEdBQXNCLE1BQU0sY0FBYyxDQUFDLFlBQVksQ0FBQyxDQUFDO1FBRTNFLElBQUksWUFBWSxDQUFDLE9BQU8sRUFBRSxDQUFDO1lBQ3pCLGFBQWEsR0FBRyxnQ0FBZ0MsWUFBWSxDQUFDLEVBQUUsc0JBQXNCLFlBQVksQ0FBQyxPQUFPLElBQUksQ0FBQztZQUM5RyxJQUFJLFlBQVksQ0FBQyxPQUFPLEVBQUUsQ0FBQztnQkFDekIsYUFBYSxJQUFJLGlCQUFpQixZQUFZLENBQUMsT0FBTyxHQUFHLENBQUM7WUFDNUQsQ0FBQztZQUNELE1BQU0sQ0FBQyxJQUFJLENBQ1QsMkNBQTJDLE1BQU0sYUFBYSxFQUM5RCxZQUFZLENBQ2IsQ0FBQztRQUNKLENBQUM7YUFBTSxDQUFDO1lBQ04sYUFBYSxHQUFHLHdEQUF3RCxZQUFZLENBQUMsT0FBTyxJQUFJLDRCQUE0QixFQUFFLENBQUM7WUFDL0gsTUFBTSxDQUFDLEtBQUssQ0FDVix3Q0FBd0MsTUFBTSxhQUFhLEVBQzNELFlBQVksQ0FDYixDQUFDO1FBQ0osQ0FBQztJQUNILENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLE1BQU0sQ0FBQyxLQUFLLENBQ1YsNERBQTRELE1BQU0sR0FBRyxFQUNyRSxLQUFLLENBQ04sQ0FBQztRQUNGLGFBQWEsR0FBRyxrRUFBa0UsS0FBSyxDQUFDLE9BQU8sSUFBSSxlQUFlLEVBQUUsQ0FBQztJQUN2SCxDQUFDO0lBRUQsT0FBTyxhQUFhLENBQUM7QUFDdkIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7XG4gIFN0cnVjdHVyZWRFbWFpbFF1ZXJ5LFxuICBidWlsZEdtYWlsU2VhcmNoUXVlcnksXG59IGZyb20gJy4uL3NraWxscy9ubHVfZW1haWxfaGVscGVyJztcbmltcG9ydCB7XG4gIHNlYXJjaE15RW1haWxzLFxuICByZWFkRW1haWwsXG4gIGV4dHJhY3RDb250cmFjdEVuZERhdGUsXG4gIEVtYWlsLFxufSBmcm9tICcuLi9za2lsbHMvZW1haWxTa2lsbHMnO1xuLy8gQXNzdW1lIGEgd2F5IHRvIHNlbmQgbWVzc2FnZXMgYmFjayB0byB0aGUgdXNlciwgZS5nLiwgdGhyb3VnaCBhIGNoYXQgaW50ZXJmYWNlLlxuLy8gVGhpcyBpcyBhIHBsYWNlaG9sZGVyIGZvciB0aGUgYWN0dWFsIG1lc3NhZ2luZyBmdW5jdGlvbi5cbi8vIGltcG9ydCB7IHNlbmRBZ2VudFJlc3BvbnNlIH0gZnJvbSAnLi4vYWdlbnRSZXNwb25zZSc7XG5pbXBvcnQgeyBleHRyYWN0SW5mb3JtYXRpb25Gcm9tRW1haWxCb2R5IH0gZnJvbSAnLi4vc2tpbGxzL2VtYWlsU2tpbGxzJztcbmltcG9ydCB7IHVuZGVyc3RhbmRFbWFpbFNlYXJjaFF1ZXJ5TExNIH0gZnJvbSAnLi4vc2tpbGxzL2xsbV9lbWFpbF9xdWVyeV91bmRlcnN0YW5kZXInOyAvLyBJbXBvcnQgTExNIHF1ZXJ5IHVuZGVyc3RhbmRlclxuXG5pbXBvcnQge1xuICBzZWFyY2hNeUVtYWlscyxcbiAgcmVhZEVtYWlsLFxuICBFbWFpbCxcbiAgc2VuZEVtYWlsIGFzIHNlbmRFbWFpbFNraWxsLFxuICBFbWFpbERldGFpbHMsXG4gIFNlbmRFbWFpbFJlc3BvbnNlLFxufSBmcm9tICcuLi9za2lsbHMvZW1haWxTa2lsbHMnOyAvLyBBZGRlZCBzZW5kRW1haWxTa2lsbCwgRW1haWxEZXRhaWxzLCBTZW5kRW1haWxSZXNwb25zZVxuaW1wb3J0IHsgbG9nZ2VyIH0gZnJvbSAnLi4vLi4vX3V0aWxzL2xvZ2dlcic7IC8vIEFzc3VtaW5nIGxvZ2dlciBpcyBhdmFpbGFibGVcblxuLy8gRGVmaW5lIHRoZSB0eXBlcyBmb3Igd2hhdCB0aGUgTkxVIHNlcnZpY2Ugc2hvdWxkIHByb3ZpZGUgdG8gdGhpcyBoYW5kbGVyXG5leHBvcnQgdHlwZSBFbWFpbEFjdGlvblR5cGUgPVxuICB8ICdHRVRfRlVMTF9DT05URU5UJ1xuICB8ICdHRVRfU0VOREVSJ1xuICB8ICdHRVRfU1VCSkVDVCdcbiAgfCAnR0VUX0RBVEUnXG4gIHwgJ0ZJTkRfU1BFQ0lGSUNfSU5GTycgLy8gRm9yIHRhcmdldGVkIGV4dHJhY3Rpb25cbiAgfCAnU1VNTUFSSVpFX0VNQUlMJyAvLyBGdXR1cmUgY2FwYWJpbGl0eVxuICB8ICdTRU5EX0VNQUlMJzsgLy8gTmV3IGFjdGlvbiB0eXBlXG5cbmV4cG9ydCBpbnRlcmZhY2UgRW1haWxBY3Rpb25SZXF1ZXN0IHtcbiAgYWN0aW9uVHlwZTogRW1haWxBY3Rpb25UeXBlO1xuICBpbmZvS2V5d29yZHM/OiBzdHJpbmdbXTsgLy8gVXNlZCB3aGVuIGFjdGlvblR5cGUgaXMgRklORF9TUEVDSUZJQ19JTkZPXG4gIC8vIENvdWxkIGFsc28gaW5jbHVkZSBhIG5hdHVyYWwgbGFuZ3VhZ2UgcXVlc3Rpb24gZm9yIEZJTkRfU1BFQ0lGSUNfSU5GTyBpZiBMTE0gZXh0cmFjdG9yIHN1cHBvcnRzIGl0XG4gIG5hdHVyYWxMYW5ndWFnZVF1ZXN0aW9uPzogc3RyaW5nO1xufVxuXG4vLyBUaGlzIHJlcXVlc3Qgbm93IHRha2VzIHRoZSByYXcgdXNlciBxdWVyeSBmb3IgZW1haWxzLFxuLy8gd2hpY2ggd2lsbCBiZSBwcm9jZXNzZWQgYnkgdGhlIExMTSBxdWVyeSB1bmRlcnN0YW5kZXIuXG5leHBvcnQgaW50ZXJmYWNlIFBhcnNlZE5sdUVtYWlsUmVxdWVzdCB7XG4gIHVzZXJJZDogc3RyaW5nO1xuICByYXdFbWFpbFNlYXJjaFF1ZXJ5OiBzdHJpbmc7IC8vIGUuZy4sIFwiZW1haWxzIGZyb20gSmFuZSBhYm91dCBRMyByZXBvcnQgbGFzdCB3ZWVrXCJcbiAgYWN0aW9uUmVxdWVzdGVkOiBFbWFpbEFjdGlvblJlcXVlc3Q7XG4gIHRhcmdldEVtYWlsSWQ/OiBzdHJpbmc7IC8vIE9wdGlvbmFsOiBpZiBOTFUgaWRlbnRpZmllZCBhIHNwZWNpZmljIGVtYWlsIElEIGRpcmVjdGx5XG59XG5cbi8vIEludGVyZmFjZSBmb3IgYSBcInNlbmQgZW1haWxcIiByZXF1ZXN0IGZyb20gTkxVXG5leHBvcnQgaW50ZXJmYWNlIFBhcnNlZE5sdVNlbmRFbWFpbFJlcXVlc3Qge1xuICB1c2VySWQ6IHN0cmluZztcbiAgZW1haWxEZXRhaWxzOiBFbWFpbERldGFpbHM7IC8vIFJldXNpbmcgRW1haWxEZXRhaWxzIGZyb20gZW1haWxTa2lsbHMudHNcbn1cblxuLyoqXG4gKiBIYW5kbGVzIGEgZ2VuZXJpYyBlbWFpbCBpbnF1aXJ5OiB1bmRlcnN0YW5kcyB0aGUgc2VhcmNoIHF1ZXJ5IHVzaW5nIGFuIExMTSxcbiAqIGZpbmRzIGFuIGVtYWlsLCBhbmQgcGVyZm9ybXMgYW4gYWN0aW9uIG9uIGl0IChlLmcuLCBleHRyYWN0cyBpbmZvLCBnZXRzIG1ldGFkYXRhKS5cbiAqL1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZUVtYWlsSW5xdWlyeShcbiAgcmVxdWVzdDogUGFyc2VkTmx1RW1haWxSZXF1ZXN0XG4pOiBQcm9taXNlPHN0cmluZz4ge1xuICBjb25zdCB7IHVzZXJJZCwgcmF3RW1haWxTZWFyY2hRdWVyeSwgYWN0aW9uUmVxdWVzdGVkLCB0YXJnZXRFbWFpbElkIH0gPVxuICAgIHJlcXVlc3Q7XG4gIGxldCBtZXNzYWdlVG9Vc2VyID0gJyc7XG5cbiAgdHJ5IHtcbiAgICBsZXQgdGFyZ2V0RW1haWw6IEVtYWlsIHwgbnVsbCA9IG51bGw7XG5cbiAgICAvLyBTdGVwIDE6IE9idGFpbiB0aGUgdGFyZ2V0IGVtYWlsIChlaXRoZXIgYnkgSUQgb3IgYnkgc2VhcmNoaW5nKVxuICAgIGlmICh0YXJnZXRFbWFpbElkKSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYEFnZW50OiBBdHRlbXB0aW5nIHRvIHJlYWQgc3BlY2lmaWVkIGVtYWlsIElEICR7dGFyZ2V0RW1haWxJZH0gZm9yIHVzZXIgJHt1c2VySWR9LmBcbiAgICAgICk7XG4gICAgICBjb25zdCBlbWFpbERldGFpbHNSZXNwb25zZSA9IGF3YWl0IHJlYWRFbWFpbCh1c2VySWQsIHRhcmdldEVtYWlsSWQpO1xuICAgICAgaWYgKGVtYWlsRGV0YWlsc1Jlc3BvbnNlLnN1Y2Nlc3MgJiYgZW1haWxEZXRhaWxzUmVzcG9uc2UuZW1haWwpIHtcbiAgICAgICAgdGFyZ2V0RW1haWwgPSBlbWFpbERldGFpbHNSZXNwb25zZS5lbWFpbDtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIG1lc3NhZ2VUb1VzZXIgPSBgU29ycnksIEkgY291bGRuJ3QgcmVhZCB0aGUgZGV0YWlscyBmb3IgZW1haWwgSUQgJHt0YXJnZXRFbWFpbElkfS4gJHtlbWFpbERldGFpbHNSZXNwb25zZS5tZXNzYWdlfWA7XG4gICAgICAgIGNvbnNvbGUubG9nKCdBZ2VudCByZXNwb25zZTogJywgbWVzc2FnZVRvVXNlcik7XG4gICAgICAgIHJldHVybiBtZXNzYWdlVG9Vc2VyO1xuICAgICAgfVxuICAgIH0gZWxzZSB7XG4gICAgICAvLyBVc2UgTExNIHRvIHVuZGVyc3RhbmQgdGhlIHJhdyBzZWFyY2ggcXVlcnkgYW5kIGNvbnZlcnQgdG8gU3RydWN0dXJlZEVtYWlsUXVlcnlcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBgQWdlbnQ6IFVuZGVyc3RhbmRpbmcgZW1haWwgc2VhcmNoIHF1ZXJ5OiBcIiR7cmF3RW1haWxTZWFyY2hRdWVyeX1cIiBmb3IgdXNlciAke3VzZXJJZH1gXG4gICAgICApO1xuICAgICAgY29uc3Qgc3RydWN0dXJlZFNlYXJjaFBhcmFtcyA9XG4gICAgICAgIGF3YWl0IHVuZGVyc3RhbmRFbWFpbFNlYXJjaFF1ZXJ5TExNKHJhd0VtYWlsU2VhcmNoUXVlcnkpO1xuXG4gICAgICBjb25zdCBnbWFpbFF1ZXJ5U3RyaW5nID0gYnVpbGRHbWFpbFNlYXJjaFF1ZXJ5KHN0cnVjdHVyZWRTZWFyY2hQYXJhbXMpO1xuICAgICAgaWYgKCFnbWFpbFF1ZXJ5U3RyaW5nKSB7XG4gICAgICAgIC8vIFRoaXMgbWlnaHQgaGFwcGVuIGlmIExMTSByZXR1cm5zIGVtcHR5IG9iamVjdCBmb3IgYSB2YWd1ZSBxdWVyeS5cbiAgICAgICAgbWVzc2FnZVRvVXNlciA9XG4gICAgICAgICAgXCJJIGNvdWxkbid0IGRldGVybWluZSBzcGVjaWZpYyBzZWFyY2ggY3JpdGVyaWEgZnJvbSB5b3VyIHJlcXVlc3QuIENvdWxkIHlvdSBiZSBtb3JlIHByZWNpc2U/XCI7XG4gICAgICAgIGNvbnNvbGUubG9nKCdBZ2VudCByZXNwb25zZTogJywgbWVzc2FnZVRvVXNlcik7XG4gICAgICAgIHJldHVybiBtZXNzYWdlVG9Vc2VyO1xuICAgICAgfVxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGBBZ2VudDogU2VhcmNoaW5nIGVtYWlscyBmb3IgdXNlciAke3VzZXJJZH0gd2l0aCBMTE0tZGVyaXZlZCBxdWVyeTogJHtnbWFpbFF1ZXJ5U3RyaW5nfWBcbiAgICAgICk7XG4gICAgICBjb25zdCBlbWFpbHNGb3VuZCA9IGF3YWl0IHNlYXJjaE15RW1haWxzKHVzZXJJZCwgZ21haWxRdWVyeVN0cmluZywgNSk7XG5cbiAgICAgIGlmICghZW1haWxzRm91bmQgfHwgZW1haWxzRm91bmQubGVuZ3RoID09PSAwKSB7XG4gICAgICAgIG1lc3NhZ2VUb1VzZXIgPVxuICAgICAgICAgIFwiSSBjb3VsZG4ndCBmaW5kIGFueSBlbWFpbHMgbWF0Y2hpbmcgeW91ciBjcml0ZXJpYSBiYXNlZCBvbiBteSB1bmRlcnN0YW5kaW5nIG9mIHlvdXIgcmVxdWVzdC5cIjtcbiAgICAgICAgY29uc29sZS5sb2coJ0FnZW50IHJlc3BvbnNlOiAnLCBtZXNzYWdlVG9Vc2VyKTtcbiAgICAgICAgcmV0dXJuIG1lc3NhZ2VUb1VzZXI7XG4gICAgICB9XG5cbiAgICAgIGlmIChlbWFpbHNGb3VuZC5sZW5ndGggPiAxKSB7XG4gICAgICAgIC8vIE11bHRpcGxlIGVtYWlscyBmb3VuZCwgYXNrIGZvciBjbGFyaWZpY2F0aW9uLlxuICAgICAgICBtZXNzYWdlVG9Vc2VyID0gJ0kgZm91bmQgYSBmZXcgZW1haWxzIG1hdGNoaW5nIHlvdXIgY3JpdGVyaWE6XFxuJztcbiAgICAgICAgZW1haWxzRm91bmQuc2xpY2UoMCwgMykuZm9yRWFjaCgoZW1haWwsIGluZGV4KSA9PiB7XG4gICAgICAgICAgLy8gU2hvdyB1cCB0byAzXG4gICAgICAgICAgbWVzc2FnZVRvVXNlciArPSBgJHtpbmRleCArIDF9LiBTdWJqZWN0OiBcIiR7ZW1haWwuc3ViamVjdCB8fCAnTm8gU3ViamVjdCd9XCIgKElEOiAuLi4ke2VtYWlsLmlkLnNsaWNlKC02KX0pXFxuYDtcbiAgICAgICAgfSk7XG4gICAgICAgIGlmIChlbWFpbHNGb3VuZC5sZW5ndGggPiAzKSB7XG4gICAgICAgICAgbWVzc2FnZVRvVXNlciArPSBgQW5kICR7ZW1haWxzRm91bmQubGVuZ3RoIC0gM30gbW9yZS5cXG5gO1xuICAgICAgICB9XG4gICAgICAgIG1lc3NhZ2VUb1VzZXIgKz1cbiAgICAgICAgICAnV2hpY2ggb25lIGFyZSB5b3UgaW50ZXJlc3RlZCBpbj8gWW91IGNhbiB0ZWxsIG1lIHRoZSBudW1iZXIgb3IgcHJvdmlkZSBtb3JlIGRldGFpbHMgdG8gbmFycm93IGl0IGRvd24uJztcbiAgICAgICAgY29uc29sZS5sb2coJ0FnZW50IG5lZWRzIGNsYXJpZmljYXRpb246ICcsIG1lc3NhZ2VUb1VzZXIpO1xuICAgICAgICAvLyBJbiBhIGZ1bGwgZGlhbG9ndWUgc3lzdGVtLCB0aGUgYWdlbnQgd291bGQgc2V0IGEgc3RhdGUgZXhwZWN0aW5nIGNsYXJpZmljYXRpb24uXG4gICAgICAgIC8vIEZvciBub3csIHJldHVybmluZyB0aGlzIG1lc3NhZ2UgbWVhbnMgdGhlIGN1cnJlbnQgaW50ZXJhY3Rpb24gcGF0aCBzdG9wcyBoZXJlLlxuICAgICAgICByZXR1cm4gbWVzc2FnZVRvVXNlcjtcbiAgICAgIH1cblxuICAgICAgLy8gT25seSBvbmUgZW1haWwgZm91bmQsIG9yIGNsYXJpZmljYXRpb24gaGFzIGxlZCB0byBvbmUuXG4gICAgICBjb25zdCBzaW5nbGVFbWFpbFN1bW1hcnkgPSBlbWFpbHNGb3VuZFswXTtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBgQWdlbnQ6IEZvdW5kIGVtYWlsIElEICR7c2luZ2xlRW1haWxTdW1tYXJ5LmlkfS4gU3ViamVjdDogXCIke3NpbmdsZUVtYWlsU3VtbWFyeS5zdWJqZWN0fVwiLiBGZXRjaGluZyBkZXRhaWxzLi4uYFxuICAgICAgKTtcblxuICAgICAgLy8gVm9pY2UtZnJpZW5kbHkgdXBkYXRlOlxuICAgICAgLy8gY29uc29sZS5sb2coYEFnZW50OiBGb3VuZCBlbWFpbCBJRCAke3NpbmdsZUVtYWlsU3VtbWFyeS5pZH0uIFN1YmplY3Q6IFwiJHtzaW5nbGVFbWFpbFN1bW1hcnkuc3ViamVjdH1cIi4gRmV0Y2hpbmcgZGV0YWlscy4uLmApO1xuICAgICAgLy8gQ29uc2lkZXIgYSBzcG9rZW4gY29uZmlybWF0aW9uOiBzZW5kQWdlbnRSZXNwb25zZSh1c2VySWQsIGBPa2F5LCBJIGZvdW5kIGFuIGVtYWlsIHRpdGxlZCBcIiR7c2luZ2xlRW1haWxTdW1tYXJ5LnN1YmplY3R9XCIuIExldCBtZSBnZXQgdGhlIGRldGFpbHMuYCk7XG5cbiAgICAgIGNvbnN0IGVtYWlsRGV0YWlsc1Jlc3BvbnNlID0gYXdhaXQgcmVhZEVtYWlsKFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIHNpbmdsZUVtYWlsU3VtbWFyeS5pZFxuICAgICAgKTtcbiAgICAgIGlmIChlbWFpbERldGFpbHNSZXNwb25zZS5zdWNjZXNzICYmIGVtYWlsRGV0YWlsc1Jlc3BvbnNlLmVtYWlsKSB7XG4gICAgICAgIHRhcmdldEVtYWlsID0gZW1haWxEZXRhaWxzUmVzcG9uc2UuZW1haWw7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBtZXNzYWdlVG9Vc2VyID0gYEkgZm91bmQgYW4gZW1haWwgdGl0bGVkIFwiJHtzaW5nbGVFbWFpbFN1bW1hcnkuc3ViamVjdH1cIiwgYnV0IEknbSBoYXZpbmcgdHJvdWJsZSBsb2FkaW5nIGl0cyBmdWxsIGNvbnRlbnQgcmlnaHQgbm93LiBUaGUgZXJyb3Igd2FzOiAke2VtYWlsRGV0YWlsc1Jlc3BvbnNlLm1lc3NhZ2UgfHwgJ1Vua25vd24gZXJyb3InfS5gO1xuICAgICAgICBjb25zb2xlLmxvZygnQWdlbnQgcmVzcG9uc2U6ICcsIG1lc3NhZ2VUb1VzZXIpO1xuICAgICAgICByZXR1cm4gbWVzc2FnZVRvVXNlcjtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAoIXRhcmdldEVtYWlsKSB7XG4gICAgICBtZXNzYWdlVG9Vc2VyID1cbiAgICAgICAgXCJJIGNvdWxkbid0IGlkZW50aWZ5IGEgc3BlY2lmaWMgZW1haWwgdG8gcHJvY2VzcyB3aXRoIHRoZSBpbmZvcm1hdGlvbiBwcm92aWRlZC4gQ291bGQgeW91IHRyeSBzZWFyY2hpbmcgYWdhaW4gd2l0aCBkaWZmZXJlbnQgdGVybXM/XCI7XG4gICAgICBjb25zb2xlLmxvZygnQWdlbnQgcmVzcG9uc2U6ICcsIG1lc3NhZ2VUb1VzZXIpO1xuICAgICAgcmV0dXJuIG1lc3NhZ2VUb1VzZXI7XG4gICAgfVxuXG4gICAgLy8gU3RlcCAyOiBQZXJmb3JtIHRoZSByZXF1ZXN0ZWQgYWN0aW9uIG9uIHRoZSB0YXJnZXRFbWFpbFxuICAgIGNvbnN0IGVtYWlsU3ViamVjdEZvclJlc3BvbnNlID0gdGFyZ2V0RW1haWwuc3ViamVjdCB8fCAndGhpcyBlbWFpbCc7IC8vIFVzZSBcInRoaXMgZW1haWxcIiBpZiBzdWJqZWN0IGlzIGVtcHR5IGZvciBtb3JlIG5hdHVyYWwgcmVzcG9uc2VcbiAgICBjb25zdCBlbWFpbElkU2hvcnRGb3JSZXNwb25zZSA9IHRhcmdldEVtYWlsLmlkLnNsaWNlKC02KTsgLy8gRm9yIGNvbmNpc2UgSUQgcmVmZXJlbmNlIGlmIG5lZWRlZFxuXG4gICAgc3dpdGNoIChhY3Rpb25SZXF1ZXN0ZWQuYWN0aW9uVHlwZSkge1xuICAgICAgY2FzZSAnR0VUX0ZVTExfQ09OVEVOVCc6XG4gICAgICAgIGNvbnN0IGJvZHlQcmV2aWV3ID0gdGFyZ2V0RW1haWwuYm9keVxuICAgICAgICAgID8gdGFyZ2V0RW1haWwuYm9keS5sZW5ndGggPiAyMDBcbiAgICAgICAgICAgID8gdGFyZ2V0RW1haWwuYm9keS5zdWJzdHJpbmcoMCwgMjAwKSArICcuLi4nXG4gICAgICAgICAgICA6IHRhcmdldEVtYWlsLmJvZHlcbiAgICAgICAgICA6ICdpdCBhcHBlYXJzIHRvIGhhdmUgbm8gcmVhZGFibGUgYm9keSBjb250ZW50Lic7XG4gICAgICAgIG1lc3NhZ2VUb1VzZXIgPSBgVGhlIGVtYWlsIHRpdGxlZCBcIiR7ZW1haWxTdWJqZWN0Rm9yUmVzcG9uc2V9XCIgYmVnaW5zIHdpdGg6IFwiJHtib2R5UHJldmlld31cIi4gSXMgdGhlcmUgYSBzcGVjaWZpYyBwYXJ0IHlvdSdyZSBpbnRlcmVzdGVkIGluLCBvciB3b3VsZCB5b3UgbGlrZSBtZSB0byB0cnkgYW5kIGZpbmQgc29tZXRoaW5nIHBhcnRpY3VsYXIgaW4gaXQ/YDtcbiAgICAgICAgYnJlYWs7XG4gICAgICBjYXNlICdHRVRfU0VOREVSJzpcbiAgICAgICAgbWVzc2FnZVRvVXNlciA9IGBUaGUgc2VuZGVyIG9mIFwiJHtlbWFpbFN1YmplY3RGb3JSZXNwb25zZX1cIiBpczogJHt0YXJnZXRFbWFpbC5zZW5kZXIgfHwgJ25vdCBzcGVjaWZpZWQnfS5gO1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ0dFVF9TVUJKRUNUJzpcbiAgICAgICAgbWVzc2FnZVRvVXNlciA9IGBUaGUgc3ViamVjdCBvZiB0aGUgZW1haWwgKElEIGVuZGluZyBpbiAuLi4ke2VtYWlsSWRTaG9ydEZvclJlc3BvbnNlfSkgaXM6IFwiJHt0YXJnZXRFbWFpbC5zdWJqZWN0IHx8ICdObyBTdWJqZWN0J31cIi5gO1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ0dFVF9EQVRFJzpcbiAgICAgICAgY29uc3QgZGF0ZU9wdGlvbnM6IEludGwuRGF0ZVRpbWVGb3JtYXRPcHRpb25zID0ge1xuICAgICAgICAgIHllYXI6ICdudW1lcmljJyxcbiAgICAgICAgICBtb250aDogJ2xvbmcnLFxuICAgICAgICAgIGRheTogJ251bWVyaWMnLFxuICAgICAgICAgIGhvdXI6ICdudW1lcmljJyxcbiAgICAgICAgICBtaW51dGU6ICcyLWRpZ2l0JyxcbiAgICAgICAgfTtcbiAgICAgICAgY29uc3QgZm9ybWF0dGVkRGF0ZSA9IHRhcmdldEVtYWlsLnRpbWVzdGFtcFxuICAgICAgICAgID8gbmV3IERhdGUodGFyZ2V0RW1haWwudGltZXN0YW1wKS50b0xvY2FsZURhdGVTdHJpbmcoXG4gICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgZGF0ZU9wdGlvbnNcbiAgICAgICAgICAgIClcbiAgICAgICAgICA6ICdhbiB1bmtub3duIGRhdGUnO1xuICAgICAgICBtZXNzYWdlVG9Vc2VyID0gYFRoZSBlbWFpbCBcIiR7ZW1haWxTdWJqZWN0Rm9yUmVzcG9uc2V9XCIgd2FzIHJlY2VpdmVkIG9uICR7Zm9ybWF0dGVkRGF0ZX0uYDtcbiAgICAgICAgYnJlYWs7XG4gICAgICBjYXNlICdGSU5EX1NQRUNJRklDX0lORk8nOlxuICAgICAgICBpZiAoIXRhcmdldEVtYWlsLmJvZHkpIHtcbiAgICAgICAgICBtZXNzYWdlVG9Vc2VyID0gYFRoZSBlbWFpbCBcIiR7ZW1haWxTdWJqZWN0Rm9yUmVzcG9uc2V9XCIgZG9lc24ndCBzZWVtIHRvIGhhdmUgYW55IHRleHQgY29udGVudCBmb3IgbWUgdG8gYW5hbHl6ZSBmb3IgdGhhdC5gO1xuICAgICAgICAgIGJyZWFrO1xuICAgICAgICB9XG4gICAgICAgIGNvbnN0IGtleXdvcmRzVG9FeHRyYWN0ID0gYWN0aW9uUmVxdWVzdGVkLmluZm9LZXl3b3JkcyB8fCBbXTtcbiAgICAgICAgY29uc3QgbmxRdWVzdGlvbiA9IGFjdGlvblJlcXVlc3RlZC5uYXR1cmFsTGFuZ3VhZ2VRdWVzdGlvbjtcblxuICAgICAgICBpZiAoa2V5d29yZHNUb0V4dHJhY3QubGVuZ3RoID09PSAwICYmICFubFF1ZXN0aW9uKSB7XG4gICAgICAgICAgbWVzc2FnZVRvVXNlciA9IGBZb3UgYXNrZWQgbWUgdG8gZmluZCBzcGVjaWZpYyBpbmZvcm1hdGlvbiBpbiBcIiR7ZW1haWxTdWJqZWN0Rm9yUmVzcG9uc2V9XCIsIGJ1dCBkaWRuJ3Qgc3BlY2lmeSB3aGF0IHRvIGxvb2sgZm9yLmA7XG4gICAgICAgICAgYnJlYWs7XG4gICAgICAgIH1cblxuICAgICAgICAvLyBQcmVmZXIgbmF0dXJhbCBsYW5ndWFnZSBxdWVzdGlvbiBpZiBwcm92aWRlZCB0byB0aGUgTExNIGV4dHJhY3Rvciwgb3RoZXJ3aXNlIHVzZSBrZXl3b3Jkcy5cbiAgICAgICAgLy8gVGhlIGN1cnJlbnQgTExNIGV4dHJhY3RvciBpcyBkZXNpZ25lZCBmb3Iga2V5d29yZHMsIHNvIHdlJ2xsIHBhc3Mga2V5d29yZHMuXG4gICAgICAgIC8vIElmIGEgbmF0dXJhbExhbmd1YWdlUXVlc3Rpb24gd2FzIHByb3ZpZGVkLCB0aGUgTkxVIHNlcnZpY2Ugc2hvdWxkIGlkZWFsbHkgY29udmVydCBpdCB0byBpbmZvS2V5d29yZHMuXG4gICAgICAgIC8vIEZvciB0aGlzIGV4YW1wbGUsIHdlJ2xsIGFzc3VtZSBpbmZvS2V5d29yZHMgaXMgcG9wdWxhdGVkIGNvcnJlY3RseSBieSB0aGUgTkxVIGxheWVyLlxuXG4gICAgICAgIGNvbnN0IGV4dHJhY3Rpb25JbnB1dEtleXdvcmRzID1cbiAgICAgICAgICBrZXl3b3Jkc1RvRXh0cmFjdC5sZW5ndGggPiAwXG4gICAgICAgICAgICA/IGtleXdvcmRzVG9FeHRyYWN0XG4gICAgICAgICAgICA6IG5sUXVlc3Rpb25cbiAgICAgICAgICAgICAgPyBbbmxRdWVzdGlvbl1cbiAgICAgICAgICAgICAgOiBbXTtcblxuICAgICAgICBpZiAoZXh0cmFjdGlvbklucHV0S2V5d29yZHMubGVuZ3RoID09PSAwKSB7XG4gICAgICAgICAgbWVzc2FnZVRvVXNlciA9IGBZb3UgYXNrZWQgbWUgdG8gZmluZCBzcGVjaWZpYyBpbmZvcm1hdGlvbiBpbiBcIiR7ZW1haWxTdWJqZWN0Rm9yUmVzcG9uc2V9XCIsIGJ1dCBkaWRuJ3Qgc3BlY2lmeSB3aGF0IHRvIGxvb2sgZm9yLmA7XG4gICAgICAgICAgYnJlYWs7XG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCBleHRyYWN0ZWRJbmZvID0gYXdhaXQgZXh0cmFjdEluZm9ybWF0aW9uRnJvbUVtYWlsQm9keShcbiAgICAgICAgICB0YXJnZXRFbWFpbC5ib2R5LFxuICAgICAgICAgIGV4dHJhY3Rpb25JbnB1dEtleXdvcmRzXG4gICAgICAgICk7XG4gICAgICAgIGxldCBmb3VuZEFueSA9IGZhbHNlO1xuICAgICAgICBsZXQgcmVzcG9uc2VQYXJ0czogc3RyaW5nW10gPSBbXTtcblxuICAgICAgICAvLyBDb25zdHJ1Y3QgYSBtb3JlIGNvbnZlcnNhdGlvbmFsIHJlc3BvbnNlXG4gICAgICAgIGlmIChleHRyYWN0aW9uSW5wdXRLZXl3b3Jkcy5sZW5ndGggPT09IDEpIHtcbiAgICAgICAgICAvLyBTaW5nbGUgcGllY2Ugb2YgaW5mbyByZXF1ZXN0ZWRcbiAgICAgICAgICBjb25zdCBzaW5nbGVLZXl3b3JkID0gZXh0cmFjdGlvbklucHV0S2V5d29yZHNbMF07XG4gICAgICAgICAgY29uc3QgcmVzdWx0VmFsdWUgPSBleHRyYWN0ZWRJbmZvW3NpbmdsZUtleXdvcmRdO1xuICAgICAgICAgIGlmIChyZXN1bHRWYWx1ZSkge1xuICAgICAgICAgICAgaWYgKFxuICAgICAgICAgICAgICByZXN1bHRWYWx1ZS5zdGFydHNXaXRoKCdLZXl3b3JkIFwiJykgJiZcbiAgICAgICAgICAgICAgcmVzdWx0VmFsdWUuZW5kc1dpdGgoXG4gICAgICAgICAgICAgICAgJ1wiIGZvdW5kLiAoRnVydGhlciBhbmFseXNpcyBuZWVkZWQgZm9yIHNwZWNpZmljIHZhbHVlKS4nXG4gICAgICAgICAgICAgIClcbiAgICAgICAgICAgICkge1xuICAgICAgICAgICAgICBtZXNzYWdlVG9Vc2VyID0gYFRoZSBlbWFpbCBcIiR7ZW1haWxTdWJqZWN0Rm9yUmVzcG9uc2V9XCIgbWVudGlvbnMgXCIke3NpbmdsZUtleXdvcmR9XCIuYDtcbiAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgIG1lc3NhZ2VUb1VzZXIgPSBgUmVnYXJkaW5nIFwiJHtzaW5nbGVLZXl3b3JkfVwiIGluIHRoZSBlbWFpbCBcIiR7ZW1haWxTdWJqZWN0Rm9yUmVzcG9uc2V9XCIsIEkgZm91bmQ6ICR7cmVzdWx0VmFsdWV9LmA7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBmb3VuZEFueSA9IHRydWU7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIG1lc3NhZ2VUb1VzZXIgPSBgSSBjaGVja2VkIHRoZSBlbWFpbCBcIiR7ZW1haWxTdWJqZWN0Rm9yUmVzcG9uc2V9XCIgZm9yIFwiJHtzaW5nbGVLZXl3b3JkfVwiLCBidXQgSSBjb3VsZG4ndCBmaW5kIHRoYXQgc3BlY2lmaWMgaW5mb3JtYXRpb24uYDtcbiAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgLy8gTXVsdGlwbGUgcGllY2VzIG9mIGluZm8gcmVxdWVzdGVkXG4gICAgICAgICAgcmVzcG9uc2VQYXJ0cy5wdXNoKGBJbiB0aGUgZW1haWwgXCIke2VtYWlsU3ViamVjdEZvclJlc3BvbnNlfVwiOmApO1xuICAgICAgICAgIGZvciAoY29uc3Qga2V5d29yZCBvZiBleHRyYWN0aW9uSW5wdXRLZXl3b3Jkcykge1xuICAgICAgICAgICAgY29uc3QgcmVzdWx0VmFsdWUgPSBleHRyYWN0ZWRJbmZvW2tleXdvcmRdO1xuICAgICAgICAgICAgaWYgKHJlc3VsdFZhbHVlKSB7XG4gICAgICAgICAgICAgIGlmIChcbiAgICAgICAgICAgICAgICByZXN1bHRWYWx1ZS5zdGFydHNXaXRoKCdLZXl3b3JkIFwiJykgJiZcbiAgICAgICAgICAgICAgICByZXN1bHRWYWx1ZS5lbmRzV2l0aChcbiAgICAgICAgICAgICAgICAgICdcIiBmb3VuZC4gKEZ1cnRoZXIgYW5hbHlzaXMgbmVlZGVkIGZvciBzcGVjaWZpYyB2YWx1ZSkuJ1xuICAgICAgICAgICAgICAgIClcbiAgICAgICAgICAgICAgKSB7XG4gICAgICAgICAgICAgICAgcmVzcG9uc2VQYXJ0cy5wdXNoKGAtIEl0IG1lbnRpb25zIFwiJHtrZXl3b3JkfVwiLmApO1xuICAgICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgIHJlc3BvbnNlUGFydHMucHVzaChcbiAgICAgICAgICAgICAgICAgIGAtIEZvciBcIiR7a2V5d29yZH1cIiwgSSBmb3VuZDogJHtyZXN1bHRWYWx1ZX0uYFxuICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgZm91bmRBbnkgPSB0cnVlO1xuICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgcmVzcG9uc2VQYXJ0cy5wdXNoKFxuICAgICAgICAgICAgICAgIGAtIEkgY291bGRuJ3QgZmluZCBzcGVjaWZpYyBpbmZvcm1hdGlvbiBhYm91dCBcIiR7a2V5d29yZH1cIi5gXG4gICAgICAgICAgICAgICk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICAgIGlmICghZm91bmRBbnkpIHtcbiAgICAgICAgICAgIG1lc3NhZ2VUb1VzZXIgPSBgSSBzY2FubmVkIFwiJHtlbWFpbFN1YmplY3RGb3JSZXNwb25zZX1cIiBmb3IgaW5mb3JtYXRpb24gcmVsYXRlZCB0byBcIiR7ZXh0cmFjdGlvbklucHV0S2V5d29yZHMuam9pbignLCAnKX1cIiwgYnV0IGNvdWxkbid0IGZpbmQgdGhvc2Ugc3BlY2lmaWMgZGV0YWlscy5gO1xuICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBtZXNzYWdlVG9Vc2VyID0gcmVzcG9uc2VQYXJ0cy5qb2luKCdcXG4nKTtcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgICAgYnJlYWs7XG4gICAgICBjYXNlICdTVU1NQVJJWkVfRU1BSUwnOlxuICAgICAgICAvLyBUT0RPOiBJbXBsZW1lbnQgTExNLWJhc2VkIHN1bW1hcml6YXRpb24gc2tpbGwgY2FsbFxuICAgICAgICBtZXNzYWdlVG9Vc2VyID0gYEkgY2FuJ3Qgc3VtbWFyaXplIGVtYWlscyB5ZXQsIGJ1dCBJIGZvdW5kIHRoZSBvbmUgdGl0bGVkIFwiJHtlbWFpbFN1YmplY3RGb3JSZXNwb25zZX1cIi5gO1xuICAgICAgICBicmVhaztcbiAgICAgIGRlZmF1bHQ6XG4gICAgICAgIG1lc3NhZ2VUb1VzZXIgPSBgSSBmb3VuZCB0aGUgZW1haWwgXCIke2VtYWlsU3ViamVjdEZvclJlc3BvbnNlfVwiLiBJJ20gbm90IHN1cmUgaG93IHRvIGhhbmRsZSB0aGUgYWN0aW9uOiAke2FjdGlvblJlcXVlc3RlZC5hY3Rpb25UeXBlfS5gO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKCdBZ2VudCBmaW5hbCB2b2ljZS1mcmllbmRsaWVyIHJlc3BvbnNlOiAnLCBtZXNzYWdlVG9Vc2VyKTtcbiAgICByZXR1cm4gbWVzc2FnZVRvVXNlcjtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICBgQWdlbnQ6IEVycm9yIGluIGhhbmRsZUZpbmRFbWFpbEFuZEV4dHJhY3RJbmZvIGZvciB1c2VyICR7dXNlcklkfTpgLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIG1lc3NhZ2VUb1VzZXIgPSBgSSBlbmNvdW50ZXJlZCBhbiBpc3N1ZSB3aGlsZSBwcm9jZXNzaW5nIHlvdXIgcmVxdWVzdDogJHtlcnJvci5tZXNzYWdlIHx8ICdVbmtub3duIGVycm9yJ31gO1xuICAgIC8vIGF3YWl0IHNlbmRBZ2VudFJlc3BvbnNlKHVzZXJJZCwgbWVzc2FnZVRvVXNlcik7XG4gICAgY29uc29sZS5sb2coJ0FnZW50IGVycm9yIHJlc3BvbnNlOiAnLCBtZXNzYWdlVG9Vc2VyKTtcbiAgICByZXR1cm4gbWVzc2FnZVRvVXNlcjtcbiAgfVxufVxuXG4vKlxuLy8gRXhhbXBsZSBvZiBob3cgdGhpcyBoYW5kbGVyIG1pZ2h0IGJlIGludm9rZWQgYnkgdGhlIG1haW4gYWdlbnQgb3JjaGVzdHJhdG9yXG4vLyBhZnRlciBOTFUgcHJvY2Vzc2luZyBwcm92aWRlcyBhIFBhcnNlZE5sdUVtYWlsUmVxdWVzdCBvYmplY3QuXG5cbmFzeW5jIGZ1bmN0aW9uIG1haW5BZ2VudExvZ2ljKHVzZXJJZDogc3RyaW5nLCBwYXJzZWRObHVSZXN1bHQ6IGFueSkge1xuICAgIGlmIChwYXJzZWRObHVSZXN1bHQuaW50ZW50ID09PSAnRklORF9FTUFJTF9BTkRfRVhUUkFDVF9DT05UUkFDVF9FTkRfREFURScpIHtcbiAgICAgICAgY29uc3QgcmVxdWVzdDogUGFyc2VkTmx1RW1haWxSZXF1ZXN0ID0ge1xuICAgICAgICAgICAgdXNlcklkOiB1c2VySWQsXG4gICAgICAgICAgICBzZWFyY2hQYXJhbWV0ZXJzOiB7XG4gICAgICAgICAgICAgICAgZnJvbTogcGFyc2VkTmx1UmVzdWx0LmVudGl0aWVzLnNlbmRlcixcbiAgICAgICAgICAgICAgICBzdWJqZWN0OiBwYXJzZWRObHVSZXN1bHQuZW50aXRpZXMuc3ViamVjdEtleXdvcmRzLFxuICAgICAgICAgICAgICAgIGJvZHlLZXl3b3JkczogcGFyc2VkTmx1UmVzdWx0LmVudGl0aWVzLmJvZHlLZXl3b3JkcyxcbiAgICAgICAgICAgICAgICAvLyBOTFUgbmVlZHMgdG8gY29udmVydCBcImEgZmV3IG1vbnRocyBhZ29cIiB0byBhZnRlci9iZWZvcmUgZGF0ZXNcbiAgICAgICAgICAgICAgICBhZnRlcjogcGFyc2VkTmx1UmVzdWx0LmVudGl0aWVzLmRhdGVSYW5nZT8uYWZ0ZXIsXG4gICAgICAgICAgICAgICAgYmVmb3JlOiBwYXJzZWRObHVSZXN1bHQuZW50aXRpZXMuZGF0ZVJhbmdlPy5iZWZvcmUsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgaW5mb3JtYXRpb25Ub0V4dHJhY3Q6ICdjb250cmFjdEVuZERhdGUnXG4gICAgICAgIH07XG4gICAgICAgIGF3YWl0IGhhbmRsZUZpbmRFbWFpbEFuZEV4dHJhY3RJbmZvKHJlcXVlc3QpO1xuICAgIH1cbn1cbiovXG5cbi8qKlxuICogSGFuZGxlcyBhIHJlcXVlc3QgdG8gc2VuZCBhbiBlbWFpbC5cbiAqL1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZVNlbmRFbWFpbFJlcXVlc3QoXG4gIHJlcXVlc3Q6IFBhcnNlZE5sdVNlbmRFbWFpbFJlcXVlc3Rcbik6IFByb21pc2U8c3RyaW5nPiB7XG4gIGNvbnN0IHsgdXNlcklkLCBlbWFpbERldGFpbHMgfSA9IHJlcXVlc3Q7XG4gIGxldCBtZXNzYWdlVG9Vc2VyID0gJyc7XG5cbiAgbG9nZ2VyLmluZm8oXG4gICAgYEFnZW50OiBBdHRlbXB0aW5nIHRvIHNlbmQgZW1haWwgZm9yIHVzZXIgJHt1c2VySWR9IHdpdGggZGV0YWlsczpgLFxuICAgIGVtYWlsRGV0YWlsc1xuICApO1xuXG4gIGlmIChcbiAgICAhZW1haWxEZXRhaWxzLnRvIHx8XG4gICAgIWVtYWlsRGV0YWlscy5zdWJqZWN0IHx8XG4gICAgKCFlbWFpbERldGFpbHMuYm9keSAmJiAhZW1haWxEZXRhaWxzLmh0bWxCb2R5KVxuICApIHtcbiAgICBtZXNzYWdlVG9Vc2VyID1cbiAgICAgIFwiSSdtIHNvcnJ5LCBidXQgSSdtIG1pc3Npbmcgc29tZSBjcnVjaWFsIGluZm9ybWF0aW9uIHRvIHNlbmQgdGhlIGVtYWlsLiBJIG5lZWQgYXQgbGVhc3QgYSByZWNpcGllbnQsIGEgc3ViamVjdCwgYW5kIGEgYm9keSBjb250ZW50LlwiO1xuICAgIGxvZ2dlci53YXJuKFxuICAgICAgYEFnZW50OiBNaXNzaW5nIGRldGFpbHMgZm9yIHNlbmQgZW1haWwgcmVxdWVzdCBmb3IgdXNlciAke3VzZXJJZH0uIERldGFpbHM6YCxcbiAgICAgIGVtYWlsRGV0YWlsc1xuICAgICk7XG4gICAgcmV0dXJuIG1lc3NhZ2VUb1VzZXI7XG4gIH1cblxuICB0cnkge1xuICAgIGNvbnN0IHNlbmRSZXNwb25zZTogU2VuZEVtYWlsUmVzcG9uc2UgPSBhd2FpdCBzZW5kRW1haWxTa2lsbChlbWFpbERldGFpbHMpO1xuXG4gICAgaWYgKHNlbmRSZXNwb25zZS5zdWNjZXNzKSB7XG4gICAgICBtZXNzYWdlVG9Vc2VyID0gYE9rYXksIEkndmUgc2VudCB0aGUgZW1haWwgdG8gJHtlbWFpbERldGFpbHMudG99IHdpdGggdGhlIHN1YmplY3QgXCIke2VtYWlsRGV0YWlscy5zdWJqZWN0fVwiLmA7XG4gICAgICBpZiAoc2VuZFJlc3BvbnNlLmVtYWlsSWQpIHtcbiAgICAgICAgbWVzc2FnZVRvVXNlciArPSBgIChNZXNzYWdlIElEOiAke3NlbmRSZXNwb25zZS5lbWFpbElkfSlgO1xuICAgICAgfVxuICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgIGBBZ2VudDogRW1haWwgc2VudCBzdWNjZXNzZnVsbHkgZm9yIHVzZXIgJHt1c2VySWR9LiBSZXNwb25zZTpgLFxuICAgICAgICBzZW5kUmVzcG9uc2VcbiAgICAgICk7XG4gICAgfSBlbHNlIHtcbiAgICAgIG1lc3NhZ2VUb1VzZXIgPSBgSSB0cmllZCB0byBzZW5kIHRoZSBlbWFpbCwgYnV0IHNvbWV0aGluZyB3ZW50IHdyb25nLiAke3NlbmRSZXNwb25zZS5tZXNzYWdlIHx8ICdBbiB1bmtub3duIGVycm9yIG9jY3VycmVkLid9YDtcbiAgICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICAgYEFnZW50OiBGYWlsZWQgdG8gc2VuZCBlbWFpbCBmb3IgdXNlciAke3VzZXJJZH0uIFJlc3BvbnNlOmAsXG4gICAgICAgIHNlbmRSZXNwb25zZVxuICAgICAgKTtcbiAgICB9XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICBgQWdlbnQ6IENyaXRpY2FsIGVycm9yIGluIGhhbmRsZVNlbmRFbWFpbFJlcXVlc3QgZm9yIHVzZXIgJHt1c2VySWR9OmAsXG4gICAgICBlcnJvclxuICAgICk7XG4gICAgbWVzc2FnZVRvVXNlciA9IGBJIGVuY291bnRlcmVkIGEgY3JpdGljYWwgZXJyb3Igd2hpbGUgdHJ5aW5nIHRvIHNlbmQgdGhlIGVtYWlsOiAke2Vycm9yLm1lc3NhZ2UgfHwgJ1Vua25vd24gZXJyb3InfWA7XG4gIH1cblxuICByZXR1cm4gbWVzc2FnZVRvVXNlcjtcbn1cbiJdfQ==