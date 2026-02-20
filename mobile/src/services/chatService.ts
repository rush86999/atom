/**
 * Chat Service
 *
 * Dedicated service for chat operations with offline support,
 * message feedback, search, and conversation management.
 */

import { apiService } from './api';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { offlineSyncService } from './offlineSyncService';
import { ApiResponse } from '../types/common';
import { ChatMessage, ChatSession, EpisodeContext } from '../types/agent';

const STORAGE_KEYS = {
  PENDING_MESSAGES: 'chat_pending_messages',
  FAILED_MESSAGES: 'chat_failed_messages',
  CONVERSATION_LIST: 'chat_conversation_list',
};

const OFFLINE_QUEUE = 'chat_offline_queue';

// Types
interface MessageFeedback {
  message_id: string;
  rating: number; // -1 (thumbs down) to 1 (thumbs up)
  comment?: string;
  category?: string;
}

interface MessageSearchParams {
  query: string;
  agent_id?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
}

interface ConversationSummary {
  session_id: string;
  agent_id: string;
  agent_name: string;
  agent_maturity: string;
  last_message: string;
  last_message_time: string;
  unread_count: number;
  message_count: number;
}

interface PendingMessage {
  id: string;
  agent_id: string;
  message: string;
  session_id?: string;
  attachments?: any[];
  timestamp: string;
  retry_count: number;
}

/**
 * ChatService Class
 */
class ChatService {
  private pendingMessages: Map<string, PendingMessage> = new Map();
  private failedMessages: Map<string, PendingMessage> = new Map();

  constructor() {
    this.loadPendingMessages();
  }

  /**
   * Load pending messages from storage
   */
  private async loadPendingMessages(): Promise<void> {
    try {
      const pending = await AsyncStorage.getItem(STORAGE_KEYS.PENDING_MESSAGES);
      const failed = await AsyncStorage.getItem(STORAGE_KEYS.FAILED_MESSAGES);

      if (pending) {
        const parsed = JSON.parse(pending);
        parsed.forEach((msg: PendingMessage) => {
          this.pendingMessages.set(msg.id, msg);
        });
      }

      if (failed) {
        const parsed = JSON.parse(failed);
        parsed.forEach((msg: PendingMessage) => {
          this.failedMessages.set(msg.id, msg);
        });
      }
    } catch (error) {
      console.error('Failed to load pending messages:', error);
    }
  }

  /**
   * Save pending messages to storage
   */
  private async savePendingMessages(): Promise<void> {
    try {
      const pending = Array.from(this.pendingMessages.values());
      const failed = Array.from(this.failedMessages.values());

      await AsyncStorage.setItem(STORAGE_KEYS.PENDING_MESSAGES, JSON.stringify(pending));
      await AsyncStorage.setItem(STORAGE_KEYS.FAILED_MESSAGES, JSON.stringify(failed));
    } catch (error) {
      console.error('Failed to save pending messages:', error);
    }
  }

  /**
   * Send message (streaming via WebSocket handled by WebSocketContext)
   */
  async sendMessage(
    agentId: string,
    message: string,
    sessionId?: string,
    attachments?: any[]
  ): Promise<ApiResponse<{ message: ChatMessage; session_id: string }>> {
    try {
      const response = await apiService.post<{ message: ChatMessage; session_id: string }>(
        '/api/agents/mobile/chat',
        {
          agent_id: agentId,
          message,
          session_id: sessionId,
          platform: 'mobile',
          attachments,
        }
      );

      return response;
    } catch (error: any) {
      // Queue message for offline send
      const pendingMessage: PendingMessage = {
        id: `pending_${Date.now()}`,
        agent_id: agentId,
        message,
        session_id: sessionId,
        attachments,
        timestamp: new Date().toISOString(),
        retry_count: 0,
      };

      this.pendingMessages.set(pendingMessage.id, pendingMessage);
      await this.savePendingMessages();

      // Add to offline sync queue
      await offlineSyncService.queueOperation({
        id: pendingMessage.id,
        type: 'send_message',
        data: pendingMessage,
        priority: 'high',
      });

      return {
        success: false,
        error: error.message || 'Failed to send message',
      };
    }
  }

