/**
 * Shared TypeScript Types for Test Utilities
 *
 * Common type definitions used across all platforms for testing.
 * These types provide interfaces for mocks, test data, and platform detection.
 *
 * @module @atom/test-utils/types
 */

/**
 * Mock WebSocket interface for testing WebSocket-dependent components
 * Works across web (native WebSocket), mobile (ReconnectingWebSocket), and desktop
 *
 * @example
 * const mockSocket: MockWebSocket = createMockWebSocket(true);
 * expect(mockSocket.connected).toBe(true);
 */
export interface MockWebSocket {
  /** WebSocket URL */
  url: string;
  /** Connection state */
  connected: boolean;
  /** Connection opened event handler */
  onopen: ((event: MessageEvent) => void) | null;
  /** Message received event handler */
  onmessage: ((event: MessageEvent) => void) | null;
  /** Error event handler */
  onerror: ((event: Event) => void) | null;
  /** Connection closed event handler */
  onclose: ((event: CloseEvent) => void) | null;
  /** Send data mock */
  send: jest.Mock;
  /** Close connection mock */
  close: jest.Mock;
  /** Add event listener mock */
  addEventListener: jest.Mock;
  /** Remove event listener mock */
  removeEventListener: jest.Mock;
}

/**
 * Mock agent data structure for agent governance tests
 *
 * @example
 * const mockAgent: MockAgent = {
 *   id: 'agent-123',
 *   name: 'Test Agent',
 *   maturity: 'AUTONOMOUS',
 *   confidence: 0.95
 * };
 */
export interface MockAgent {
  /** Unique agent identifier */
  id: string;
  /** Agent display name */
  name: string;
  /** Agent maturity level */
  maturity: 'STUDENT' | 'INTERN' | 'SUPERVISED' | 'AUTONOMOUS';
  /** Optional confidence score (0-1) */
  confidence?: number;
}

/**
 * Mock workflow data structure for workflow tests
 *
 * @example
 * const mockWorkflow: MockWorkflow = {
 *   id: 'workflow-456',
 *   name: 'Test Workflow',
 *   steps: 5,
 *   status: 'running'
 * };
 */
export interface MockWorkflow {
  /** Unique workflow identifier */
  id: string;
  /** Workflow display name */
  name: string;
  /** Number of workflow steps */
  steps: number;
  /** Optional workflow status */
  status?: 'pending' | 'running' | 'completed' | 'failed';
}

/**
 * Mock user data structure for authentication tests
 *
 * @example
 * const mockUser: MockUser = {
 *   id: 'user-789',
 *   name: 'Test User',
 *   email: 'test@example.com'
 * };
 */
export interface MockUser {
  /** Unique user identifier */
  id: string;
  /** User display name */
  name: string;
  /** User email address */
  email: string;
}

/**
 * Platform detection result type
 *
 * @example
 * const platform: PlatformType = getPlatform();
 * if (platform === 'ios') {
 *   // iOS-specific test setup
 * }
 */
export type PlatformType = 'web' | 'ios' | 'android' | 'desktop' | 'unknown';

/**
 * Test data fixture configuration
 * Provides common test data for consistent test scenarios across platforms
 *
 * @example
 * const fixture: TestDataFixture = {
 *   agents: mockAgents,
 *   workflows: mockWorkflows,
 *   user: mockUser
 * };
 */
export interface TestDataFixture {
  /** Array of mock agents */
  agents: MockAgent[];
  /** Array of mock workflows */
  workflows: MockWorkflow[];
  /** Mock user object */
  user: MockUser;
}

/**
 * Mock device info for platform-specific testing
 *
 * @example
 * const mockDeviceInfo: MockDeviceInfo = {
 *   osName: 'iOS',
 *   osVersion: '16.0',
 *   modelName: 'iPhone 14',
 *   platformApiLevel: 16
 * };
 */
export interface MockDeviceInfo {
  /** Operating system name */
  osName?: string;
  /** Operating system version */
  osVersion?: string;
  /** Device model name */
  modelName?: string;
  /** Device model ID */
  modelId?: string;
  /** Device brand */
  brand?: string;
  /** Device manufacturer */
  manufacturerName?: string;
  /** API level (Android) or platform version (iOS) */
  platformApiLevel?: number;
  /** Device year class */
  deviceYearClass?: number;
  /** Total memory in bytes */
  totalMemory?: number;
}

/**
 * Safe area insets for mobile testing
 *
 * @example
 * const insets: SafeAreaInsets = {
 *   top: 44,
 *   bottom: 34,
 *   left: 0,
 *   right: 0
 * };
 */
export interface SafeAreaInsets {
  /** Top inset (status bar, notch) */
  top: number;
  /** Bottom inset (home indicator, navigation bar) */
  bottom: number;
  /** Left inset (rounded corners, etc.) */
  left: number;
  /** Right inset (rounded corners, etc.) */
  right: number;
}

/**
 * Mock function with implementation
 * Generic typed mock function for testing
 *
 * @example
 * const mockFn = createMockFn((x: number) => x * 2);
 * expect(mockFn(5)).toBe(10);
 */
export type MockFunction<T extends (...args: unknown[]) => unknown> = jest.MockedFunction<T>;

/**
 * Async mock function with implementation
 * Generic typed async mock function for testing
 *
 * @example
 * const mockAsyncFn = createMockAsyncFn(async (id: string) => {
 *   return { id, name: 'Test' };
 * });
 */
export type MockAsyncFunction<T extends (...args: unknown[]) => Promise<unknown>> = jest.MockedFunction<T>;
