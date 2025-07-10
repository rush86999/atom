import { WebClient, ErrorCode as SlackErrorCode, SlackAPIError, ConversationsListResponse, ChatPostMessageResponse } from '@slack/web-api';
import { ATOM_SLACK_BOT_TOKEN } from '../_libs/constants';
import {
    SlackSkillResponse,
    SlackChannel,
    SlackMessageData,
    ListSlackChannelsData,
    SkillError,
    SlackMessage
} from '../types';
import { logger } from '../../_utils/logger';

const getSlackClient = (): WebClient | null => {
  if (!ATOM_SLACK_BOT_TOKEN) {
    logger.error('[SlackSkills] Slack Bot Token (ATOM_SLACK_BOT_TOKEN) not configured.');
    return null;
  }
  return new WebClient(ATOM_SLACK_BOT_TOKEN);
};

// Helper to determine if a string looks like a Slack ID
function isSlackId(id: string): boolean {
    if (!id) return false;
    return /^[UCGDWF][A-Z0-9]{8,10}$/.test(id);
}

// --- Helper function to enrich Slack messages with user and channel names ---
async function _enrichSlackMessagesWithNames(
  client: WebClient,
  messages: SlackMessage[],
  userCache: Map<string, string | null>,
  channelCache: Map<string, string | null>
): Promise<SlackMessage[]> {
  const userIdsToFetch = new Set<string>();
  const channelIdsToFetch = new Set<string>();

  for (const msg of messages) {
    if (msg.userId && !msg.userName && !userCache.has(msg.userId)) {
      userIdsToFetch.add(msg.userId);
    }
    if (msg.botId && !msg.userName && !userCache.has(msg.botId)) { // Also try to resolve bot names
        userIdsToFetch.add(msg.botId); // Slack's users.info works for bot IDs too
    }
    if (msg.channelId && !msg.channelName && !channelCache.has(msg.channelId)) {
      channelIdsToFetch.add(msg.channelId);
    }
  }

  if (userIdsToFetch.size > 0) {
    logger.debug(`[SlackSkills_Enrich] Fetching info for ${userIdsToFetch.size} user/bot IDs.`);
    await Promise.allSettled(
      Array.from(userIdsToFetch).map(async (uid) => {
        if (userCache.has(uid)) return;
        try {
          const response = await client.users.info({ user: uid });
          if (response.ok && response.user) {
            userCache.set(uid, response.user.real_name || response.user.name || uid);
          } else {
            // Check for bot_info if users.info fails for a bot_id
            if (uid.startsWith('B')) { // Heuristic for bot ID
                try {
                    const botInfo = await client.bots.info({bot: uid});
                    if (botInfo.ok && botInfo.bot) {
                         userCache.set(uid, (botInfo.bot as any).name || uid); // bot.name
                    } else {
                        logger.warn(`[SlackSkills_Enrich] bots.info call not ok for bot ${uid}: ${botInfo.error}`);
                        userCache.set(uid, uid);
                    }
                } catch (botError: any) {
                    logger.warn(`[SlackSkills_Enrich] Failed to fetch info for bot ${uid} via bots.info: ${botError.message}`);
                    userCache.set(uid, uid);
                }
            } else {
                logger.warn(`[SlackSkills_Enrich] users.info call not ok for ${uid}: ${response.error}`);
                userCache.set(uid, uid);
            }
          }
        } catch (e: any) {
          logger.warn(`[SlackSkills_Enrich] Failed to fetch info for user/bot ${uid}: ${e.message}`);
          userCache.set(uid, uid);
        }
      })
    );
  }

  if (channelIdsToFetch.size > 0) {
    logger.debug(`[SlackSkills_Enrich] Fetching info for ${channelIdsToFetch.size} channel IDs.`);
    await Promise.allSettled(
      Array.from(channelIdsToFetch).map(async (cid) => {
        if (channelCache.has(cid)) return;
        try {
          const convInfo = await client.conversations.info({ channel: cid });
          if (convInfo.ok && convInfo.channel) {
            let cName = (convInfo.channel as any).name;
            if (!cName && (convInfo.channel as any).is_im && (convInfo.channel as any).user) {
              const otherUserId = (convInfo.channel as any).user;
              if (userCache.has(otherUserId)) {
                cName = userCache.get(otherUserId) || otherUserId;
              } else {
                try {
                  const dmUserInfo = await client.users.info({ user: otherUserId });
                  if (dmUserInfo.ok && dmUserInfo.user) {
                    const name = dmUserInfo.user.real_name || dmUserInfo.user.name || otherUserId;
                    userCache.set(otherUserId, name);
                    cName = name;
                  } else { cName = otherUserId; }
                } catch (userFetchErr) {
                  logger.warn(`[SlackSkills_Enrich] Failed to fetch user info for DM partner ${otherUserId} in channel ${cid}`);
                  cName = otherUserId;
                }
              }
            }
            channelCache.set(cid, cName || cid);
          } else {
            logger.warn(`[SlackSkills_Enrich] conversations.info call not ok for ${cid}: ${convInfo.error}`);
            channelCache.set(cid, cid);
          }
        } catch (e: any) {
          logger.warn(`[SlackSkills_Enrich] Failed to fetch info for channel ${cid}: ${e.message}`);
          channelCache.set(cid, cid);
        }
      })
    );
  }

  return messages.map(msg => {
    const enrichedMsg = { ...msg };
    if (msg.userId && userCache.has(msg.userId)) {
      enrichedMsg.userName = userCache.get(msg.userId) || msg.userId;
    } else if (msg.botId && userCache.has(msg.botId)) { // Check botId against userCache too
      enrichedMsg.userName = userCache.get(msg.botId) || msg.botId; // Bot name
    } else if (msg.userId) {
      enrichedMsg.userName = msg.userId;
    } else if (msg.botId) {
      enrichedMsg.userName = `Bot (${msg.botId})`;
    }


    if (msg.channelId && channelCache.has(msg.channelId)) {
      enrichedMsg.channelName = channelCache.get(msg.channelId) || msg.channelId;
    } else if (msg.channelId && !enrichedMsg.channelName) {
      enrichedMsg.channelName = msg.channelId;
    }
    return enrichedMsg;
  });
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
      types: 'public_channel,private_channel,mpim,im',
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

async function getChannelIdByNameOrUser(
    client: WebClient,
    identifier: string,
    userIdForContext: string
): Promise<SlackSkillResponse<string | null>> {
    logger.debug(`[SlackSkills] getChannelIdByNameOrUser called for identifier: ${identifier}`);

    if (identifier.startsWith('#')) {
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
    } else if (identifier.startsWith('@')) {
        const userNameOrId = identifier.substring(1);
        try {
             if (isSlackId(userNameOrId)) {
                const dmResponse = await client.conversations.open({ users: userNameOrId });
                if (dmResponse.ok && dmResponse.channel?.id) {
                    return { ok: true, data: dmResponse.channel.id };
                } else {
                     logger.error(`[SlackSkills] Failed to open DM with user ID "${userNameOrId}": ${dmResponse.error}`);
                     return { ok: false, error: { code: 'DM_OPEN_FAILED', message: `Could not open DM with ${userNameOrId}. Error: ${dmResponse.error}` }};
                }
            }
            logger.warn(`[SlackSkills] Identifier "${identifier}" for DM is not a user ID. Robust name-to-ID resolution for DMs is not implemented in this helper.`);
            return { ok: true, data: null, error: { code: 'USER_RESOLUTION_NEEDED', message: `Could not resolve DM for user name ${userNameOrId} directly. User ID needed.` } };

        } catch (error: any) {
            logger.error(`[SlackSkills] Exception trying to open DM for "${identifier}":`, error);
            return { ok: false, error: { code: 'INTERNAL_ERROR', message: `Exception opening DM: ${error.message}`, details: error } };
        }
    }
    logger.warn(`[SlackSkills] Channel identifier "${identifier}" format not recognized for ID resolution (expected #channel or @user).`);
    return { ok: true, data: null };
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

/**
 * Searches Slack messages for the user using the Slack Web API.
 * @param atomUserId The Atom internal ID of the user making the request (for logging/context).
 * @param searchQuery The Slack API compatible search query string.
 * @param limit Max number of messages to return.
 * @returns A promise resolving to an array of SlackMessage objects.
 */
export async function searchMySlackMessages(
  atomUserId: string,
  searchQuery: string,
  limit: number = 10
): Promise<SlackMessage[]> {
  logger.debug(`[SlackSkills] searchMySlackMessages direct API call for Atom user ${atomUserId}, query: "${searchQuery}", limit: ${limit}`);

  const client = getSlackClient();
  if (!client) {
    logger.error('[SlackSkills] Slack client not available for searchMySlackMessages.');
    return [];
  }

  try {
    const response = await client.search.messages({
      query: searchQuery,
      count: limit,
      sort: 'timestamp',
      sort_dir: 'desc',
    });

    if (!response.ok || !response.messages?.matches) {
      const slackError = (response as any).error || 'unknown_slack_search_error';
      logger.error(`[SlackSkills] Slack API error during search.messages: ${slackError}`, response);
      return [];
    }

    let results: SlackMessage[] = (response.messages.matches || []).map((match: any ): SlackMessage => {
      return {
        id: match.ts,
        threadId: match.thread_ts || undefined,
        userId: match.user,
        userName: match.username || match.user,
        botId: match.bot_id,
        channelId: match.channel?.id,
        channelName: match.channel?.name || match.channel?.id,
        text: match.text,
        blocks: match.blocks,
        files: match.files,
        reactions: match.reactions,
        timestamp: new Date(parseFloat(match.ts) * 1000).toISOString(),
        permalink: match.permalink,
        raw: match,
      };
    });

    if (results.length > 0) {
        const userCache = new Map<string, string | null>();
        const channelCache = new Map<string, string | null>();
        results = await _enrichSlackMessagesWithNames(client, results, userCache, channelCache);
    }

    logger.info(`[SlackSkills] searchMySlackMessages direct API call found and enriched ${results.length} messages.`);
    return results;

  } catch (error: any) {
    logger.error(`[SlackSkills] Error in searchMySlackMessages direct API call for Atom user ${atomUserId}, query "${searchQuery}":`, error);
    if (error instanceof SlackAPIError) {
      logger.error(`[SlackSkills] SlackAPIError code: ${error.code}, data:`, error.data);
    }
    return [];
  }
}

/**
 * Reads the detailed content of a specific Slack message using Slack Web API.
 * @param atomUserId The Atom internal ID of the user (for logging/context).
 * @param channelId The ID of the channel containing the message.
 * @param messageTs The timestamp (ID) of the message.
 * @returns A promise resolving to a SlackMessage object or null if not found/error.
 */
export async function readSlackMessage(
  atomUserId: string,
  channelId: string,
  messageTs: string
): Promise<SlackMessage | null> {
  logger.debug(`[SlackSkills] readSlackMessage direct API call for Atom user ${atomUserId}, channelId: ${channelId}, messageTs: ${messageTs}`);

  const client = getSlackClient();
  if (!client) {
    logger.error('[SlackSkills] Slack client not available for readSlackMessage.');
    return null;
  }

  try {
    const response = await client.conversations.history({
      channel: channelId,
      latest: messageTs,
      oldest: messageTs,
      inclusive: true,
      limit: 1,
    });

    if (!response.ok || !response.messages || response.messages.length === 0) {
      const slackError = (response as any).error || 'message_not_found_or_access_denied';
      logger.warn(`[SlackSkills] Slack API error or message not found during conversations.history for ts ${messageTs} in channel ${channelId}: ${slackError}`, response);
      return null;
    }

    const msgData = response.messages[0] as any;

    let permalink;
    try {
        const permalinkResponse = await client.chat.getPermalink({ channel: channelId, message_ts: msgData.ts! });
        if (permalinkResponse.ok && permalinkResponse.permalink) {
            permalink = permalinkResponse.permalink as string;
        }
    } catch (permalinkError) {
        logger.warn(`[SlackSkills] Could not fetch permalink for message ${msgData.ts} in channel ${channelId}:`, permalinkError);
    }

    let message: SlackMessage = {
      id: msgData.ts!,
      threadId: msgData.thread_ts || undefined,
      userId: msgData.user,
      userName: msgData.username || msgData.user,
      botId: msgData.bot_id,
      channelId: channelId,
      channelName: channelId, // Placeholder
      text: msgData.text,
      blocks: msgData.blocks,
      files: msgData.files,
      reactions: msgData.reactions,
      timestamp: new Date(parseFloat(msgData.ts!) * 1000).toISOString(),
      permalink: permalink,
      raw: msgData,
    };

    const userCache = new Map<string, string | null>();
    const channelCache = new Map<string, string | null>();
    const enrichedMessages = await _enrichSlackMessagesWithNames(client, [message], userCache, channelCache);

    logger.info(`[SlackSkills] Successfully read and enriched Slack message ${messageTs} from channel ${channelId}.`);
    return enrichedMessages.length > 0 ? enrichedMessages[0] : null;

  } catch (error: any) {
    logger.error(`[SlackSkills] Error in readSlackMessage direct API call for Atom user ${atomUserId}, channel ${channelId}, ts ${messageTs}:`, error);
    if (error instanceof SlackAPIError) {
      logger.error(`[SlackSkills] SlackAPIError code: ${error.code}, data:`, error.data);
    }
    return null;
  }
}

// ... LLM extraction code and getRecentDMsAndMentionsForBriefing follow ...
// getRecentDMsAndMentionsForBriefing will also benefit from enriched messages returned by searchMySlackMessages.

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
    infoKeywords.forEach(kw => emptyResult[kw] = null);
    return fallbackResult;
  }
}

