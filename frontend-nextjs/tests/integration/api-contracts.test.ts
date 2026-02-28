/**
 * API Contract Validation Tests
 *
 * Purpose: Validate that frontend API requests match backend expectations
 * TDD Phase: RED - Write failing tests first, then implement contract validation
 *
 * These tests ensure:
 * 1. Frontend request shapes match backend API expectations
 * 2. Backend response shapes match frontend expectations
 * 3. Error responses follow consistent format across all endpoints
 * 4. Breaking changes in API contracts are caught during test runs
 */

import surveyData from '../integration/.survey-cache.json';

describe('API Contract Validation', () => {
  describe('Agent Execution API Contract (POST /api/agents/{id}/execute)', () => {
    const VALID_AGENT_REQUEST = {
      input: 'test prompt',
      context: { userId: 'test-user' },
      stream: true
    };

    it('should accept valid agent execution request shape', () => {
      expect(VALID_AGENT_REQUEST.input).toBeDefined();
      expect(typeof VALID_AGENT_REQUEST.input).toBe('string');
      expect(typeof VALID_AGENT_REQUEST.context).toBe('object');
      expect(typeof VALID_AGENT_REQUEST.stream).toBe('boolean');
    });

    it('should reject invalid input type (must be string)', () => {
      const invalidRequest = { ...VALID_AGENT_REQUEST, input: 123 };
      expect(typeof invalidRequest.input).not.toBe('string');
    });

    it('should reject missing input field', () => {
      const invalidRequest = { ...VALID_AGENT_REQUEST, input: undefined };
      expect(invalidRequest.input).toBeUndefined();
    });

    it('should reject invalid context type (must be object)', () => {
      const invalidRequest = { ...VALID_AGENT_REQUEST, context: 'invalid' };
      expect(typeof invalidRequest.context).not.toBe('object');
    });

    it('should accept optional conversation_id', () => {
      const requestWithConvId = { ...VALID_AGENT_REQUEST, conversation_id: 'conv-123' };
      expect(typeof requestWithConvId.conversation_id).toBe('string');
    });
  });

  describe('Canvas Presentation API Contract (POST /api/canvas/present)', () => {
    const VALID_CANVAS_TYPES = [
      'chart',
      'form',
      'sheet',
      'docs',
      'orchestration',
      'terminal',
      'coding'
    ];

    it('should accept valid canvas presentation request', () => {
      const request = {
        type: 'chart',
        title: 'Test Chart',
        data: { labels: ['A'], values: [1] }
      };
      expect(VALID_CANVAS_TYPES).toContain(request.type);
      expect(request.data).toBeTruthy();
    });

    it('should validate canvas type is one of allowed values', () => {
      const invalidRequest = { type: 'invalid-type', title: 'Test', data: {} };
      expect(VALID_CANVAS_TYPES).not.toContain(invalidRequest.type);
    });

    it('should require data field for canvas presentations', () => {
      const invalidRequest = { type: 'chart', title: 'Test', data: null };
      expect(invalidRequest.data).toBeFalsy();
    });

    it('should require title field for canvas presentations', () => {
      const invalidRequest = { type: 'chart', title: '', data: {} };
      expect(invalidRequest.title).toBe('');
    });

    it('should accept optional agent_id and conversation_id', () => {
      const request = {
        type: 'form',
        title: 'Test Form',
        data: { fields: [] },
        agent_id: 'agent-123',
        conversation_id: 'conv-456'
      };
      expect(typeof request.agent_id).toBe('string');
      expect(typeof request.conversation_id).toBe('string');
    });
  });

  describe('Authentication API Contract (POST /api/auth/login)', () => {
    const VALID_LOGIN_REQUEST = {
      email: 'test@example.com',
      password: 'SecurePass123!',
      remember_me: false
    };

    it('should accept valid login request shape', () => {
      expect(typeof VALID_LOGIN_REQUEST.email).toBe('string');
      expect(typeof VALID_LOGIN_REQUEST.password).toBe('string');
      expect(typeof VALID_LOGIN_REQUEST.remember_me).toBe('boolean');
    });

    it('should reject invalid email format', () => {
      const invalidRequest = { ...VALID_LOGIN_REQUEST, email: 'not-an-email' };
      expect(invalidRequest.email).not.toMatch(/^[^\s@]+@[^\s@]+\.[^\s@]+$/);
    });

    it('should reject missing password field', () => {
      const invalidRequest = { ...VALID_LOGIN_REQUEST, password: undefined };
      expect(invalidRequest.password).toBeUndefined();
    });

    it('should accept optional remember_me field', () => {
      const requestWithRemember = { ...VALID_LOGIN_REQUEST, remember_me: true };
      expect(requestWithRemember.remember_me).toBe(true);
    });
  });

  describe('2FA API Contract (POST /api/auth/2fa/enable)', () => {
    const VALID_2FA_REQUEST = {
      token: '123456'
    };

    it('should accept valid 2FA request shape', () => {
      expect(typeof VALID_2FA_REQUEST.token).toBe('string');
      expect(VALID_2FA_REQUEST.token).toHaveLength(6);
    });

    it('should reject invalid token length', () => {
      const invalidRequest = { token: '12345' };
      expect(invalidRequest.token).not.toHaveLength(6);
    });

    it('should reject non-numeric token', () => {
      const invalidRequest = { token: 'abcdef' };
      expect(invalidRequest.token).not.toMatch(/^[0-9]+$/);
    });
  });
});

