/**
 * Test Helpers for React Hooks
 *
 * Reusable mocking utilities for testing custom hooks with complex side effects.
 * Provides consistent mocking patterns for WebSocket, Speech APIs, timers, and fetch.
 */

/**
 * Mock WebSocket factory
 *
 * Creates a mock WebSocket instance with spies and helper methods for testing.
 *
 * @example
 * ```ts
 * const mockWs = createMockWebSocket();
 * global.WebSocket = jest.fn(() => mockWs) as any;
 *
 * // Simulate events
 * mockWs.simulateOpen();
 * mockWs.simulateMessage({ type: 'ping' });
 * mockWs.simulateClose({ code: 1000, reason: 'Normal closure' });
 * ```
 */
export function createMockWebSocket(options?: {
  readyState?: number;
  delayOpen?: boolean;
}) {
  const {
    readyState = 0, // CONNECTING by default
    delayOpen = false,
  } = options || {};

  const mockWs = {
    readyState,
    url: '',
    protocol: '',

    // Event handlers (set by the hook)
    onopen: null as ((event: Event) => void) | null,
    onmessage: null as ((event: MessageEvent) => void) | null,
    onerror: null as ((event: Event) => void) | null,
    onclose: null as ((event: CloseEvent) => void) | null,

    // Spies
    send: jest.fn(),
    close: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),

    // Helper methods to simulate events
    simulateOpen: () => {
      mockWs.readyState = WebSocket.OPEN;
      if (mockWs.onopen) {
        mockWs.onopen(new Event('open'));
      }
    },

    simulateMessage: (data: string | object) => {
      const message = typeof data === 'string' ? data : JSON.stringify(data);
      if (mockWs.onmessage) {
        mockWs.onmessage(new MessageEvent('message', { data: message }));
      }
    },

    simulateClose: (code = 1000, reason = 'Normal closure') => {
      mockWs.readyState = WebSocket.CLOSED;
      if (mockWs.onclose) {
        mockWs.onclose(new CloseEvent('close', { code, reason }));
      }
    },

    simulateError: (error = new Event('error')) => {
      if (mockWs.onerror) {
        mockWs.onerror(error);
      }
    },
  };

  return mockWs;
}

/**
 * Mock SpeechRecognition factory
 *
 * Creates a mock SpeechRecognition instance with spies and helper methods.
 *
 * @example
 * ```ts
 * const mockRecognition = createMockSpeechRecognition();
 * global.SpeechRecognition = jest.fn(() => mockRecognition) as any;
 * global.webkitSpeechRecognition = global.SpeechRecognition;
 *
 * // Simulate recognition results
 * mockRecognition.triggerResult('Hello world');
 * mockRecognition.triggerError(new Error('No speech detected'));
 * ```
 */
export function createMockSpeechRecognition() {
  const mockRecognition = {
    continuous: false,
    interimResults: false,
    lang: 'en-US',
    maxAlternatives: 1,

    // Spies
    start: jest.fn(),
    stop: jest.fn(),
    abort: jest.fn(),

    // Event handlers
    onresult: null as ((event: any) => void) | null,
    onerror: null as ((event: any) => void) | null,
    onend: null as ((event: any) => void) | null,
    onstart: null as ((event: any) => void) | null,

    // Helper methods to trigger callbacks
    triggerResult: (transcript: string, isFinal = true) => {
      if (mockRecognition.onresult) {
        mockRecognition.onresult({
          results: [{
            0: {
              transcript,
              confidence: 0.95,
            },
            isFinal,
            length: 1,
          }],
          resultIndex: 0,
        });
      }
    },

    triggerError: (error: Error | string) => {
      if (mockRecognition.onerror) {
        mockRecognition.onerror({
          error: typeof error === 'string' ? error : error.message,
          message: typeof error === 'string' ? error : error.message,
        });
      }
    },

    triggerEnd: () => {
      if (mockRecognition.onend) {
        mockRecognition.onend({});
      }
    },

    triggerStart: () => {
      if (mockRecognition.onstart) {
        mockRecognition.onstart({});
      }
    },
  };

  return mockRecognition;
}

