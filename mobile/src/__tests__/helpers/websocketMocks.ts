/**
 * WebSocket Mock Utilities
 *
 * Helper functions and mock classes for testing Socket.IO WebSocket functionality.
 * Provides realistic Socket.IO client mocking for WebSocketContext tests.
 *
 * @module websocketMocks
 *
 * @example
 * import { createMockSocket, simulateConnection, simulateEvent } from './websocketMocks';
 *
 * const mockSocket = createMockSocket('socket-1');
 * simulateConnection('socket-1');
 * simulateEvent('socket-1', 'agent:message', { text: 'Hello' });
 */

// ============================================================================
// TypeScript Interfaces
// ============================================================================

/**
 * Mock Socket.IO socket instance
 */
export interface MockSocket {
  /** Socket identifier */
  id: string;
  /** Connection URL */
  url: string;
  /** Connection options */
  opts: any;
  /** Current connection state */
  connected: boolean;
  /** Event handlers registry */
  eventHandlers: Map<string, Array<(...args: any[]) => void>>;
  ** Rooms the socket has joined */
  rooms: Set<string>;
  /** Events emitted to server (for verification) */
  emittedEvents: Array<{ event: string; data: any }>;

  /** Connect to server */
  connect(): void;
  /** Disconnect from server */
  disconnect(reason?: string): void;
  /** Emit event to server */
  emit(event: string, ...args: any[]): void;
  /** Register event handler */
  on(event: string, callback: (...args: any[]) => void): void;
  /** Unregister event handler */
  off(event: string, callback?: (...args: any[]) => void): void;
  /** Register one-time event handler */
  once(event: string, callback: (...args: any[]) => void): void;
}

/**
 * Options for creating mock socket
 */
export interface MockSocketOptions {
  /** Socket identifier (default: auto-generated UUID) */
  id?: string;
  /** Connection URL (required) */
  url: string;
  /** Connection options */
  opts?: any;
  /** Auto-connect on creation (default: true) */
  autoConnect?: boolean;
  /** Connection delay in ms (default: 0) */
  connectDelay?: number;
}

// ============================================================================
// Mock Socket Registry
// ============================================================================

/** Registry of all mock sockets */
const mockSockets = new Map<string, MockSocket>();

/** Counter for generating unique socket IDs */
let socketCounter = 0;

/**
 * Generate unique socket ID
 */
function generateSocketId(): string {
  return `mock_socket_${++socketCounter}`;
}

// ============================================================================
// MockSocket Class
// ============================================================================

/**
 * Mock Socket.IO socket implementation
 */
class MockSocketImpl implements MockSocket {
  id: string;
  url: string;
  opts: any;
  connected: boolean;
  eventHandlers: Map<string, Array<(...args: any[]) => void>>;
  rooms: Set<string>;
  emittedEvents: Array<{ event: string; data: any }>;
  private connectTimeout: NodeJS.Timeout | null = null;

  constructor(url: string, opts: any) {
    this.id = generateSocketId();
    this.url = url;
    this.opts = opts || {};
    this.connected = false;
    this.eventHandlers = new Map();
    this.rooms = new Set();
    this.emittedEvents = [];
  }

  connect(): void {
    if (this.connected) {
      console.log(`[MockSocket] ${this.id} already connected`);
      return;
    }

    console.log(`[MockSocket] ${this.id} connecting to ${this.url}`);
    this.connected = true;

    // Trigger connect event after delay
    const delay = this.opts.connectDelay || 0;
    this.connectTimeout = setTimeout(() => {
      this._triggerEvent('connect', this.id);
    }, delay);
  }

  disconnect(reason: string = 'client disconnect'): void {
    if (!this.connected) {
      console.log(`[MockSocket] ${this.id} not connected`);
      return;
    }

    console.log(`[MockSocket] ${this.id} disconnecting: ${reason}`);
    this.connected = false;

    if (this.connectTimeout) {
      clearTimeout(this.connectTimeout);
      this.connectTimeout = null;
    }

    // Trigger disconnect event
    this._triggerEvent('disconnect', reason);
  }

  emit(event: string, ...args: any[]): void {
    console.log(`[MockSocket] ${this.id} emitting: ${event}`, args);

    // Store emitted event for verification
    this.emittedEvents.push({
      event,
      data: args.length === 1 ? args[0] : args,
    });

    // Auto-respond to ping with pong
    if (event === 'ping') {
      setTimeout(() => {
        this._triggerEvent('pong');
      }, 10);
    }
  }

