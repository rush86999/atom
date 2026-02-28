// Polyfill for MSW 2.x - must come before any other imports
import * as WebStreamsPolyfill from 'web-streams-polyfill';
import { TextEncoder, TextDecoder } from 'util';
import { Blob, File } from 'buffer';
import { Request, Response, Headers } from 'node-fetch';

Object.defineProperties(globalThis, {
  ReadableStream: { value: WebStreamsPolyfill.ReadableStream },
  TransformStream: { value: WebStreamsPolyfill.TransformStream },
  TextEncoder: { value: TextEncoder },
  TextDecoder: { value: TextDecoder },
  Blob: { value: Blob },
  File: { value: File },
  Request: { value: Request },
  Response: { value: Response },
  Headers: { value: Headers },
});

import "@testing-library/jest-dom";

// Optional MSW server - only if no import errors
let server: any;
try {
  server = require('./mocks/server').server;
} catch (e) {
  console.warn('MSW server not available:', (e as Error).message);
}

// Establish API mocking before all tests (only if server loaded)
if (server) {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  // Reset any request handlers that we may add during the tests,
  // so they don't affect other tests
  afterEach(() => server.resetHandlers());
  // Clean up after the tests are finished
  afterAll(() => server.close());
}

// Reset any request handlers that we may add during the tests,
// so they don't affect other tests
afterEach(() => server.resetHandlers());

// Clean up after the tests are finished
afterAll(() => server.close());

// Mock scrollIntoView
Element.prototype.scrollIntoView = jest.fn();

// Mock window.scrollTo
global.scrollTo = jest.fn();

// Mock window.matchMedia
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: jest.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(), // deprecated
    removeListener: jest.fn(), // deprecated
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// Mock ResizeObserver
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Mock IntersectionObserver
global.IntersectionObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Mock IntersectionObserverEntry
global.IntersectionObserverEntry = jest.fn().mockImplementation((entry) => ({
  ...entry,
  isIntersecting: false,
  intersectionRatio: 0,
  boundingClientRect: {},
  intersectionRect: {},
  rootBounds: {},
  time: 0,
}));

// Mock URL.createObjectURL and URL.revokeObjectURL
global.URL.createObjectURL = jest.fn();
global.URL.revokeObjectURL = jest.fn();

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
  length: 0,
  key: jest.fn(),
};
global.localStorage = localStorageMock as any;

// Mock sessionStorage
const sessionStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
  length: 0,
  key: jest.fn(),
};
global.sessionStorage = sessionStorageMock as any;

// Mock clipboard API
Object.assign(navigator, {
  clipboard: {
    writeText: jest.fn(),
    readText: jest.fn(),
  },
});

// Mock got module to handle ESM imports
jest.mock('got', () => ({
  __esModule: true,
  default: jest.fn(() => Promise.resolve({ body: '{}' })),
  post: jest.fn(() => Promise.resolve({ body: '{}' })),
  get: jest.fn(() => Promise.resolve({ body: '{}' })),
  extend: jest.fn(() => jest.fn(() => Promise.resolve({ body: '{}' }))),
}));

// Mock fetch API
global.fetch = jest.fn(() =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: async () => ({}),
    text: async () => '',
    blob: async () => new Blob(),
    arrayBuffer: async () => new ArrayBuffer(0),
    headers: {},
  })
) as any;

// Mock WebSocket - define constants first
const WEBSOCKET_CONNECTING = 0;
const WEBSOCKET_OPEN = 1;
const WEBSOCKET_CLOSING = 2;
const WEBSOCKET_CLOSED = 3;

class MockWebSocket {
  static CONNECTING = WEBSOCKET_CONNECTING;
  static OPEN = WEBSOCKET_OPEN;
  static CLOSING = WEBSOCKET_CLOSING;
  static CLOSED = WEBSOCKET_CLOSED;

  readyState: number;
  send: jest.Mock;
  close: jest.Mock;
  _onopen: ((event: Event) => void) | null = null;
  _onmessage: ((event: MessageEvent) => void) | null = null;
  _onclose: ((event: CloseEvent) => void) | null = null;
  _onerror: ((event: Event) => void) | null = null;
  _url: string;

  constructor(url: string) {
    this._url = url;
    this.readyState = WEBSOCKET_CONNECTING;
    this.send = jest.fn();
    this.close = jest.fn();

    // Track constructor calls for testing
    (MockWebSocket as any).mock.calls?.push([url]);
    (MockWebSocket as any).mock.instances?.push(this);
  }

  set onopen(value: ((event: Event) => void) | null) {
    this._onopen = value;
  }
  get onopen() {
    return this._onopen;
  }

  set onmessage(value: ((event: MessageEvent) => void) | null) {
    this._onmessage = value;
  }
  get onmessage() {
    return this._onmessage;
  }

  set onclose(value: ((event: CloseEvent) => void) | null) {
    this._onclose = value;
  }
  get onclose() {
    return this._onclose;
  }

  set onerror(value: ((event: Event) => void) | null) {
    this._onerror = value;
  }
  get onerror() {
    return this._onerror;
  }
}

// Add mock tracking properties
(MockWebSocket as any).mock = {
  calls: [],
  instances: [],
};

(MockWebSocket as any).getMockCalls = () => (MockWebSocket as any).mock.calls;
(MockWebSocket as any).getMockInstances = () => (MockWebSocket as any).mock.instances;

(global as any).WebSocket = MockWebSocket as any;

// Mock console methods to reduce noise in tests
global.console = {
  ...console,
  // Uncomment to ignore specific console methods during tests
  // log: jest.fn(),
  // debug: jest.fn(),
  // info: jest.fn(),
  // warn: jest.fn(),
  // error: jest.fn(),
};

// Mock custom useToast hook
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: jest.fn(),
    dismiss: jest.fn(),
    toasts: [],
  }),
  ToastProvider: ({ children }: { children: any }) => children,
}));

// Mock AgentAudioControlContext
jest.mock('@/contexts/AgentAudioControlContext', () => ({
  AgentAudioControlProvider: ({ children }: { children: any }) => children,
  useAgentAudioControl: () => ({
    isRecording: false,
    startRecording: jest.fn(),
    stopRecording: jest.fn(),
    isProcessing: false,
  }),
}));

// Mock WakeWordContext
jest.mock('@/contexts/WakeWordContext', () => ({
  WakeWordProvider: ({ children }: { children: any }) => children,
  useWakeWord: () => ({
    isListening: false,
    startListening: jest.fn(),
    stopListening: jest.fn(),
    wakeWord: 'hey atom',
  }),
}));

// Mock Next.js router
jest.mock('next/router', () => ({
  useRouter: () => ({
    route: '/',
    pathname: '/',
    query: {},
    asPath: '/',
    push: jest.fn(),
    replace: jest.fn(),
    reload: jest.fn(),
    back: jest.fn(),
    prefetch: jest.fn().mockResolvedValue(undefined),
    beforePopState: jest.fn(),
    events: {
      on: jest.fn(),
      off: jest.fn(),
      emit: jest.fn(),
    },
  }),
  default: {
    route: '/',
    pathname: '/',
    query: {},
    asPath: '/',
    push: jest.fn(),
    replace: jest.fn(),
    reload: jest.fn(),
    back: jest.fn(),
    prefetch: jest.fn().mockResolvedValue(undefined),
    beforePopState: jest.fn(),
    events: {
      on: jest.fn(),
      off: jest.fn(),
      emit: jest.fn(),
    },
  },
}));

