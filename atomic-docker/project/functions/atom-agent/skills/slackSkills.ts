import { WebClient, ErrorCode as SlackErrorCode, SlackAPIError, ConversationsListResponse, ChatPostMessageResponse } from '@slack/web-api';
import { ATOM_SLACK_BOT_TOKEN } from '../_libs/constants';
import {
    SlackSkillResponse,
    SlackChannel,
    SlackMessageData,
    ListSlackChannelsData,
    SkillError,
    SlackMessage // Import the new SlackMessage type
} from '../types';
import { logger } from '../../_utils/logger'; // Assuming logger is available
import fetch from 'node-fetch'; // For Hasura calls

// Helper to call Hasura Actions (simplified from emailSkills.ts)
const HASURA_GRAPHQL_ENDPOINT = process.env.HASURA_GRAPHQL_ENDPOINT || 'http://hasura:8080/v1/graphql'; // Use internal docker name for Hasura

const callHasuraActionGraphQL = async (userId: string, operationName: string, query: string, variables: Record<string, any>) => {
    logger.debug(`[SlackSkills] Calling Hasura Action GQL: ${operationName} for user ${userId}`);
    try {
        const response = await fetch(HASURA_GRAPHQL_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // Assuming actions are permissioned for 'user' role and expect X-Hasura-User-Id
                'X-Hasura-Role': 'user', // Or 'agent_service' if using a specific role for backend services
                'X-Hasura-User-Id': userId,
                ...(process.env.HASURA_ADMIN_SECRET && !userId ? { 'x-hasura-admin-secret': process.env.HASURA_ADMIN_SECRET } : {})
            },
            body: JSON.stringify({ query, variables }),
        });

        if (!response.ok) {
            const errorBody = await response.text();
            logger.error(`[SlackSkills] Hasura GQL call to ${operationName} failed with status ${response.status}: ${errorBody}`);
            throw new Error(`Hasura GQL call to ${operationName} failed: ${response.statusText}`);
        }
        const jsonResponse = await response.json();
        if (jsonResponse.errors) {
            logger.error(`[SlackSkills] Hasura GQL call to ${operationName} returned errors: ${JSON.stringify(jsonResponse.errors)}`);
            throw new Error(`Hasura GQL call to ${operationName} returned errors: ${jsonResponse.errors.map((e: any) => e.message).join(', ')}`);
        }
        logger.debug(`[SlackSkills] Hasura GQL call to ${operationName} successful.`);
        return jsonResponse.data;
    } catch (error) {
        logger.error(`[SlackSkills] Error calling Hasura Action GQL ${operationName}:`, error);
        throw error;
    }
};


const getSlackClient = (): WebClient | null => {
  if (!ATOM_SLACK_BOT_TOKEN) {
    logger.error('[SlackSkills] Slack Bot Token (ATOM_SLACK_BOT_TOKEN) not configured.');
    return null;
  }
  return new WebClient(ATOM_SLACK_BOT_TOKEN);
};

// Helper to determine if a string looks like a Slack ID (User, Channel, Group, IM)
function isSlackId(id: string): boolean {
    if (!id) return false;
    // Adjusted regex to be more inclusive of potential ID formats Slack might use or for flexibility
    return /^[UCGDWF][A-Z0-9]{8,10}$/.test(id);
}


export async function listSlackChannels(
  userId: string,
  limit: number = 100,
  cursor?: string
): Promise<SlackSkillResponse<ListSlackChannelsData>> {
  logger.debug(`[SlackSkills] listSlackChannels called by userId: ${userId}, limit: ${limit}, cursor: ${cursor}`);
  const client = getSlackClient();
  if (!client) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Slack Bot Token not configured.' } };
  }

  try {
    const result: ConversationsListResponse = await client.conversations.list({
      limit: limit,
      cursor: cursor,
      types: 'public_channel,private_channel,mpim,im', // Include DMs and group DMs
      exclude_archived: true,
    });

    if (!result.ok || !result.channels) {
        const slackError = result.error || 'unknown_slack_api_error';
        logger.error(`[SlackSkills] Slack API error while listing channels (result.ok is false): ${slackError}`);
        return { ok: false, error: { code: 'SLACK_API_ERROR', message: `Failed to list channels: ${slackError}`, details: result } };
    }

    return {
      ok: true,
      data: {
        channels: (result.channels as SlackChannel[]) || [],
        nextPageCursor: result.response_metadata?.next_cursor,
      }
    };
  } catch (error: any) {
    logger.error(`[SlackSkills] Error listing Slack channels for userId ${userId}:`, error);
    if (error instanceof SlackAPIError) {
      return {
        ok: false,
        error: {
          code: error.code || 'SLACK_API_ERROR',
          message: error.data?.error || error.message || 'Slack API error while listing channels',
          details: error.data
        }
      };
    }
    return {
        ok: false,
        error: {
            code: 'INTERNAL_ERROR',
            message: 'Failed to list Slack channels due to an unexpected error.',
            details: (error as Error).message
        }
    };
  }
}

