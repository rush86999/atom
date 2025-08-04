import {
  SkillResponse,
  SlackMessage,
  // NLU entity types for Slack - will be defined or imported
} from '../types';
import { logger } from '../../_utils/logger';
import {
  understandSlackSearchQueryLLM,
  StructuredSlackQuery,
} from './llm_slack_query_understander';
import { buildSlackSearchQuery } from './nlu_slack_helper';
import {
  searchMySlackMessages as searchMySlackMessagesBackend,
  readSlackMessage as readSlackMessageBackend,
  extractInformationFromSlackMessage,
  getSlackMessagePermalink as getSlackMessagePermalinkBackend,
} from './slackSkills'; // The actual backend callers

// NLU Entity Interfaces (Conceptual - for documentation and type safety if NLU provides them directly)
// These would align with the inputs expected by the LLM parser or a direct NLU service.
export interface SearchSlackMessagesNluEntities {
  raw_query_text: string; // The full natural language query from the user
  limit_number?: number;
  // Other potential pre-parsed entities like channel_name, from_user by NLU if available
  // However, the primary path is for raw_query_text to be parsed by understandSlackSearchQueryLLM
}

export interface ExtractInfoFromSlackMessageNluEntities {
  message_reference_text: string; // e.g., "last message from bob in #general", "the message about budget", permalink
  // OR specific identifiers if NLU can provide them:
  // channel_id?: string;
  // message_ts?: string;
  information_keywords: string[]; // Array of what to extract
  message_text_context?: string; // Optional: if skill receives message text directly
}

// --- Skill Implementations ---

export async function handleSearchSlackMessages(
  userId: string,
  rawUserQuery: string,
  limit: number = 20 // Default limit for Slack search results
): Promise<SkillResponse<{ messages: SlackMessage[]; userMessage: string }>> {
  logger.info(
    `[handleSearchSlackMessages] User: ${userId}, Query: "${rawUserQuery}", Limit: ${limit}`
  );

  try {
    const structuredQuery: Partial<StructuredSlackQuery> =
      await understandSlackSearchQueryLLM(rawUserQuery);
    logger.info(
      `[handleSearchSlackMessages] LLM structured query for Slack: ${JSON.stringify(structuredQuery)}`
    );

    // Resolve user/channel names to IDs if LLM provided names.
    // This is a complex step and might require calls to listUsers/listChannels if not already IDs.
    // For V1, we might rely on the Hasura Action/slack-service to handle some name resolution
    // or require users to use IDs/exact names that Slack search understands.
    // The `buildSlackSearchQuery` helper currently assumes names might be passed.
    // TODO: Enhance with ID resolution step here or ensure LLM provides IDs where possible.
    // Example: if (structuredQuery.fromUser && !isSlackUserId(structuredQuery.fromUser)) { structuredQuery.fromUser = await resolveSlackUserNameToId(structuredQuery.fromUser); }
    // Example: if (structuredQuery.inChannel && !isSlackChannelId(structuredQuery.inChannel)) { structuredQuery.inChannel = await resolveSlackChannelNameToId(structuredQuery.inChannel); }

    const slackApiQueryString = buildSlackSearchQuery(
      structuredQuery,
      rawUserQuery
    );
    logger.info(
      `[handleSearchSlackMessages] Constructed Slack API query string: "${slackApiQueryString}"`
    );

    if (!slackApiQueryString || slackApiQueryString.trim() === '') {
      return {
        ok: true,
        data: {
          messages: [],
          userMessage:
            "I couldn't determine specific search criteria for Slack from your request. Please try rephrasing.",
        },
      };
    }

    const messages: SlackMessage[] = await searchMySlackMessagesBackend(
      userId,
      slackApiQueryString,
      limit
    );

    let userMessage = '';
    if (messages.length === 0) {
      userMessage =
        "I couldn't find any Slack messages matching your search criteria.";
    } else {
      userMessage = `I found ${messages.length} Slack message(s) matching your criteria:\n`;
      messages.forEach((msg, index) => {
        userMessage += `${index + 1}. ${msg.text ? msg.text.substring(0, 150) + '...' : '[No text content]'} (From: ${msg.userName || msg.userId || 'Unknown'}, In: ${msg.channelName || msg.channelId || 'Unknown'}, Date: ${new Date(msg.timestamp).toLocaleString()})\n   Permalink: ${msg.permalink || 'N/A'}\n`;
      });
    }
    return { ok: true, data: { messages, userMessage } };
  } catch (error: any) {
    logger.error(`[handleSearchSlackMessages] Error: ${error.message}`, error);
    return {
      ok: false,
      error: {
        code: 'SLACK_SEARCH_FAILED',
        message: error.message || 'Failed to search Slack messages.',
      },
      data: {
        messages: [],
        userMessage: `Sorry, I encountered an error while searching Slack: ${error.message}`,
      },
    };
  }
}

