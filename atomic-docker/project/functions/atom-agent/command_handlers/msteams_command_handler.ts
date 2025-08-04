import { understandMSTeamsSearchQueryLLM } from '../skills/llm_msteams_query_understander';
import { buildMSTeamsSearchQuery } from '../skills/nlu_msteams_helper';
import {
  searchMyMSTeamsMessages,
  readMSTeamsMessage,
  extractInformationFromMSTeamsMessage,
  getMSTeamsMessageWebUrl,
  GetMSTeamsMessageDetailInput, // Input type for readMSTeamsMessage
} from '../skills/msTeamsSkills';
import { MSTeamsMessage } from '../types';
import { logger } from '../../_utils/logger';

export type MSTeamsActionType =
  | 'GET_MSTEAMS_MESSAGE_CONTENT'
  | 'FIND_INFO_IN_MSTEAMS_MESSAGE'
  | 'GET_MSTEAMS_MESSAGE_LINK'
  | 'SUMMARIZE_MSTEAMS_MESSAGE'; // Future capability

export interface MSTeamsActionRequest {
  actionType: MSTeamsActionType;
  infoKeywords?: string[];
  naturalLanguageQuestion?: string;
}

export interface ParsedNluMSTeamsRequest {
  userId: string;
  rawMSTeamsSearchQuery: string;
  actionRequested: MSTeamsActionRequest;
  // Fields to directly target a message if NLU identifies them
  targetMessageId?: string;
  targetChatId?: string;
  targetTeamId?: string;
  targetChannelId?: string;
}

