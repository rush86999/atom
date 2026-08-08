/**
 * Chat Service Tests
 *
 * Tests for chat operations:
 * - sendMessage (payload, offline queuing, dedupe of repeated failures)
 * - Conversation history/list, search, feedback
 * - Message management (regenerate, delete, mark-as-read, retry)
 * - Pending/failed message lifecycle (counts, retries, sync convergence)
 * - Session management (create, delete, archive)
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { chatService } from '../../services/chatService';
import { apiService } from '../../services/api';
import { offlineSyncService } from '../../services/offlineSyncService';

// Mock service dependencies
jest.mock('../../services/api', () => ({
  apiService: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  },
}));

jest.mock('../../services/offlineSyncService', () => ({
  offlineSyncService: {
    getSyncState: jest.fn(),
    queueAction: jest.fn(),
  },
}));

const mockApiService = apiService as jest.Mocked<typeof apiService>;
const mockOfflineSyncService = offlineSyncService as jest.Mocked<typeof offlineSyncService>;

const okResponse = (data?: any) => ({ success: true, data, message: 'ok' });

describe('chatService', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    (global as any).__resetAsyncStorageMock?.();

    mockOfflineSyncService.queueAction.mockResolvedValue('action-1');
    mockApiService.post.mockResolvedValue(okResponse());
    mockApiService.get.mockResolvedValue(okResponse([]));
    mockApiService.delete.mockResolvedValue(okResponse());

    // The singleton keeps in-memory pending/failed maps — reset them.
    await chatService.clearPendingMessages();
  });

  // ========================================================================
  // sendMessage Tests
  // ========================================================================

  describe('sendMessage', () => {
    test('should POST the message with the mobile payload', async () => {
      const response = okResponse({ message: { id: 'm1' }, session_id: 's1' });
      mockApiService.post.mockResolvedValue(response);

      const result = await chatService.sendMessage('a1', 'hello', 's1', []);

      expect(mockApiService.post).toHaveBeenCalledWith('/api/agents/mobile/chat', {
        agent_id: 'a1',
        message: 'hello',
        session_id: 's1',
        platform: 'mobile',
        attachments: [],
      });
      expect(result.success).toBe(true);
      // Nothing queued on success
      expect(chatService.getPendingMessageCount()).toBe(0);
      expect(mockOfflineSyncService.queueAction).not.toHaveBeenCalled();
    });

    test('should queue the message offline and return failure when the request throws', async () => {
      mockApiService.post.mockRejectedValue(new Error('Network error'));

      const result = await chatService.sendMessage('a1', 'hello', 's1', []);

      expect(result.success).toBe(false);
      expect(result.error).toBe('Network error');
      expect(chatService.getPendingMessages()).toHaveLength(1);
      const pending = chatService.getPendingMessages()[0];
      expect(pending.agent_id).toBe('a1');
      expect(pending.message).toBe('hello');
      expect(pending.retry_count).toBe(0);

      // Offline queue action is registered with high priority and default ids
      expect(mockOfflineSyncService.queueAction).toHaveBeenCalledWith(
        'agent_message',
        expect.objectContaining({ agent_id: 'a1', message: 'hello', session_id: 's1' }),
        'high',
        'unknown_user',
        'mobile_device',
        'last_write_wins'
      );
    });

    test('should use stored user/device ids when queuing offline', async () => {
      mockApiService.post.mockRejectedValue(new Error('offline'));
      await AsyncStorage.setItem('atom_user_id', 'user-42');
      await AsyncStorage.setItem('atom_device_id', 'device-7');

      await chatService.sendMessage('a1', 'hello');

      expect(mockOfflineSyncService.queueAction).toHaveBeenCalledWith(
        'agent_message',
        expect.anything(),
        'high',
        'user-42',
        'device-7',
        'last_write_wins'
      );
    });

    test('should dedupe repeated failures for the same message', async () => {
      mockApiService.post.mockRejectedValue(new Error('offline'));

      await chatService.sendMessage('a1', 'hello', 's1');
      await chatService.sendMessage('a1', 'hello', 's1');

      // Same pending entry, retry count bumped — no unbounded duplicate chain
      expect(chatService.getPendingMessages()).toHaveLength(1);
      expect(chatService.getPendingMessages()[0].retry_count).toBe(1);
      // Still only one offline action queued per attempt
      expect(mockOfflineSyncService.queueAction).toHaveBeenCalledTimes(2);
    });

    test('should keep distinct messages as separate pending entries', async () => {
      mockApiService.post.mockRejectedValue(new Error('offline'));

      await chatService.sendMessage('a1', 'first');
      await chatService.sendMessage('a1', 'second');

      expect(chatService.getPendingMessages()).toHaveLength(2);
    });
  });

  // ========================================================================
  // Error Fallback Tests
  // ========================================================================

  describe('Error Fallbacks', () => {
    test('should use generic fallback messages when the thrown value is not an Error', async () => {
      const cases: Array<[string, () => Promise<any>, string]> = [
        ['getConversationHistory', () => chatService.getConversationHistory('s1'), 'Failed to fetch conversation history'],
        ['getConversationList', () => chatService.getConversationList(), 'Failed to fetch conversation list'],
        ['searchMessages', () => chatService.searchMessages({ query: 'x' }), 'Failed to search messages'],
        ['getFeedbackOptions', () => chatService.getFeedbackOptions(), 'Failed to fetch feedback options'],
        ['submitFeedback', () => chatService.submitFeedback({ message_id: 'm1', rating: 1 }), 'Failed to submit feedback'],
        ['regenerateResponse', () => chatService.regenerateResponse('m1'), 'Failed to regenerate response'],
        ['deleteMessage', () => chatService.deleteMessage('m1'), 'Failed to delete message'],
        ['markAsRead', () => chatService.markAsRead('s1'), 'Failed to mark as read'],
        ['createSession', () => chatService.createSession('a1'), 'Failed to create session'],
        ['deleteSession', () => chatService.deleteSession('s1'), 'Failed to delete session'],
        ['archiveSession', () => chatService.archiveSession('s1'), 'Failed to archive session'],
        ['sendMessage', () => chatService.sendMessage('a1', 'hello'), 'Failed to send message'],
      ];

      for (const [name, invoke, fallback] of cases) {
        mockApiService.get.mockReset();
        mockApiService.post.mockReset();
        mockApiService.delete.mockReset();
        // A thrown non-Error value has no .message — the fallback text is used
        mockApiService.get.mockRejectedValue('raw failure');
        mockApiService.post.mockRejectedValue('raw failure');
        mockApiService.delete.mockRejectedValue('raw failure');

        const result = await invoke();
        expect(result.success).toBe(false);
        expect(result.error).toBe(fallback);
        expect(result.error).not.toBe('raw failure');
      }
    });
  });

  // ========================================================================
  // Conversation Tests
  // ========================================================================

  describe('Conversations', () => {
    test('should fetch conversation history with limit', async () => {
      const messages = [{ id: 'm1', role: 'user' }];
      mockApiService.get.mockResolvedValue(okResponse(messages));

      const result = await chatService.getConversationHistory('s1', 25);

      expect(mockApiService.get).toHaveBeenCalledWith('/api/chat/sessions/s1/messages', {
        params: { limit: 25 },
      });
      expect(result.success).toBe(true);
      expect(result.data).toEqual(messages);
    });

    test('should default conversation history limit to 50', async () => {
      mockApiService.get.mockResolvedValue(okResponse([]));

      await chatService.getConversationHistory('s1');

      expect(mockApiService.get).toHaveBeenCalledWith('/api/chat/sessions/s1/messages', {
        params: { limit: 50 },
      });
    });

    test('should return failure when history fetch throws', async () => {
      mockApiService.get.mockRejectedValue(new Error('boom'));

      const result = await chatService.getConversationHistory('s1');

      expect(result.success).toBe(false);
      expect(result.error).toBe('boom');
    });

    test('should fetch conversation list with pagination', async () => {
      const conversations = [{ session_id: 's1' }];
      mockApiService.get.mockResolvedValue(okResponse(conversations));

      const result = await chatService.getConversationList(20, 40);

      expect(mockApiService.get).toHaveBeenCalledWith('/api/chat/conversations', {
        params: { limit: 20, offset: 40 },
      });
      expect(result.data).toEqual(conversations);
    });

    test('should search messages with the given params', async () => {
      const results = [{ id: 'm1' }];
      mockApiService.post.mockResolvedValue(okResponse(results));

      const params = { query: 'sales', agent_id: 'a1', limit: 5 };
      const result = await chatService.searchMessages(params);

      expect(mockApiService.post).toHaveBeenCalledWith('/api/chat/messages/search', params);
      expect(result.data).toEqual(results);
    });
  });

  // ========================================================================
  // Feedback Tests
  // ========================================================================

  describe('Feedback', () => {
    test('should fetch feedback options', async () => {
      const options = [{ value: 'accurate' }];
      mockApiService.get.mockResolvedValue(okResponse(options));

      const result = await chatService.getFeedbackOptions();

      expect(mockApiService.get).toHaveBeenCalledWith('/api/chat/feedback/options');
      expect(result.data).toEqual(options);
    });

    test('should submit feedback with rating payload', async () => {
      mockApiService.post.mockResolvedValue(okResponse());

      const result = await chatService.submitFeedback({ message_id: 'm1', rating: 1 });

      expect(mockApiService.post).toHaveBeenCalledWith('/api/chat/feedback', {
        message_id: 'm1',
        rating: 1,
      });
      expect(result.success).toBe(true);
    });

    test('should return failure when submitting feedback throws', async () => {
      mockApiService.post.mockRejectedValue(new Error('rate limited'));

      const result = await chatService.submitFeedback({ message_id: 'm1', rating: -1 });

      expect(result.success).toBe(false);
      expect(result.error).toBe('rate limited');
    });
  });

  // ========================================================================
  // Message Management Tests
  // ========================================================================

  describe('Message Management', () => {
    test('should regenerate a response', async () => {
      const regenerated = { message: { id: 'm2' } };
      mockApiService.post.mockResolvedValue(okResponse(regenerated));

      const result = await chatService.regenerateResponse('m1');

      expect(mockApiService.post).toHaveBeenCalledWith('/api/chat/messages/m1/regenerate');
      expect(result.data).toEqual(regenerated);
    });

    test('should delete a message', async () => {
      const result = await chatService.deleteMessage('m1');

      expect(mockApiService.delete).toHaveBeenCalledWith('/api/chat/messages/m1');
      expect(result.success).toBe(true);
    });

    test('should mark a session as read', async () => {
      const result = await chatService.markAsRead('s1');

      expect(mockApiService.post).toHaveBeenCalledWith('/api/chat/sessions/s1/read');
      expect(result.success).toBe(true);
    });

    test('should delete a chat session', async () => {
      const result = await chatService.deleteSession('s1');

      expect(mockApiService.delete).toHaveBeenCalledWith('/api/chat/sessions/s1');
      expect(result.success).toBe(true);
    });

    test('should archive a chat session', async () => {
      const result = await chatService.archiveSession('s1');

      expect(mockApiService.post).toHaveBeenCalledWith('/api/chat/sessions/s1/archive');
      expect(result.success).toBe(true);
    });
  });

  // ========================================================================
  // Session Creation Tests
  // ========================================================================

  describe('Sessions', () => {
    test('should create a session for an agent', async () => {
      const session = { id: 's1', agent_id: 'a1', messages: [] };
      mockApiService.post.mockResolvedValue(okResponse(session));

      const result = await chatService.createSession('a1');

      expect(mockApiService.post).toHaveBeenCalledWith('/api/chat/sessions', {
        agent_id: 'a1',
      });
      expect(result.data).toEqual(session);
    });

    test('should return failure when session creation throws', async () => {
      mockApiService.post.mockRejectedValue(new Error('no agent'));

      const result = await chatService.createSession('missing');

      expect(result.success).toBe(false);
      expect(result.error).toBe('no agent');
    });
  });

  // ========================================================================
  // Retry Tests
  // ========================================================================

  describe('retryMessage', () => {
    test('should report an error when the message is not in the failed queue', async () => {
      const result = await chatService.retryMessage('nope');

      expect(result.success).toBe(false);
      expect(result.error).toBe('Message not found in failed queue');
    });

    test('should resend a failed message and clear it on success', async () => {
      (chatService as any).failedMessages.set('m1', {
        id: 'm1',
        agent_id: 'a1',
        message: 'hello',
        timestamp: '2024-01-01T00:00:00Z',
        retry_count: 3,
      });
      mockApiService.post.mockResolvedValue(okResponse({ message: { id: 'new' }, session_id: 's1' }));

      const result = await chatService.retryMessage('m1');

      expect(mockApiService.post).toHaveBeenCalledWith('/api/agents/mobile/chat', expect.objectContaining({
        agent_id: 'a1',
        message: 'hello',
      }));
      expect(result.success).toBe(true);
      expect(chatService.getFailedMessages()).toHaveLength(0);
    });

    test('should keep the message in the failed queue when the resend fails', async () => {
      (chatService as any).failedMessages.set('m1', {
        id: 'm1',
        agent_id: 'a1',
        message: 'hello',
        timestamp: '2024-01-01T00:00:00Z',
        retry_count: 3,
      });
      mockApiService.post.mockRejectedValue(new Error('offline'));

      const result = await chatService.retryMessage('m1');

      expect(result.success).toBe(false);
      expect(chatService.getFailedMessages()).toHaveLength(1);
    });
  });

  // ========================================================================
  // Pending Message Lifecycle Tests
  // ========================================================================

  describe('Pending Messages', () => {
    test('should report pending + failed counts', async () => {
      mockApiService.post.mockRejectedValue(new Error('offline'));
      await chatService.sendMessage('a1', 'hi');

      expect(chatService.getPendingMessageCount()).toBe(1);
      expect(chatService.getPendingMessages()).toHaveLength(1);
    });

    test('should clear pending and failed messages', async () => {
      mockApiService.post.mockRejectedValue(new Error('offline'));
      await chatService.sendMessage('a1', 'hi');
      (chatService as any).failedMessages.set('f1', { id: 'f1', retry_count: 3 });

      await chatService.clearPendingMessages();

      expect(chatService.getPendingMessageCount()).toBe(0);
    });

    test('should remove pending messages that sync successfully', async () => {
      mockApiService.post.mockRejectedValueOnce(new Error('offline'));
      await chatService.sendMessage('a1', 'hi');

      mockApiService.post.mockResolvedValue(okResponse({ message: { id: 'm1' }, session_id: 's1' }));
      await chatService.syncPendingMessages();

      expect(chatService.getPendingMessages()).toHaveLength(0);
    });

    test('should converge: failed syncs graduate to the failed queue, pending empties', async () => {
      mockApiService.post.mockRejectedValue(new Error('offline'));
      await chatService.sendMessage('a1', 'hi'); // pending, retry 0

      // Each sync attempt fails -> dedupe bumps retry_count on the SAME entry
      await chatService.syncPendingMessages(); // retry 1
      await chatService.syncPendingMessages(); // retry 2
      await chatService.syncPendingMessages(); // retry 3 -> failed queue

      // Pending is fully drained — no duplicate chain is left behind
      expect(chatService.getPendingMessages()).toHaveLength(0);
      expect(chatService.getFailedMessages()).toHaveLength(1);
      expect(chatService.getFailedMessages()[0].retry_count).toBe(3);
      expect(chatService.getFailedMessages()[0].message).toBe('hi');
    });
  });
});
