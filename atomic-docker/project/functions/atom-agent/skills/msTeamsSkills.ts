import { logger } from '../../_utils/logger';
import { callHasuraActionGraphQL } from './utils'; // Assuming a shared Hasura call utility
import { MSTeamsMessage, GraphSkillResponse, SkillError } from '../types'; // Import MSTeamsMessage and response types

// GraphQL mutation for searching MS Teams messages via Hasura action
const GQL_SEARCH_MS_TEAMS_MESSAGES = `
  mutation SearchUserMSTeamsMessages($input: SearchMSTeamsMessagesInput!) {
    searchUserMSTeamsMessages(input: $input) {
      success
      message
      results { # This structure should match the MSTeamsMessageObject in actions.graphql
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
        attachments {
          id
          name
          contentType
          contentUrl
          size
        }
        mentions {
          id
          mentionText
          mentioned {
            user {
              id
              displayName
              userIdentityType
            }
          }
        }
        # raw # If raw is passed by Hasura action
      }
    }
  }
`;

/**
 * Searches Microsoft Teams messages for the user via a Hasura action.
 * @param userId The ID of the user making the request.
 * @param searchQuery The KQL search query string.
 * @param limit Max number of messages to return.
 * @returns A promise resolving to an array of MSTeamsMessage objects.
 */
export async function searchMyMSTeamsMessages(
  userId: string,
  searchQuery: string,
  limit: number = 10
): Promise<MSTeamsMessage[]> {
  logger.debug(`[MSTeamsSkills] searchMyMSTeamsMessages called for user ${userId}, query: "${searchQuery}", limit: ${limit}`);

  try {
    // The Hasura action 'searchUserMSTeamsMessages' will call 'searchTeamsMessages' in 'msteams-service.ts'.
    // Input for Hasura action: { query: String!, maxResults: Int }
    const responseData = await callHasuraActionGraphQL(userId, "SearchUserMSTeamsMessages", GQL_SEARCH_MS_TEAMS_MESSAGES, {
      input: { query: searchQuery, maxResults: limit }
    });

    const searchResult = responseData.searchUserMSTeamsMessages;

    if (!searchResult.success) {
      logger.error(`[MSTeamsSkills] searchUserMSTeamsMessages action failed for user ${userId}: ${searchResult.message}`);
      return []; // Or throw new Error(searchResult.message) or return a more structured error
    }

    // Transform results from Hasura (MSTeamsMessageObject) to agent's MSTeamsMessage type.
    // This mapping assumes the GraphQL MSTeamsMessageObject closely matches MSTeamsMessage.
    return (searchResult.results || []).map((item: any): MSTeamsMessage => ({
      id: item.id,
      chatId: item.chatId,
      teamId: item.teamId,
      channelId: item.channelId,
      replyToId: item.replyToId,
      userId: item.userId,
      userName: item.userName,
      content: item.content,
      contentType: item.contentType as 'html' | 'text',
      createdDateTime: item.createdDateTime,
      lastModifiedDateTime: item.lastModifiedDateTime,
      webUrl: item.webUrl,
      attachments: item.attachments?.map((att: any) => ({
        id: att.id,
        name: att.name,
        contentType: att.contentType,
        contentUrl: att.contentUrl,
        size: att.size,
      })) || [],
      mentions: item.mentions?.map((men: any) => ({
        id: men.id,
        mentionText: men.mentionText,
        mentioned: men.mentioned ? {
            user: men.mentioned.user ? {
                id: men.mentioned.user.id,
                displayName: men.mentioned.user.displayName,
                userIdentityType: men.mentioned.user.userIdentityType,
            } : undefined,
            // Include other mentioned types if necessary (application, conversation, tag)
        } : undefined,
      })) || [],
      raw: item.raw, // If raw is passed and desired
    }));

  } catch (error) {
    logger.error(`[MSTeamsSkills] Error in searchMyMSTeamsMessages for user ${userId}, query "${searchQuery}":`, error);
    return [];
  }
}