export async function handleExtractInfoFromSlackMessage(
  userId: string,
  messageReference: string, // Can be permalink, or "channelId/messageTs", or natural language reference
  informationKeywords: string[],
  messageTextContext?: string
): Promise<
  SkillResponse<{
    extractedInfo: Record<string, string | null>;
    userMessage: string;
  }>
> {
  logger.info(
    `[handleExtractInfoFromSlack] User: ${userId}, MessageRef: "${messageReference}", Keywords: [${informationKeywords.join(', ')}]`
  );

  if (!informationKeywords || informationKeywords.length === 0) {
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Please specify what information you want to extract.',
      },
    };
  }

  let messageText: string | null = messageTextContext || null;
  let resolvedChannelId: string | null = null;
  let resolvedMessageTs: string | null = null;
  let messageDescription = `the message (Ref: ${messageReference.substring(0, 50)}...)`;

  try {
    if (!messageText) {
      // Attempt to parse permalink: https://[your-team].slack.com/archives/[CHANNEL_ID]/p[MESSAGE_TS_NO_DOT]
      const permalinkMatch = messageReference.match(
        /slack\.com\/archives\/([CDGUW][A-Z0-9]{8,10})\/p(\d{10})(\d{6})/
      );
      if (permalinkMatch) {
        resolvedChannelId = permalinkMatch[1];
        resolvedMessageTs = `${permalinkMatch[2]}.${permalinkMatch[3]}`;
        logger.info(
          `[handleExtractInfoFromSlack] Parsed permalink to Channel ID: ${resolvedChannelId}, Message TS: ${resolvedMessageTs}`
        );
      } else if (messageReference.includes('/')) {
        // Basic check for "channelId/messageTs"
        const parts = messageReference.split('/');
        if (parts.length === 2 && parts[0] && parts[1]) {
          // rudimentary check
          resolvedChannelId = parts[0];
          resolvedMessageTs = parts[1];
          logger.info(
            `[handleExtractInfoFromSlack] Interpreted reference as Channel ID: ${resolvedChannelId}, Message TS: ${resolvedMessageTs}`
          );
        }
      }

      // If not resolved yet, this indicates a natural language reference or an unparseable one.
      // TODO: For NL reference (e.g., "last message from Bob"), call handleSearchSlackMessages.
      // This is complex due to ambiguity. For V1, we might require permalink or ID format.
      if (!resolvedChannelId || !resolvedMessageTs) {
        logger.warn(
          `[handleExtractInfoFromSlack] Could not resolve message reference "${messageReference}" to channelId/messageTs. Advanced NL reference resolution is a TODO.`
        );
        throw new Error(
          `Could not identify the specific Slack message from your reference: "${messageReference}". Please try providing a permalink or more specific details.`
        );
      }

      const slackMessage = await readSlackMessageBackend(
        userId,
        resolvedChannelId,
        resolvedMessageTs
      );
      if (slackMessage && slackMessage.text) {
        messageText = slackMessage.text;
        messageDescription = `the message in ${slackMessage.channelName || resolvedChannelId} from ${slackMessage.userName || resolvedMessageTs}`;
      } else {
        throw new Error(
          `Could not find or read the Slack message (Channel: ${resolvedChannelId}, TS: ${resolvedMessageTs}).`
        );
      }
    }

    if (!messageText || messageText.trim() === '') {
      return {
        ok: false,
        error: {
          code: 'SLACK_MESSAGE_EMPTY',
          message: `The Slack message body for "${messageDescription}" is empty.`,
        },
        data: {
          extractedInfo: {},
          userMessage: `The Slack message body for "${messageDescription}" is empty, so I couldn't extract information.`,
        },
      };
    }

    const extractedInfo = await extractInformationFromSlackMessage(
      messageText,
      informationKeywords
    );

    let foundCount = 0;
    let messageParts: string[] = [`From my review of ${messageDescription}:`];
    informationKeywords.forEach((keyword) => {
      if (
        extractedInfo[keyword] !== null &&
        extractedInfo[keyword] !== undefined
      ) {
        messageParts.push(`- For "${keyword}": ${extractedInfo[keyword]}`);
        foundCount++;
      } else {
        messageParts.push(`- I couldn't find information about "${keyword}".`);
      }
    });

    const userMessage =
      foundCount > 0
        ? messageParts.join('\n')
        : `I reviewed ${messageDescription} but couldn't find the specific information you asked for (${informationKeywords.join(', ')}).`;

    return { ok: true, data: { extractedInfo, userMessage } };
  } catch (error: any) {
    logger.error(`[handleExtractInfoFromSlack] Error: ${error.message}`, error);
    return {
      ok: false,
      error: {
        code: 'SLACK_EXTRACT_FAILED',
        message:
          error.message || 'Failed to extract information from Slack message.',
      },
      data: {
        extractedInfo: {},
        userMessage: `Sorry, I encountered an error while extracting information from the Slack message: ${error.message}`,
      },
    };
  }
}
