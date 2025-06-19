import { WebClient, ErrorCode as SlackErrorCode, SlackAPIError, ConversationsListResponse, ChatPostMessageResponse } from '@slack/web-api';
import { ATOM_SLACK_BOT_TOKEN } from '../_libs/constants';
import {
    SlackSkillResponse,
    SlackChannel,
    SlackMessageData,
    ListSlackChannelsData,
    SkillError
} from '../types';

const getSlackClient = (): WebClient | null => {
  if (!ATOM_SLACK_BOT_TOKEN) {
    console.error('Slack Bot Token not configured.');
    return null;
  }
  return new WebClient(ATOM_SLACK_BOT_TOKEN);
};

// Helper to determine if a string looks like a Slack ID (User, Channel, Group, IM)
function isSlackId(id: string): boolean {
    if (!id) return false;
    return /^[UCGDW][A-Z0-9]{8,}$/.test(id); // Basic check for typical Slack ID patterns C..., U..., G..., D...
}


export async function listSlackChannels(
  userId: string, // Retained for logging/context, not directly used in API call logic unless for specific user-related channel fetching in future
  limit: number = 100,
  cursor?: string
): Promise<SlackSkillResponse<ListSlackChannelsData>> {
  console.log(`listSlackChannels called by userId: ${userId}, limit: ${limit}, cursor: ${cursor}`);
  const client = getSlackClient();
  if (!client) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Slack Bot Token not configured.' } };
  }

  try {
    const result: ConversationsListResponse = await client.conversations.list({
      limit: limit,
      cursor: cursor,
      types: 'public_channel,private_channel',
      exclude_archived: true,
    });

    if (!result.ok || !result.channels) { // Slack API itself might return ok: false in the body
        const slackError = result.error || 'unknown_slack_api_error';
        console.error(`Slack API error while listing channels (result.ok is false): ${slackError}`);
        return { ok: false, error: { code: 'SLACK_API_ERROR', message: `Failed to list channels: ${slackError}`, details: result } };
    }

    return {
      ok: true,
      data: {
        channels: (result.channels as SlackChannel[]) || [], // Ensure SlackChannel type matches our definition
        nextPageCursor: result.response_metadata?.next_cursor,
      }
    };
  } catch (error: any) {
    console.error(`Error listing Slack channels for userId ${userId}:`, error);
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
            details: error.message
        }
    };
  }
}

async function getChannelIdByName(
    client: WebClient,
    channelName: string,
    userIdForContext: string // For logging
): Promise<SlackSkillResponse<string | null>> {
    console.log(`getChannelIdByName called for channelName: ${channelName}`);
    let normalizedChannelName = channelName.startsWith('#') ? channelName.substring(1) : channelName;
    let cursor: string | undefined = undefined;
    let attempts = 0; // To prevent infinite loops in case of unexpected API behavior

    try {
        while (attempts < 10) { // Max 10 pages (e.g. 1000 channels if limit is 100)
            const response = await listSlackChannels(userIdForContext, 200, cursor); // Use existing listSlackChannels

            if (!response.ok || !response.data?.channels) {
                console.error(`Error fetching channels to find ID for "${normalizedChannelName}":`, response.error);
                return { ok: false, error: response.error || { code: 'LOOKUP_FAILED', message: 'Failed to list channels during ID lookup.'} };
            }

            const foundChannel = response.data.channels.find(ch => ch.name === normalizedChannelName);
            if (foundChannel && foundChannel.id) {
                return { ok: true, data: foundChannel.id };
            }

            cursor = response.data.nextPageCursor;
            if (!cursor) {
                break; // No more pages
            }
            attempts++;
        }
        console.log(`Channel "${normalizedChannelName}" not found after checking relevant pages.`);
        return { ok: true, data: null }; // Channel not found after search
    } catch (error: any) { // Should be caught by listSlackChannels, but as a safeguard
        console.error(`Exception in getChannelIdByName for "${normalizedChannelName}":`, error);
        return { ok: false, error: { code: 'INTERNAL_ERROR', message: `Exception looking up channel ID: ${error.message}`, details: error } };
    }
}


export async function sendSlackMessage(
  userId: string, // Used for context/logging and potentially as a default channel if it's a Slack User ID
  channelIdentifier: string, // Can be a channel ID, user ID (for DM), or channel name (e.g. #general)
  text: string
): Promise<SlackSkillResponse<SlackMessageData>> {
  console.log(`sendSlackMessage called by userId: ${userId} to channelIdentifier: ${channelIdentifier}`);
  const client = getSlackClient();
  if (!client) {
    return { ok: false, error: { code: 'CONFIG_ERROR', message: 'Slack Bot Token not configured.' } };
  }

  if (!channelIdentifier || !text) {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Channel identifier and text are required to send a Slack message.' } };
  }

  let targetChannelId = channelIdentifier;

  // If channelIdentifier is not a Slack ID (e.g. Cxxxx, Uxxxx, Dxxxx), try to resolve it as a name.
  if (!isSlackId(channelIdentifier)) {
    const nameToResolve = channelIdentifier.startsWith('#') ? channelIdentifier.substring(1) : channelIdentifier;
    console.log(`Channel identifier "${channelIdentifier}" does not look like an ID, attempting to resolve name "${nameToResolve}"...`);
    const idResponse = await getChannelIdByName(client, nameToResolve, userId);
    if (!idResponse.ok) {
        console.error(`Failed to resolve channel name "${nameToResolve}":`, idResponse.error);
        return { ok: false, error: idResponse.error || {code: 'CHANNEL_RESOLUTION_FAILED', message: `Could not resolve channel name ${nameToResolve}.`} };
    }
    if (!idResponse.data) {
      return { ok: false, error: { code: 'CHANNEL_NOT_FOUND', message: `Channel "${nameToResolve}" not found.` } };
    }
    targetChannelId = idResponse.data;
    console.log(`Resolved channel name "${nameToResolve}" to ID "${targetChannelId}"`);
  }

  try {
    const result: ChatPostMessageResponse = await client.chat.postMessage({
      channel: targetChannelId,
      text: text,
    });

    if (!result.ok || !result.ts) { // Slack API itself might return ok: false in the body
        const slackError = result.error || 'unknown_slack_api_error_on_post';
        console.error(`Slack API error sending message (result.ok is false or no ts): ${slackError} to channel ${targetChannelId}`);
        return { ok: false, error: { code: 'SLACK_API_ERROR', message: `Failed to send message: ${slackError}`, details: result } };
    }

    return {
        ok: true,
        data: {
            ts: result.ts,
            channel: result.channel, // This is the channel ID the message was posted to
            message: result.message as SlackMessageData['message'], // Cast if necessary, ensure structure matches
        }
    };
  } catch (error: any) {
    console.error(`Error sending Slack message for userId ${userId} to channel ${targetChannelId}:`, error);
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
            details: error.message
        }
    };
  }
}
