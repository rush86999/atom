import { WebClient, ErrorCode as SlackErrorCode, SlackAPIError } from '@slack/web-api';
import { ATOM_SLACK_BOT_TOKEN } from '../atom-agent/_libs/constants'; // Assuming constants are in atom-agent/_libs
import { logger } from '../_utils/logger'; // Assuming logger is in _utils

// Basic SlackMessage interface - This will be refined later in slackSkills.ts or types.ts
export interface AgentSlackMessage {
  ts: string; // Slack message timestamp (serves as ID)
  thread_ts?: string; // Timestamp of the parent message, if in a thread
  channel?: { id: string; name?: string }; // Channel ID and optionally name
  user?: { id: string; name?: string }; // User ID and optionally name
  text?: string;
  blocks?: any[]; // Slack blocks
  files?: any[]; // Slack files
  reactions?: any[]; // Slack reactions
  permalink?: string;
  raw?: any; // Store the raw Slack message object if needed
}

let slackWebClientInstance: WebClient | null = null;

/**
 * Returns an initialized Slack WebClient.
 * For now, it returns a global client based on ATOM_SLACK_BOT_TOKEN.
 * Sets up a pattern for potential future user-specific Slack configurations.
 * @param userId The ID of the user (currently for logging/context).
 * @returns An initialized WebClient instance or null if configuration is missing.
 */
export function getSlackClientForUser(userId: string): WebClient | null {
  // userId is logged for now, but could be used for user-specific tokens in the future
  logger.debug(`[SlackService] getSlackClientForUser called for userId: ${userId}`);

  if (slackWebClientInstance) {
    return slackWebClientInstance;
  }

  if (!ATOM_SLACK_BOT_TOKEN) {
    logger.error('[SlackService] Slack Bot Token (ATOM_SLACK_BOT_TOKEN) is not configured.');
    return null;
  }

  try {
    slackWebClientInstance = new WebClient(ATOM_SLACK_BOT_TOKEN);
    logger.info('[SlackService] Slack WebClient initialized successfully.');
    return slackWebClientInstance;
  } catch (error) {
    logger.error('[SlackService] Failed to initialize Slack WebClient:', error);
    return null;
  }
}

/**
 * Searches Slack messages using the search.messages API.
 * @param userId The ID of the user (for logging/context).
 *   client.search.messages({ query, count, page })
 * @param query The search query string (compatible with Slack's search syntax).
 * @param maxResults Desired maximum number of results. Pagination will be handled to try to meet this.
 * @returns A promise resolving to an array of AgentSlackMessage objects.
 * @throws Error if the Slack client is not configured or if the API call fails.
 */
export async function searchSlackMessages(
  userId: string,
  query: string,
  maxResults: number = 20
): Promise<AgentSlackMessage[]> {
  logger.debug(`[SlackService] searchSlackMessages called for userId: ${userId}, query: "${query}", maxResults: ${maxResults}`);
  const client = getSlackClientForUser(userId);
  if (!client) {
    throw new Error('[SlackService] Slack client is not available. Check configuration.');
  }

  const messages: AgentSlackMessage[] = [];
  let currentPage = 1;
  const countPerPage = Math.min(maxResults, 100); // Slack's max count for search.messages is often 100

  try {
    while (messages.length < maxResults) {
      const response = await client.search.messages({
        query: query,
        count: countPerPage,
        page: currentPage,
        sort: 'timestamp', // Sort by relevance (score) or timestamp
        sort_dir: 'desc',  // 'desc' for newest first if sorting by timestamp
      });

      if (!response.ok || !response.messages?.matches) {
        const errorMsg = `Slack API error during search: ${response.error || 'Unknown error'}`;
        logger.error(`[SlackService] ${errorMsg}`, response);
        // If it's a critical error, or first page fails, throw. Otherwise, might return what we have.
        if (currentPage === 1) throw new Error(errorMsg);
        else break; // Stop if subsequent pages fail
      }

      const matches = response.messages.matches;
      for (const match of matches) {
        if (messages.length >= maxResults) break;

        // Basic transformation - this will be improved when AgentSlackMessage is finalized
        messages.push({
          ts: match.ts!, // ts is message ID
          thread_ts: match.thread_ts,
          channel: { id: match.channel?.id!, name: match.channel?.name },
          user: { id: match.user!, name: match.username || match.user }, // Prefer username, fallback to user ID
          text: match.text,
          permalink: match.permalink,
          raw: match, // Store the raw match for now
        });
      }

      // Check for pagination: Slack's search.messages pagination is based on 'page' number.
      // We stop if we have enough messages, if there are no more results, or if we fetched fewer than requested (implies end).
      const totalPages = response.messages.paging?.total_pages || currentPage;
      if (messages.length >= maxResults || currentPage >= totalPages || matches.length < countPerPage) {
        break;
      }
      currentPage++;
    }
    logger.info(`[SlackService] Found ${messages.length} messages for query "${query}" for user ${userId}.`);
    return messages;
  } catch (error: any) {
    logger.error(`[SlackService] Error during searchSlackMessages for userId ${userId}, query "${query}":`, error);
    if (error instanceof SlackAPIError) {
      throw new Error(`[SlackService] Slack API Error (${error.code}): ${error.data?.error || error.message}`);
    }
    throw error; // Re-throw other errors
  }
}

