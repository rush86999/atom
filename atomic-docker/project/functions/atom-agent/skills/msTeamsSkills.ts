import { logger } from '../../_utils/logger';
// Removed callHasuraActionGraphQL and GQL constants
import {
  MSTeamsMessage,
  GraphSkillResponse,
  SkillError,
  GetMSTeamsMessageDetailInput,
} from '../types';
// Direct import from msteams-service.ts
import * as msTeamsService from '../../msteams-service/service';

/**
 * Searches Microsoft Teams messages for the user by calling the msteams-service directly.
 * @param atomUserId The Atom internal ID of the user making the request.
 * @param kqlQuery The KQL search query string.
 * @param limit Max number of messages to return.
 * @returns A promise resolving to an array of MSTeamsMessage objects.
 */
export async function searchMyMSTeamsMessages(
  atomUserId: string,
  kqlQuery: string,
  limit: number = 10
): Promise<MSTeamsMessage[]> {
  logger.debug(
    `[MSTeamsSkills] searchMyMSTeamsMessages direct call for Atom user ${atomUserId}, KQL: "${kqlQuery}", limit: ${limit}`
  );

  try {
    // Call the service function directly.
    // The service function `searchTeamsMessages` returns GraphSkillResponse<AgentMSTeamsMessage[]>
    // We need to adapt this to Promise<MSTeamsMessage[]> or handle the GraphSkillResponse structure.
    // For now, let's assume we adapt to MSTeamsMessage[] if successful.
    const response = await msTeamsService.searchTeamsMessages(
      atomUserId,
      kqlQuery,
      limit
    );

    if (!response.ok || !response.data) {
      logger.error(
        `[MSTeamsSkills] msteams-service.searchTeamsMessages failed for user ${atomUserId}: ${response.error?.message}`
      );
      return [];
    }
    // Assuming AgentMSTeamsMessage is compatible with MSTeamsMessage for the fields we need.
    // If not, a mapping function would be required here.
    // MSTeamsMessage from types.ts is more detailed than AgentMSTeamsMessage in service.ts.
    // Let's ensure proper mapping.
    return response.data.map(
      (item: msTeamsService.AgentMSTeamsMessage): MSTeamsMessage => ({
        id: item.id,
        chatId: item.chatId,
        teamId: item.teamId,
        channelId: item.channelId,
        replyToId: item.replyToId,
        userId: item.userId,
        userName: item.userName,
        content: item.content,
        contentType: item.contentType as 'html' | 'text', // service might return string
        createdDateTime: item.createdDateTime,
        lastModifiedDateTime: item.lastModifiedDateTime,
        webUrl: item.webUrl,
        attachments: item.attachments, // Assuming structure matches
        mentions: item.mentions, // Assuming structure matches
        raw: item.raw,
      })
    );
  } catch (error: any) {
    logger.error(
      `[MSTeamsSkills] Error in searchMyMSTeamsMessages direct call for Atom user ${atomUserId}, KQL "${kqlQuery}":`,
      error
    );
    return [];
  }
}

// Removed _getUserGraphObjectId as AAD ID fetching is now part of msteams-service.getDelegatedMSGraphTokenForUser

export async function getRecentChatsAndMentionsForBriefing(
  atomUserId: string,
  targetDate: Date,
  count: number = 3
): Promise<
  GraphSkillResponse<{ results: MSTeamsMessage[]; query_executed?: string }>