  /**
   * Get conversation history
   */
  async getConversationHistory(
    sessionId: string,
    limit: number = 50
  ): Promise<ApiResponse<ChatMessage[]>> {
    try {
      const response = await apiService.get<ChatMessage[]>(
        `/api/chat/sessions/${sessionId}/messages`,
        { params: { limit } }
      );
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to fetch conversation history',
      };
    }
  }

  /**
   * Get conversation list
   */
  async getConversationList(
    limit: number = 20,
    offset: number = 0
  ): Promise<ApiResponse<ConversationSummary[]>> {
    try {
      const response = await apiService.get<ConversationSummary[]>('/api/chat/conversations', {
        params: { limit, offset },
      });
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to fetch conversation list',
      };
    }
  }

  /**
   * Search messages
   */
  async searchMessages(
    params: MessageSearchParams
  ): Promise<ApiResponse<ChatMessage[]>> {
    try {
      const response = await apiService.post<ChatMessage[]>('/api/chat/messages/search', params);
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to search messages',
      };
    }
  }

  /**
   * Get message feedback options
   */
  async getFeedbackOptions(): Promise<ApiResponse<any[]>> {
    try {
      const response = await apiService.get<any[]>('/api/chat/feedback/options');
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to fetch feedback options',
      };
    }
  }

  /**
   * Submit message feedback
   */
  async submitFeedback(feedback: MessageFeedback): Promise<ApiResponse<void>> {
    try {
      const response = await apiService.post<void>('/api/chat/feedback', feedback);
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to submit feedback',
      };
    }
  }

  /**
   * Regenerate agent response
   */
  async regenerateResponse(
    messageId: string
  ): Promise<ApiResponse<{ message: ChatMessage }>> {
    try {
      const response = await apiService.post<{ message: ChatMessage }>(
        `/api/chat/messages/${messageId}/regenerate`
      );
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to regenerate response',
      };
    }
  }

  /**
   * Delete message (user only)
   */
  async deleteMessage(messageId: string): Promise<ApiResponse<void>> {
    try {
      const response = await apiService.delete<void>(`/api/chat/messages/${messageId}`);
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to delete message',
      };
    }
  }

  /**
   * Mark messages as read
   */
  async markAsRead(sessionId: string): Promise<ApiResponse<void>> {
    try {
      const response = await apiService.post<void>(`/api/chat/sessions/${sessionId}/read`);
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to mark as read',
      };
    }
  }

  /**
   * Retry failed message
   */
  async retryMessage(messageId: string): Promise<ApiResponse<void>> {
    const failedMessage = this.failedMessages.get(messageId);
    if (!failedMessage) {
      return {
        success: false,
        error: 'Message not found in failed queue',
      };
    }

    try {
      const response = await this.sendMessage(
        failedMessage.agent_id,
        failedMessage.message,
        failedMessage.session_id,
        failedMessage.attachments
      );

      if (response.success) {
        this.failedMessages.delete(messageId);
        await this.savePendingMessages();
      }

      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to retry message',
      };
    }
  }

  /**
   * Get pending message count
   */
  getPendingMessageCount(): number {
    return this.pendingMessages.size + this.failedMessages.size;
  }

  /**
   * Get all pending messages
   */
  getPendingMessages(): PendingMessage[] {
    return Array.from(this.pendingMessages.values());
  }

  /**
   * Get all failed messages
   */
  getFailedMessages(): PendingMessage[] {
    return Array.from(this.failedMessages.values());
  }

  /**
   * Clear all pending/failed messages
   */
  async clearPendingMessages(): Promise<void> {
    this.pendingMessages.clear();
    this.failedMessages.clear();
    await this.savePendingMessages();
  }

  /**
   * Sync pending messages when online
   */
  async syncPendingMessages(): Promise<void> {
    const pending = Array.from(this.pendingMessages.values());

    for (const message of pending) {
      try {
        const response = await this.sendMessage(
          message.agent_id,
          message.message,
          message.session_id,
          message.attachments
        );

        if (response.success) {
          this.pendingMessages.delete(message.id);
        } else {
          // Move to failed after 3 retries
          message.retry_count += 1;
          if (message.retry_count >= 3) {
            this.pendingMessages.delete(message.id);
            this.failedMessages.set(message.id, message);
          }
        }
      } catch (error) {
        console.error(`Failed to sync message ${message.id}:`, error);
      }
    }

    await this.savePendingMessages();
  }

  /**
   * Create new chat session
   */
  async createSession(agentId: string): Promise<ApiResponse<ChatSession>> {
    try {
      const response = await apiService.post<ChatSession>('/api/chat/sessions', {
        agent_id: agentId,
      });
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to create session',
      };
    }
  }

  /**
   * Delete chat session
   */
  async deleteSession(sessionId: string): Promise<ApiResponse<void>> {
    try {
      const response = await apiService.delete<void>(`/api/chat/sessions/${sessionId}`);
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to delete session',
      };
    }
  }

  /**
   * Archive chat session
   */
  async archiveSession(sessionId: string): Promise<ApiResponse<void>> {
    try {
      const response = await apiService.post<void>(`/api/chat/sessions/${sessionId}/archive`);
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to archive session',
      };
    }
  }
}

// Export singleton instance
export const chatService = new ChatService();
export default chatService;
