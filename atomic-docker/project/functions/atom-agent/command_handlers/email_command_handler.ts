import { StructuredEmailQuery, buildGmailSearchQuery } from '../skills/nlu_email_helper';
import { searchMyEmails, readEmail, extractContractEndDate, Email } from '../skills/emailSkills';
// Assume a way to send messages back to the user, e.g., through a chat interface.
// This is a placeholder for the actual messaging function.
// import { sendAgentResponse } from '../agentResponse';
import { extractInformationFromEmailBody } from '../skills/emailSkills';
import { understandEmailSearchQueryLLM } from '../skills/llm_email_query_understander'; // Import LLM query understander

import { searchMyEmails, readEmail, Email, sendEmail as sendEmailSkill, EmailDetails, SendEmailResponse } from '../skills/emailSkills'; // Added sendEmailSkill, EmailDetails, SendEmailResponse
import { logger } from '../../_utils/logger'; // Assuming logger is available

// Define the types for what the NLU service should provide to this handler
export type EmailActionType =
  | "GET_FULL_CONTENT"
  | "GET_SENDER"
  | "GET_SUBJECT"
  | "GET_DATE"
  | "FIND_SPECIFIC_INFO" // For targeted extraction
  | "SUMMARIZE_EMAIL" // Future capability
  | "SEND_EMAIL"; // New action type

export interface EmailActionRequest {
  actionType: EmailActionType;
  infoKeywords?: string[]; // Used when actionType is FIND_SPECIFIC_INFO
  // Could also include a natural language question for FIND_SPECIFIC_INFO if LLM extractor supports it
  naturalLanguageQuestion?: string;
}

// This request now takes the raw user query for emails,
// which will be processed by the LLM query understander.
export interface ParsedNluEmailRequest {
  userId: string;
  rawEmailSearchQuery: string; // e.g., "emails from Jane about Q3 report last week"
  actionRequested: EmailActionRequest;
  targetEmailId?: string; // Optional: if NLU identified a specific email ID directly
}

// Interface for a "send email" request from NLU
export interface ParsedNluSendEmailRequest {
  userId: string;
  emailDetails: EmailDetails; // Reusing EmailDetails from emailSkills.ts
}

/**
 * Handles a generic email inquiry: understands the search query using an LLM,
 * finds an email, and performs an action on it (e.g., extracts info, gets metadata).
 */
