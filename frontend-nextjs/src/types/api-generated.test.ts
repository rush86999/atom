/**
 * Example usage tests for auto-generated API types
 *
 * This file demonstrates how to import and use the types generated from
 * the backend OpenAPI specification. These types provide compile-time
 * safety for API requests and responses across frontend, mobile, and desktop.
 *
 * Regenerate types: npm run generate:api-types
 */

import type { paths, components, operations } from './api-generated';

describe('Generated API Types - Usage Examples', () => {
  describe('Path-based type extraction', () => {
    it('should type agent GET response', () => {
      // Extract response type for GET /api/v1/agents/{agent_id}
      type AgentResponse = paths['/api/v1/agents/{agent_id}']['get']['responses']['200']['content']['application/json'];

      const mockAgent: AgentResponse = {
        id: 'agent-123',
        name: 'Test Agent',
        maturity_level: 'INTERN',
        confidence: 0.75,
      };

      expect(mockAgent.id).toBe('agent-123');
      expect(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS']).toContain(mockAgent.maturity_level);
    });

    it('should type agent execution request', () => {
      // Extract request body type for POST /api/v1/agents/{agent_id}/execute
      type ExecuteRequest = paths['/api/v1/agents/{agent_id}']['post']['requestBody']['content']['application/json'];

      const request: ExecuteRequest = {
        prompt: 'Test prompt',
        context: {},
        stream: true,
      };

      expect(request.prompt).toBeDefined();
    });
  });

  describe('Component schema types', () => {
    it('should use Agent schema type', () => {
      type Agent = components['schemas']['Agent'];

      const agent: Agent = {
        id: 'agent-456',
        name: 'Schema Agent',
        maturity_level: 'SUPERVISED',
        created_at: '2026-03-06T00:00:00Z',
        updated_at: '2026-03-06T00:00:00Z',
      };

      expect(agent.maturity_level).toBe('SUPERVISED');
    });

    it('should handle optional fields', () => {
      type Agent = components['schemas']['Agent'];

      const agent: Agent = {
        id: 'agent-789',
        name: 'Minimal Agent',
        maturity_level: 'AUTONOMOUS',
        created_at: '2026-03-06T00:00:00Z',
        updated_at: '2026-03-06T00:00:00Z',
        confidence: undefined, // Optional field
      };

      expect(agent.confidence).toBeUndefined();
    });
  });

  describe('Operation types', () => {
    it('should type operation parameters', () => {
      type GetAgentParams = operations['getAgent']['parameters']['path'];

      const params: GetAgentParams = {
        agent_id: 'agent-001',
      };

      expect(params.agent_id).toBe('agent-001');
    });
  });

  describe('Common patterns', () => {
    it('should extract error response types', () => {
      type ErrorResponse = paths['/api/v1/agents/{agent_id}']['get']['responses']['404']['content']['application/json'];

      const error: ErrorResponse = {
        detail: 'Agent not found',
        error_code: 'AGENT_NOT_FOUND',
      };

      expect(error.error_code).toBe('AGENT_NOT_FOUND');
    });

    it('should handle union types for maturity levels', () => {
      type MaturityLevel = components['schemas']['Agent']['maturity_level'];

      const levels: MaturityLevel[] = ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'];
      expect(levels).toHaveLength(4);
    });
  });

  describe('Cross-platform compatibility', () => {
    it('should demonstrate mobile import pattern', () => {
      // Mobile (React Native): Import from symlinked types
      // import type { paths, components } from '../../types/api-generated';

      type Agent = components['schemas']['Agent'];
      const agent: Agent = {
        id: 'mobile-agent',
        name: 'Mobile Test',
        maturity_level: 'INTERN',
        created_at: '2026-03-06T00:00:00Z',
        updated_at: '2026-03-06T00:00:00Z',
      };

      expect(agent.id).toBe('mobile-agent');
    });

    it('should demonstrate desktop import pattern', () => {
      // Desktop (Tauri): Import from src-types symlink
      // import type { paths, components } from '../src-types/api-generated';

      type Agent = components['schemas']['Agent'];
      const agent: Agent = {
        id: 'desktop-agent',
        name: 'Desktop Test',
        maturity_level: 'AUTONOMOUS',
        created_at: '2026-03-06T00:00:00Z',
        updated_at: '2026-03-06T00:00:00Z',
      };

      expect(agent.id).toBe('desktop-agent');
    });
  });
});
