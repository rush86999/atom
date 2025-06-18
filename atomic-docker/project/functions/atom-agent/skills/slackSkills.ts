import { WebClient, ErrorCode as SlackErrorCode, SlackAPIError } from '@slack/web-api';
import { ATOM_SLACK_BOT_TOKEN } from '../_libs/constants';
import { SlackMessageResponse, ListSlackChannelsResponse, SlackChannel } from '../types';

const getSlackClient = () => {
  if (!ATOM_SLACK_BOT_TOKEN) {
    console.error('Slack Bot Token not configured.');
    return null;
  }
  return new WebClient(ATOM_SLACK_BOT_TOKEN);
};

export async function sendSlackMessage(
  userId: string,
  channel: string,
  text: string
): Promise<SlackMessageResponse> {
  console.log(`sendSlackMessage called by userId: ${userId} to channel: ${channel}`);
  const client = getSlackClient();
  if (!client) {
    return { ok: false, error: 'Slack Bot Token not configured.' };
  }

  if (!channel || !text) {
    return { ok: false, error: 'Channel and text are required to send a Slack message.' };
  }

  try {
    const result = await client.chat.postMessage({
      channel: channel,
      text: text,
    });
    // The SlackAPIClient result types are quite broad, so we cast to our specific response type.
    // Ensure that the properties you expect (like ts, channel, message.text etc.) are covered by the Slack API response.
    return result as SlackMessageResponse;
  } catch (error: any) {
    console.error(`Error sending Slack message for userId ${userId} to channel ${channel}:`, error);
    if (error instanceof SlackAPIError && error.code === SlackErrorCode.PlatformError) {
      // Platform errors usually have a `data.error` field with the Slack-specific error string like 'channel_not_found'
      return { ok: false, error: error.data.error || 'Slack platform error' };
    } else if (error instanceof SlackAPIError) {
        // Other Slack API errors (network, rate limits, etc.)
        return { ok: false, error: error.message || 'Slack API error'};
    }
    // Generic error
    return { ok: false, error: 'Failed to send Slack message due to an unexpected error.' };
  }
}

export async function listSlackChannels(
  userId: string,
  limit: number = 100,
  cursor?: string
): Promise<ListSlackChannelsResponse> {
  console.log(`listSlackChannels called by userId: ${userId}, limit: ${limit}, cursor: ${cursor}`);
  const client = getSlackClient();
  if (!client) {
    return { ok: false, error: 'Slack Bot Token not configured.' };
  }

  try {
    const result = await client.conversations.list({
      limit: limit,
      cursor: cursor,
      types: 'public_channel,private_channel', // Comma-separated string for types
      exclude_archived: true,
    });

    // The response.channels are already typed by the SDK, but we cast to our SlackChannel for consistency
    // and to ensure our interface matches what we expect and use.
    return {
      ok: true,
      channels: (result.channels as SlackChannel[]) || [],
      nextPageCursor: result.response_metadata?.next_cursor,
    };
  } catch (error: any) {
    console.error(`Error listing Slack channels for userId ${userId}:`, error);
     if (error instanceof SlackAPIError && error.code === SlackErrorCode.PlatformError) {
      return { ok: false, error: error.data.error || 'Slack platform error while listing channels' };
    } else if (error instanceof SlackAPIError) {
        return { ok: false, error: error.message || 'Slack API error while listing channels'};
    }
    return { ok: false, error: 'Failed to list Slack channels due to an unexpected error.' };
  }
}