export async function handleEmailInquiry(request: ParsedNluEmailRequest): Promise<string> {
  const { userId, rawEmailSearchQuery, actionRequested, targetEmailId } = request;
  let messageToUser = "";

  try {
    let targetEmail: Email | null = null;

    // Step 1: Obtain the target email (either by ID or by searching)
    if (targetEmailId) {
      console.log(`Agent: Attempting to read specified email ID ${targetEmailId} for user ${userId}.`);
      const emailDetailsResponse = await readEmail(userId, targetEmailId);
      if (emailDetailsResponse.success && emailDetailsResponse.email) {
        targetEmail = emailDetailsResponse.email;
      } else {
        messageToUser = `Sorry, I couldn't read the details for email ID ${targetEmailId}. ${emailDetailsResponse.message}`;
        console.log("Agent response: ", messageToUser);
        return messageToUser;
      }
    } else {
      // Use LLM to understand the raw search query and convert to StructuredEmailQuery
      console.log(`Agent: Understanding email search query: "${rawEmailSearchQuery}" for user ${userId}`);
      const structuredSearchParams = await understandEmailSearchQueryLLM(rawEmailSearchQuery);

      const gmailQueryString = buildGmailSearchQuery(structuredSearchParams);
      if (!gmailQueryString) {
        // This might happen if LLM returns empty object for a vague query.
        messageToUser = "I couldn't determine specific search criteria from your request. Could you be more precise?";
        console.log("Agent response: ", messageToUser);
        return messageToUser;
      }
      console.log(`Agent: Searching emails for user ${userId} with LLM-derived query: ${gmailQueryString}`);
      const emailsFound = await searchMyEmails(userId, gmailQueryString, 5);

      if (!emailsFound || emailsFound.length === 0) {
        messageToUser = "I couldn't find any emails matching your criteria based on my understanding of your request.";
        console.log("Agent response: ", messageToUser);
        return messageToUser;
      }

      if (emailsFound.length > 1) {
        // Multiple emails found, ask for clarification.
        messageToUser = "I found a few emails matching your criteria:\n";
        emailsFound.slice(0, 3).forEach((email, index) => { // Show up to 3
          messageToUser += `${index + 1}. Subject: "${email.subject || 'No Subject'}" (ID: ...${email.id.slice(-6)})\n`;
        });
        if (emailsFound.length > 3) {
          messageToUser += `And ${emailsFound.length - 3} more.\n`;
        }
        messageToUser += "Which one are you interested in? You can tell me the number or provide more details to narrow it down.";
        console.log("Agent needs clarification: ", messageToUser);
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
      } else {
        messageToUser = `I found an email titled "${singleEmailSummary.subject}", but I'm having trouble loading its full content right now. The error was: ${emailDetailsResponse.message || 'Unknown error'}.`;
        console.log("Agent response: ", messageToUser);
        return messageToUser;
      }
    }

    if (!targetEmail) {
        messageToUser = "I couldn't identify a specific email to process with the information provided. Could you try searching again with different terms?";
        console.log("Agent response: ", messageToUser);
        return messageToUser;
    }

    // Step 2: Perform the requested action on the targetEmail
    const emailSubjectForResponse = targetEmail.subject || "this email"; // Use "this email" if subject is empty for more natural response
    const emailIdShortForResponse = targetEmail.id.slice(-6); // For concise ID reference if needed

    switch (actionRequested.actionType) {
      case "GET_FULL_CONTENT":
        const bodyPreview = targetEmail.body
          ? (targetEmail.body.length > 200 ? targetEmail.body.substring(0, 200) + "..." : targetEmail.body)
          : "it appears to have no readable body content.";
        messageToUser = `The email titled "${emailSubjectForResponse}" begins with: "${bodyPreview}". Is there a specific part you're interested in, or would you like me to try and find something particular in it?`;
        break;
      case "GET_SENDER":
        messageToUser = `The sender of "${emailSubjectForResponse}" is: ${targetEmail.sender || 'not specified'}.`;
        break;
      case "GET_SUBJECT":
        messageToUser = `The subject of the email (ID ending in ...${emailIdShortForResponse}) is: "${targetEmail.subject || 'No Subject'}".`;
        break;
      case "GET_DATE":
        const dateOptions: Intl.DateTimeFormatOptions = { year: 'numeric', month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit' };
        const formattedDate = targetEmail.timestamp ? new Date(targetEmail.timestamp).toLocaleDateString(undefined, dateOptions) : 'an unknown date';
        messageToUser = `The email "${emailSubjectForResponse}" was received on ${formattedDate}.`;
        break;
      case "FIND_SPECIFIC_INFO":
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

        const extractionInputKeywords = keywordsToExtract.length > 0 ? keywordsToExtract : (nlQuestion ? [nlQuestion] : []);

        if (extractionInputKeywords.length === 0) {
             messageToUser = `You asked me to find specific information in "${emailSubjectForResponse}", but didn't specify what to look for.`;
             break;
        }

        const extractedInfo = await extractInformationFromEmailBody(targetEmail.body, extractionInputKeywords);
        let foundAny = false;
        let responseParts: string[] = [];

        // Construct a more conversational response
        if (extractionInputKeywords.length === 1) { // Single piece of info requested
            const singleKeyword = extractionInputKeywords[0];
            const resultValue = extractedInfo[singleKeyword];
            if (resultValue) {
                if (resultValue.startsWith("Keyword \"") && resultValue.endsWith("\" found. (Further analysis needed for specific value).")) {
                    messageToUser = `The email "${emailSubjectForResponse}" mentions "${singleKeyword}".`;
                } else {
                    messageToUser = `Regarding "${singleKeyword}" in the email "${emailSubjectForResponse}", I found: ${resultValue}.`;
                }
                foundAny = true;
            } else {
                 messageToUser = `I checked the email "${emailSubjectForResponse}" for "${singleKeyword}", but I couldn't find that specific information.`;
            }
        } else { // Multiple pieces of info requested
            responseParts.push(`In the email "${emailSubjectForResponse}":`);
            for (const keyword of extractionInputKeywords) {
              const resultValue = extractedInfo[keyword];
              if (resultValue) {
                if (resultValue.startsWith("Keyword \"") && resultValue.endsWith("\" found. (Further analysis needed for specific value).")) {
                  responseParts.push(`- It mentions "${keyword}".`);
                } else {
                  responseParts.push(`- For "${keyword}", I found: ${resultValue}.`);
                }
                foundAny = true;
              } else {
                responseParts.push(`- I couldn't find specific information about "${keyword}".`);
              }
            }
            if (!foundAny) {
                messageToUser = `I scanned "${emailSubjectForResponse}" for information related to "${extractionInputKeywords.join(', ')}", but couldn't find those specific details.`;
            } else {
                messageToUser = responseParts.join('\n');
            }
        }
        break;
      case "SUMMARIZE_EMAIL":
        // TODO: Implement LLM-based summarization skill call
        messageToUser = `I can't summarize emails yet, but I found the one titled "${emailSubjectForResponse}".`;
        break;
      default:
        messageToUser = `I found the email "${emailSubjectForResponse}". I'm not sure how to handle the action: ${actionRequested.actionType}.`;
    }

    console.log("Agent final voice-friendlier response: ", messageToUser);
    return messageToUser;

  } catch (error: any) {
    console.error(`Agent: Error in handleFindEmailAndExtractInfo for user ${userId}:`, error);
    messageToUser = `I encountered an issue while processing your request: ${error.message || 'Unknown error'}`;
    // await sendAgentResponse(userId, messageToUser);
    console.log("Agent error response: ", messageToUser);
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
export async function handleSendEmailRequest(request: ParsedNluSendEmailRequest): Promise<string> {
  const { userId, emailDetails } = request;
  let messageToUser = "";

  logger.info(`Agent: Attempting to send email for user ${userId} with details:`, emailDetails);

  if (!emailDetails.to || !emailDetails.subject || (!emailDetails.body && !emailDetails.htmlBody)) {
    messageToUser = "I'm sorry, but I'm missing some crucial information to send the email. I need at least a recipient, a subject, and a body content.";
    logger.warn(`Agent: Missing details for send email request for user ${userId}. Details:`, emailDetails);
    return messageToUser;
  }

  try {
    const sendResponse: SendEmailResponse = await sendEmailSkill(emailDetails);

    if (sendResponse.success) {
      messageToUser = `Okay, I've sent the email to ${emailDetails.to} with the subject "${emailDetails.subject}".`;
      if (sendResponse.emailId) {
        messageToUser += ` (Message ID: ${sendResponse.emailId})`;
      }
      logger.info(`Agent: Email sent successfully for user ${userId}. Response:`, sendResponse);
    } else {
      messageToUser = `I tried to send the email, but something went wrong. ${sendResponse.message || "An unknown error occurred."}`;
      logger.error(`Agent: Failed to send email for user ${userId}. Response:`, sendResponse);
    }
  } catch (error: any) {
    logger.error(`Agent: Critical error in handleSendEmailRequest for user ${userId}:`, error);
    messageToUser = `I encountered a critical error while trying to send the email: ${error.message || 'Unknown error'}`;
  }

  return messageToUser;
}