export async function getRecentDMsAndMentionsForBriefing(
  atomUserId: string, // Atom's internal user ID
  targetDate: Date,
  count: number = 3
): Promise<SlackSkillResponse<{ results: SlackMessage[], query_executed?: string }>> {
  logger.debug(`[SlackSkills] getRecentDMsAndMentionsForBriefing for Atom user: ${atomUserId}, TargetDate: ${targetDate.toISOString().split('T')[0]}, Count: ${count}`);

  const client = getSlackClient();
  if (!client) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Slack Bot Token not configured.' } };
  }

  try {
    let userSlackId: string | undefined;
    try {
      const authTestResponse = await client.auth.test();
      if (authTestResponse.ok && authTestResponse.user_id) {
        userSlackId = authTestResponse.user_id;
        logger.info(`[SlackSkills] Resolved Slack user ID for search: ${userSlackId}`);
      } else {
        logger.warn(`[SlackSkills] Could not resolve Slack user ID via auth.test. Mentions search might be impacted. Error: ${authTestResponse.error}`);
      }
    } catch (authError: any) {
       logger.warn(`[SlackSkills] Exception during client.auth.test: ${authError.message}. Mentions search might be impacted.`);
    }

    const formatDateForSlack = (date: Date): string => {
      const year = date.getUTCFullYear();
      const month = (date.getUTCMonth() + 1).toString().padStart(2, '0');
      const day = date.getUTCDate().toString().padStart(2, '0');
      return `${year}-${month}-${day}`;
    };

    const afterDate = new Date(targetDate);
    afterDate.setUTCHours(0, 0, 0, 0);
    const beforeDate = new Date(targetDate);
    beforeDate.setUTCHours(0, 0, 0, 0);
    beforeDate.setUTCDate(targetDate.getUTCDate() + 1);

    let querySegments: string[] = [];
    if (userSlackId) {
      querySegments.push(`(@${userSlackId} OR to:${userSlackId} OR in:${userSlackId})`);
    } else {
      querySegments.push(`(is:dm)`);
      logger.warn("[SlackSkills] No specific Slack User ID for DMs/Mentions search, results might be less targeted if using a bot token without specific user context for DMs.");
    }

    querySegments.push(`after:${formatDateForSlack(afterDate)}`);
    querySegments.push(`before:${formatDateForSlack(beforeDate)}`);

    const searchQuery = querySegments.join(' ');
    const fullSearchQueryWithSort = `${searchQuery} sort:timestamp dir:desc`;

    logger.info(`[SlackSkills] Constructed Slack search query for briefing: "${fullSearchQueryWithSort}"`);

    const searchResults: SlackMessage[] = await searchMySlackMessages(atomUserId, fullSearchQueryWithSort, count);

    logger.info(`[SlackSkills] Found ${searchResults.length} Slack messages for briefing.`);
    return { ok: true, data: { results: searchResults, query_executed: fullSearchQueryWithSort } };

  } catch (error: any) {
    logger.error(`[SlackSkills] Error in getRecentDMsAndMentionsForBriefing for Atom user ${atomUserId}: ${error.message}`, error);
    return {
      ok: false,
      error: { code: 'SLACK_BRIEFING_FETCH_FAILED', message: error.message || "Failed to fetch recent DMs/mentions for briefing." }
    };
  }
}

