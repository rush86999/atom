/**
 * Mock Data Generators
 *
 * Provides factory functions for generating consistent mock data across tests.
 * Each generator accepts an overrides object for customizing specific fields.
 *
 * Usage:
 * ```typescript
 * import { mockAgentExecution, mockCanvasAudit } from '@/tests/mocks/data';
 *
 * const execution = mockAgentExecution({
 *   status: 'failed',
 *   agent_id: 'custom-agent-id'
 * });
 * ```
 */

// ============================================================================
// Agent Execution Mock Data
// ============================================================================

export interface MockAgentExecutionOptions {
  id?: string;
  agent_id?: string;
  status?: string;
  created_at?: string;
  completed_at?: string;
  error?: string;
}

/**
 * Generate mock agent execution data
 *
 * @param overrides - Optional fields to override defaults
 * @returns Mock agent execution object
 */
export const mockAgentExecution = (overrides: MockAgentExecutionOptions = {}) => ({
  id: 'exec-mock-123',
  agent_id: 'agent-mock-456',
  status: 'completed',
  created_at: new Date().toISOString(),
  completed_at: new Date().toISOString(),
  error: null,
  ...overrides,
});

// ============================================================================
// Canvas Audit Mock Data
// ============================================================================

export interface MockCanvasAuditOptions {
  id?: string;
  canvas_id?: string;
  action?: string;
  timestamp?: string;
  agent_id?: string;
}

/**
 * Generate mock canvas audit data
 *
 * @param overrides - Optional fields to override defaults
 * @returns Mock canvas audit object
 */
export const mockCanvasAudit = (overrides: MockCanvasAuditOptions = {}) => ({
  id: 'audit-mock-789',
  canvas_id: 'canvas-mock-001',
  action: 'present',
  timestamp: new Date().toISOString(),
  agent_id: 'agent-mock-456',
  ...overrides,
});

// ============================================================================
// Device Session Mock Data
// ============================================================================

export interface MockDeviceSessionOptions {
  id?: string;
  device_node_id?: string;
  status?: string;
  started_at?: string;
  ended_at?: string;
}

/**
 * Generate mock device session data
 *
 * @param overrides - Optional fields to override defaults
 * @returns Mock device session object
 */
export const mockDeviceSession = (overrides: MockDeviceSessionOptions = {}) => ({
  id: 'session-mock-abc',
  device_node_id: 'device-mock-123',
  status: 'active',
  started_at: new Date().toISOString(),
  ended_at: null,
  ...overrides,
});

// ============================================================================
// Agent Registry Mock Data
// ============================================================================

export interface MockAgentOptions {
  id?: string;
  name?: string;
  description?: string;
  maturity_level?: string;
  status?: string;
  confidence?: number;
}

/**
 * Generate mock agent registry data
 *
 * @param overrides - Optional fields to override defaults
 * @returns Mock agent object
 */
export const mockAgent = (overrides: MockAgentOptions = {}) => ({
  id: 'agent-mock-001',
  name: 'Test Agent',
  description: 'Mock agent for testing',
  maturity_level: 'AUTONOMOUS',
  status: 'active',
  confidence: 0.95,
  created_at: new Date().toISOString(),
  ...overrides,
});

// ============================================================================
// Chat Message Mock Data
// ============================================================================

export interface MockChatMessageOptions {
  role?: string;
  content?: string;
  timestamp?: string;
}

/**
 * Generate mock chat message data
 *
 * @param overrides - Optional fields to override defaults
 * @returns Mock chat message object
 */
export const mockChatMessage = (overrides: MockChatMessageOptions = {}) => ({
  role: 'user',
  content: 'Test message',
  timestamp: new Date().toISOString(),
  ...overrides,
});

// ============================================================================
// Form Submission Mock Data
// ============================================================================

export interface MockFormSubmissionOptions {
  canvas_id?: string;
  form_data?: Record<string, any>;
  agent_execution_id?: string;
  agent_id?: string;
}

/**
 * Generate mock form submission data
 *
 * @param overrides - Optional fields to override defaults
 * @returns Mock form submission object
 */
export const mockFormSubmission = (overrides: MockFormSubmissionOptions = {}) => ({
  canvas_id: 'canvas-mock-001',
  form_data: { field1: 'value1', field2: 'value2' },
  agent_execution_id: 'exec-mock-123',
  agent_id: 'agent-mock-001',
  ...overrides,
});

// ============================================================================
// Device Node Mock Data
// ============================================================================

export interface MockDeviceNodeOptions {
  id?: string;
  device_id?: string;
  name?: string;
  node_type?: string;
  status?: string;
  capabilities?: string[];
}

/**
 * Generate mock device node data
 *
 * @param overrides - Optional fields to override defaults
 * @returns Mock device node object
 */
export const mockDeviceNode = (overrides: MockDeviceNodeOptions = {}) => ({
  id: 'device-mock-001',
  device_id: 'camera-001',
  name: 'Mock Camera',
  node_type: 'camera',
  status: 'online',
  capabilities: ['snap', 'stream'],
  ...overrides,
});

// ============================================================================
// Batch Generators
// ============================================================================

/**
 * Generate multiple mock agent executions
 *
 * @param count - Number of executions to generate
 * @param overrides - Optional fields to override defaults
 * @returns Array of mock agent execution objects
 */
export const mockAgentExecutions = (
  count: number,
  overrides: MockAgentExecutionOptions = {}
) =>
  Array.from({ length: count }, (_, i) =>
    mockAgentExecution({
      ...overrides,
      id: `exec-mock-${i}`,
    })
  );

/**
 * Generate multiple mock canvas audits
 *
 * @param count - Number of audits to generate
 * @param overrides - Optional fields to override defaults
 * @returns Array of mock canvas audit objects
 */
export const mockCanvasAudits = (
  count: number,
  overrides: MockCanvasAuditOptions = {}
) =>
  Array.from({ length: count }, (_, i) =>
    mockCanvasAudit({
      ...overrides,
      id: `audit-mock-${i}`,
    })
  );

/**
 * Generate multiple mock agents
 *
 * @param count - Number of agents to generate
 * @param overrides - Optional fields to override defaults
 * @returns Array of mock agent objects
 */
export const mockAgents = (count: number, overrides: MockAgentOptions = {}) =>
  Array.from({ length: count }, (_, i) =>
    mockAgent({
      ...overrides,
      id: `agent-mock-${i}`,
      name: `Test Agent ${i}`,
    })
  );