  on(event: string, callback: (...args: any[]) => void): void {
    console.log(`[MockSocket] ${this.id} registering handler for: ${event}`);

    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, []);
    }

    this.eventHandlers.get(event)!.push(callback);
  }

  off(event: string, callback?: (...args: any[]) => void): void {
    console.log(`[MockSocket] ${this.id} removing handler for: ${event}`);

    if (!this.eventHandlers.has(event)) {
      return;
    }

    if (callback) {
      // Remove specific callback
      const handlers = this.eventHandlers.get(event)!;
      const index = handlers.indexOf(callback);
      if (index > -1) {
        handlers.splice(index, 1);
      }

      if (handlers.length === 0) {
        this.eventHandlers.delete(event);
      }
    } else {
      // Remove all handlers for event
      this.eventHandlers.delete(event);
    }
  }

  once(event: string, callback: (...args: any[]) => void): void {
    console.log(`[MockSocket] ${this.id} registering one-time handler for: ${event}`);

    const wrappedCallback = (...args: any[]) => {
      callback(...args);
      this.off(event, wrappedCallback);
    };

    this.on(event, wrappedCallback);
  }

  /**
   * Trigger event to all registered handlers
   */
  private _triggerEvent(event: string, ...args: any[]): void {
    const handlers = this.eventHandlers.get(event);
    if (!handlers || handlers.length === 0) {
      console.log(`[MockSocket] ${this.id} no handlers for: ${event}`);
      return;
    }

    console.log(`[MockSocket] ${this.id} triggering: ${event}`, args);
    handlers.forEach(handler => {
      try {
        handler(...args);
      } catch (error) {
        console.error(`[MockSocket] ${this.id} error in handler for ${event}:`, error);
      }
    });
  }
}

// ============================================================================
// Factory Functions
// ============================================================================

/**
 * Create a new mock socket instance
 *
 * @param url - Connection URL
 * @param opts - Connection options
 * @returns Mock socket instance
 */
export function createMockSocket(url: string, opts?: any): MockSocket {
  const mockSocket = new MockSocketImpl(url, opts);
  mockSockets.set(mockSocket.id, mockSocket);

  // Auto-connect if specified
  if (opts?.autoConnect !== false) {
    mockSocket.connect();
  }

  return mockSocket;
}

/**
 * Get mock socket by ID
 *
 * @param socketId - Socket identifier
 * @returns Mock socket or undefined if not found
 */
export function getMockSocket(socketId: string): MockSocket | undefined {
  return mockSockets.get(socketId);
}

/**
 * Get all mock sockets
 *
 * @returns Array of all mock sockets
 */
export function getAllMockSockets(): MockSocket[] {
  return Array.from(mockSockets.values());
}

/**
 * Reset all mock sockets (clear registry)
 */
export function resetMockSockets(): void {
  // Disconnect all sockets
  mockSockets.forEach(socket => {
    if (socket.connected) {
      socket.disconnect('test cleanup');
    }
  });

  // Clear registry
  mockSockets.clear();
  socketCounter = 0;
}

// ============================================================================
// Simulation Helpers
// ============================================================================

/**
 * Simulate socket connection
 *
 * @param socketId - Socket identifier
 */
export function simulateConnection(socketId: string): void {
  const socket = mockSockets.get(socketId);
  if (!socket) {
    throw new Error(`Socket not found: ${socketId}`);
  }

  if (!socket.connected) {
    socket.connect();
  }
}

/**
 * Simulate socket disconnection
 *
 * @param socketId - Socket identifier
 * @param reason - Disconnection reason
 */
export function simulateDisconnection(socketId: string, reason: string = 'test disconnect'): void {
  const socket = mockSockets.get(socketId);
  if (!socket) {
    throw new Error(`Socket not found: ${socketId}`);
  }

  if (socket.connected) {
    socket.disconnect(reason);
  }
}

/**
 * Simulate server sending event to socket
 *
 * @param socketId - Socket identifier
 * @param event - Event name
 * @param data - Event data
 */
