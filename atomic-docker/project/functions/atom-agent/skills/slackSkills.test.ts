import { sendSlackMessage, listSlackChannels } from './slackSkills';
import { WebClient, ErrorCode as SlackErrorCode, SlackAPIError } from '@slack/web-api';
import * as constants from '../_libs/constants';
import { SlackChannel, SlackMessageResponse, ListSlackChannelsResponse } from '../types';

jest.mock('@slack/web-api');
jest.mock('../_libs/constants', () => ({
    ATOM_SLACK_BOT_TOKEN: 'test-slack-bot-token', // Default mock value
}));

// Define mock functions for Slack WebClient methods
let mockChatPostMessage: jest.Mock;
let mockConversationsList: jest.Mock;

// Spy on console.error and console.log
let consoleErrorSpy: jest.SpyInstance;
let consoleLogSpy: jest.SpyInstance;

describe('slackSkills', () => {
  beforeEach(() => {
    // Reset constants.ATOM_SLACK_BOT_TOKEN to its default mock value for each test
    // This is a bit tricky since it's a const; a better way would be to mock the module and provide a setter.
    // For this setup, we'll re-import or directly manipulate the mocked value if the test needs a different one.
    // Or, ensure the mock itself can be modified. Let's assume the jest.mock above handles this for subsequent changes.
    // The most robust way is to ensure the constants module is fully mockable.
    jest.spyOn(constants, 'ATOM_SLACK_BOT_TOKEN', 'get').mockReturnValue('test-slack-bot-token');


    mockChatPostMessage = jest.fn();
    mockConversationsList = jest.fn();

    (WebClient as jest.Mock).mockImplementation(() => {
      return {
        chat: {
          postMessage: mockChatPostMessage,
        },
        conversations: {
          list: mockConversationsList,
        },
      };
    });

    // Spy on console.error and console.log and suppress output
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.clearAllMocks();
    // Restore original console spies
    consoleErrorSpy.mockRestore();
    consoleLogSpy.mockRestore();
  });

  describe('sendSlackMessage', () => {
    const userId = 'user1';
    const channelId = 'C123';
    const text = 'Hello, Slack!';

    it('should send a message successfully', async () => {
      const mockResponse: Partial<SlackMessageResponse> = { // Partial because the SDK might return more
        ok: true,
        ts: '123456.789',
        channel: channelId,
        message: { text: text, user: 'U0BOTID', bot_id: 'B0BOTID', ts: '123456.789', type: 'message' },
      };
      mockChatPostMessage.mockResolvedValueOnce(mockResponse);

      const result = await sendSlackMessage(userId, channelId, text);

      expect(result.ok).toBe(true);
      expect(result.ts).toBe('123456.789');
      expect(result.channel).toBe(channelId);
      expect(result.message?.text).toBe(text);
      expect(mockChatPostMessage).toHaveBeenCalledWith({ channel: channelId, text: text });
      expect(consoleLogSpy).toHaveBeenCalledWith(`sendSlackMessage called by userId: ${userId} to channel: ${channelId}`);
    });

    it('should return error if ATOM_SLACK_BOT_TOKEN is missing', async () => {
      jest.spyOn(constants, 'ATOM_SLACK_BOT_TOKEN', 'get').mockReturnValue(''); // Set token to empty

      const result = await sendSlackMessage(userId, channelId, text);

      expect(result).toEqual({ ok: false, error: 'Slack Bot Token not configured.' });
      expect(mockChatPostMessage).not.toHaveBeenCalled();
      expect(consoleErrorSpy).toHaveBeenCalledWith('Slack Bot Token not configured.');
    });

    it('should return error if channel or text is missing', async () => {
        let result = await sendSlackMessage(userId, '', text);
        expect(result).toEqual({ ok: false, error: 'Channel and text are required to send a Slack message.' });

        result = await sendSlackMessage(userId, channelId, '');
        expect(result).toEqual({ ok: false, error: 'Channel and text are required to send a Slack message.' });

        expect(mockChatPostMessage).not.toHaveBeenCalled();
    });

    it('should handle Slack API PlatformError', async () => {
      const slackErrorData = { ok: false, error: 'channel_not_found', /* other data */ };
      // SlackAPIError constructor: message, code, httpStatusCode, data
      const apiError = new SlackAPIError('platform_error_from_test', SlackErrorCode.PlatformError, undefined, slackErrorData);

      mockChatPostMessage.mockRejectedValueOnce(apiError);
      const result = await sendSlackMessage(userId, channelId, text);

      expect(result.ok).toBe(false);
      expect(result.error).toBe('channel_not_found');
      expect(consoleErrorSpy).toHaveBeenCalledWith(`Error sending Slack message for userId ${userId} to channel ${channelId}:`, apiError);
    });

    it('should handle other SlackAPIErrors (e.g. network, rate limit)', async () => {
        const errorMessage = "A different Slack API error occurred";
        const apiError = new SlackAPIError(errorMessage, SlackErrorCode.RequestTimeout, undefined, { ok: false, error: 'timeout' });
        mockChatPostMessage.mockRejectedValueOnce(apiError);
        const result = await sendSlackMessage(userId, channelId, text);
        expect(result.ok).toBe(false);
        expect(result.error).toBe(errorMessage); // The message property of the error
    });

    it('should handle other non-SlackAPIError errors', async () => {
      const genericError = new Error('Network issue');
      mockChatPostMessage.mockRejectedValueOnce(genericError);

      const result = await sendSlackMessage(userId, channelId, text);

      // The actual implementation prepends a custom string, so we match that.
      expect(result).toEqual({ ok: false, error: 'Failed to send Slack message due to an unexpected error.' });
      expect(consoleErrorSpy).toHaveBeenCalledWith(`Error sending Slack message for userId ${userId} to channel ${channelId}:`, genericError);
    });
  });

  describe('listSlackChannels', () => {
    const userId = 'user2';

    it('should list channels successfully (first page)', async () => {
      const mockChannels: SlackChannel[] = [
        { id: 'C01', name: 'general', is_channel: true, num_members: 10 },
        { id: 'C02', name: 'random', is_channel: true, num_members: 5 },
      ];
      const mockResponse = {
        ok: true,
        channels: mockChannels,
        response_metadata: { next_cursor: 'cursor123' },
      };
      mockConversationsList.mockResolvedValueOnce(mockResponse);

      const result = await listSlackChannels(userId);

      expect(result.ok).toBe(true);
      expect(result.channels).toEqual(mockChannels);
      expect(result.nextPageCursor).toBe('cursor123');
      expect(mockConversationsList).toHaveBeenCalledWith({
        limit: 100, // Default limit
        types: 'public_channel,private_channel',
        exclude_archived: true,
        cursor: undefined, // No cursor for first page
      });
      expect(consoleLogSpy).toHaveBeenCalledWith(`listSlackChannels called by userId: ${userId}, limit: 100, cursor: undefined`);
    });

    it('should list channels successfully with specified limit and cursor', async () => {
      const mockResponse = {
        ok: true,
        channels: [],
        response_metadata: { next_cursor: 'newCursor456' },
      };
      mockConversationsList.mockResolvedValueOnce(mockResponse);

      await listSlackChannels(userId, 50, 'prevCursor123');

      expect(mockConversationsList).toHaveBeenCalledWith({
        limit: 50,
        cursor: 'prevCursor123',
        types: 'public_channel,private_channel',
        exclude_archived: true,
      });
       expect(consoleLogSpy).toHaveBeenCalledWith(`listSlackChannels called by userId: ${userId}, limit: 50, cursor: prevCursor123`);
    });

    it('should return empty channels array if API returns null or undefined channels', async () => {
      mockConversationsList.mockResolvedValueOnce({ ok: true, channels: null, response_metadata: { next_cursor: '' } });
      let result = await listSlackChannels(userId);
      expect(result.ok).toBe(true);
      expect(result.channels).toEqual([]);

      mockConversationsList.mockResolvedValueOnce({ ok: true, channels: undefined, response_metadata: { next_cursor: '' } });
      result = await listSlackChannels(userId);
      expect(result.ok).toBe(true);
      expect(result.channels).toEqual([]);
    });

    it('should return error if ATOM_SLACK_BOT_TOKEN is missing', async () => {
      jest.spyOn(constants, 'ATOM_SLACK_BOT_TOKEN', 'get').mockReturnValue('');
      const result = await listSlackChannels(userId);
      expect(result).toEqual({ ok: false, error: 'Slack Bot Token not configured.' });
      expect(mockConversationsList).not.toHaveBeenCalled();
      expect(consoleErrorSpy).toHaveBeenCalledWith('Slack Bot Token not configured.');
    });

    it('should handle Slack API PlatformError when listing channels', async () => {
      const slackErrorData = { ok: false, error: 'invalid_limit', /* other data */ };
      const apiError = new SlackAPIError('platform_error_listing_test', SlackErrorCode.PlatformError, undefined, slackErrorData);
      mockConversationsList.mockRejectedValueOnce(apiError);

      const result = await listSlackChannels(userId);
      expect(result.ok).toBe(false);
      expect(result.error).toBe('invalid_limit');
      expect(consoleErrorSpy).toHaveBeenCalledWith(`Error listing Slack channels for userId ${userId}:`, apiError);
    });

    it('should handle other SlackAPIErrors when listing channels', async () => {
        const errorMessage = "A different Slack API error occurred during list";
        const apiError = new SlackAPIError(errorMessage, SlackErrorCode.TooManyRequests, undefined, { ok: false, error: 'ratelimited' });
        mockConversationsList.mockRejectedValueOnce(apiError);
        const result = await listSlackChannels(userId);
        expect(result.ok).toBe(false);
        expect(result.error).toBe(errorMessage);
    });

    it('should handle other non-SlackAPIError errors when listing channels', async () => {
      const genericError = new Error('DNS resolution failed');
      mockConversationsList.mockRejectedValueOnce(genericError);
      const result = await listSlackChannels(userId);
      expect(result).toEqual({ ok: false, error: 'Failed to list Slack channels due to an unexpected error.' });
      expect(consoleErrorSpy).toHaveBeenCalledWith(`Error listing Slack channels for userId ${userId}:`, genericError);
    });
  });
});
