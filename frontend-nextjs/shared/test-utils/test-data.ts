/**
 * Shared Test Data Fixtures
 *
 * Common test data fixtures (agents, workflows, users) usable across
 * frontend, mobile, and desktop platforms. Reduces duplication and ensures
 * consistent test data.
 *
 * TypeScript exports for web/mobile testing, JSON fixtures for Rust desktop.
 *
 * @module @atom/test-utils/test-data
 */

import type { MockAgent, MockWorkflow, MockUser, TestDataFixture } from './types';

// ============================================================================
// Common Test Agents
// ============================================================================

/**
 * Common test agents for governance and execution tests
 *
 * @example
 * import { mockAgents } from '@atom/test-utils';
 *
 * test('agent maturity levels', () => {
 *   const autonomousAgent = mockAgents.find(a => a.maturity === 'AUTONOMOUS');
 *   expect(autonomousAgent?.confidence).toBeGreaterThan(0.9);
 * });
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

// ============================================================================
// Common Test Workflows
// ============================================================================

/**
 * Common test workflows for workflow engine tests
 *
 * @example
 * import { mockWorkflows } from '@atom/test-utils';
 *
 * test('workflow status', () => {
 *   const runningWorkflow = mockWorkflows.find(w => w.status === 'running');
 *   expect(runningWorkflow?.steps).toBeGreaterThan(0);
 * });
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

// ============================================================================
// Common Test User
// ============================================================================

/**
 * Common test user for authentication and authorization tests
 *
 * @example
 * import { mockUser } from '@atom/test-utils';
 *
 * test('user authentication', () => {
 *   expect(mockUser.email).toContain('@');
 *   expect(mockUser.id).toBeTruthy();
 * });
 */
export const mockUser: MockUser = {
  id: 'user-1',
  name: 'Test User',
  email: 'test@example.com',
};

// ============================================================================
// Complete Test Data Fixture Bundle
// ============================================================================

/**
 * Complete test data fixture bundle
 *
 * Provides all common test data in a single object for convenient imports.
 * Use this when you need multiple fixture types in a test.
 *
 * @example
 * import { testDataFixture } from '@atom/test-utils';
 *
 * test('agent execution with workflow', () => {
 *   const { agents, workflows, user } = testDataFixture;
 *   const agent = agents[0];
 *   const workflow = workflows[0];
 *   // Test agent executing workflow with user context
 * });
 */
export const testDataFixture: TestDataFixture = {
  agents: mockAgents,
  workflows: mockWorkflows,
  user: mockUser,
};
