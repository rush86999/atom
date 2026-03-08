/**
 * Tests for TypeScript interfaces (API types)
 *
 * Verifies type structure, optional fields, and type validation
 * for API-generated types from OpenAPI spec.
 */

import { describe, it, expect } from '@jest/globals';

// Import types from api-generated.ts
import type {
  components,
  paths,
  operations
} from '../../types/api-generated';

// Extract commonly used types for convenience
type AgentResponse = components['schemas']['AgentResponse'];
type CanvasData = components['schemas']['CanvasData'];
type PaginatedResponse<T> = components['schemas']['PaginatedResponse'];
type ErrorResponse = components['schemas']['ErrorResponse'];

describe('API Types', () => {
  describe('AgentResponse', () => {
    it('has required fields', () => {
      const agent: AgentResponse = {
        id: 'test-agent',
        name: 'Test Agent',
        maturity_level: 'AUTONOMOUS',
        status: 'active'
      };

      expect(agent.id).toBeDefined();
      expect(agent.name).toBeDefined();
      expect(agent.maturity_level).toBeDefined();
      expect(agent.status).toBeDefined();
    });

    it('accepts all maturity levels', () => {
      const maturities = ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'] as const;

      maturities.forEach(maturity => {
        const agent: AgentResponse = {
          id: `agent-${maturity}`,
          name: 'Test',
          maturity_level: maturity,
          status: 'active'
        };

        expect(agent.maturity_level).toBe(maturity);
      });
    });

    it('accepts optional fields', () => {
      const agent: AgentResponse = {
        id: 'test-agent',
        name: 'Test Agent',
        maturity_level: 'STUDENT',
        status: 'active',
        description: 'Optional description',
        created_at: '2026-03-08T12:00:00Z'
      };

      expect(agent.description).toBe('Optional description');
      expect(agent.created_at).toBeDefined();
    });
  });

  describe('CanvasData', () => {
    it('has required fields', () => {
      const canvas: CanvasData = {
        id: 'canvas-123',
        canvas_type: 'chart',
        content: {}
      };

      expect(canvas.id).toBeDefined();
      expect(canvas.canvas_type).toBeDefined();
      expect(canvas.content).toBeDefined();
    });

    it('accepts different canvas types', () => {
      const types = ['chart', 'form', 'markdown', 'sheet', 'image', 'video', 'custom'] as const;

      types.forEach(type => {
        const canvas: CanvasData = {
          id: `canvas-${type}`,
          canvas_type: type,
          content: {}
        };

        expect(canvas.canvas_type).toBe(type);
      });
    });
  });

  describe('PaginatedResponse', () => {
    it('has correct structure', () => {
      type AgentPaginated = PaginatedResponse<AgentResponse>;

      const response: AgentPaginated = {
        success: true,
        data: [
          {
            id: 'agent-1',
            name: 'Agent 1',
            maturity_level: 'AUTONOMOUS',
            status: 'active'
          },
          {
            id: 'agent-2',
            name: 'Agent 2',
            maturity_level: 'STUDENT',
            status: 'active'
          }
        ],
        pagination: {
          total: 2,
          page: 1,
          page_size: 50,
          total_pages: 1
        },
        timestamp: '2026-03-08T12:00:00Z'
      };

      expect(response.success).toBe(true);
      expect(response.data).toHaveLength(2);
      expect(response.pagination.total).toBe(2);
      expect(response.pagination.page).toBe(1);
    });

    it('handles empty data array', () => {
      type EmptyPaginated = PaginatedResponse<AgentResponse>;

      const response: EmptyPaginated = {
        success: true,
        data: [],
        pagination: {
          total: 0,
          page: 1,
          page_size: 50,
          total_pages: 0
        },
        timestamp: '2026-03-08T12:00:00Z'
      };

      expect(response.data).toEqual([]);
      expect(response.pagination.total).toBe(0);
    });
  });

  describe('ErrorResponse', () => {
    it('has required fields', () => {
      const error: ErrorResponse = {
        success: false,
        error_code: 'NOT_FOUND',
        message: 'Resource not found'
      };

      expect(error.success).toBe(false);
      expect(error.error_code).toBe('NOT_FOUND');
      expect(error.message).toBe('Resource not found');
    });

    it('accepts optional details', () => {
      const error: ErrorResponse = {
        success: false,
        error_code: 'VALIDATION_ERROR',
        message: 'Invalid input',
        details: {
          field: 'email',
          error: 'Invalid email format'
        }
      };

      expect(error.details).toBeDefined();
      expect(error.details?.field).toBe('email');
    });

    it('accepts optional request_id', () => {
      const error: ErrorResponse = {
        success: false,
        error_code: 'INTERNAL_ERROR',
        message: 'Server error',
        request_id: 'req_abc123'
      };

      expect(error.request_id).toBe('req_abc123');
    });
  });

  describe('Type Compatibility', () => {
    it('AgentResponse has correct field types', () => {
      const agent: AgentResponse = {
        id: 'string',
        name: 'string',
        maturity_level: 'AUTONOMOUS',
        status: 'string'
      };

      // Type assertions
      expect(typeof agent.id).toBe('string');
      expect(typeof agent.name).toBe('string');
      expect(typeof agent.maturity_level).toBe('string');
      expect(typeof agent.status).toBe('string');
    });

    it('CanvasData content can be any object', () => {
      const canvas: CanvasData = {
        id: 'canvas-1',
        canvas_type: 'chart',
        content: {
          chartType: 'line',
          data: [1, 2, 3],
          labels: ['A', 'B', 'C']
        }
      };

      expect(typeof canvas.content).toBe('object');
      expect(canvas.content).toHaveProperty('chartType');
    });
  });

  describe('Optional vs Required Fields', () => {
    it('AgentResponse optional fields are truly optional', () => {
      const minimalAgent: AgentResponse = {
        id: 'test',
        name: 'Test',
        maturity_level: 'AUTONOMOUS',
        status: 'active'
        // No optional fields
      };

      expect(minimalAgent.id).toBeDefined();
      expect(minimalAgent.description).toBeUndefined();
    });

    it('ErrorResponse details is optional', () => {
      const errorWithoutDetails: ErrorResponse = {
        success: false,
        error_code: 'ERROR',
        message: 'Error occurred'
        // No details
      };

      expect(errorWithoutDetails.details).toBeUndefined();
    });
  });

  describe('Timestamp Format', () => {
    it('accepts ISO 8601 timestamp strings', () => {
      const timestamps = [
        '2026-03-08T12:00:00Z',
        '2026-03-08T12:00:00.000Z',
        '2026-03-08T12:00:00+00:00'
      ];

      timestamps.forEach(timestamp => {
        const response: PaginatedResponse<AgentResponse> = {
          success: true,
          data: [],
          pagination: { total: 0, page: 1, page_size: 50, total_pages: 0 },
          timestamp
        };

        expect(response.timestamp).toBe(timestamp);
      });
    });
  });
});
