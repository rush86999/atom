import { StructuredEmailQuery, buildGmailSearchQuery } from '../skills/nlu_email_helper';
import { searchMyEmails, readEmail, extractContractEndDate, Email } from '../skills/emailSkills';
// Assume a way to send messages back to the user, e.g., through a chat interface.
// This is a placeholder for the actual messaging function.
// import { sendAgentResponse } from '../agentResponse';
import { extractInformationFromEmailBody } from '../skills/emailSkills';
import { understandEmailSearchQueryLLM } from '../skills/llm_email_query_understander'; // Import LLM query understander

// Define the types for what the NLU service should provide to this handler
export type EmailActionType =
  | "GET_FULL_CONTENT"
  | "GET_SENDER"
  | "GET_SUBJECT"
  | "GET_DATE"
  | "FIND_SPECIFIC_INFO" // For targeted extraction
  | "SUMMARIZE_EMAIL"; // Future capability

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
      // TODO: Implement clarification if emailsFound.length > 1. For now, use the first.
      const firstFoundEmailSummary = emailsFound[0];
      console.log(`Agent: Found email ID ${firstFoundEmailSummary.id}. Subject: "${firstFoundEmailSummary.subject}". Fetching details...`);

      const emailDetailsResponse = await readEmail(userId, firstFoundEmailSummary.id);
      if (emailDetailsResponse.success && emailDetailsResponse.email) {
        targetEmail = emailDetailsResponse.email;
      } else {
        messageToUser = `Sorry, I found an email summary but couldn't read its full details. ${emailDetailsResponse.message}`;
        console.log("Agent response: ", messageToUser);
        return messageToUser;
      }
    }

    if (!targetEmail) {
        messageToUser = "Could not identify a target email to process.";
        console.log("Agent response: ", messageToUser);
        return messageToUser;
    }

    // Step 2: Perform the requested action on the targetEmail
    switch (actionRequested.actionType) {
      case "GET_FULL_CONTENT":
        messageToUser = `Full content of email "${targetEmail.subject}":\n${targetEmail.body}`;
        break;
      case "GET_SENDER":
        messageToUser = `The sender of email "${targetEmail.subject}" is: ${targetEmail.sender}.`;
        break;
      case "GET_SUBJECT":
        messageToUser = `The subject of the email (ID: ${targetEmail.id}) is: "${targetEmail.subject}".`;
        break;
      case "GET_DATE":
        messageToUser = `The email "${targetEmail.subject}" was received on: ${new Date(targetEmail.timestamp).toLocaleString()}.`;
        break;
      case "FIND_SPECIFIC_INFO":
        if (!targetEmail.body) {
          messageToUser = `The email "${targetEmail.subject}" doesn't seem to have a body content to analyze.`;
          break;
        }
        if (!actionRequested.infoKeywords || actionRequested.infoKeywords.length === 0) {
          messageToUser = `You asked me to find specific information in "${targetEmail.subject}", but didn't specify what to look for.`;
          break;
        }
        const extractedInfo = await extractInformationFromEmailBody(targetEmail.body, actionRequested.infoKeywords);
        let foundAny = false;
        let responseParts: string[] = [`Regarding email "${targetEmail.subject}":`];
        for (const keyword of actionRequested.infoKeywords) {
          if (extractedInfo[keyword]) {
            responseParts.push(`- For "${keyword}", I found: ${extractedInfo[keyword]}`);
            foundAny = true;
          } else {
            responseParts.push(`- I couldn't find information about "${keyword}".`);
          }
        }
        messageToUser = foundAny ? responseParts.join('\n') : `I checked the email "${targetEmail.subject}" but couldn't find the requested information for: ${actionRequested.infoKeywords.join(', ')}.`;
        break;
      case "SUMMARIZE_EMAIL":
        // TODO: Implement summarization skill call
        messageToUser = `Summarization for email "${targetEmail.subject}" is not implemented yet.`;
        break;
      default:
        messageToUser = `I found the email "${targetEmail.subject}", but I'm not sure what to do with the action: ${actionRequested.actionType}.`;
    }

    console.log("Agent final response: ", messageToUser);
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
