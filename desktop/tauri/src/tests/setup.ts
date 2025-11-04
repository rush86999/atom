/**
 * Jest Test Setup
 */

// Mock Tauri API
jest.mock('@tauri-apps/api/tauri', () => ({
  invoke: jest.fn()
}));

// Mock Date for consistent testing
const mockDate = new Date('2025-11-02T10:00:00Z');
Object.defineProperty(global, 'Date', {
  value: jest.fn(() => mockDate),
  writable: true,
});

// Mock console methods for cleaner test output
global.console = {
  ...console,
  log: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
  debug: jest.fn()
};

// Extend Jest matchers
expect.extend({
  toBeWithinRange(received: number, floor: number, ceiling: number) {
    const pass = received >= floor && received <= ceiling;
    if (pass) {
      return {
        message: () =>
          `expected ${received} not to be within range ${floor} - ${ceiling}`,
        pass: true,
      };
    } else {
      return {
        message: () =>
          `expected ${received} to be within range ${floor} - ${ceiling}`,
        pass: false,
      };
    }
  },
});

// Mock WebSocket for EventBus
global.WebSocket = jest.fn().mockImplementation(() => ({
  close: jest.fn(),
  send: jest.fn(),
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
}));

// Setup global test utilities
global.mockInvoke = jest.fn();
global.mockDate = mockDate;

// Test utilities
export const createMockEvent = (type: string, data: any) => ({
  type,
  data,
  timestamp: mockDate.toISOString()
});

export const createMockUserContext = () => ({
  userId: 'test-user',
  sessionId: 'test-session',
  timestamp: mockDate.toISOString(),
  intent: 'test_intent',
  entities: [],
  confidence: 0.9
});