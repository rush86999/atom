import "@testing-library/jest-dom";

// Mock scrollIntoView
Element.prototype.scrollIntoView = jest.fn();

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

// Mock URL.createObjectURL and URL.revokeObjectURL
global.URL.createObjectURL = jest.fn();
global.URL.revokeObjectURL = jest.fn();

// Mock clipboard API
Object.assign(navigator, {
  clipboard: {
    writeText: jest.fn(),
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

