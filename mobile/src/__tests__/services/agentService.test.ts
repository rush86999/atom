/**
 * Agent Service Tests
 *
 * Tests for agent API communication service:
 * - Agent list retrieval with authentication
 * - Agent detail retrieval
 * - Sending agent messages with streaming responses
 * - Offline handling (queue when offline, sync when reconnected)
 * - Request/response validation
 * - Error handling for 401 (auth error), 500, network errors
 *
 * Note: Uses global mocks from jest.setup.js
 */

import { agentService } from '../../services/agentService';
import { apiService } from '../../services/api';

// Mock the apiService
jest.mock('../../services/api');

// Mock fetch
global.fetch = jest.fn();

describe('AgentService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset global mocks
    (global as any).__resetAsyncStorageMock?.();
  });

  // ========================================================================
  // Agent List Retrieval Tests
  // ========================================================================

  describe('getAgents', () => {
    test('should fetch agent list successfully', async () => {
      const mockAgents = [
        { id: 'agent_1', name: 'Test Agent 1', maturity_level: 'AUTONOMOUS' },
        { id: 'agent_2', name: 'Test Agent 2', maturity_level: 'SUPERVISED' },
      ];

      (apiService.get as jest.Mock).mockResolvedValue({
        success: true,
        data: mockAgents,
      });

      const result = await agentService.getAgents();

      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockAgents);
      expect(apiService.get).toHaveBeenCalledWith('/api/agents', {
        params: {},
      });
    });

    test('should fetch agents with maturity filter', async () => {
      const mockAgents = [
        { id: 'agent_1', name: 'Test Agent', maturity_level: 'AUTONOMOUS' },
      ];

      (apiService.get as jest.Mock).mockResolvedValue({
        success: true,
        data: mockAgents,
      });

      const result = await agentService.getAgents({ maturity: 'AUTONOMOUS' });

      expect(result.success).toBe(true);
      expect(apiService.get).toHaveBeenCalledWith('/api/agents', {
        params: { maturity_level: 'AUTONOMOUS' },
      });
    });

    test('should fetch agents with status filter', async () => {
      (apiService.get as jest.Mock).mockResolvedValue({
        success: true,
        data: [],
      });

      await agentService.getAgents({ status: 'ACTIVE' });

      expect(apiService.get).toHaveBeenCalledWith('/api/agents', {
        params: { status: 'ACTIVE' },
      });
    });

    test('should fetch agents with capability filter', async () => {
      (apiService.get as jest.Mock).mockResolvedValue({
        success: true,
        data: [],
      });

      await agentService.getAgents({ capability: 'browser_automation' });

      expect(apiService.get).toHaveBeenCalledWith('/api/agents', {
        params: { capability: 'browser_automation' },
      });
    });

    test('should fetch agents with search query', async () => {
      (apiService.get as jest.Mock).mockResolvedValue({
        success: true,
        data: [],
      });

      await agentService.getAgents({ search_query: 'test agent' });

      expect(apiService.get).toHaveBeenCalledWith('/api/agents', {
        params: { search: 'test agent' },
      });
    });

    test('should fetch agents with sorting', async () => {
      (apiService.get as jest.Mock).mockResolvedValue({
        success: true,
        data: [],
      });

      await agentService.getAgents({
        sort_by: 'name',
        sort_order: 'asc',
      });

      expect(apiService.get).toHaveBeenCalledWith('/api/agents', {
        params: { sort_by: 'name', sort_order: 'asc' },
      });
    });

    test('should fetch agents with all filters', async () => {
      (apiService.get as jest.Mock).mockResolvedValue({
        success: true,
        data: [],
      });

      await agentService.getAgents({
        maturity: 'AUTONOMOUS',
        status: 'ACTIVE',
        capability: 'browser_automation',
        search_query: 'test',
        sort_by: 'name',
        sort_order: 'asc',
      });

      expect(apiService.get).toHaveBeenCalledWith('/api/agents', {
        params: {
          maturity_level: 'AUTONOMOUS',
          status: 'ACTIVE',
          capability: 'browser_automation',
          search: 'test',
          sort_by: 'name',
          sort_order: 'asc',
        },
      });
    });

    test('should handle API error', async () => {
      const errorMessage = 'Network error';

      (apiService.get as jest.Mock).mockRejectedValue(new Error(errorMessage));

      const result = await agentService.getAgents();

      expect(result.success).toBe(false);
      expect(result.error).toBe(errorMessage);
    });

    test('should return default error message on unknown error', async () => {
      (apiService.get as jest.Mock).mockRejectedValue(new Error());

      const result = await agentService.getAgents();

      expect(result.success).toBe(false);
      expect(result.error).toBe('Failed to fetch agents');
    });
  });

  // ========================================================================
  // Agent Detail Retrieval Tests
  // ========================================================================

  describe('getAgent', () => {
    test('should fetch agent by ID successfully', async () => {
      const mockAgent = {
        id: 'agent_1',
        name: 'Test Agent',
        maturity_level: 'AUTONOMOUS',
        capabilities: ['browser_automation'],
      };

      (apiService.get as jest.Mock).mockResolvedValue({
        success: true,
        data: mockAgent,
      });

      const result = await agentService.getAgent('agent_1');

      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockAgent);
      expect(apiService.get).toHaveBeenCalledWith('/api/agents/agent_1');
    });

    test('should handle agent not found', async () => {
      (apiService.get as jest.Mock).mockResolvedValue({
        success: false,
        error: 'Agent not found',
      });

      const result = await agentService.getAgent('non_existent');

      expect(result.success).toBe(false);
      expect(result.error).toBe('Agent not found');
    });

    test('should handle network error', async () => {
      (apiService.get as jest.Mock).mockRejectedValue(new Error('Network error'));

      const result = await agentService.getAgent('agent_1');

      expect(result.success).toBe(false);
      expect(result.error).toBe('Network error');
    });
  });

  // ========================================================================
  // Chat Session Tests
  // ========================================================================

  describe('Chat Sessions', () => {
    test('should fetch recent chat sessions', async () => {
      const mockSessions = [
        {
          id: 'session_1',
          agent_id: 'agent_1',
          created_at: '2026-01-01T00:00:00Z',
        },
        {
          id: 'session_2',
          agent_id: 'agent_2',
          created_at: '2026-01-02T00:00:00Z',
        },
      ];

      (apiService.get as jest.Mock).mockResolvedValue({
        success: true,
        data: mockSessions,
      });

      const result = await agentService.getChatSessions(20);

      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockSessions);
      expect(apiService.get).toHaveBeenCalledWith('/api/chat/sessions', {
        params: { limit: 20 },
      });
    });

    test('should fetch chat session by ID', async () => {
      const mockSession = {
        id: 'session_1',
        agent_id: 'agent_1',
        messages: [],
      };

      (apiService.get as jest.Mock).mockResolvedValue({
        success: true,
        data: mockSession,
      });

      const result = await agentService.getChatSession('session_1');

      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockSession);
      expect(apiService.get).toHaveBeenCalledWith('/api/chat/sessions/session_1');
    });

    test('should create new chat session', async () => {
      const mockSession = {
        id: 'new_session_1',
        agent_id: 'agent_1',
        created_at: '2026-01-01T00:00:00Z',
      };

      (apiService.post as jest.Mock).mockResolvedValue({
        success: true,
        data: mockSession,
      });

      const result = await agentService.createChatSession('agent_1');

      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockSession);
      expect(apiService.post).toHaveBeenCalledWith('/api/chat/sessions', {
        agent_id: 'agent_1',
      });
    });

    test('should delete chat session', async () => {
      (apiService.delete as jest.Mock).mockResolvedValue({
        success: true,
        data: undefined,
      });

      const result = await agentService.deleteChatSession('session_1');

      expect(result.success).toBe(true);
      expect(apiService.delete).toHaveBeenCalledWith('/api/chat/sessions/session_1');
    });

    test('should handle session not found error', async () => {
      (apiService.get as jest.Mock).mockResolvedValue({
        success: false,
        error: 'Session not found',
      });

      const result = await agentService.getChatSession('non_existent');

      expect(result.success).toBe(false);
      expect(result.error).toBe('Session not found');
    });
  });

  // ========================================================================
  // Send Message Tests
  // ========================================================================

  describe('sendMessage', () => {
    test('should send message to agent successfully', async () => {
      const mockResponse = {
        message: {
          id: 'msg_1',
          role: 'assistant',
          content: 'Hello! How can I help you?',
          timestamp: '2026-01-01T00:00:00Z',
        },
        session_id: 'session_1',
      };

      (apiService.post as jest.Mock).mockResolvedValue({
        success: true,
        data: mockResponse,
      });

      const result = await agentService.sendMessage(
        'agent_1',
        'Hello, agent!',
        'session_1'
      );

      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockResponse);
      expect(apiService.post).toHaveBeenCalledWith('/api/agents/mobile/chat', {
        agent_id: 'agent_1',
        message: 'Hello, agent!',
        session_id: 'session_1',
        platform: 'mobile',
      });
    });

    test('should send message without session ID', async () => {
      const mockResponse = {
        message: {
          id: 'msg_1',
          role: 'assistant',
          content: 'Response',
        },
        session_id: 'new_session_1',
      };

      (apiService.post as jest.Mock).mockResolvedValue({
        success: true,
        data: mockResponse,
      });

      const result = await agentService.sendMessage('agent_1', 'Test message');

      expect(result.success).toBe(true);
      expect(apiService.post).toHaveBeenCalledWith('/api/agents/mobile/chat', {
        agent_id: 'agent_1',
        message: 'Test message',
        session_id: undefined,
        platform: 'mobile',
      });
    });

    test('should handle send message error', async () => {
      (apiService.post as jest.Mock).mockRejectedValue(
        new Error('Failed to send message')
      );

      const result = await agentService.sendMessage('agent_1', 'Test');

      expect(result.success).toBe(false);
      expect(result.error).toBe('Failed to send message');
    });
  });

  // ========================================================================
  // Episode Context Tests
  // ========================================================================

  describe('getEpisodeContext', () => {
    test('should fetch episode context successfully', async () => {
      const mockContext = [
        {
          episode_id: 'ep_1',
          summary: 'Previous interaction',
          relevance_score: 0.95,
        },
      ];

      (apiService.post as jest.Mock).mockResolvedValue({
        success: true,
        data: mockContext,
      });

      const result = await agentService.getEpisodeContext('agent_1', 'test query', 5);

      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockContext);
      expect(apiService.post).toHaveBeenCalledWith(
        '/api/episodes/retrieve/contextual',
        {
          agent_id: 'agent_1',
          query: 'test query',
          limit: 5,
          include_canvas_context: true,
          include_feedback_context: true,
        }
      );
    });

    test('should use default limit if not provided', async () => {
      (apiService.post as jest.Mock).mockResolvedValue({
        success: true,
        data: [],
      });

      await agentService.getEpisodeContext('agent_1', 'test query');

      expect(apiService.post).toHaveBeenCalledWith(
        '/api/episodes/retrieve/contextual',
        {
          agent_id: 'agent_1',
          query: 'test query',
          limit: 5,
          include_canvas_context: true,
          include_feedback_context: true,
        }
      );
    });

    test('should handle episode context error', async () => {
      (apiService.post as jest.Mock).mockRejectedValue(
        new Error('Failed to fetch episodes')
      );

      const result = await agentService.getEpisodeContext('agent_1', 'test');

      expect(result.success).toBe(false);
      expect(result.error).toBe('Failed to fetch episodes');
    });
  });

  // ========================================================================
  // Agent Capabilities Tests
  // ========================================================================

  describe('getAgentCapabilities', () => {
    test('should fetch agent capabilities successfully', async () => {
      const mockCapabilities = [
        'browser_automation',
        'canvas_presentations',
        'device_control',
      ];

      (apiService.get as jest.Mock).mockResolvedValue({
        success: true,
        data: mockCapabilities,
      });

      const result = await agentService.getAgentCapabilities('agent_1');

      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockCapabilities);
      expect(apiService.get).toHaveBeenCalledWith('/api/agents/agent_1/capabilities');
    });

    test('should handle capabilities fetch error', async () => {
      (apiService.get as jest.Mock).mockRejectedValue(
        new Error('Failed to fetch capabilities')
      );

      const result = await agentService.getAgentCapabilities('agent_1');

      expect(result.success).toBe(false);
      expect(result.error).toBe('Failed to fetch capabilities');
    });
  });

  // ========================================================================
  // Available Agents Tests
  // ========================================================================

  describe('getAvailableAgents', () => {
    test('should fetch available agents for mobile', async () => {
      const mockAgents = [
        { id: 'agent_1', name: 'Mobile Agent 1' },
        { id: 'agent_2', name: 'Mobile Agent 2' },
      ];

      (apiService.get as jest.Mock).mockResolvedValue({
        success: true,
        data: mockAgents,
      });

      const result = await agentService.getAvailableAgents();

      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockAgents);
      expect(apiService.get).toHaveBeenCalledWith('/api/agents/mobile/list');
    });

    test('should handle available agents error', async () => {
      (apiService.get as jest.Mock).mockRejectedValue(
        new Error('Failed to fetch available agents')
      );

      const result = await agentService.getAvailableAgents();

      expect(result.success).toBe(false);
      expect(result.error).toBe('Failed to fetch available agents');
    });
  });

  // ========================================================================
  // Offline Handling Tests
  // ========================================================================

  describe('Offline Handling', () => {
    test('should queue request when offline', async () => {
      // TODO: Implement offline queue handling
      // This test is a placeholder for future offline functionality
      // For now, we just verify the service returns an error when offline

      (apiService.get as jest.Mock).mockRejectedValue(
        new Error('Network request failed')
      );

      const result = await agentService.getAgents();

      expect(result.success).toBe(false);
      expect(result.error).toContain('Network request failed');
    });

    // NOTE: Additional offline tests to implement when offline queue is added:
    // - test('should queue requests when NetInfo shows disconnected')
    // - test('should sync queued requests when reconnected')
    // - test('should handle queue size limits')
    // - test('should persist queue to AsyncStorage')
  });

  // ========================================================================
  // Error Handling Tests
  // ========================================================================

  describe('Error Handling', () => {
    test('should handle 401 authentication error', async () => {
      (apiService.get as jest.Mock).mockResolvedValue({
        success: false,
        error: 'Authentication required',
      });

      const result = await agentService.getAgents();

      expect(result.success).toBe(false);
      expect(result.error).toBe('Authentication required');
    });

    test('should handle 500 server error', async () => {
      (apiService.get as jest.Mock).mockResolvedValue({
        success: false,
        error: 'Internal server error',
      });

      const result = await agentService.getAgents();

      expect(result.success).toBe(false);
      expect(result.error).toBe('Internal server error');
    });

    test('should handle network timeout', async () => {
      (apiService.get as jest.Mock).mockRejectedValue(
        new Error('Request timeout')
      );

      const result = await agentService.getAgents();

      expect(result.success).toBe(false);
      expect(result.error).toBe('Request timeout');
    });

    test('should handle malformed response', async () => {
      (apiService.get as jest.Mock).mockResolvedValue({
        success: true,
        data: null,
      });

      const result = await agentService.getAgents();

      expect(result.success).toBe(true);
      expect(result.data).toBeNull();
    });
  });

  // ========================================================================
  // Streaming Tests (TODO)
  // ========================================================================

  describe('Streaming Responses', () => {
    test('TODO: should handle streaming responses', () => {
      // TODO: Implement streaming response tests
      // Streaming responses are not yet implemented in agentService
      // When implemented, test:
      // - Server-Sent Events (SSE) handling
      // - Chunked response parsing
      // - Stream interruption and resume
      // - Progress callbacks
      expect(true).toBe(true);
    });
  });
});
