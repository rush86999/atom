import {
  StructuredSlackQuery,
  understandSlackSearchQueryLLM,
} from '../skills/llm_slack_query_understander';
import { buildSlackSearchQuery } from '../skills/nlu_slack_helper';
import {
  searchMySlackMessages,
  readSlackMessage,
  extractInformationFromSlackMessage,
  getSlackMessagePermalink,
} from '../skills/slackSkills';
import { SlackMessage } from '../types'; // Assuming SlackMessage is in global types
import { logger } from '../../_utils/logger';

export type SlackActionType =
  | 'GET_SLACK_MESSAGE_CONTENT'
  | 'FIND_INFO_IN_SLACK_MESSAGE'
  | 'GET_SLACK_MESSAGE_LINK'
  | 'SUMMARIZE_SLACK_MESSAGE'; // Future capability

export interface SlackActionRequest {
  actionType: SlackActionType;
  infoKeywords?: string[]; // For FIND_INFO_IN_SLACK_MESSAGE
  naturalLanguageQuestion?: string; // Could be used by LLM for more nuanced extraction
}

export interface ParsedNluSlackRequest {
  userId: string;
  rawSlackSearchQuery: string; // e.g., "messages from Jane about Q3 report last week in #general"
  actionRequested: SlackActionRequest;
  targetChannelId?: string; // Optional: if NLU identified a specific channel ID
  targetMessageTs?: string; // Optional: if NLU identified a specific message TS
}

/**
 * Handles a generic Slack inquiry: understands the search query using an LLM,
 * finds a message, and performs an action on it (e.g., extracts info, gets content, gets link).
 */