async function getChannelIdByNameOrUser( // Renamed for clarity
    client: WebClient,
    identifier: string, // Can be #channel-name or @user-name (for DMs)
    userIdForContext: string
): Promise<SlackSkillResponse<string | null>> {
    logger.debug(`[SlackSkills] getChannelIdByNameOrUser called for identifier: ${identifier}`);

    if (identifier.startsWith('#')) { // Public or private channel name
        const channelName = identifier.substring(1);
        let cursor: string | undefined = undefined;
        let attempts = 0;
        try {
            while (attempts < 10) {
                const response = await listSlackChannels(userIdForContext, 200, cursor);
                if (!response.ok || !response.data?.channels) {
                    logger.error(`[SlackSkills] Error fetching channels to find ID for "#${channelName}":`, response.error);
                    return { ok: false, error: response.error || { code: 'LOOKUP_FAILED', message: 'Failed to list channels during ID lookup.'} };
                }
                const foundChannel = response.data.channels.find(ch => ch.name === channelName && (ch.is_channel || ch.is_group));
                if (foundChannel?.id) return { ok: true, data: foundChannel.id };
                cursor = response.data.nextPageCursor;
                if (!cursor) break;
                attempts++;
            }
            logger.warn(`[SlackSkills] Channel "#${channelName}" not found.`);
            return { ok: true, data: null };
        } catch (error: any) {
            logger.error(`[SlackSkills] Exception in getChannelIdByNameOrUser for "#${channelName}":`, error);
            return { ok: false, error: { code: 'INTERNAL_ERROR', message: `Exception looking up channel ID: ${error.message}`, details: error } };
        }
    } else if (identifier.startsWith('@')) { // User name for DM
        const userName = identifier.substring(1);
        try {
            // This requires users:read scope.
            // Note: client.users.lookupByEmail is an option if email is known.
            // For resolving by name, typically you list users and find a match, which can be heavy.
            // A more direct way is to use client.conversations.open with user ID.
            // If 'identifier' is a user ID (Uxxxxxxx), conversations.open is the way.
            // If it's a display name, it needs resolution first.
            // For simplicity, this example assumes if it's @name, it might be a user ID or needs prior resolution.
            // This part might need enhancement if robust name-to-ID resolution for DMs is critical here.
            // A common pattern is that the NLU provides the user ID directly.
            // For now, if it's not an ID, we can't resolve it here robustly without listing all users.
            logger.warn(`[SlackSkills] DM channel resolution for "${identifier}" by name is complex and may require prior user ID resolution. Assuming it might be a user ID for conversations.open if it's an ID.`);
            // If identifier is actually a User ID (e.g. "U012ABCDEF"), this will work for opening a DM.
             if (isSlackId(identifier)) { // If it's already a User ID
                const dmResponse = await client.conversations.open({ users: identifier });
                if (dmResponse.ok && dmResponse.channel?.id) {
                    return { ok: true, data: dmResponse.channel.id };
                } else {
                     logger.error(`[SlackSkills] Failed to open DM with user ID "${identifier}": ${dmResponse.error}`);
                     return { ok: false, error: { code: 'DM_OPEN_FAILED', message: `Could not open DM with ${identifier}. Error: ${dmResponse.error}` }};
                }
            }
            // Fallback if it was a name and not an ID - this is a simplification.
            logger.warn(`[SlackSkills] Identifier "${identifier}" for DM is not a user ID. Robust name resolution for DMs is not implemented in this helper.`);
            return { ok: true, data: null, error: { code: 'USER_RESOLUTION_NEEDED', message: `Could not resolve DM for user name ${userName} directly. User ID needed.` } };

        } catch (error: any) {
            logger.error(`[SlackSkills] Exception trying to open DM for "${identifier}":`, error);
            return { ok: false, error: { code: 'INTERNAL_ERROR', message: `Exception opening DM: ${error.message}`, details: error } };
        }
    }
    logger.warn(`[SlackSkills] Channel identifier "${identifier}" format not recognized for ID resolution (expected #channel or @user).`);
    return { ok: true, data: null }; // Identifier format not handled for name resolution
}


