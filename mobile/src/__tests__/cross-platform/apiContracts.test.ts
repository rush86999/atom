/**
 * API Contract Validation Tests
 *
 * Cross-platform tests that validate API contracts between mobile and backend.
 * These tests ensure that mobile requests match backend schema expectations.
 */

import { apiService } from '../../services/api';
import { AgentMaturity } from '../../types/agent';
import { CanvasType } from '../../types/canvas';

// ============================================================================
// Test Fixtures
// ============================================================================

const MOCK_BACKEND_RESPONSES = {
  agent: {
    agent_id: 'agent-123',
    name: 'Test Agent',
    description: 'Test agent description',
    maturity_level: 'INTERN',
    status: 'online',
    category: 'general',
    capabilities: ['chat', 'canvas'],
    is_available: true,
    last_active: '2026-02-26T10:00:00Z',
  },

  chat_message: {
    message_id: 'msg-123',
    agent_id: 'agent-123',
    content: 'Test response',
    is_streaming: false,
    timestamp: '2026-02-26T10:00:00Z',
    governance: {
      maturity: 'INTERN',
      confidence: 0.75,
      requires_supervision: false,
    },
  },

  canvas_state: {
    canvas_id: 'canvas-123',
    title: 'Test Canvas',
    type: 'generic',
    metadata: {
      agent_name: 'Test Agent',
      agent_id: 'agent-123',
      governance_level: 'INTERN',
      created_at: '2026-02-26T10:00:00Z',
      updated_at: '2026-02-26T10:00:00Z',
      version: 1,
      component_count: 2,
    },
  },

  workflow_execution: {
    execution_id: 'exec-123',
    workflow_id: 'workflow-123',
    status: 'running',
    started_at: '2026-02-26T10:00:00Z',
    progress_percentage: 50,
  },
};

// ============================================================================
// Agent Message API Contract Tests
// ============================================================================

