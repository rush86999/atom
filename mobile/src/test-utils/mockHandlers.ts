/**
 * Mock API Handlers for Atom Mobile Tests
 *
 * This file provides Mock Service Worker (MSW) handlers for intercepting
 * API requests during tests. Mocks all backend endpoints for agents,
 * workflows, canvases, auth, and more.
 *
 * Features:
 * - REST API handlers (agents, workflows, canvases, episodes)
 * - Auth endpoint handlers
 * - WebSocket mock
 * - Error response handlers
 */

import { rest } from 'msw';
import { setupServer } from 'msw/node';

// Import mock data
import {
  mockAgents,
  mockCanvases,
  mockWorkflows,
  mockWorkflowExecutions,
  mockEpisodes,
  mockUser,
  mockConversations,
  mockMessages,
} from './mockData';

// ============================================================================
// API Base URL
// ============================================================================

const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';

// ============================================================================
// Auth Handlers
// ============================================================================

export const authHandlers = [
  // Login
  rest.post(`${API_BASE_URL}/api/auth/login`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: {
          user: mockUser,
          token: 'test-auth-token',
          refreshToken: 'test-refresh-token',
        },
      })
    );
  }),

  // Register
  rest.post(`${API_BASE_URL}/api/auth/register`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: {
          user: mockUser,
          token: 'test-auth-token',
        },
      })
    );
  }),

  // Refresh Token
  rest.post(`${API_BASE_URL}/api/auth/refresh`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: {
          token: 'new-test-auth-token',
        },
      })
    );
  }),

  // Logout
  rest.post(`${API_BASE_URL}/api/auth/logout`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        message: 'Logged out successfully',
      })
    );
  }),

  // Forgot Password
  rest.post(`${API_BASE_URL}/api/auth/forgot-password`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        message: 'Password reset email sent',
      })
    );
  }),
];

// ============================================================================
// Agent Handlers
// ============================================================================

export const agentHandlers = [
  // List Agents
  rest.get(`${API_BASE_URL}/api/agents`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: mockAgents,
      })
    );
  }),

  // Get Agent
  rest.get(`${API_BASE_URL}/api/agents/:id`, (req, res, ctx) => {
    const { id } = req.params;
    const agent = mockAgents.find((a) => a.id === id);

    if (!agent) {
      return res(
        ctx.status(404),
        ctx.json({
          success: false,
          error: 'Agent not found',
        })
      );
    }

    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: agent,
      })
    );
  }),

  // Execute Agent
  rest.post(`${API_BASE_URL}/api/agents/:id/execute`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: {
          executionId: 'execution-123',
          agentId: req.params.id,
          status: 'running',
          response: 'Agent is executing...',
        },
      })
    );
  }),
];

// ============================================================================
// Workflow Handlers
// ============================================================================

export const workflowHandlers = [
  // List Workflows
  rest.get(`${API_BASE_URL}/api/workflows`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: mockWorkflows,
      })
    );
  }),

  // Get Workflow
  rest.get(`${API_BASE_URL}/api/workflows/:id`, (req, res, ctx) => {
    const { id } = req.params;
    const workflow = mockWorkflows.find((w) => w.id === id);

    if (!workflow) {
      return res(
        ctx.status(404),
        ctx.json({
          success: false,
          error: 'Workflow not found',
        })
      );
    }

    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: workflow,
      })
    );
  }),

  // Trigger Workflow
  rest.post(`${API_BASE_URL}/api/workflows/:id/trigger`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: {
          executionId: 'execution-123',
          workflowId: req.params.id,
          status: 'running',
        },
      })
    );
  }),

  // Get Workflow Executions
  rest.get(`${API_BASE_URL}/api/workflows/:id/executions`, (req, res, ctx) => {
    const executions = mockWorkflowExecutions.filter(
      (e) => e.workflowId === req.params.id
    );

    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: executions,
      })
    );
  }),
];

// ============================================================================
// Canvas Handlers
// ============================================================================

export const canvasHandlers = [
  // List Canvases
  rest.get(`${API_BASE_URL}/api/canvases`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: mockCanvases,
      })
    );
  }),

  // Get Canvas
  rest.get(`${API_BASE_URL}/api/canvases/:id`, (req, res, ctx) => {
    const { id } = req.params;
    const canvas = mockCanvases.find((c) => c.id === id);

    if (!canvas) {
      return res(
        ctx.status(404),
        ctx.json({
          success: false,
          error: 'Canvas not found',
        })
      );
    }

    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: canvas,
      })
    );
  }),

  // Submit Canvas Form
  rest.post(`${API_BASE_URL}/api/canvases/:id/submit`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        message: 'Form submitted successfully',
      })
    );
  }),
];