> {
  logger.debug(
    `[MSTeamsSkills] getRecentChatsAndMentionsForBriefing for Atom user: ${atomUserId}, TargetDate: ${targetDate.toISOString().split('T')[0]}, Count: ${count}`
  );

  try {
    // 1. Get token and user AAD identifiers from msteams-service
    const tokenDetailsResponse =
      await msTeamsService.getDelegatedMSGraphTokenForUser(atomUserId);
    if (
      !tokenDetailsResponse.ok ||
      !tokenDetailsResponse.data?.accessToken ||
      !tokenDetailsResponse.data?.userAadObjectId
    ) {
      logger.error(
        `[MSTeamsSkills] Could not get valid token or user AAD Object ID for user ${atomUserId}. Error: ${tokenDetailsResponse.error?.message}`
      );
      return {
        ok: false,
        error: tokenDetailsResponse.error || {
          code: 'MSTEAMS_AUTH_FAILED',
          message: 'Authentication or user ID retrieval failed for MS Teams.',
        },
      };
    }
    const { userAadObjectId, userPrincipalName } = tokenDetailsResponse.data;
    // Note: accessToken is managed within msteams-service calls, not directly used here anymore.

    if (!userAadObjectId && !userPrincipalName) {
      logger.warn(
        `[MSTeamsSkills] User AAD Object ID and UPN are both null for user ${atomUserId}. KQL query will be very broad.`
      );
      // Fallback to a very generic query or return error, for now, proceed with broad query.
    }

    const startOfDay = new Date(targetDate);
    startOfDay.setUTCHours(0, 0, 0, 0);
    const endOfDay = new Date(targetDate);
    endOfDay.setUTCHours(23, 59, 59, 999);
    const startOfDayISO = startOfDay.toISOString();
    const endOfDayISO = endOfDay.toISOString();

    // 2. Construct KQL query using AAD Object ID or UPN
    const dateFilterKQL = `createdDateTime>=${startOfDayISO} AND createdDateTime<=${endOfDayISO}`;
    let userSpecificKQL = '';

    if (userAadObjectId) {
      // Using AAD Object ID is generally more robust for mentions and identifying users.
      // This query targets messages mentioning the user OR messages sent by the user.
      // It helps find @mentions in channels/group chats and user's own messages in DMs/group chats.
      // It doesn't specifically isolate DMs *to* the user if they haven't replied and weren't mentioned.
      userSpecificKQL = `(mentions:"${userAadObjectId}" OR from:"${userAadObjectId}")`;
    } else if (userPrincipalName) {
      // Fallback to UPN if AAD Object ID is not available.
      // UPN might work for `from` but can be less reliable for `mentions` if display names are used more often.
      userSpecificKQL = `(mentions:"${userPrincipalName}" OR from:"${userPrincipalName}")`;
      logger.warn(
        `[MSTeamsSkills] Using UPN for KQL construction as AAD Object ID was not available for user ${atomUserId}. This might be less precise for mentions.`
      );
    } else {
      logger.warn(
        `[MSTeamsSkills] No user AAD ID or UPN available for user ${atomUserId}. KQL will only use date filters and be very broad. Results might not be relevant DMs/mentions.`
      );
      // If no user identifier, the query will just be the date filter, relying on the user's token context.
      // This will fetch all messages accessible to the user in that time range.
    }

    const kqlQuery = userSpecificKQL
      ? `${userSpecificKQL} AND ${dateFilterKQL}`
      : dateFilterKQL;

    logger.info(
      `[MSTeamsSkills] Constructed KQL query for briefing: "${kqlQuery}"`
    );

    // 3. Call the refactored searchMyMSTeamsMessages
    // The `searchMyMSTeamsMessages` will pass this KQL to the msteams-service,
    // which executes it against the Graph Search API.
    const searchResponse = await searchMyMSTeamsMessages(
      atomUserId,
      kqlQuery,
      count
    );

    // searchMyMSTeamsMessages now returns MSTeamsMessage[] directly, not a GraphSkillResponse.
    // The error handling and transformation to GraphSkillResponse should happen here.
    // However, looking at the current searchMyMSTeamsMessages, it already returns MSTeamsMessage[] and logs errors.
    // For consistency, getRecentChatsAndMentionsForBriefing should also return GraphSkillResponse.

    logger.info(
      `[MSTeamsSkills] Found ${searchResponse.length} MS Teams messages for briefing using KQL.`
    );
    return {
      ok: true,
      data: { results: searchResponse, query_executed: kqlQuery },
    };
  } catch (error: any) {
    logger.error(
      `[MSTeamsSkills] Error in getRecentChatsAndMentionsForBriefing for Atom user ${atomUserId}: ${error.message}`,
      error
    );
    const skillError: SkillError = {
      code: 'MSTEAMS_BRIEFING_FETCH_FAILED',
      message:
        error.message ||
        'Failed to fetch recent MS Teams messages for briefing.',
      details: error,
    };
    return { ok: false, error: skillError };
  }
}

// Removed GQL_GET_MS_TEAMS_MESSAGE_WEB_URL constant

// Input type for the Hasura action, mirrors GetMSTeamsMessageDetailInput for identifying the message
// This interface is defined in types.ts, so no need to redefine here if imported.
// export interface GetMSTeamsMessageWebUrlInput extends GetMSTeamsMessageDetailInput {}

/**
 * Gets a permalink (webUrl) for a specific MS Teams message by calling the msteams-service.
 * @param atomUserId The Atom internal ID of the user.
 * @param identifier An object to identify the message (messageId and chatId or teamId/channelId).
 * @returns A promise resolving to the webUrl string or null.
 */