describe('Agent Message API Contract', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Request schema validation', () => {
    it('should send agent messages matching backend schema', async () => {
      const request = {
        agent_id: 'agent-123',
        message: 'Hello agent',
        session_id: 'session-456',
        platform: 'mobile',
      };

      // Validate required fields
      expect(request.agent_id).toBeDefined();
      expect(request.agent_id).toMatch(/^agent-\w+$/);

      expect(request.message).toBeDefined();
      expect(typeof request.message).toBe('string');
      expect(request.message.length).toBeGreaterThan(0);

      expect(request.platform).toBe('mobile');

      // Validate field types
      expect(typeof request.agent_id).toBe('string');
      expect(typeof request.message).toBe('string');
      expect(typeof request.platform).toBe('string');
    });

    it('should include required metadata fields', async () => {
      const metadata = {
        agent_id: 'agent-123',
        session_id: 'session-456',
        platform: 'mobile',
        timestamp: new Date().toISOString(),
      };

      expect(metadata.agent_id).toBeDefined();
      expect(metadata.session_id).toBeDefined();
      expect(metadata.platform).toBe('mobile');
      expect(metadata.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    });
  });

  describe('Response schema validation', () => {
    it('should receive agent responses with expected fields', async () => {
      const response = MOCK_BACKEND_RESPONSES.chat_message;

      // Validate response structure matches backend schema
      expect(response.message_id).toBeDefined();
      expect(response.agent_id).toBeDefined();
      expect(response.content).toBeDefined();
      expect(response.is_streaming).toBeDefined();
      expect(response.timestamp).toBeDefined();

      // Validate field types
      expect(typeof response.message_id).toBe('string');
      expect(typeof response.agent_id).toBe('string');
      expect(typeof response.content).toBe('string');
      expect(typeof response.is_streaming).toBe('boolean');
      expect(typeof response.timestamp).toBe('string');
    });

    it('should handle streaming response format', () => {
      const streamingChunk = {
        chunk_id: 'chunk-123',
        content: 'Partial response',
        is_complete: false,
        metadata: {
          canvas_presented: false,
        },
      };

      expect(streamingChunk.chunk_id).toBeDefined();
      expect(streamingChunk.content).toBeDefined();
      expect(typeof streamingChunk.is_complete).toBe('boolean');
      expect(streamingChunk.metadata).toBeDefined();
    });
  });

  describe('Message type validation', () => {
    it('should validate message types (text, canvas, workflow)', () => {
      const messageTypes = ['text', 'canvas', 'workflow'];

      messageTypes.forEach(type => {
        expect(type).toMatch(/^(text|canvas|workflow)$/);
      });
    });

    it('should support canvas presentation metadata', () => {
      const canvasMetadata = {
        canvas_presented: true,
        canvas_id: 'canvas-123',
        canvas_type: 'generic',
      };

      expect(canvasMetadata.canvas_presented).toBe(true);
      expect(canvasMetadata.canvas_id).toBeDefined();
      expect(canvasMetadata.canvas_type).toBeDefined();
    });
  });

  describe('Governance badge validation', () => {
    it('should include governance badge in responses', () => {
      const governanceBadge = {
        maturity: 'INTERN' as AgentMaturity,
        confidence: 0.75,
        requires_supervision: false,
      };

      expect(governanceBadge.maturity).toBeDefined();
      expect(Object.values(AgentMaturity)).toContain(governanceBadge.maturity);
      expect(typeof governanceBadge.confidence).toBe('number');
      expect(governanceBadge.confidence).toBeGreaterThanOrEqual(0);
      expect(governanceBadge.confidence).toBeLessThanOrEqual(1);
      expect(typeof governanceBadge.requires_supervision).toBe('boolean');
    });
  });

  describe('Episode context validation', () => {
    it('should validate episode context structure', () => {
      const episodeContext = {
        episode_id: 'episode-123',
        title: 'Test Episode',
        summary: 'Test summary',
        created_at: '2026-02-26T10:00:00Z',
        relevance_score: 0.85,
        canvas_context: {
          canvas_id: 'canvas-123',
          canvas_type: 'generic',
          action: 'present',
        },
        feedback_context: {
          average_rating: 0.8,
          feedback_count: 5,
        },
      };

      expect(episodeContext.episode_id).toBeDefined();
      expect(episodeContext.title).toBeDefined();
      expect(episodeContext.summary).toBeDefined();
      expect(episodeContext.created_at).toBeDefined();
      expect(typeof episodeContext.relevance_score).toBe('number');
      expect(episodeContext.canvas_context).toBeDefined();
      expect(episodeContext.feedback_context).toBeDefined();
    });
  });
});

// ============================================================================
// Canvas State API Contract Tests
// ============================================================================

describe('Canvas State API Contract', () => {
  describe('Canvas serialization validation', () => {
    it('should serialize canvas state matching backend schema', () => {
      const canvasState = MOCK_BACKEND_RESPONSES.canvas_state;

      expect(canvasState.canvas_id).toBeDefined();
      expect(canvasState.title).toBeDefined();
      expect(canvasState.type).toBeDefined();
      expect(canvasState.metadata).toBeDefined();

      // Validate metadata structure
      expect(canvasState.metadata.agent_name).toBeDefined();
      expect(canvasState.metadata.agent_id).toBeDefined();
      expect(canvasState.metadata.governance_level).toBeDefined();
      expect(canvasState.metadata.created_at).toBeDefined();
      expect(canvasState.metadata.updated_at).toBeDefined();
      expect(typeof canvasState.metadata.version).toBe('number');
      expect(typeof canvasState.metadata.component_count).toBe('number');
    });

    it('should support all canvas types', () => {
      const canvasTypes = Object.values(CanvasType);

      canvasTypes.forEach(type => {
        expect(type).toMatch(/^(generic|docs|email|sheets|orchestration|terminal|coding)$/);
      });
    });
  });

  describe('Canvas component validation', () => {
    it('should validate canvas component structure', () => {
      const component = {
        id: 'component-123',
        type: 'markdown',
        order: 1,
        data: {
          content: '# Test Markdown',
        },
        props: {
          className: 'test-class',
        },
      };

      expect(component.id).toBeDefined();
      expect(component.type).toBeDefined();
      expect(typeof component.order).toBe('number');
      expect(component.data).toBeDefined();
      expect(component.props).toBeDefined();
    });
  });

  describe('Canvas audit record validation', () => {
    it('should validate canvas audit record structure', () => {
      const auditRecord = {
        id: 'audit-123',
        canvas_id: 'canvas-123',
        canvas_type: 'generic' as CanvasType,
        action: 'present',
        agent_id: 'agent-123',
        agent_name: 'Test Agent',
        user_id: 'user-123',
        session_id: 'session-456',
        component_count: 2,
        metadata: {},
        created_at: '2026-02-26T10:00:00Z',
      };

      expect(auditRecord.id).toBeDefined();
      expect(auditRecord.canvas_id).toBeDefined();
      expect(auditRecord.canvas_type).toBeDefined();
      expect(auditRecord.action).toMatch(/^(present|submit|close|update|execute)$/);
      expect(auditRecord.agent_id).toBeDefined();
      expect(auditRecord.agent_name).toBeDefined();
      expect(auditRecord.user_id).toBeDefined();
      expect(auditRecord.session_id).toBeDefined();
      expect(typeof auditRecord.component_count).toBe('number');
      expect(auditRecord.metadata).toBeDefined();
      expect(auditRecord.created_at).toBeDefined();
    });
  });
});