export async function handleMSTeamsInquiry(
  request: ParsedNluMSTeamsRequest
): Promise<string> {
  const {
    userId,
    rawMSTeamsSearchQuery,
    actionRequested,
    targetMessageId,
    targetChatId,
    targetTeamId,
    targetChannelId,
  } = request;
  let messageToUser = '';

  logger.debug(
    `[MSTeamsCommandHandler] Handling MS Teams inquiry for user ${userId}:`,
    request
  );

  try {
    let targetMessage: MSTeamsMessage | null = null;

    // Step 1: Obtain the target message
    if (
      targetMessageId &&
      (targetChatId || (targetTeamId && targetChannelId))
    ) {
      const identifier: GetMSTeamsMessageDetailInput = {
        messageId: targetMessageId,
      };
      if (targetChatId) identifier.chatId = targetChatId;
      if (targetTeamId) identifier.teamId = targetTeamId;
      if (targetChannelId) identifier.channelId = targetChannelId;

      logger.info(
        `[MSTeamsCommandHandler] Attempting to read specified MS Teams message:`,
        identifier
      );
      targetMessage = await readMSTeamsMessage(userId, identifier);
      if (!targetMessage) {
        messageToUser = `Sorry, I couldn't find or read the specific Teams message you referred to.`;
        logger.warn(
          `[MSTeamsCommandHandler] Failed to read specific message: ${messageToUser}`
        );
        return messageToUser;
      }
    } else {
      logger.info(
        `[MSTeamsCommandHandler] Understanding MS Teams search query: "${rawMSTeamsSearchQuery}"`
      );
      const structuredSearchParams = await understandMSTeamsSearchQueryLLM(
        rawMSTeamsSearchQuery
      );

      if (
        Object.keys(structuredSearchParams).length === 0 &&
        !rawMSTeamsSearchQuery.toLowerCase().includes('latest')
      ) {
        messageToUser =
          "I couldn't determine specific search criteria for Teams from your request. Could you be more precise?";
        logger.warn(
          `[MSTeamsCommandHandler] LLM returned empty search params for query: "${rawMSTeamsSearchQuery}"`
        );
        return messageToUser;
      }

      const kqlQueryString = buildMSTeamsSearchQuery(structuredSearchParams);
      logger.info(
        `[MSTeamsCommandHandler] Searching MS Teams messages with KQL query: "${kqlQueryString}" (Limit 5)`
      );
      const messagesFound = await searchMyMSTeamsMessages(
        userId,
        kqlQueryString,
        5
      );

      if (!messagesFound || messagesFound.length === 0) {
        messageToUser =
          "I couldn't find any Teams messages matching your criteria.";
        logger.info(
          `[MSTeamsCommandHandler] No messages found for KQL query: "${kqlQueryString}"`
        );
        return messageToUser;
      }

      if (
        messagesFound.length > 1 &&
        actionRequested.actionType !== 'FIND_INFO_IN_MSTEAMS_MESSAGE'
      ) {
        messageToUser =
          'I found a few Teams messages matching your criteria:\n';
        messagesFound.slice(0, 3).forEach((msg, index) => {
          const msgTextPreview = msg.content
            ? msg.content.replace(/<[^>]+>/g, ' ').substring(0, 70) + '...'
            : 'No text content';
          const context = msg.channelName
            ? `in ${msg.channelName}`
            : msg.chatId
              ? `in chat ${msg.chatId.substring(0, 10)}...`
              : '';
          messageToUser += `${index + 1}. From ${msg.userName || 'Unknown User'} ${context}: "${msgTextPreview}" (ID: ...${msg.id.slice(-6)})\n`;
        });
        if (messagesFound.length > 3)
          messageToUser += `And ${messagesFound.length - 3} more.\n`;
        messageToUser +=
          'Which one are you interested in? You can tell me the number or provide more details (like its ID).';
        logger.info(
          `[MSTeamsCommandHandler] Multiple messages found, clarification needed.`
        );
        return messageToUser;
      }
      targetMessage = messagesFound[0];
      logger.info(
        `[MSTeamsCommandHandler] Single message identified for processing. ID: ${targetMessage.id}`
      );

      // Ensure full content if search result was partial (heuristic: check if content seems too short or lacks detail)
      // This might require a more robust check or always fetching full details if search API returns summaries.
      // For now, assume search returns enough, or readMSTeamsMessage is called if specific ID is known.
      // If targetMessage.content seems like a snippet, fetch full.
      // This check is simplified; Graph search results for messages usually contain the full body.
    }

    if (!targetMessage) {
      messageToUser =
        "I couldn't identify a specific Teams message to process.";
      logger.warn(`[MSTeamsCommandHandler] No target message identified.`);
      return messageToUser;
    }

    // Step 2: Perform the requested action
    const messageDesc =
      `the Teams message from ${targetMessage.userName || 'Unknown User'}` +
      (targetMessage.channelName
        ? ` in ${targetMessage.channelName}`
        : targetMessage.chatId
          ? ` in chat`
          : '');

    switch (actionRequested.actionType) {
      case 'GET_MSTEAMS_MESSAGE_CONTENT':
        const contentPreview = targetMessage.content
          ? targetMessage.content.replace(/<[^>]+>/g, ' ').substring(0, 200) +
            '...'
          : 'it appears to have no readable content.';
        messageToUser = `The content of ${messageDesc} (ID: ...${targetMessage.id.slice(-6)}) starts with: "${contentPreview}".`;
        break;

      case 'FIND_INFO_IN_MSTEAMS_MESSAGE':
        if (!targetMessage.content) {
          messageToUser = `${messageDesc} (ID: ...${targetMessage.id.slice(-6)}) doesn't seem to have any content for me to analyze.`;
          break;
        }
        const keywords = actionRequested.infoKeywords || [];
        if (keywords.length === 0) {
          messageToUser = `You asked me to find specific information in ${messageDesc}, but didn't specify what to look for.`;
          break;
        }
        logger.info(
          `[MSTeamsCommandHandler] Extracting info for keywords [${keywords.join(', ')}] from message ID ${targetMessage.id}`
        );
        const extracted = await extractInformationFromMSTeamsMessage(
          targetMessage.content,
          keywords
        );
        let foundAnyInfo = false;
        let parts: string[] = [
          `Regarding ${messageDesc} (ID: ...${targetMessage.id.slice(-6)}):`,
        ];
        for (const keyword of keywords) {
          const val = extracted[keyword];
          if (val) {
            parts.push(`- For "${keyword}", I found: ${val}.`);
            foundAnyInfo = true;
          } else {
            parts.push(
              `- I couldn't find specific information about "${keyword}".`
            );
          }
        }
        messageToUser = foundAnyInfo
          ? parts.join('\n')
          : `I scanned ${messageDesc} for "${keywords.join(', ')}", but couldn't find those details.`;
        break;

      case 'GET_MSTEAMS_MESSAGE_LINK':
        if (targetMessage.webUrl) {
          messageToUser = `Here's the link to ${messageDesc} (ID: ...${targetMessage.id.slice(-6)}): ${targetMessage.webUrl}`;
        } else {
          // Attempt to fetch it if not directly on the object (though our service populates it)
          const identifier: GetMSTeamsMessageDetailInput = {
            messageId: targetMessage.id,
          };
          if (targetMessage.chatId) identifier.chatId = targetMessage.chatId;
          if (targetMessage.teamId) identifier.teamId = targetMessage.teamId;
          if (targetMessage.channelId)
            identifier.channelId = targetMessage.channelId;
          const link = await getMSTeamsMessageWebUrl(userId, identifier);
          if (link) {
            messageToUser = `Here's the link to ${messageDesc} (ID: ...${targetMessage.id.slice(-6)}): ${link}`;
          } else {
            messageToUser = `I tried, but I couldn't get a direct link for ${messageDesc} (ID: ...${targetMessage.id.slice(-6)}).`;
          }
        }
        break;

      case 'SUMMARIZE_MSTEAMS_MESSAGE':
        messageToUser = `I can't summarize Teams messages yet, but I found ${messageDesc} (ID: ...${targetMessage.id.slice(-6)}).`;
        break;

      default:
        // @ts-expect-error actionType might be an unexpected value
        messageToUser = `I found ${messageDesc} (ID: ...${targetMessage.id.slice(-6)}). I'm not sure how to handle your request: ${actionRequested.actionType}.`;
        logger.warn(
          `[MSTeamsCommandHandler] Unknown actionType: ${actionRequested.actionType}`
        );
    }

    logger.info(
      `[MSTeamsCommandHandler] Final response for user ${userId}: "${messageToUser.substring(0, 150)}..."`
    );
    return messageToUser;
  } catch (error: any) {
    logger.error(
      `[MSTeamsCommandHandler] Critical error in handleMSTeamsInquiry for user ${userId}:`,
      error
    );
    messageToUser = `I encountered an issue while processing your Microsoft Teams request: ${error.message || 'Unknown error'}. Please try again.`;
    return messageToUser;
  }
}