export async function getMSTeamsMessageWebUrl(
  atomUserId: string,
  identifier: GetMSTeamsMessageDetailInput // Use the one from types.ts
): Promise<string | null> {
  logger.debug(
    `[MSTeamsSkills] getMSTeamsMessageWebUrl direct call for Atom user ${atomUserId}, identifier:`,
    identifier
  );

  if (
    !identifier.messageId ||
    (!identifier.chatId && (!identifier.teamId || !identifier.channelId))
  ) {
    logger.error(
      '[MSTeamsSkills] Invalid identifier for getMSTeamsMessageWebUrl.'
    );
    return null;
  }

  try {
    // To get webUrl, we might need to fetch the message details first if not available otherwise
    // The msteams-service layer doesn't have a dedicated "get permalink" function.
    // We can call readMSTeamsMessage and extract webUrl.
    const message = await readMSTeamsMessage(atomUserId, identifier);
    if (message && message.webUrl) {
      return message.webUrl;
    } else if (message) {
      logger.warn(
        `[MSTeamsSkills] Message found but webUrl is missing for message ID ${identifier.messageId}.`
      );
      return null;
    } else {
      logger.warn(
        `[MSTeamsSkills] Could not read message to get webUrl for ID ${identifier.messageId}.`
      );
      return null;
    }
  } catch (error) {
    logger.error(
      `[MSTeamsSkills] Error in getMSTeamsMessageWebUrl for Atom user ${atomUserId}, identifier:`,
      identifier,
      error
    );
    return null;
  }
}

// --- LLM Information Extraction from MS Teams Message ---
import OpenAI from 'openai'; // Assuming OpenAI is standard for LLM tasks
import { ChatCompletionMessageParam } from 'openai/resources/chat/completions';
import { ATOM_OPENAI_API_KEY, ATOM_NLU_MODEL_NAME } from '../_libs/constants';

let openAIClientForMSTeamsExtraction: OpenAI | null = null;

function getMSTeamsExtractionOpenAIClient(): OpenAI {
  if (openAIClientForMSTeamsExtraction) {
    return openAIClientForMSTeamsExtraction;
  }
  if (!ATOM_OPENAI_API_KEY) {
    logger.error(
      '[MSTeamsSkills] OpenAI API Key not configured for LLM MS Teams Extractor.'
    );
    throw new Error(
      'OpenAI API Key not configured for LLM MS Teams Extractor.'
    );
  }
  openAIClientForMSTeamsExtraction = new OpenAI({
    apiKey: ATOM_OPENAI_API_KEY,
  });
  logger.info(
    '[MSTeamsSkills] OpenAI client for MS Teams extraction initialized.'
  );
  return openAIClientForMSTeamsExtraction;
}

// System prompt for extracting info from MS Teams messages.
// Similar to Slack/Email, but can be tailored for Teams message nuances.
const MSTEAMS_EXTRACTION_SYSTEM_PROMPT_TEMPLATE = `
You are an expert system designed to extract specific pieces of information from a Microsoft Teams message.
The user will provide the message content (which might be HTML or plain text) and a list of information points (keywords).
For each keyword, find the corresponding information in the message.
Respond ONLY with a single, valid JSON object. Do not include any explanatory text before or after the JSON.
The JSON object should have keys corresponding to the user's original keywords.
The value for each key should be the extracted information as a string.
If information for a keyword is not found, the value for that key should be null.

Example:
User provides keywords: ["task details", "assigned to", "deadline"]
Message content: "<div><p>Hey @Alex, please look into the <b>spec review for feature X</b>. It needs to be completed by エンドオブデー Friday.</p></div>"
Your JSON response (assuming EOD Friday is understood as a deadline):
{
  "task details": "spec review for feature X",
  "assigned to": "@Alex",
  "deadline": "EOD Friday"
}

The keywords you need to extract information for are: {{KEYWORDS_JSON_ARRAY_STRING}}
Extract the information from the Teams message content provided by the user. If the content is HTML, focus on the textual information.
`;

/**
 * Uses an LLM to extract specific pieces of information from an MS Teams message body.
 * @param messageContent The content of the MS Teams message (can be HTML or plain text).
 * @param infoKeywords An array of strings representing the concepts/keywords to search for.
 * @returns A Promise resolving to a record where keys are infoKeywords and values are the extracted strings (or null).
 */