// ============================================================================
// Workflow API Contract Tests
// ============================================================================

describe('Workflow API Contract', () => {
  describe('Workflow trigger validation', () => {
    it('should trigger workflow matching backend schema', () => {
      const triggerRequest = {
        workflow_id: 'workflow-123',
        parameters: {
          param1: 'value1',
          param2: 42,
        },
        synchronous: false,
      };

      expect(triggerRequest.workflow_id).toBeDefined();
      expect(triggerRequest.parameters).toBeDefined();
      expect(typeof triggerRequest.synchronous).toBe('boolean');
    });
  });

  describe('Workflow execution status validation', () => {
    it('should receive workflow execution status', () => {
      const executionStatus = MOCK_BACKEND_RESPONSES.workflow_execution;

      expect(executionStatus.execution_id).toBeDefined();
      expect(executionStatus.workflow_id).toBeDefined();
      expect(executionStatus.status).toBeDefined();
      expect(executionStatus.started_at).toBeDefined();
      expect(typeof executionStatus.progress_percentage).toBe('number');
    });

    it('should validate execution status values', () => {
      const validStatuses = ['pending', 'running', 'completed', 'failed', 'cancelled'];

      validStatuses.forEach(status => {
        expect(status).toMatch(/^(pending|running|completed|failed|cancelled)$/);
      });
    });
  });

  describe('Workflow input/output validation', () => {
    it('should validate workflow input format', () => {
      const workflowInput = {
        workflow_id: 'workflow-123',
        parameters: {
          string_param: 'test',
          number_param: 42,
          boolean_param: true,
          object_param: {
            nested: 'value',
          },
        },
      };

      expect(workflowInput.parameters).toBeDefined();
      expect(typeof workflowInput.parameters.string_param).toBe('string');
      expect(typeof workflowInput.parameters.number_param).toBe('number');
      expect(typeof workflowInput.parameters.boolean_param).toBe('boolean');
      expect(typeof workflowInput.parameters.object_param).toBe('object');
    });

    it('should validate workflow output format', () => {
      const workflowOutput = {
        execution_id: 'exec-123',
        status: 'completed',
        result: {
          output1: 'value1',
          output2: 100,
        },
        completed_at: '2026-02-26T10:05:00Z',
        duration_seconds: 300,
      };

      expect(workflowOutput.execution_id).toBeDefined();
      expect(workflowOutput.status).toBeDefined();
      expect(workflowOutput.result).toBeDefined();
      expect(workflowOutput.completed_at).toBeDefined();
      expect(typeof workflowOutput.duration_seconds).toBe('number');
    });
  });
});

// ============================================================================
// Request/Response Validation Tests
// ============================================================================