/**
 * Fetches the content of a specific Slack message.
 * Uses conversations.history with latest, oldest, and inclusive flags to pinpoint the message.
 * @param userId The ID of the user (for logging/context).
 * @param channelId The ID of the channel where the message resides.
 * @param messageTs The timestamp (ID) of the message to fetch.
 * @returns A promise resolving to an AgentSlackMessage object or null if not found/error.
 * @throws Error if the Slack client is not configured or if the API call fails critically.
 */
export async function getSlackMessageContent(
  userId: string,
  channelId: string,
  messageTs: string
): Promise<AgentSlackMessage | null> {
  logger.debug(`[SlackService] getSlackMessageContent called for userId: ${userId}, channelId: ${channelId}, messageTs: ${messageTs}`);
  const client = getSlackClientForUser(userId);
  if (!client) {
    throw new Error('[SlackService] Slack client is not available. Check configuration.');
  }

  if (!channelId || !messageTs) {
    logger.warn('[SlackService] getSlackMessageContent: channelId or messageTs is missing.');
    return null;
  }

  try {
    const response = await client.conversations.history({
      channel: channelId,
      latest: messageTs,
      oldest: messageTs, // Fetch just this one message
      inclusive: true,
      limit: 1,
    });

    if (!response.ok || !response.messages || response.messages.length === 0) {
      const errorMsg = `Slack API error fetching message content: ${response.error || 'Message not found or no content'}`;
      logger.warn(`[SlackService] ${errorMsg} for channel ${channelId}, ts ${messageTs}`, response);
      return null;
    }

    const rawMessage = response.messages[0];

    // TODO: Potentially fetch user info here to populate user.name if not available in message object.
    // const userInfo = await client.users.info({ user: rawMessage.user });
    // const userName = userInfo.ok ? userInfo.user.real_name || userInfo.user.name : rawMessage.user;

    // Basic transformation - to be refined
    const message: AgentSlackMessage = {
      ts: rawMessage.ts!,
      thread_ts: rawMessage.thread_ts,
      channel: { id: channelId }, // We know channelId, name might need separate lookup or come from elsewhere
      user: { id: rawMessage.user!, name: rawMessage.user }, // Placeholder for name, ideally resolve user ID
      text: rawMessage.text,
      blocks: rawMessage.blocks,
      files: rawMessage.files,
      reactions: rawMessage.reactions,
      // permalink: will be fetched by getSlackPermalink if needed
      raw: rawMessage,
    };
    logger.debug(`[SlackService] Successfully fetched message content for ts ${messageTs} in channel ${channelId}`);
    return message;

  } catch (error: any) {
    logger.error(`[SlackService] Error in getSlackMessageContent for channel ${channelId}, ts ${messageTs}:`, error);
    if (error instanceof SlackAPIError) {
      // Specific Slack errors like 'message_not_found', 'channel_not_found' can be handled here
      if (error.code === SlackErrorCode.MessageNotFound || error.code === SlackErrorCode.ChannelNotFound) {
        return null;
      }
      throw new Error(`[SlackService] Slack API Error (${error.code}) fetching message content: ${error.data?.error || error.message}`);
    }
    throw error; // Re-throw other errors
  }
}

/**
 * Fetches a permalink for a specific Slack message.
 * @param userId The ID of the user (for logging/context).
 * @param channelId The ID of the channel where the message resides.
 * @param messageTs The timestamp (ID) of the message.
 * @returns A promise resolving to the permalink string or null if not found/error.
 * @throws Error if the Slack client is not configured or if the API call fails critically.
 */
export async function getSlackPermalink(
  userId: string,
  channelId: string,
  messageTs: string
): Promise<string | null> {
  logger.debug(`[SlackService] getSlackPermalink called for userId: ${userId}, channelId: ${channelId}, messageTs: ${messageTs}`);
  const client = getSlackClientForUser(userId);
  if (!client) {
    throw new Error('[SlackService] Slack client is not available. Check configuration.');
  }

  if (!channelId || !messageTs) {
    logger.warn('[SlackService] getSlackPermalink: channelId or messageTs is missing.');
    return null;
  }

  try {
    const response = await client.chat.getPermalink({
      channel: channelId,
      message_ts: messageTs,
    });

    if (!response.ok || !response.permalink) {
      const errorMsg = `Slack API error fetching permalink: ${response.error || 'Permalink not found'}`;
      logger.warn(`[SlackService] ${errorMsg} for channel ${channelId}, ts ${messageTs}`, response);
      return null;
    }

    logger.debug(`[SlackService] Successfully fetched permalink for ts ${messageTs} in channel ${channelId}`);
    return response.permalink as string;

  } catch (error: any) {
    logger.error(`[SlackService] Error in getSlackPermalink for channel ${channelId}, ts ${messageTs}:`, error);
    if (error instanceof SlackAPIError) {
      if (error.code === SlackErrorCode.MessageNotFound || error.code === SlackErrorCode.ChannelNotFound) {
        return null;
      }
      throw new Error(`[SlackService] Slack API Error (${error.code}) fetching permalink: ${error.data?.error || error.message}`);
    }
    throw error; // Re-throw other errors
  }
}
