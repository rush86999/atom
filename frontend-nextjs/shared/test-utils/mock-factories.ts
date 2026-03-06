/**
 * Mock Factory Functions for Cross-Platform Testing
 *
 * Shared mock object factories that work across web (React), mobile (React Native),
 * and desktop (Electron/Tauri) testing environments.
 *
 * These factories provide type-safe mock objects using Jest's MockedFunction type
 * for full TypeScript compatibility and IntelliSense support.
 *
 * @module @atom/test-utils/mock-factories
 */

import type { MockWebSocket } from './types';

// ============================================================================
// Mock WebSocket Factory
// ============================================================================

/**
 * Create a mock WebSocket with realistic connection behavior
 * For testing WebSocket-dependent components
 *
 * @param connected - Initial connection state (default: true)
 * @returns MockWebSocket object with jest.MockedFunction methods
 *
 * @example
 * const mockSocket = createMockWebSocket(true);
 * expect(mockSocket.connected).toBe(true);
 * expect(mockSocket.send).toBeDefined();
 *
 * // Simulate sending data
 * mockSocket.send('{"type":"message"}');
 * expect(mockSocket.send).toHaveBeenCalledWith('{"type":"message"}');
 *
 * // Simulate connection state change
 * mockSocket.connected = false;
 * expect(mockSocket.connected).toBe(false);
 */
export const createMockWebSocket = (connected = true): MockWebSocket => {
  return {
    url: 'ws://localhost:8000',
    connected,
    onopen: null,
    onmessage: null,
    onerror: null,
    onclose: null,
    send: jest.fn(),
    close: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
  };
};

// ============================================================================
// Mock Function Factories
// ============================================================================

/**
 * Create a mock function with implementation
 * Generic factory for typed synchronous mock functions
 *
 * @typeParam T - Function type signature
 * @param implementation - Implementation function
 * @returns jest.MockedFunction<T> - Typed mock function
 *
 * @example
 * const mockFn = createMockFn((x: number) => x * 2);
 * expect(mockFn(5)).toBe(10);
 * expect(mockFn).toHaveBeenCalledWith(5);
 *
 * @example
 * interface UserService {
 *   getName: (id: string) => string;
 * }
 * const getNameMock = createMockFn<UserService['getName']>((id) => `User-${id}`);
 * expect(getNameMock('123')).toBe('User-123');
 */
export const createMockFn = <T extends (...args: unknown[]) => unknown>(
  implementation: T
): jest.MockedFunction<T> => {
  return jest.fn(implementation) as jest.MockedFunction<T>;
};

/**
 * Create a mock async function with implementation
 * Generic factory for typed asynchronous mock functions
 *
 * @typeParam T - Async function type signature returning Promise
 * @param implementation - Implementation function
 * @returns jest.MockedFunction<T> - Typed async mock function
 *
 * @example
 * const mockAsyncFn = createMockAsyncFn(async (id: number) => {
 *   return { id, name: 'Test' };
 * });
 * const result = await mockAsyncFn(1);
 * expect(result).toEqual({ id: 1, name: 'Test' });
 *
 * @example
 * interface ApiService {
 *   fetchUser: (id: string) => Promise<{ id: string; name: string }>;
 * }
 * const fetchUserMock = createMockAsyncFn<ApiService['fetchUser']>(async (id) => {
 *   return { id, name: `User-${id}` };
 * });
 * const user = await fetchUserMock('abc');
 * expect(user.name).toBe('User-abc');
 */
export const createMockAsyncFn = <
  T extends (...args: unknown[]) => Promise<unknown>
>(
  implementation: T
): jest.MockedFunction<T> => {
  return jest.fn(implementation) as jest.MockedFunction<T>;
};