export async function sendSlackMessage(
  userId: string,
  channelIdentifier: string,
  text: string
): Promise<SlackSkillResponse<SlackMessageData>> {
  logger.debug(`[SlackSkills] sendSlackMessage called by userId: ${userId} to channelIdentifier: ${channelIdentifier}, text: "${text.substring(0,50)}..."`);
  const client = getSlackClient();
  if (!client) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Slack Bot Token not configured.' } };
  }

  if (!channelIdentifier || !text) {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Channel identifier and text are required.' } };
  }

  let targetChannelId = channelIdentifier;

  if (!isSlackId(channelIdentifier)) {
    logger.debug(`[SlackSkills] Channel identifier "${channelIdentifier}" is not an ID. Attempting to resolve...`);
    const idResponse = await getChannelIdByNameOrUser(client, channelIdentifier, userId);
    if (!idResponse.ok) {
        logger.error(`[SlackSkills] Failed to resolve channel identifier "${channelIdentifier}":`, idResponse.error);
        return { ok: false, error: idResponse.error || {code: 'CHANNEL_RESOLUTION_FAILED', message: `Could not resolve channel identifier ${channelIdentifier}.`} };
    }
    if (!idResponse.data) {
      logger.warn(`[SlackSkills] Channel identifier "${channelIdentifier}" not found or could not be resolved to an ID.`);
      return { ok: false, error: { code: 'CHANNEL_NOT_FOUND', message: `Channel or user "${channelIdentifier}" not found.` } };
    }
    targetChannelId = idResponse.data;
    logger.debug(`[SlackSkills] Resolved identifier "${channelIdentifier}" to ID "${targetChannelId}"`);
  }

  try {
    const result: ChatPostMessageResponse = await client.chat.postMessage({
      channel: targetChannelId,
      text: text,
    });

    if (!result.ok || !result.ts) {
        const slackError = result.error || 'unknown_slack_api_error_on_post';
        logger.error(`[SlackSkills] Slack API error sending message to channel ${targetChannelId}: ${slackError}`);
        return { ok: false, error: { code: 'SLACK_API_ERROR', message: `Failed to send message: ${slackError}`, details: result } };
    }
    logger.info(`[SlackSkills] Message sent successfully to channel ${targetChannelId} by user ${userId}. TS: ${result.ts}`);
    return {
        ok: true,
        data: {
            ts: result.ts,
            channel: result.channel,
            message: result.message as SlackMessageData['message'],
        }
    };
  } catch (error: any) {
    logger.error(`[SlackSkills] Error sending Slack message for userId ${userId} to channel ${targetChannelId}:`, error);
    if (error instanceof SlackAPIError) {
      return {
        ok: false,
        error: {
          code: error.code || 'SLACK_API_ERROR',
          message: error.data?.error || error.message || 'Slack API error sending message',
          details: error.data
        }
      };
    }
     return {
        ok: false,
        error: {
            code: 'INTERNAL_ERROR',
            message: 'Failed to send Slack message due to an unexpected error.',
            details: (error as Error).message
        }
    };
  }
}

// --- New Slack Skills for Search and Read ---

const GQL_SEARCH_SLACK_MESSAGES = `
  mutation SearchUserSlackMessages($input: SlackSearchQueryInput!) {
    searchUserSlackMessages(input: $input) {
      success
      message
      results { # Assuming 'results' is an array of objects matching AgentSlackMessage structure
        id
        threadId
        userId
        userName
        botId
        channelId
        channelName
        text
        # files { id name mimetype size url_private permalink } # Example file structure
        # reactions { name count users } # Example reaction structure
        timestamp
        permalink
        # raw # If you decide to pass the raw object
      }
    }
  }
`;