/**
 * Gets a permalink for a specific Slack message using the Slack Web API.
 * @param atomUserId The Atom internal ID of the user (for logging/context).
 * @param channelId The ID of the channel containing the message.
 * @param messageTs The timestamp (ID) of the message.
 * @returns A promise resolving to the permalink string or null if not found/error.
 */
export async function getSlackMessagePermalink(
  atomUserId: string, // Atom user ID for context
  channelId: string,
  messageTs: string
): Promise<string | null> {
  logger.debug(`[SlackSkills] getSlackMessagePermalink direct API call for Atom user ${atomUserId}, channelId: ${channelId}, messageTs: ${messageTs}`);

  const client = getSlackClient();
  if (!client) {
    logger.error('[SlackSkills] Slack client not available for getSlackMessagePermalink.');
    return null;
  }

  try {
    const response = await client.chat.getPermalink({
      channel: channelId,
      message_ts: messageTs,
    });

    if (!response.ok || !response.permalink) {
      const slackError = (response as any).error || 'permalink_not_found';
      logger.warn(`[SlackSkills] Slack API error or permalink not found for ts ${messageTs} in channel ${channelId}: ${slackError}`, response);
      return null;
    }
    logger.info(`[SlackSkills] Successfully fetched permalink for message ${messageTs}.`);
    return response.permalink as string;

  } catch (error: any) {
    logger.error(`[SlackSkills] Error in getSlackMessagePermalink direct API call for Atom user ${atomUserId}, channel ${channelId}, ts ${messageTs}:`, error);
     if (error instanceof SlackAPIError) {
      logger.error(`[SlackSkills] SlackAPIError code: ${error.code}, data:`, error.data);
    }
    return null;
  }
}
