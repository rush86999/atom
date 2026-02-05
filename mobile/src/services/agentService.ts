/**
 * Agent Service
 * Handles agent-related API calls for mobile app
 */

import { apiService } from './api';
import { ApiResponse } from '../types/common';
import {
  Agent,
  AgentFilters,
  ChatMessage,
  ChatSession,
  EpisodeContext,
  StreamingChunk,
} from '../types/agent';

const API_BASE_URL = __DEV__
  ? 'http://localhost:8000'
  : 'https://api.atom-platform.com';

class AgentService {
  /**
   * Get list of agents with optional filtering
   */
  async getAgents(filters?: AgentFilters): Promise<ApiResponse<Agent[]>> {
    try {
      const params: Record<string, string> = {};

      if (filters?.maturity && filters.maturity !== 'ALL') {
        params.maturity_level = filters.maturity;
      }

      if (filters?.status && filters.status !== 'ALL') {
        params.status = filters.status;
      }

      if (filters?.capability) {
        params.capability = filters.capability;
      }

      if (filters?.search_query) {
        params.search = filters.search_query;
      }

      if (filters?.sort_by) {
        params.sort_by = filters.sort_by;
      }

      if (filters?.sort_order) {
        params.sort_order = filters.sort_order;
      }

      const response = await apiService.get<Agent[]>('/api/agents', { params });
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to fetch agents',
      };
    }
  }

  /**
   * Get agent by ID
   */
  async getAgent(agentId: string): Promise<ApiResponse<Agent>> {
    try {
      const response = await apiService.get<Agent>(`/api/agents/${agentId}`);
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to fetch agent',
      };
    }
  }

  /**
   * Get recent chat sessions
   */
  async getChatSessions(limit: number = 20): Promise<ApiResponse<ChatSession[]>> {
    try {
      const response = await apiService.get<ChatSession[]>('/api/chat/sessions', {
        params: { limit },
      });
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to fetch chat sessions',
      };
    }
  }

  /**
   * Get chat session by ID
   */
  async getChatSession(sessionId: string): Promise<ApiResponse<ChatSession>> {
    try {
      const response = await apiService.get<ChatSession>(`/api/chat/sessions/${sessionId}`);
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to fetch chat session',
      };
    }
  }

  /**
   * Send chat message (non-streaming)
   */
  async sendMessage(
    agentId: string,
    message: string,
    sessionId?: string
  ): Promise<ApiResponse<{ message: ChatMessage; session_id: string }>> {
    try {
      const response = await apiService.post<{ message: ChatMessage; session_id: string }>(
        '/api/agents/mobile/chat',
        {
          agent_id: agentId,
          message,
          session_id: sessionId,
          platform: 'mobile',
        }
      );
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to send message',
      };
    }
  }

  /**
   * Get episode context for a message
   */
  async getEpisodeContext(
    agentId: string,
    query: string,
    limit: number = 5
  ): Promise<ApiResponse<EpisodeContext[]>> {
    try {
      const response = await apiService.post<EpisodeContext[]>('/api/episodes/retrieve/contextual', {
        agent_id: agentId,
        query,
        limit,
        include_canvas_context: true,
        include_feedback_context: true,
      });
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to fetch episode context',
      };
    }
  }

  /**
   * Create new chat session
   */
  async createChatSession(agentId: string): Promise<ApiResponse<ChatSession>> {
    try {
      const response = await apiService.post<ChatSession>('/api/chat/sessions', {
        agent_id: agentId,
      });
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to create chat session',
      };
    }
  }

  /**
   * Delete chat session
   */
  async deleteChatSession(sessionId: string): Promise<ApiResponse<void>> {
    try {
      const response = await apiService.delete<void>(`/api/chat/sessions/${sessionId}`);
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to delete chat session',
      };
    }
  }

  /**
   * Get agent capabilities
   */
  async getAgentCapabilities(agentId: string): Promise<ApiResponse<string[]>> {
    try {
      const response = await apiService.get<string[]>(`/api/agents/${agentId}/capabilities`);
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to fetch agent capabilities',
      };
    }
  }

  /**
   * Get available agents for quick select
   */
  async getAvailableAgents(): Promise<ApiResponse<Agent[]>> {
    try {
      const response = await apiService.get<Agent[]>('/api/agents/mobile/list');
      return response;
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to fetch available agents',
      };
    }
  }
}

// Export singleton instance
export const agentService = new AgentService();
export default agentService;