export function simulateEvent(socketId: string, event: string, data?: any): void {
  const socket = mockSockets.get(socketId);
  if (!socket) {
    throw new Error(`Socket not found: ${socketId}`);
  }

  const handlers = socket.eventHandlers.get(event);
  if (!handlers || handlers.length === 0) {
    console.warn(`[simulateEvent] No handlers for ${event} on socket ${socketId}`);
    return;
  }

  handlers.forEach(handler => {
    try {
      handler(data);
    } catch (error) {
      console.error(`[simulateEvent] Error in handler for ${event}:`, error);
    }
  });
}

/**
 * Get all emitted events for a socket
 *
 * @param socketId - Socket identifier
 * @returns Array of emitted events
 */
export function getEmittedEvents(socketId: string): Array<{ event: string; data: any }> {
  const socket = mockSockets.get(socketId);
  if (!socket) {
    throw new Error(`Socket not found: ${socketId}`);
  }

  return socket.emittedEvents;
}

/**
 * Get all emitted events across all sockets
 *
 * @returns Array of emitted events with socket IDs
 */
export function getAllEmittedEvents(): Array<{ socketId: string; event: string; data: any }> {
  const allEvents: Array<{ socketId: string; event: string; data: any }> = [];

  mockSockets.forEach((socket, socketId) => {
    socket.emittedEvents.forEach(({ event, data }) => {
      allEvents.push({ socketId, event, data });
    });
  });

  return allEvents;
}

/**
 * Clear emitted events for a socket
 *
 * @param socketId - Socket identifier
 */
export function clearEmittedEvents(socketId: string): void {
  const socket = mockSockets.get(socketId);
  if (!socket) {
    throw new Error(`Socket not found: ${socketId}`);
  }

  socket.emittedEvents = [];
}

/**
 * Simulate reconnection attempt
 *
 * @param socketId - Socket identifier
 * @param attemptNumber - Attempt number (1-based)
 */
export function simulateReconnectAttempt(socketId: string, attemptNumber: number): void {
  simulateEvent(socketId, 'reconnect_attempt', attemptNumber);
}

/**
 * Simulate successful reconnection
 *
 * @param socketId - Socket identifier
 * @param attemptNumber - Attempt number
 */
export function simulateReconnect(socketId: string, attemptNumber: number): void {
  const socket = mockSockets.get(socketId);
  if (!socket) {
    throw new Error(`Socket not found: ${socketId}`);
  }

  socket.connected = true;
  simulateEvent(socketId, 'reconnect', attemptNumber);
}

/**
 * Simulate reconnection failure
 *
 * @param socketId - Socket identifier
 */
export function simulateReconnectFailed(socketId: string): void {
  const socket = mockSockets.get(socketId);
  if (!socket) {
    throw new Error(`Socket not found: ${socketId}`);
  }

  socket.connected = false;
  simulateEvent(socketId, 'reconnect_failed');
}

/**
 * Simulate connection error
 *
 * @param socketId - Socket identifier
 * @param error - Error message or object
 */
export function simulateConnectionError(socketId: string, error: string | Error): void {
  const socket = mockSockets.get(socketId);
  if (!socket) {
    throw new Error(`Socket not found: ${socketId}`);
  }

  socket.connected = false;
  const errorObj = typeof error === 'string' ? new Error(error) : error;
  simulateEvent(socketId, 'connect_error', errorObj);
}

// ============================================================================
// Jest Mock Setup
// ============================================================================

/**
 * Create jest mock for socket.io-client module
 *
 * @example
 * // In test file:
 * jest.mock('socket.io-client', () => require('./websocketMocks').createSocketIOClientMock());
 */
export function createSocketIOClientMock() {
  const mockFn = jest.fn((url: string, opts?: any) => {
    return createMockSocket(url, opts);
  });

  return mockFn;
}

// ============================================================================
// Cleanup
// ============================================================================

/**
 * Setup and teardown hooks for Jest
 *
 * @example
 * // In test file:
 * import { setupWebSocketMocks, cleanupWebSocketMocks } from './websocketMocks';
 *
 * beforeEach(() => setupWebSocketMocks());
 * afterEach(() => cleanupWebSocketMocks());
 */
export function setupWebSocketMocks() {
  // Reset before each test
  resetMockSockets();
}

export function cleanupWebSocketMocks() {
  // Clean up after each test
  resetMockSockets();
}