// Conceptual helper to get user's MS Graph Object ID (AAD ID)
// In a real scenario, this would involve getting a token for the user and calling Graph API /me
// or this ID might be stored/retrieved alongside their MS Teams OAuth tokens.
async function _getUserGraphObjectId(atomUserId: string, client: any /* MSGraphClient or similar */): Promise<string | null> {
  logger.debug(`[MSTeamsSkills] _getUserGraphObjectId: Attempting to get Graph Object ID for Atom user ${atomUserId}. (Conceptual)`);
  // Placeholder: Assume a mechanism exists to map atomUserId to an AAD ObjectId or UPN
  // For testing, one might return a known test AAD User ID.
  // Example using a hypothetical Graph call (if client was an authenticated MSGraphClient):
  // try {
  //   const userProfile = await client.api('/me').select('id,userPrincipalName').get();
  //   return userProfile.id; // This is the AAD Object ID
  // } catch (error) {
  //   logger.error(`[MSTeamsSkills] Failed to fetch user's Graph Object ID for Atom user ${atomUserId}:`, error);
  //   return null;
  // }
  // For now, as this is complex to implement fully here without actual token flow for /me:
  logger.warn(`[MSTeamsSkills] _getUserGraphObjectId is a placeholder. Returning null. KQL query for mentions will be less effective.`);
  // To make search work somewhat for testing without a real user ID, one might search for a common term
  // or a known display name if the search API supports that well in KQL.
  // For now, returning null means mention search part of KQL will be skipped or use a placeholder.
  return null;
}


