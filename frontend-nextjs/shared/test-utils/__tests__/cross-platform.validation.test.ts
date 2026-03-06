/**
 * Cross-platform validation test for shared utilities
 *
 * This test validates that all shared utilities are:
 * - Importable via @atom/test-utils
 * - Functionally correct (basic smoke tests)
 * - Type-safe (TypeScript compilation)
 *
 * Run from frontend: cd frontend-nextjs && npm test -- cross-platform.validation
 * Run from mobile: cd mobile && npm test -- cross-platform.validation
 */

import {
  // Async utilities (Plan 02)
  waitForAsync,
  flushPromises,
  waitForCondition,
  wait,
  advanceTimersByTime,
  advanceTimersByTimeSync,
  // Mock factories (Plan 03)
  createMockWebSocket,
  createMockFn,
  createMockAsyncFn,
  // Assertions (Plan 03)
  assertThrows,
  assertRejects,
  assertRendersWithoutThrow,
  // Platform guards (Plan 04)
  isWeb,
  isReactNative,
  isTauri,
  isIOS,
  isAndroid,
  skipIfNotWeb,
  // Cleanup (Plan 04)
  resetAllMocks,
  setupFakeTimers,
  cleanupTest,
  // Test data (Plan 05a)
  mockAgents,
  mockWorkflows,
  mockUser,
  testDataFixture,
  // Types (Plan 01)
  type MockWebSocket,
  type MockAgent,
  type MockWorkflow,
  type MockUser,
} from '@atom/test-utils';

describe('Cross-Platform Shared Utilities Validation', () => {
  describe('Async Utilities', () => {
    it('should import waitForAsync', () => {
      expect(typeof waitForAsync).toBe('function');
    });

    it('should import flushPromises', () => {
      expect(typeof flushPromises).toBe('function');
    });

    it('should import waitForCondition', () => {
      expect(typeof waitForCondition).toBe('function');
    });

    it('should import wait', () => {
      expect(typeof wait).toBe('function');
    });

    it('should import advanceTimersByTime', () => {
      expect(typeof advanceTimersByTime).toBe('function');
    });

    it('should import advanceTimersByTimeSync', () => {
      expect(typeof advanceTimersByTimeSync).toBe('function');
    });

    it('should execute flushPromises without errors', async () => {
      await expect(flushPromises()).resolves.not.toThrow();
    });
  });

  describe('Mock Factories', () => {
    it('should import createMockWebSocket', () => {
      expect(typeof createMockWebSocket).toBe('function');
    });

    it('should import createMockFn', () => {
      expect(typeof createMockFn).toBe('function');
    });

    it('should import createMockAsyncFn', () => {
      expect(typeof createMockAsyncFn).toBe('function');
    });

    it('should create mock WebSocket with expected interface', () => {
      const mockWs = createMockWebSocket(true);
      expect(mockWs).toHaveProperty('url');
      expect(mockWs).toHaveProperty('connected');
      expect(mockWs).toHaveProperty('send');
      expect(mockWs).toHaveProperty('close');
    });
  });

  describe('Assertions', () => {
    it('should import assertThrows', () => {
      expect(typeof assertThrows).toBe('function');
    });

    it('should import assertRejects', () => {
      expect(typeof assertRejects).toBe('function');
    });

    it('should import assertRendersWithoutThrow', () => {
      expect(typeof assertRendersWithoutThrow).toBe('function');
    });

    it('should assert throws correctly', () => {
      expect(() => assertThrows(() => { throw new Error('test'); })).not.toThrow();
    });
  });

  describe('Platform Guards', () => {
    it('should import isWeb', () => {
      expect(typeof isWeb).toBe('function');
    });

    it('should import isReactNative', () => {
      expect(typeof isReactNative).toBe('function');
    });

    it('should import isTauri', () => {
      expect(typeof isTauri).toBe('function');
    });

    it('should import isIOS', () => {
      expect(typeof isIOS).toBe('function');
    });

    it('should import isAndroid', () => {
      expect(typeof isAndroid).toBe('function');
    });

    it('should import skipIfNotWeb', () => {
      expect(typeof skipIfNotWeb).toBe('function');
    });

    it('should detect platform correctly', () => {
      const web = isWeb();
      const rn = isReactNative();
      const tauri = isTauri();
      // At least one should be true in a test environment
      expect(web || rn || tauri).toBe(true);
    });
  });

  describe('Cleanup Utilities', () => {
    it('should import resetAllMocks', () => {
      expect(typeof resetAllMocks).toBe('function');
    });

    it('should import setupFakeTimers', () => {
      expect(typeof setupFakeTimers).toBe('function');
    });

    it('should import cleanupTest', () => {
      expect(typeof cleanupTest).toBe('function');
    });

    it('should execute setupFakeTimers without errors', () => {
      expect(() => setupFakeTimers()).not.toThrow();
    });
  });

  describe('Test Data Fixtures', () => {
    it('should import mockAgents', () => {
      expect(Array.isArray(mockAgents)).toBe(true);
      expect(mockAgents.length).toBeGreaterThan(0);
    });

    it('should import mockWorkflows', () => {
      expect(Array.isArray(mockWorkflows)).toBe(true);
      expect(mockWorkflows.length).toBeGreaterThan(0);
    });

    it('should import mockUser', () => {
      expect(typeof mockUser).toBe('object');
      expect(mockUser).toHaveProperty('id');
      expect(mockUser).toHaveProperty('email');
    });

    it('should import testDataFixture', () => {
      expect(typeof testDataFixture).toBe('object');
      expect(testDataFixture).toHaveProperty('agents');
      expect(testDataFixture).toHaveProperty('workflows');
      expect(testDataFixture).toHaveProperty('user');
    });

    it('should have agents with expected structure', () => {
      const agent = mockAgents[0];
      expect(agent).toHaveProperty('id');
      expect(agent).toHaveProperty('name');
      expect(agent).toHaveProperty('maturity');
      expect(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS']).toContain(agent.maturity);
    });
  });
});