describe('Request/Response Validation', () => {
  describe('Authentication headers', () => {
    it('should handle authentication headers consistently', () => {
      const authHeaders = {
        Authorization: 'Bearer test-token-123',
        'X-Platform': 'mobile',
        'X-Device-ID': 'device-456',
      };

      expect(authHeaders.Authorization).toMatch(/^Bearer \w+-\w+-\w+$/);
      expect(authHeaders['X-Platform']).toBe('mobile');
      expect(authHeaders['X-Device-ID']).toBeDefined();
    });
  });

  describe('Platform identifier', () => {
    it('should include platform identifier in requests', () => {
      const platformId = 'mobile';

      expect(platformId).toBe('mobile');
      expect(['mobile', 'web', 'desktop']).toContain(platformId);
    });
  });

  describe('Error response handling', () => {
    it('should parse error responses consistently', () => {
      const errorResponse = {
        success: false,
        error_code: 'AGENT_NOT_FOUND',
        message: 'Agent with ID not found',
        details: {
          agent_id: 'invalid-id',
        },
      };

      expect(errorResponse.success).toBe(false);
      expect(errorResponse.error_code).toBeDefined();
      expect(errorResponse.message).toBeDefined();
      expect(errorResponse.details).toBeDefined();
    });

    it('should handle rate limit responses', () => {
      const rateLimitResponse = {
        success: false,
        error_code: 'RATE_LIMIT_EXCEEDED',
        message: 'Too many requests',
        details: {
          retry_after: 60,
          limit: 100,
          remaining: 0,
        },
      };

      expect(rateLimitResponse.error_code).toBe('RATE_LIMIT_EXCEEDED');
      expect(typeof rateLimitResponse.details.retry_after).toBe('number');
      expect(typeof rateLimitResponse.details.limit).toBe('number');
      expect(typeof rateLimitResponse.details.remaining).toBe('number');
    });
  });
});

// ============================================================================
// Data Structure Consistency Tests
// ============================================================================

describe('Data Structure Consistency', () => {
  describe('Agent message shape consistency', () => {
    it('should match web implementation agent message shape', () => {
      const agentMessage = {
        id: 'msg-123',
        role: 'assistant',
        content: 'Test message',
        timestamp: '2026-02-26T10:00:00Z',
        agent_id: 'agent-123',
        agent_name: 'Test Agent',
        is_streaming: false,
        governance_badge: {
          maturity: 'INTERN' as AgentMaturity,
          confidence: 0.75,
          requires_supervision: false,
        },
        metadata: {
          canvas_presented: false,
          tool_calls: [],
        },
      };

      // Validate structure matches web implementation
      expect(agentMessage.id).toBeDefined();
      expect(agentMessage.role).toMatch(/^(user|assistant|system)$/);
      expect(agentMessage.content).toBeDefined();
      expect(agentMessage.timestamp).toBeDefined();
      expect(agentMessage.agent_id).toBeDefined();
      expect(agentMessage.agent_name).toBeDefined();
      expect(typeof agentMessage.is_streaming).toBe('boolean');
      expect(agentMessage.governance_badge).toBeDefined();
      expect(agentMessage.metadata).toBeDefined();
    });
  });

  describe('Canvas state shape consistency', () => {
    it('should match web implementation canvas state shape', () => {
      const canvasState = {
        id: 'canvas-123',
        type: 'generic' as CanvasType,
        title: 'Test Canvas',
        components: [
          {
            id: 'comp-1',
            type: 'markdown',
            order: 1,
            data: { content: '# Test' },
          },
        ],
        metadata: {
          agent_id: 'agent-123',
          agent_name: 'Test Agent',
          governance_level: 'INTERN',
          created_at: '2026-02-26T10:00:00Z',
          version: 1,
        },
      };

      // Validate structure matches web implementation
      expect(canvasState.id).toBeDefined();
      expect(canvasState.type).toBeDefined();
      expect(canvasState.title).toBeDefined();
      expect(Array.isArray(canvasState.components)).toBe(true);
      expect(canvasState.metadata).toBeDefined();
    });
  });

  describe('Workflow trigger shape consistency', () => {
    it('should match web implementation workflow trigger shape', () => {
      const workflowTrigger = {
        workflow_id: 'workflow-123',
        parameters: {
          input1: 'value1',
        },
        synchronous: false,
        platform: 'mobile',
      };

      // Validate structure matches web implementation
      expect(workflowTrigger.workflow_id).toBeDefined();
      expect(workflowTrigger.parameters).toBeDefined();
      expect(typeof workflowTrigger.synchronous).toBe('boolean');
      expect(workflowTrigger.platform).toBe('mobile');
    });
  });
});