/**
 * Mock SpeechSynthesis factory
 *
 * Creates a mock speechSynthesis object with spies and helper methods.
 *
 * @example
 * ```ts
 * const mockSynthesis = createMockSpeechSynthesis();
 * global.speechSynthesis = mockSynthesis;
 *
 * // Simulate voices becoming available
 * mockSynthesis.triggerVoicesChanged();
 * ```
 */
export function createMockSpeechSynthesis() {
  const mockSynthesis = {
    // Spies
    speak: jest.fn(),
    cancel: jest.fn(),
    pause: jest.fn(),
    resume: jest.fn(),
    getVoices: jest.fn(() => []),

    // Helper method to trigger voiceschanged event
    triggerVoicesChanged: () => {
      const event = new Event('voiceschanged');
      window.dispatchEvent(event);
    },
  };

  return mockSynthesis;
}

/**
 * Setup fake timers for testing
 *
 * Wraps Jest's fake timers with consistent configuration.
 * Always call cleanupFakeTimers() after use to restore real timers.
 *
 * @example
 * ```ts
 * beforeEach(() => {
 *   setupFakeTimers();
 * });
 *
 * afterEach(() => {
 *   cleanupFakeTimers();
 * });
 *
 * // In tests
 * act(() => {
 *   jest.advanceTimersByTime(1000);
 * });
 * ```
 */
export function setupFakeTimers() {
  jest.useFakeTimers();
}

/**
 * Cleanup fake timers and restore real timers
 *
 * Should always be called after setupFakeTimers() to avoid polluting other tests.
 */
export function cleanupFakeTimers() {
  jest.useRealTimers();
}

/**
 * Mock fetch response helper
 *
 * Creates a standardized fetch mock for successful responses.
 *
 * @example
 * ```ts
 * mockFetchResponse({ id: 1, name: 'Test' });
 *
 * // Test code that calls fetch
 * const response = await fetch('/api/test');
 * const data = await response.json();
 * ```
 */
export function mockFetchResponse(data: any, ok: boolean = true) {
  return jest.fn().mockImplementation(() =>
    Promise.resolve({
      ok,
      status: ok ? 200 : 400,
      json: async () => data,
      text: async () => JSON.stringify(data),
    })
  );
}

/**
 * Mock fetch error helper
 *
 * Creates a standardized fetch mock for error responses.
 *
 * @example
 * ```ts
 * mockFetchError(new Error('Network error'));
 *
 * // Test code that calls fetch
 * try {
 *   await fetch('/api/test');
 * } catch (error) {
 *   expect(error.message).toBe('Network error');
 * }
 * ```
 */
export function mockFetchError(error: Error) {
  return jest.fn().mockImplementation(() => Promise.reject(error));
}

/**
 * Create mock event listener spies
 *
 * Spies on window.addEventListener and window.removeEventListener for testing event cleanup.
 *
 * @example
 * ```ts
 * const eventSpies = createMockEventListeners();
 *
 * // Trigger event listener
 * eventSpies.trigger('mousedown');
 *
 * // Verify cleanup
 * expect(eventSpies.removeEventListener).toHaveBeenCalledWith('mousedown', expect.any(Function));
 * ```
 */
export function createMockEventListeners() {
  const listeners: Map<string, Function[]> = new Map();

  const addEventListener = jest.spyOn(window, 'addEventListener').mockImplementation(
    (event: string, handler: any, options?: any) => {
      if (!listeners.has(event)) {
        listeners.set(event, []);
      }
      listeners.get(event)!.push(handler);
      return undefined; // addEventListener returns void
    }
  );

  const removeEventListener = jest.spyOn(window, 'removeEventListener').mockImplementation(
    (event: string, handler: any) => {
      const handlers = listeners.get(event);
      if (handlers) {
        const index = handlers.indexOf(handler);
        if (index > -1) {
          handlers.splice(index, 1);
        }
      }
      return undefined; // removeEventListener returns void
    }
  );

  const trigger = (event: string, eventData?: Event) => {
    const handlers = listeners.get(event);
    if (handlers) {
      handlers.forEach(handler => handler(eventData || new Event(event)));
    }
  };

  const cleanup = () => {
    addEventListener.mockRestore();
    removeEventListener.mockRestore();
    listeners.clear();
  };

  return {
    addEventListener,
    removeEventListener,
    trigger,
    cleanup,
    listeners,
  };
}