export async function getRecentChatsAndMentionsForBriefing(
  atomUserId: string,
  targetDate: Date,
  count: number = 3
): Promise<GraphSkillResponse<{ results: MSTeamsMessage[], query_executed?: string }>> { // Use GraphSkillResponse for consistency
  logger.debug(`[MSTeamsSkills] getRecentChatsAndMentionsForBriefing for Atom user: ${atomUserId}, TargetDate: ${targetDate.toISOString().split('T')[0]}, Count: ${count}`);

  // MS Graph client for /me endpoint would be needed if we were to fetch AAD ID here.
  // This is complex as it requires a user-delegated token.
  // For now, we'll construct a KQL that might work more broadly or assume AAD ID is somehow available.
  // Let's assume for this skill, we don't have direct access to make a /me call easily.
  // The searchMyMSTeamsMessages itself uses a token obtained via getDelegatedMSGraphTokenForUser,
  // which is associated with the atomUserId. The KQL search will run in that user's context.

  try {
    const startOfDay = new Date(targetDate);
    startOfDay.setUTCHours(0, 0, 0, 0);
    const endOfDay = new Date(targetDate);
    endOfDay.setUTCHours(23, 59, 59, 999);

    const startOfDayISO = startOfDay.toISOString();
    const endOfDayISO = endOfDay.toISOString();

    // Construct KQL Query.
    // Searching for mentions of the user (requires knowing their display name or AAD ID which is hard here)
    // OR messages in 1:1 chats (isChatMessage=true AND chatMessage.chatType eq 'oneOnOne' might not be KQL)
    // OR messages sent by the user (from.user.id eq 'userGraphId')
    // KQL for Graph Search API is powerful but specific.
    // A simpler approach for DMs and mentions might be:
    // 1. Fetch user's chats: /me/chats (filter for 1on1, get last message preview)
    // 2. Fetch user's activity feed for mentions: /me/teamwork/activityfeed
    // These are different API calls than /search/query.
    //
    // Given we must use searchMyMSTeamsMessages which uses /search/query with KQL:
    // We'll try a KQL that looks for messages TO or FROM the current user (implicit from token)
    // in their chats, and separately for @mentions if we had their AAD ID.
    // Since getting AAD ID here is hard, let's make a best-effort KQL.
    // The `from` field in KQL usually refers to sender's name/email.
    // `participants` can be used with user IDs.
    //
    // Let's assume the search is in the context of the user provided by the token.
    // We want messages where this user is a participant (implicitly true for their chats)
    // AND ( (the message is in a 1:1 chat) OR (the message @mentions them) ).
    // KQL for chat messages might not directly support "is:dm" or easy "@me" like Slack.
    // A KQL query focusing on recency and user involvement:
    // "(participants:\"Me\" OR mentions:\"Me\")" - "Me" might not work, needs actual ID/name.
    // For this iteration, let's simplify: fetch recent messages from user's chats and hope mentions are caught by text search.
    // A more robust solution would require the user's AAD ID.
    //
    // If we had userAadId:
    // const kqlQuery = `((mentions:"${userAadId}") OR (participants:"${userAadId}" AND IsGroupChat:"false")) AND createdDateTime>=${startOfDayISO} AND createdDateTime<=${endOfDayISO}`;
    // Without userAadId, we rely on the search being scoped to the user's accessible messages.
    // We'll search for messages within the date range.
    // Filtering for DMs/Mentions will be done client-side on results if KQL is too limited without specific ID.

    // For now, let's just get recent messages for the user on that day and assume the search endpoint is smart.
    // This is a simplification due to the difficulty of getting user's own AAD ID easily within this skill layer
    // without another Graph call. The search will be run as the user.
    const kqlQuery = `createdDateTime>=${startOfDayISO} AND createdDateTime<=${endOfDayISO}`;
    logger.info(`[MSTeamsSkills] Constructed KQL query for briefing: "${kqlQuery}" (This is broad, needs user context from token)`);

    const searchResults = await searchMyMSTeamsMessages(atomUserId, kqlQuery, count * 5); // Fetch more to filter client-side

    // Client-side filtering for DMs or mentions (since KQL is broad here)
    // This is NOT ideal but a workaround if user's own AAD ID isn't easily available for KQL.
    // A better backend search is preferred.
    const relevantMessages: MSTeamsMessage[] = [];
    if (searchResults && searchResults.length > 0) {
        // Attempt to get user's own AAD ID by making a /me call if not already available
        // This is a conceptual step for now.
        const userGraphId = await _getUserGraphObjectId(atomUserId, null); // Pass a conceptual client or token

        for (const msg of searchResults) {
            let isRelevant = false;
            // Check if it's a DM-like chat (assuming chatId exists for DMs, and it's not a channel message)
            if (msg.chatId && !msg.teamId && !msg.channelId) {
                 // Heuristic: if it's a chat message and the sender is not the user, it might be a DM to the user.
                 // Or if the chat itself is known to be a 1:1 with the user. This requires more context.
                 // For now, include if it's a chat message and not from self (very rough)
                 if (userGraphId && msg.userId !== userGraphId) isRelevant = true;
                 else if (!userGraphId) isRelevant = true; // If we can't get self ID, take all chat messages
            }
            // Check for mentions
            if (msg.mentions && userGraphId) {
                if (msg.mentions.some(mention => mention.mentioned?.user?.id === userGraphId)) {
                    isRelevant = true;
                }
            }
            if (isRelevant) {
                relevantMessages.push(msg);
            }
            if (relevantMessages.length >= count) break;
        }
    }

    logger.info(`[MSTeamsSkills] Found ${relevantMessages.length} relevant MS Teams messages for briefing.`);
    return { ok: true, data: { results: relevantMessages, query_executed: kqlQuery } };

  } catch (error: any) {
    logger.error(`[MSTeamsSkills] Error in getRecentChatsAndMentionsForBriefing for Atom user ${atomUserId}: ${error.message}`, error);
    const skillError: SkillError = {
        code: 'MSTEAMS_BRIEFING_FETCH_FAILED',
        message: error.message || "Failed to fetch recent MS Teams messages for briefing.",
        details: error
    };
    return { ok: false, error: skillError };
  }
}


const GQL_GET_MS_TEAMS_MESSAGE_WEB_URL = `
  mutation GetMSTeamsMessageWebUrl($input: GetMSTeamsMessageWebUrlInput!) {
    getMSTeamsMessageWebUrl(input: $input) {
      success
      message
      webUrl
    }
  }
`;

