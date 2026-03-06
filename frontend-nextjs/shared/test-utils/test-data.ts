/**
 * Shared Test Data Fixtures for Atom
 *
 * Common test data fixtures shared across:
 * - Frontend (Next.js with @testing-library/react)
 * - Mobile (React Native with @testing-library/react-native)
 * - Desktop (Tauri with cargo test - JSON fixtures only)
 *
 * Import via: @atom/test-utils
 *
 * @example
 * import { mockAgents, mockWorkflows, mockUser } from '@atom/test-utils';
 *
 * @module @atom/test-utils/test-data
 */

import type {
  MockAgent,
  MockWorkflow,
  MockUser,
  TestDataFixture,
} from './types';

/**
 * Common test agents for governance and execution tests
 *
 * Provides mock agents across all maturity levels for testing
 * agent governance, execution, and maturity-based routing.
 *
 * @example
 * const autonomousAgent = mockAgents.find(a => a.maturity === 'AUTONOMOUS');
 * expect(autonomousAgent.confidence).toBeGreaterThan(0.9);
 */
export const mockAgents: MockAgent[] = [
  {
    id: 'agent-1',
    name: 'Test Agent 1',
    maturity: 'AUTONOMOUS',
    confidence: 0.95,
  },
  {
    id: 'agent-2',
    name: 'Test Agent 2',
    maturity: 'SUPERVISED',
    confidence: 0.75,
  },
  {
    id: 'agent-3',
    name: 'Test Agent 3',
    maturity: 'INTERN',
    confidence: 0.55,
  },
  {
    id: 'agent-4',
    name: 'Test Agent 4',
    maturity: 'STUDENT',
    confidence: 0.35,
  },
];

/**
 * Common test workflows for workflow engine tests
 *
 * Provides mock workflows in various states for testing
 * workflow execution, step tracking, and state transitions.
 *
 * @example
 * const runningWorkflow = mockWorkflows.find(w => w.status === 'running');
 * expect(runningWorkflow.steps).toBe(10);
 */
export const mockWorkflows: MockWorkflow[] = [
  {
    id: 'workflow-1',
    name: 'Test Workflow 1',
    steps: 5,
    status: 'pending',
  },
  {
    id: 'workflow-2',
    name: 'Test Workflow 2',
    steps: 10,
    status: 'running',
  },
  {
    id: 'workflow-3',
    name: 'Test Workflow 3',
    steps: 3,
    status: 'completed',
  },
];

/**
 * Common test user for authentication and authorization tests
 *
 * Provides a standard mock user for testing authentication flows,
 * authorization checks, and user-specific features.
 *
 * @example
 * expect(mockUser.email).toMatch(/@example\.com$/);
 * expect(mockUser.id).toBe('user-1');
 */
export const mockUser: MockUser = {
  id: 'user-1',
  name: 'Test User',
  email: 'test@example.com',
};

/**
 * Complete test data fixture bundle
 *
 * Aggregates all test data fixtures into a single object for
 * convenient import in test files.
 *
 * @example
 * import { testDataFixture } from '@atom/test-utils';
 * const { agents, workflows, user } = testDataFixture;
 */
export const testDataFixture: TestDataFixture = {
  agents: mockAgents,
  workflows: mockWorkflows,
  user: mockUser,
};