/**
 * Searches Slack messages for the user.
 * This function calls a Hasura action which in turn uses the slack-service.
 * @param userId The ID of the user making the request.
 * @param searchQuery The raw search query string (this will be constructed by LLM + helper).
 * @param limit Max number of messages to return.
 * @returns A promise resolving to an array of SlackMessage objects.
 */
export async function searchMySlackMessages(
  userId: string,
  searchQuery: string,
  limit: number = 10
): Promise<SlackMessage[]> {
  logger.debug(`[SlackSkills] searchMySlackMessages called for user ${userId}, query: "${searchQuery}", limit: ${limit}`);

  try {
    // The Hasura action 'searchUserSlackMessages' will be responsible for calling the
    // 'searchSlackMessages' function in 'slack-service.ts'.
    // The input to the Hasura action should match what 'searchSlackMessages' in service layer expects,
    // or be transformed by the Hasura action handler.
    // For now, let's assume the Hasura action takes 'query' and 'maxResults'.
    const responseData = await callHasuraActionGraphQL(userId, "SearchUserSlackMessages", GQL_SEARCH_SLACK_MESSAGES, {
        input: { query: searchQuery, maxResults: limit }
    });

    const searchResult = responseData.searchUserSlackMessages;

    if (!searchResult.success) {
      logger.error(`[SlackSkills] searchUserSlackMessages action failed for user ${userId}: ${searchResult.message}`);
      // Consider throwing an error or returning a SlackSkillResponse with error
      return [];
    }

    // Transform the results from Hasura (which should align with AgentSlackMessage from service)
    // to the SlackMessage type defined in agent/types.ts.
    // This mapping depends on the exact structure returned by the Hasura action.
    // Assuming the Hasura action's 'results' field returns objects that are already
    // very close or identical to the 'SlackMessage' interface.
    return (searchResult.results || []).map((item: any): SlackMessage => ({
      id: item.id, // ts
      threadId: item.threadId,
      userId: item.userId,
      userName: item.userName,
      botId: item.botId,
      channelId: item.channelId,
      channelName: item.channelName,
      text: item.text,
      blocks: item.blocks, // Assuming blocks are passed through if available
      files: item.files,     // Assuming files are structured as SlackMessageFile[]
      reactions: item.reactions, // Assuming reactions are structured as SlackMessageReaction[]
      timestamp: item.timestamp, // Should be ISO string
      permalink: item.permalink,
      raw: item.raw, // If raw is passed by Hasura action
    }));

  } catch (error) {
    logger.error(`[SlackSkills] Error in searchMySlackMessages for user ${userId}, query "${searchQuery}":`, error);
    return []; // Return empty or throw, or return SlackSkillResponse
  }
}

const GQL_GET_SLACK_MESSAGE_DETAIL = `
  mutation GetSlackMessageDetail($input: SlackMessageIdentifierInput!) {
    getSlackMessageDetail(input: $input) {
      success
      message
      slackMessage { # Assuming the output is a single SlackMessage object
        id
        threadId
        userId
        userName
        botId
        channelId
        channelName
        text
        blocks
        files {
          id
          created
          timestamp
          name
          title
          mimetype
          filetype
          pretty_type
          user
          editable
          size
          mode
          is_external
          external_type
          is_public
          public_url_shared
          display_as_bot
          username
          url_private
          url_private_download
          permalink
          permalink_public
        }
        reactions {
          name
          users
          count
        }
        timestamp
        permalink
        raw
      }
    }
  }
`;

/**
 * Reads the detailed content of a specific Slack message.
 * Calls a Hasura action which in turn uses the slack-service.
 * @param userId The ID of the user.
 * @param channelId The ID of the channel containing the message.
 * @param messageTs The timestamp (ID) of the message.
 * @returns A promise resolving to a SlackMessage object or null if not found/error.
 */