export async function handleSlackInquiry(
  request: ParsedNluSlackRequest
): Promise<string> {
  const {
    userId,
    rawSlackSearchQuery,
    actionRequested,
    targetChannelId,
    targetMessageTs,
  } = request;
  let messageToUser = '';

  logger.debug(
    `[SlackCommandHandler] Handling Slack inquiry for user ${userId}:`,
    request
  );

  try {
    let targetMessage: SlackMessage | null = null;

    // Step 1: Obtain the target message (either by ID/TS or by searching)
    if (targetChannelId && targetMessageTs) {
      logger.info(
        `[SlackCommandHandler] Attempting to read specified Slack message: Channel ${targetChannelId}, TS ${targetMessageTs}`
      );
      targetMessage = await readSlackMessage(
        userId,
        targetChannelId,
        targetMessageTs
      );
      if (!targetMessage) {
        messageToUser = `Sorry, I couldn't find or read the specific Slack message you referred to (Channel: ${targetChannelId}, TS: ${targetMessageTs}).`;
        logger.warn(
          `[SlackCommandHandler] Failed to read specific message: ${messageToUser}`
        );
        return messageToUser;
      }
    } else {
      logger.info(
        `[SlackCommandHandler] Understanding Slack search query: "${rawSlackSearchQuery}"`
      );
      const structuredSearchParams: Partial<StructuredSlackQuery> =
        await understandSlackSearchQueryLLM(rawSlackSearchQuery);

      if (
        Object.keys(structuredSearchParams).length === 0 &&
        !rawSlackSearchQuery.toLowerCase().includes('latest')
      ) {
        // If LLM returns empty and it's not a query for "latest" (which might imply broad search)
        messageToUser =
          "I couldn't determine specific search criteria from your Slack request. Could you be more precise?";
        logger.warn(
          `[SlackCommandHandler] LLM returned empty search params for query: "${rawSlackSearchQuery}"`
        );
        return messageToUser;
      }

      const slackApiQueryString = buildSlackSearchQuery(structuredSearchParams);
      logger.info(
        `[SlackCommandHandler] Searching Slack messages with LLM-derived query: "${slackApiQueryString}" (Limit 5)`
      );
      // TODO: The limit for searchMySlackMessages might need to be adjusted based on context or NLU.
      // If the user asks for "the latest message from X", limit should be 1.
      const messagesFound = await searchMySlackMessages(
        userId,
        slackApiQueryString,
        5
      );

      if (!messagesFound || messagesFound.length === 0) {
        messageToUser =
          "I couldn't find any Slack messages matching your criteria based on my understanding of your request.";
        logger.info(
          `[SlackCommandHandler] No messages found for query: "${slackApiQueryString}"`
        );
        return messageToUser;
      }

      if (
        messagesFound.length > 1 &&
        actionRequested.actionType !== 'FIND_INFO_IN_SLACK_MESSAGE'
      ) {
        // If multiple messages found and the action isn't a broad search for info (which might process multiple), ask for clarification.
        // For FIND_INFO_IN_SLACK_MESSAGE, we might iterate or pick the most relevant one later.
        messageToUser =
          'I found a few Slack messages matching your criteria:\n';
        messagesFound.slice(0, 3).forEach((msg, index) => {
          const msgTextPreview = msg.text
            ? msg.text.length > 50
              ? msg.text.substring(0, 47) + '...'
              : msg.text
            : 'No text content';
          messageToUser += `${index + 1}. From ${msg.userName || msg.userId || 'Unknown User'} in ${msg.channelName || msg.channelId || 'Unknown Channel'}: "${msgTextPreview}" (TS: ...${msg.id.slice(-6)})\n`;
        });
        if (messagesFound.length > 3) {
          messageToUser += `And ${messagesFound.length - 3} more.\n`;
        }
        messageToUser +=
          'Which one are you interested in? You can tell me the number or provide more details (like its timestamp).';
        logger.info(
          `[SlackCommandHandler] Multiple messages found, clarification needed.`
        );
        return messageToUser;
      }
      // If one message found, or if the action is FIND_INFO and we'll process the first/most_relevant one.
      targetMessage = messagesFound[0];
      logger.info(
        `[SlackCommandHandler] Single message identified for processing. TS: ${targetMessage.id}`
      );
      // Ensure full content is loaded if it was a search result (might be partial)
      if (
        targetMessage.channelId &&
        targetMessage.id &&
        !targetMessage.raw?.blocks
      ) {
        // Heuristic: if blocks are missing, it might be a summary
        logger.debug(
          `[SlackCommandHandler] Search result for ${targetMessage.id} seems partial, fetching full content.`
        );
        const fullMessage = await readSlackMessage(
          userId,
          targetMessage.channelId,
          targetMessage.id
        );
        if (fullMessage) targetMessage = fullMessage;
        else
          logger.warn(
            `[SlackCommandHandler] Failed to fetch full content for partial message ${targetMessage.id}`
          );
      }
    }

    if (!targetMessage) {
      messageToUser =
        "I couldn't identify a specific Slack message to process with the information provided.";
      logger.warn(
        `[SlackCommandHandler] No target message identified after search/direct lookup.`
      );
      return messageToUser;
    }

    // Step 2: Perform the requested action on the targetMessage
    const messageDescForResponse =
      `the message from ${targetMessage.userName || targetMessage.userId || 'Unknown User'}` +
      (targetMessage.channelName
        ? ` in ${targetMessage.channelName}`
        : targetMessage.channelId
          ? ` in channel ${targetMessage.channelId}`
          : '');

    switch (actionRequested.actionType) {
      case 'GET_SLACK_MESSAGE_CONTENT':
        const bodyPreview = targetMessage.text
          ? targetMessage.text.length > 200
            ? targetMessage.text.substring(0, 197) + '...'
            : targetMessage.text
          : 'it appears to have no readable text content.';
        messageToUser = `The content of ${messageDescForResponse} (TS: ...${targetMessage.id.slice(-6)}) starts with: "${bodyPreview}".`;
        break;

      case 'FIND_INFO_IN_SLACK_MESSAGE':
        if (!targetMessage.text) {
          messageToUser = `${messageDescForResponse} (TS: ...${targetMessage.id.slice(-6)}) doesn't seem to have any text content for me to analyze.`;
          break;
        }
        const keywordsToExtract = actionRequested.infoKeywords || [];
        // const nlQuestion = actionRequested.naturalLanguageQuestion; // For future enhancement

        if (keywordsToExtract.length === 0) {
          messageToUser = `You asked me to find specific information in ${messageDescForResponse}, but didn't specify what to look for.`;
          break;
        }
        logger.info(
          `[SlackCommandHandler] Extracting info for keywords [${keywordsToExtract.join(', ')}] from message TS ${targetMessage.id}`
        );
        const extractedInfo = await extractInformationFromSlackMessage(
          targetMessage.text,
          keywordsToExtract
        );
        let foundAny = false;
        let responseParts: string[] = [
          `Regarding ${messageDescForResponse} (TS: ...${targetMessage.id.slice(-6)}):`,
        ];

        for (const keyword of keywordsToExtract) {
          const resultValue = extractedInfo[keyword];
          if (resultValue) {
            responseParts.push(`- For "${keyword}", I found: ${resultValue}.`);
            foundAny = true;
          } else {
            responseParts.push(
              `- I couldn't find specific information about "${keyword}".`
            );
          }
        }
        if (!foundAny && keywordsToExtract.length > 0) {
          messageToUser = `I scanned ${messageDescForResponse} (TS: ...${targetMessage.id.slice(-6)}) for information related to "${keywordsToExtract.join(', ')}", but couldn't find those specific details.`;
        } else {
          messageToUser = responseParts.join('\n');
        }
        break;

      case 'GET_SLACK_MESSAGE_LINK':
        if (!targetMessage.channelId || !targetMessage.id) {
          messageToUser = `I'm sorry, I don't have enough information (channel ID or message ID) to get a link for ${messageDescForResponse}.`;
          break;
        }
        logger.info(
          `[SlackCommandHandler] Getting permalink for message TS ${targetMessage.id} in channel ${targetMessage.channelId}`
        );
        const permalink = await getSlackMessagePermalink(
          userId,
          targetMessage.channelId,
          targetMessage.id
        );
        if (permalink) {
          messageToUser = `Here's the link to ${messageDescForResponse} (TS: ...${targetMessage.id.slice(-6)}): ${permalink}`;
        } else {
          messageToUser = `I tried, but I couldn't get a direct link for ${messageDescForResponse} (TS: ...${targetMessage.id.slice(-6)}).`;
        }
        break;

      case 'SUMMARIZE_SLACK_MESSAGE':
        // TODO: Implement LLM-based summarization skill call for Slack messages
        messageToUser = `I can't summarize Slack messages yet, but I found ${messageDescForResponse} (TS: ...${targetMessage.id.slice(-6)}). Its content starts with: "${targetMessage.text?.substring(0, 100)}..."`;
        break;

      default:
        // @ts-expect-error actionType might be an unexpected value
        messageToUser = `I found ${messageDescForResponse} (TS: ...${targetMessage.id.slice(-6)}). I'm not sure how to handle the action: ${actionRequested.actionType}.`;
        logger.warn(
          `[SlackCommandHandler] Unknown actionType: ${actionRequested.actionType}`
        );
    }

    logger.info(
      `[SlackCommandHandler] Final response to user: "${messageToUser.substring(0, 100)}..."`
    );
    return messageToUser;
  } catch (error: any) {
    logger.error(
      `[SlackCommandHandler] Critical error in handleSlackInquiry for user ${userId}:`,
      error
    );
    messageToUser = `I encountered an issue while processing your Slack request: ${error.message || 'Unknown error'}. Please try again.`;
    return messageToUser;
  }
}