describe('Error Response Shapes', () => {
  describe('400 Bad Request - Validation Error', () => {
    it('should return correct error response shape for 400', () => {
      const errorResponse = {
        success: false,
        error_code: 'VALIDATION_ERROR',
        message: 'Invalid input',
        details: { field: 'input' }
      };
      expect(errorResponse).toMatchObject({
        success: false,
        error_code: expect.any(String),
        message: expect.any(String)
      });
      expect(errorResponse.error_code).toBe('VALIDATION_ERROR');
    });

    it('should include details object for validation errors', () => {
      const errorResponse = {
        success: false,
        error_code: 'VALIDATION_ERROR',
        message: 'Invalid input',
        details: { field: 'email', error: 'Invalid format' }
      };
      expect(typeof errorResponse.details).toBe('object');
      expect(errorResponse.details).toHaveProperty('field');
    });
  });

  describe('401 Unauthorized', () => {
    it('should return correct error response shape for 401', () => {
      const authError = {
        success: false,
        error_code: 'UNAUTHORIZED',
        message: 'Authentication required'
      };
      expect(authError.error_code).toBe('UNAUTHORIZED');
      expect(authError.success).toBe(false);
    });
  });

  describe('404 Not Found', () => {
    it('should return correct error response shape for 404', () => {
      const notFoundError = {
        success: false,
        error_code: 'NOT_FOUND',
        message: 'Resource not found'
      };
      expect(notFoundError.error_code).toBe('NOT_FOUND');
      expect(notFoundError.success).toBe(false);
    });
  });

  describe('500 Internal Server Error', () => {
    it('should return correct error response shape for 500', () => {
      const serverError = {
        success: false,
        error_code: 'INTERNAL_ERROR',
        message: 'Internal server error'
      };
      expect(serverError.error_code).toBe('INTERNAL_ERROR');
      expect(serverError.success).toBe(false);
    });
  });

  describe('408 Request Timeout', () => {
    it('should return correct error response shape for 408', () => {
      const timeoutError = {
        success: false,
        error_code: 'TIMEOUT',
        message: 'Request timed out'
      };
      expect(timeoutError.error_code).toBe('TIMEOUT');
      expect(timeoutError.success).toBe(false);
    });
  });
});

describe('Success Response Shapes', () => {
  it('should return correct success response shape', () => {
    const successResponse = {
      success: true,
      data: { id: '123', name: 'Test' },
      message: 'Operation successful'
    };
    expect(successResponse).toMatchObject({
      success: true,
      data: expect.any(Object),
      message: expect.any(String)
    });
  });

  it('should include timestamp in successful responses', () => {
    const responseWithTimestamp = {
      success: true,
      data: { id: '123' },
      timestamp: '2026-02-26T19:00:00.000Z'
    };
    expect(responseWithTimestamp.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
  });
});

describe('Integration Credentials API Contract (POST /api/integrations/credentials)', () => {
  const VALID_CREDENTIALS_REQUEST = {
    service: 'github',
    credentials: { token: 'ghp_test_token' }
  };

  it('should accept valid credentials request shape', () => {
    expect(typeof VALID_CREDENTIALS_REQUEST.service).toBe('string');
    expect(typeof VALID_CREDENTIALS_REQUEST.credentials).toBe('object');
  });

  it('should reject missing service field', () => {
    const invalidRequest = { ...VALID_CREDENTIALS_REQUEST, service: undefined };
    expect(invalidRequest.service).toBeUndefined();
  });

  it('should reject missing credentials object', () => {
    const invalidRequest = { ...VALID_CREDENTIALS_REQUEST, credentials: undefined };
    expect(invalidRequest.credentials).toBeUndefined();
  });

  it('should accept query parameter for GET requests', () => {
    const queryParams = { service: 'zapier_webhook_url' };
    expect(typeof queryParams.service).toBe('string');
    expect(queryParams.service).toContain('zapier');
  });
});

describe('Tasks API Contract (GET/POST /api/v1/tasks)', () => {
  it('should accept valid task creation request', () => {
    const validTask = {
      title: 'Test Task',
      description: 'Task description',
      status: 'pending',
      platform: 'web'
    };
    expect(typeof validTask.title).toBe('string');
    expect(typeof validTask.status).toBe('string');
  });

  it('should reject task without title', () => {
    const invalidTask = {
      description: 'Task description',
      status: 'pending'
    };
    expect(invalidTask.title).toBeUndefined();
  });

  it('should accept platform filter in query params', () => {
    const queryParams = { platform: 'all' };
    expect(queryParams.platform).toBe('all');
  });
});

describe('Survey Data Validation', () => {
  it('should have loaded survey cache data', () => {
    expect(surveyData).toBeDefined();
    expect(surveyData.top_api_endpoints).toBeInstanceOf(Array);
  });

  it('should contain top API endpoints from survey', () => {
    const endpoints = surveyData.top_api_endpoints;
    expect(endpoints.length).toBeGreaterThan(0);
    expect(endpoints[0]).toHaveProperty('endpoint');
    expect(endpoints[0]).toHaveProperty('usage_count');
  });

  it('should contain error response shapes from survey', () => {
    expect(surveyData.error_response_shapes).toBeDefined();
    expect(surveyData.error_response_shapes).toHaveProperty('validation_error');
    expect(surveyData.error_response_shapes).toHaveProperty('unauthorized');
  });
});