export async function extractInformationFromMSTeamsMessage(
  messageContent: string,
  infoKeywords: string[]
): Promise<Record<string, string | null>> {
  if (!infoKeywords || infoKeywords.length === 0) {
    logger.debug(
      '[MSTeamsSkills] extractInformationFromMSTeamsMessage: No infoKeywords provided.'
    );
    return {};
  }
  if (!messageContent || messageContent.trim() === '') {
    logger.debug(
      '[MSTeamsSkills] extractInformationFromMSTeamsMessage: Empty messageContent provided.'
    );
    const emptyResult: Record<string, string | null> = {};
    infoKeywords.forEach((kw) => (emptyResult[kw] = null));
    return emptyResult;
  }

  logger.debug(
    `[MSTeamsSkills] LLM Extractor: Attempting to extract from MS Teams message for keywords: [${infoKeywords.join(', ')}]`
  );
  const client = getMSTeamsExtractionOpenAIClient();

  const keywordsJsonArrayString = JSON.stringify(infoKeywords);
  const systemPrompt = MSTEAMS_EXTRACTION_SYSTEM_PROMPT_TEMPLATE.replace(
    '{{KEYWORDS_JSON_ARRAY_STRING}}',
    keywordsJsonArrayString
  );

  // Simple HTML to text conversion if content type is HTML, for cleaner input to LLM
  // More sophisticated stripping might be needed for complex HTML.
  let processedContent = messageContent;
  // Basic stripping of HTML tags for LLM processing if it's likely HTML
  if (messageContent.includes('<') && messageContent.includes('>')) {
    processedContent = messageContent
      .replace(/<[^>]+>/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
    logger.debug(
      '[MSTeamsSkills] LLM Extractor: Stripped HTML from message content.'
    );
  }

  const messages: ChatCompletionMessageParam[] = [
    { role: 'system', content: systemPrompt },
    {
      role: 'user',
      content: `MS Teams Message Content:\n---\n${processedContent}\n---`,
    },
  ];

  try {
    const completion = await client.chat.completions.create({
      model: ATOM_NLU_MODEL_NAME,
      messages: messages,
      temperature: 0.1,
      response_format: { type: 'json_object' },
    });

    const llmResponse = completion.choices[0]?.message?.content;
    if (!llmResponse) {
      logger.error(
        '[MSTeamsSkills] LLM Extractor: Received an empty response from AI for MS Teams message.'
      );
      throw new Error('LLM Extractor (MS Teams): Empty response from AI.');
    }

    logger.debug(
      '[MSTeamsSkills] LLM Extractor: Raw LLM JSON response for MS Teams:',
      llmResponse
    );
    const parsedResponse = JSON.parse(llmResponse);

    const result: Record<string, string | null> = {};
    for (const keyword of infoKeywords) {
      result[keyword] = parsedResponse.hasOwnProperty(keyword)
        ? parsedResponse[keyword]
        : null;
    }

    logger.debug(
      '[MSTeamsSkills] LLM Extractor: Parsed and reconciled extraction from MS Teams:',
      result
    );
    return result;
  } catch (error: any) {
    logger.error(
      '[MSTeamsSkills] LLM Extractor: Error processing information extraction from MS Teams message with OpenAI:',
      error.message
    );
    if (error instanceof SyntaxError) {
      logger.error(
        '[MSTeamsSkills] LLM Extractor: Failed to parse JSON response from LLM for MS Teams message.'
      );
      throw new Error(
        'LLM Extractor (MS Teams): Failed to parse response from AI.'
      );
    }
    const fallbackResult: Record<string, string | null> = {};
    infoKeywords.forEach((kw) => (fallbackResult[kw] = null));
    return fallbackResult;
  }
}

// Placeholder for callHasuraActionGraphQL utility if it's not in a shared location yet.
// Ensure this is implemented or imported correctly. For now, using a simplified version.
// import fetch from 'node-fetch';
// const HASURA_GRAPHQL_ENDPOINT = process.env.HASURA_GRAPHQL_ENDPOINT || 'http://hasura:8080/v1/graphql';

// async function callHasuraActionGraphQL(userId: string, operationName: string, query: string, variables: Record<string, any>): Promise<any> {
//   logger.debug(`[MSTeamsSkills] Calling Hasura Action GQL: ${operationName} for user ${userId}`);
//   try {
//       const response = await fetch(HASURA_GRAPHQL_ENDPOINT, {
//           method: 'POST',
//           headers: {
//               'Content-Type': 'application/json',
//               'X-Hasura-Role': 'user',
//               'X-Hasura-User-Id': userId,
//               ...(process.env.HASURA_ADMIN_SECRET && !userId ? { 'x-hasura-admin-secret': process.env.HASURA_ADMIN_SECRET } : {})
//           },
//           body: JSON.stringify({ query, variables }),
//       });
//       if (!response.ok) { /* ... error handling ... */ throw new Error(`Hasura GQL call to ${operationName} failed: ${response.statusText}`); }
//       const jsonResponse = await response.json();
//       if (jsonResponse.errors) { /* ... error handling ... */ throw new Error(`Hasura GQL call to ${operationName} returned errors: ${jsonResponse.errors.map((e: any) => e.message).join(', ')}`);}
//       return jsonResponse.data;
//   } catch (error) { /* ... error handling ... */ throw error; }
// }

const GQL_GET_MS_TEAMS_MESSAGE_DETAIL = `
  mutation GetMSTeamsMessageDetail($input: GetMSTeamsMessageDetailInput!) {
    getMSTeamsMessageDetail(input: $input) {
      success
      message
      msTeamsMessage { # This structure should match MSTeamsMessageObject
        id
        chatId
        teamId
        channelId
        replyToId
        userId
        userName
        content
        contentType
        createdDateTime
        lastModifiedDateTime
        webUrl
        attachments { id name contentType contentUrl size }
        mentions {
          id
          mentionText
          mentioned {
            user { id displayName userIdentityType }
          }
        }
        # raw
      }
    }
  }
`;

export interface GetMSTeamsMessageDetailInput {
  messageId: string;
  chatId?: string; // Provide if it's a chat message
  teamId?: string; // Provide with channelId if it's a channel message
  channelId?: string; // Provide with teamId if it's a channel message
}

/**
 * Reads the detailed content of a specific MS Teams message.
 * @param userId The ID of the user.
 * @param identifier An object to identify the message, containing messageId and context (chatId or teamId/channelId).
 * @returns A promise resolving to an MSTeamsMessage object or null if not found/error.
 */
export async function readMSTeamsMessage(
  userId: string,
  identifier: GetMSTeamsMessageDetailInput
): Promise<MSTeamsMessage | null> {
  logger.debug(
    `[MSTeamsSkills] readMSTeamsMessage called for user ${userId}, identifier:`,
    identifier
  );

  if (
    !identifier.messageId ||
    (!identifier.chatId && (!identifier.teamId || !identifier.channelId))
  ) {
    logger.error(
      '[MSTeamsSkills] Invalid identifier for readMSTeamsMessage. Need messageId and (chatId or teamId+channelId).'
    );
    return null;
  }

  try {
    const responseData = await callHasuraActionGraphQL(
      userId,
      'GetMSTeamsMessageDetail',
      GQL_GET_MS_TEAMS_MESSAGE_DETAIL,
      {
        input: identifier,
      }
    );

    const getResult = responseData.getMSTeamsMessageDetail;

    if (!getResult.success || !getResult.msTeamsMessage) {
      logger.warn(
        `[MSTeamsSkills] getMSTeamsMessageDetail action failed or message not found for user ${userId}: ${getResult.message}`,
        identifier
      );
      return null;
    }

    // Direct cast if GraphQL output matches agent's MSTeamsMessage type.
    // Ensure nested structures like attachments and mentions are also correctly typed/mapped if needed.
    const message: MSTeamsMessage = {
      ...getResult.msTeamsMessage,
      contentType: getResult.msTeamsMessage.contentType as 'html' | 'text', // Ensure enum type if not guaranteed by GQL
      attachments:
        getResult.msTeamsMessage.attachments?.map((att: any) => ({
          id: att.id,
          name: att.name,
          contentType: att.contentType,
          contentUrl: att.contentUrl,
          size: att.size,
        })) || [],
      mentions:
        getResult.msTeamsMessage.mentions?.map((men: any) => ({
          id: men.id,
          mentionText: men.mentionText,
          mentioned: men.mentioned
            ? {
                user: men.mentioned.user
                  ? {
                      id: men.mentioned.user.id,
                      displayName: men.mentioned.user.displayName,
                      userIdentityType: men.mentioned.user.userIdentityType,
                    }
                  : undefined,
              }
            : undefined,
        })) || [],
    };
    return message;
  } catch (error) {
    logger.error(
      `[MSTeamsSkills] Error in readMSTeamsMessage for user ${userId}, identifier:`,
      identifier,
      error
    );
    return null;
  }
}