// ============================================================================
// Episode Handlers
// ============================================================================

export const episodeHandlers = [
  // List Episodes
  rest.get(`${API_BASE_URL}/api/episodes`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: mockEpisodes,
      })
    );
  }),

  // Get Episode
  rest.get(`${API_BASE_URL}/api/episodes/:id`, (req, res, ctx) => {
    const { id } = req.params;
    const episode = mockEpisodes.find((e) => e.id === id);

    if (!episode) {
      return res(
        ctx.status(404),
        ctx.json({
          success: false,
          error: 'Episode not found',
        })
      );
    }

    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: episode,
      })
    );
  }),
];

// ============================================================================
// Chat/Conversation Handlers
// ============================================================================

export const chatHandlers = [
  // List Conversations
  rest.get(`${API_BASE_URL}/api/conversations`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: mockConversations,
      })
    );
  }),

  // Get Conversation Messages
  rest.get(`${API_BASE_URL}/api/conversations/:id/messages`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: mockMessages.filter((m) => m.conversationId === req.params.id),
      })
    );
  }),

  // Send Message
  rest.post(`${API_BASE_URL}/api/conversations/:id/messages`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: {
          id: 'message-new',
          role: 'assistant',
          content: 'This is a mock response',
          timestamp: new Date().toISOString(),
        },
      })
    );
  }),
];

// ============================================================================
// Device Handlers
// ============================================================================

export const deviceHandlers = [
  // Register Device
  rest.post(`${API_BASE_URL}/api/device/register`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: {
          deviceId: 'device-test-123',
          registeredAt: new Date().toISOString(),
        },
      })
    );
  }),

  // Update Device Token
  rest.put(`${API_BASE_URL}/api/device/token`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        message: 'Token updated successfully',
      })
    );
  }),
];

// ============================================================================
// Error Handlers
// ============================================================================

export const errorHandlers = [
  // 401 Unauthorized
  rest.get(`${API_BASE_URL}/api/401`, (req, res, ctx) => {
    return res(
      ctx.status(401),
      ctx.json({
        success: false,
        error_code: 'UNAUTHORIZED',
        message: 'Authentication required',
      })
    );
  }),

  // 403 Forbidden
  rest.get(`${API_BASE_URL}/api/403`, (req, res, ctx) => {
    return res(
      ctx.status(403),
      ctx.json({
        success: false,
        error_code: 'FORBIDDEN',
        message: 'Insufficient permissions',
      })
    );
  }),

  // 404 Not Found
  rest.get(`${API_BASE_URL}/api/404`, (req, res, ctx) => {
    return res(
      ctx.status(404),
      ctx.json({
        success: false,
        error_code: 'NOT_FOUND',
        message: 'Resource not found',
      })
    );
  }),

  // 500 Server Error
  rest.get(`${API_BASE_URL}/api/500`, (req, res, ctx) => {
    return res(
      ctx.status(500),
      ctx.json({
        success: false,
        error_code: 'INTERNAL_ERROR',
        message: 'Internal server error',
      })
    );
  }),
];

// ============================================================================
// Combine All Handlers
// ============================================================================

export const allHandlers = [
  ...authHandlers,
  ...agentHandlers,
  ...workflowHandlers,
  ...canvasHandlers,
  ...episodeHandlers,
  ...chatHandlers,
  ...deviceHandlers,
  ...errorHandlers,
];

// ============================================================================
// MSW Server Setup
// ============================================================================

export const mockServer = setupServer(...allHandlers);

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Start mock server (call in beforeAll)
 */
export function startMockServer() {
  mockServer.listen({
    onUnhandledRequest: 'warn',
  });
}

/**
 * Stop mock server (call in afterAll)
 */
export function stopMockServer() {
  mockServer.close();
}

/**
 * Reset request handlers (call in afterEach)
 */
export function resetMockHandlers() {
  mockServer.resetHandlers();
}

/**
 * Override specific handlers for testing error scenarios
 */
export function overrideHandlers(...handlers: rest.RequestHandler[]) {
  mockServer.resetHandlers(...allHandlers, ...handlers);
}

// ============================================================================
// Default Export
// ============================================================================

export default {
  authHandlers,
  agentHandlers,
  workflowHandlers,
  canvasHandlers,
  episodeHandlers,
  chatHandlers,
  deviceHandlers,
  errorHandlers,
  allHandlers,
  mockServer,
  startMockServer,
  stopMockServer,
  resetMockHandlers,
  overrideHandlers,
};