// Input type for the Hasura action, mirrors GetMSTeamsMessageDetailInput for identifying the message
export interface GetMSTeamsMessageWebUrlInput extends GetMSTeamsMessageDetailInput {}


/**
 * Gets a permalink (webUrl) for a specific MS Teams message.
 * This might call a specific Hasura action that in turn calls a service function
 * to retrieve just the webUrl, or it could potentially reuse getMSTeamsMessageDetail
 * if the overhead is acceptable and webUrl is consistently populated.
 * For this implementation, we'll assume a dedicated Hasura action for focused retrieval if possible,
 * or rely on readMSTeamsMessage to have populated it.
 * Since webUrl is part of the MSTeamsMessage, this skill could simply ensure the message is read
 * and then return the webUrl property.
 * However, to align with a potential direct permalink fetching in service layer (if Graph has such specific endpoint or if it's part of minimal fetch):
 *
 * @param userId The ID of the user.
 * @param identifier An object to identify the message.
 * @returns A promise resolving to the webUrl string or null.
 */
export async function getMSTeamsMessageWebUrl(
  userId: string,
  identifier: GetMSTeamsMessageWebUrlInput
): Promise<string | null> {
  logger.debug(`[MSTeamsSkills] getMSTeamsMessageWebUrl called for user ${userId}, identifier:`, identifier);

  if (!identifier.messageId || (!identifier.chatId && (!identifier.teamId || !identifier.channelId))) {
    logger.error('[MSTeamsSkills] Invalid identifier for getMSTeamsMessageWebUrl.');
    return null;
  }

  // Option 1: Call a specific Hasura action for the permalink
  try {
    const responseData = await callHasuraActionGraphQL(userId, "GetMSTeamsMessageWebUrl", GQL_GET_MS_TEAMS_MESSAGE_WEB_URL, {
      input: identifier
    });
    const getResult = responseData.getMSTeamsMessageWebUrl;
    if (getResult.success && getResult.webUrl) {
      return getResult.webUrl as string;
    } else {
      logger.warn(`[MSTeamsSkills] getMSTeamsMessageWebUrl action failed or webUrl not found: ${getResult.message}`, identifier);
      // Fallback: Try reading the whole message if direct permalink failed
      // This might be redundant if the Hasura action itself already does this.
      // const message = await readMSTeamsMessage(userId, identifier);
      // return message?.webUrl || null;
      return null;
    }
  } catch (error) {
    logger.error(`[MSTeamsSkills] Error in getMSTeamsMessageWebUrl for user ${userId}, identifier:`, identifier, error);
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
    logger.error('[MSTeamsSkills] OpenAI API Key not configured for LLM MS Teams Extractor.');
    throw new Error('OpenAI API Key not configured for LLM MS Teams Extractor.');
  }
  openAIClientForMSTeamsExtraction = new OpenAI({ apiKey: ATOM_OPENAI_API_KEY });
  logger.info('[MSTeamsSkills] OpenAI client for MS Teams extraction initialized.');
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
    logger.debug('[MSTeamsSkills] extractInformationFromMSTeamsMessage: No infoKeywords provided.');
    return {};
  }
  if (!messageContent || messageContent.trim() === '') {
    logger.debug('[MSTeamsSkills] extractInformationFromMSTeamsMessage: Empty messageContent provided.');
    const emptyResult: Record<string, string | null> = {};
    infoKeywords.forEach(kw => emptyResult[kw] = null);
    return emptyResult;
  }

  logger.debug(`[MSTeamsSkills] LLM Extractor: Attempting to extract from MS Teams message for keywords: [${infoKeywords.join(', ')}]`);
  const client = getMSTeamsExtractionOpenAIClient();

  const keywordsJsonArrayString = JSON.stringify(infoKeywords);
  const systemPrompt = MSTEAMS_EXTRACTION_SYSTEM_PROMPT_TEMPLATE.replace("{{KEYWORDS_JSON_ARRAY_STRING}}", keywordsJsonArrayString);

  // Simple HTML to text conversion if content type is HTML, for cleaner input to LLM
  // More sophisticated stripping might be needed for complex HTML.
  let processedContent = messageContent;
  // Basic stripping of HTML tags for LLM processing if it's likely HTML
  if (messageContent.includes("<") && messageContent.includes(">")) {
      processedContent = messageContent.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
      logger.debug('[MSTeamsSkills] LLM Extractor: Stripped HTML from message content.');
  }


  const messages: ChatCompletionMessageParam[] = [
    { role: 'system', content: systemPrompt },
    { role: 'user', content: `MS Teams Message Content:\n---\n${processedContent}\n---` },
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
      logger.error('[MSTeamsSkills] LLM Extractor: Received an empty response from AI for MS Teams message.');
      throw new Error('LLM Extractor (MS Teams): Empty response from AI.');
    }

    logger.debug('[MSTeamsSkills] LLM Extractor: Raw LLM JSON response for MS Teams:', llmResponse);
    const parsedResponse = JSON.parse(llmResponse);

    const result: Record<string, string | null> = {};
    for (const keyword of infoKeywords) {
      result[keyword] = parsedResponse.hasOwnProperty(keyword) ? parsedResponse[keyword] : null;
    }

    logger.debug('[MSTeamsSkills] LLM Extractor: Parsed and reconciled extraction from MS Teams:', result);
    return result;

  } catch (error: any) {
    logger.error('[MSTeamsSkills] LLM Extractor: Error processing information extraction from MS Teams message with OpenAI:', error.message);
    if (error instanceof SyntaxError) {
        logger.error('[MSTeamsSkills] LLM Extractor: Failed to parse JSON response from LLM for MS Teams message.');
        throw new Error('LLM Extractor (MS Teams): Failed to parse response from AI.');
    }
    const fallbackResult: Record<string, string | null> = {};
    infoKeywords.forEach(kw => fallbackResult[kw] = null);
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
  logger.debug(`[MSTeamsSkills] readMSTeamsMessage called for user ${userId}, identifier:`, identifier);

  if (!identifier.messageId || (!identifier.chatId && (!identifier.teamId || !identifier.channelId))) {
    logger.error('[MSTeamsSkills] Invalid identifier for readMSTeamsMessage. Need messageId and (chatId or teamId+channelId).');
    return null;
  }

  try {
    const responseData = await callHasuraActionGraphQL(userId, "GetMSTeamsMessageDetail", GQL_GET_MS_TEAMS_MESSAGE_DETAIL, {
      input: identifier
    });

    const getResult = responseData.getMSTeamsMessageDetail;

    if (!getResult.success || !getResult.msTeamsMessage) {
      logger.warn(`[MSTeamsSkills] getMSTeamsMessageDetail action failed or message not found for user ${userId}: ${getResult.message}`, identifier);
      return null;
    }

    // Direct cast if GraphQL output matches agent's MSTeamsMessage type.
    // Ensure nested structures like attachments and mentions are also correctly typed/mapped if needed.
    const message: MSTeamsMessage = {
        ...getResult.msTeamsMessage,
        contentType: getResult.msTeamsMessage.contentType as 'html' | 'text', // Ensure enum type if not guaranteed by GQL
         attachments: getResult.msTeamsMessage.attachments?.map((att: any) => ({
            id: att.id,
            name: att.name,
            contentType: att.contentType,
            contentUrl: att.contentUrl,
            size: att.size,
        })) || [],
        mentions: getResult.msTeamsMessage.mentions?.map((men: any) => ({
            id: men.id,
            mentionText: men.mentionText,
            mentioned: men.mentioned ? {
                user: men.mentioned.user ? {
                    id: men.mentioned.user.id,
                    displayName: men.mentioned.user.displayName,
                    userIdentityType: men.mentioned.user.userIdentityType,
                } : undefined,
            } : undefined,
        })) || [],
    };
    return message;

  } catch (error) {
    logger.error(`[MSTeamsSkills] Error in readMSTeamsMessage for user ${userId}, identifier:`, identifier, error);
    return null;
  }
}