export async function readSlackMessage(
  userId: string,
  channelId: string,
  messageTs: string
): Promise<SlackMessage | null> {
  logger.debug(`[SlackSkills] readSlackMessage called for user ${userId}, channelId: ${channelId}, messageTs: ${messageTs}`);

  try {
    const responseData = await callHasuraActionGraphQL(userId, "GetSlackMessageDetail", GQL_GET_SLACK_MESSAGE_DETAIL, {
      input: { channelId: channelId, messageTs: messageTs }
    });

    const getResult = responseData.getSlackMessageDetail;

    if (!getResult.success || !getResult.slackMessage) {
      logger.warn(`[SlackSkills] getSlackMessageDetail action failed or message not found for user ${userId}, channel ${channelId}, ts ${messageTs}: ${getResult.message}`);
      return null;
    }

    // Assuming getResult.slackMessage is already in the desired SlackMessage format
    // If not, a transformation step similar to searchMySlackMessages would be needed.
    // For now, direct cast if the GQL output matches the SlackMessage interface.
    const messageDetail: SlackMessage = getResult.slackMessage;

    // Ensure timestamp is handled correctly (e.g., if it's numeric from Slack, convert to ISO string)
    // The AgentSlackMessage in service layer should ideally handle this transformation.
    // If slackMessage.timestamp is already an ISO string from Hasura, this is fine.
    // If it's a number (Unix epoch), it would need: new Date(item.timestamp * 1000).toISOString()

    return messageDetail;

  } catch (error) {
    logger.error(`[SlackSkills] Error in readSlackMessage for user ${userId}, channel ${channelId}, ts ${messageTs}:`, error);
    return null;
  }
}

// Reusing LLM client logic from emailSkills or a shared LLM service module would be ideal.
// For now, duplicating the client setup for clarity within this skill file.
import OpenAI from 'openai';
import { ChatCompletionMessageParam } from 'openai/resources/chat/completions';
import { ATOM_OPENAI_API_KEY, ATOM_NLU_MODEL_NAME } from '../_libs/constants';

let openAIClientForSlackExtraction: OpenAI | null = null;

function getSlackExtractionOpenAIClient(): OpenAI {
  if (openAIClientForSlackExtraction) {
    return openAIClientForSlackExtraction;
  }
  if (!ATOM_OPENAI_API_KEY) {
    logger.error('[SlackSkills] OpenAI API Key not configured for LLM Slack Extractor.');
    throw new Error('OpenAI API Key not configured for LLM Slack Extractor.');
  }
  openAIClientForSlackExtraction = new OpenAI({ apiKey: ATOM_OPENAI_API_KEY });
  logger.info('[SlackSkills] OpenAI client for Slack extraction initialized.');
  return openAIClientForSlackExtraction;
}

// System prompt for extracting info from Slack messages.
// This is very similar to the email one, but could be tailored more for Slack's typical message style (e.g. mentions, threads, emojis).
const SLACK_EXTRACTION_SYSTEM_PROMPT_TEMPLATE = `
You are an expert system designed to extract specific pieces of information from a Slack message body.
The user will provide a message body and a list of information points they are looking for (keywords).
For each keyword, find the corresponding information in the message body.
Respond ONLY with a single, valid JSON object. Do not include any explanatory text before or after the JSON.
The JSON object should have keys corresponding to the user's original keywords.
The value for each key should be the extracted information as a string.
If a specific piece of information for a keyword is not found in the message body, the value for that key should be null.

Example:
User provides keywords: ["task assigned to", "due date", "project name"]
Message body: "Hey @anna can you take on the 'UI design for Project Phoenix'? Needs to be done by next Friday."
Your JSON response:
{
  "task assigned to": "@anna",
  "due date": "next Friday",
  "project name": "Project Phoenix"
}

If information for a keyword is not found, use null for its value.
The keywords you need to extract information for are: {{KEYWORDS_JSON_ARRAY_STRING}}
Extract the information from the Slack message body provided by the user.
`;

/**
 * Uses an LLM to extract specific pieces of information from a Slack message body
 * based on a list of keywords or concepts.
 * @param messageText The plain text content of the Slack message.
 * @param infoKeywords An array of strings representing the concepts/keywords to search for.
 * @returns A Promise resolving to a record where keys are infoKeywords and values are the extracted strings (or null).
 */
export async function extractInformationFromSlackMessage(
  messageText: string,
  infoKeywords: string[]
): Promise<Record<string, string | null>> {
  if (!infoKeywords || infoKeywords.length === 0) {
    logger.debug('[SlackSkills] extractInformationFromSlackMessage: No infoKeywords provided.');
    return {};
  }
  if (!messageText || messageText.trim() === '') {
    logger.debug('[SlackSkills] extractInformationFromSlackMessage: Empty messageText provided.');
    const emptyResult: Record<string, string | null> = {};
    infoKeywords.forEach(kw => emptyResult[kw] = null);
    return emptyResult;
  }


  logger.debug(`[SlackSkills] LLM Extractor: Attempting to extract from Slack message for keywords: [${infoKeywords.join(', ')}]`);
  const client = getSlackExtractionOpenAIClient();

  const keywordsJsonArrayString = JSON.stringify(infoKeywords);
  const systemPrompt = SLACK_EXTRACTION_SYSTEM_PROMPT_TEMPLATE.replace("{{KEYWORDS_JSON_ARRAY_STRING}}", keywordsJsonArrayString);

  const messages: ChatCompletionMessageParam[] = [
    { role: 'system', content: systemPrompt },
    { role: 'user', content: `Slack Message Body:\n---\n${messageText}\n---` },
  ];

  try {
    const completion = await client.chat.completions.create({
      model: ATOM_NLU_MODEL_NAME, // Or a more capable model
      messages: messages,
      temperature: 0.1,
      response_format: { type: 'json_object' },
    });

    const llmResponse = completion.choices[0]?.message?.content;
    if (!llmResponse) {
      logger.error('[SlackSkills] LLM Extractor: Received an empty response from AI for Slack message.');
      throw new Error('LLM Extractor (Slack): Empty response from AI.');
    }

    logger.debug('[SlackSkills] LLM Extractor: Raw LLM JSON response for Slack:', llmResponse);
    const parsedResponse = JSON.parse(llmResponse);

    const result: Record<string, string | null> = {};
    for (const keyword of infoKeywords) {
      result[keyword] = parsedResponse.hasOwnProperty(keyword) ? parsedResponse[keyword] : null;
    }

    logger.debug('[SlackSkills] LLM Extractor: Parsed and reconciled extraction from Slack:', result);
    return result;

  } catch (error: any) {
    logger.error('[SlackSkills] LLM Extractor: Error processing information extraction from Slack message with OpenAI:', error.message);
    if (error instanceof SyntaxError) {
        logger.error('[SlackSkills] LLM Extractor: Failed to parse JSON response from LLM for Slack message.');
        throw new Error('LLM Extractor (Slack): Failed to parse response from AI.');
    }
    // Fallback to return null for all keywords if LLM fails
    const fallbackResult: Record<string, string | null> = {};
    infoKeywords.forEach(kw => fallbackResult[kw] = null);
    return fallbackResult;
  }
}

const GQL_GET_SLACK_MESSAGE_PERMALINK = `
  mutation GetSlackMessagePermalink($input: SlackMessageIdentifierInput!) {
    getSlackMessagePermalink(input: $input) {
      success
      message
      permalink
    }
  }
`;

/**
 * Gets a permalink for a specific Slack message.
 * Calls a Hasura action which in turn uses the slack-service.
 * @param userId The ID of the user.
 * @param channelId The ID of the channel containing the message.
 * @param messageTs The timestamp (ID) of the message.
 * @returns A promise resolving to the permalink string or null if not found/error.
 */
export async function getSlackMessagePermalink(
  userId: string,
  channelId: string,
  messageTs: string
): Promise<string | null> {
  logger.debug(`[SlackSkills] getSlackMessagePermalink called for user ${userId}, channelId: ${channelId}, messageTs: ${messageTs}`);

  try {
    const responseData = await callHasuraActionGraphQL(userId, "GetSlackMessagePermalink", GQL_GET_SLACK_MESSAGE_PERMALINK, {
      input: { channelId: channelId, messageTs: messageTs }
    });

    const getResult = responseData.getSlackMessagePermalink;

    if (!getResult.success || !getResult.permalink) {
      logger.warn(`[SlackSkills] getSlackMessagePermalink action failed or permalink not found for user ${userId}, channel ${channelId}, ts ${messageTs}: ${getResult.message}`);
      return null;
    }

    return getResult.permalink as string;

  } catch (error) {
    logger.error(`[SlackSkills] Error in getSlackMessagePermalink for user ${userId}, channel ${channelId}, ts ${messageTs}:`, error);
    return null;
  }
}
