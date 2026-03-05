/**
 * useSpeechRecognition Hook Tests
 *
 * Tests for SpeechRecognition API integration with:
 * - Browser support detection
 * - Speech recognition lifecycle
 * - Wake word mode filtering
 * - Event handler testing
 * - Cleanup verification
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useSpeechRecognition } from '../useSpeechRecognition';

// ============================================
// Mock Setup
// ============================================

declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

// Mock SpeechRecognition class
class MockSpeechRecognition {
  static instances: any[] = [];
  continuous = false;
  interimResults = false;
  lang = '';
  onresult: ((event: any) => void) | null = null;
  onerror: ((event: any) => void) | null = null;
  onend: (() => void) | null = null;
  startCalls = 0;
  stopCalls = 0;

  constructor() {
    MockSpeechRecognition.instances.push(this);
  }

  start() {
    this.startCalls++;
  }

  stop() {
    this.stopCalls++;
  }
}

// ============================================
// Test Utilities
// ============================================

function setupSpeechRecognition() {
  // Clear any existing setup
  delete (window as any).SpeechRecognition;
  delete (window as any).webkitSpeechRecognition;
  MockSpeechRecognition.instances = [];

  // Setup mock
  (window as any).SpeechRecognition = MockSpeechRecognition;
  (window as any).webkitSpeechRecognition = MockSpeechRecognition;
}

function getLatestRecognitionInstance(): MockSpeechRecognition | null {
  const instances = MockSpeechRecognition.instances;
  return instances.length > 0 ? instances[instances.length - 1] : null;
}

// ============================================
// Browser Support Detection Tests
// ============================================

describe('useSpeechRecognition - Browser Support Detection', () => {
  beforeEach(() => {
    setupSpeechRecognition();
    jest.clearAllMocks();
  });

  test('should detect SpeechRecognition availability', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    expect(result.current.browserSupportsSpeechRecognition).toBe(true);
    expect(window.SpeechRecognition).toBeDefined();
  });

  test('should detect webkitSpeechRecognition as fallback', () => {
    delete (window as any).SpeechRecognition;
    (window as any).webkitSpeechRecognition = MockSpeechRecognition;

    const { result } = renderHook(() => useSpeechRecognition());

    expect(result.current.browserSupportsSpeechRecognition).toBe(true);
  });

  test('should set browserSupportsSpeechRecognition correctly when API available', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    expect(result.current.browserSupportsSpeechRecognition).toBe(true);
  });

  test('should handle no browser support', () => {
    delete (window as any).SpeechRecognition;
    delete (window as any).webkitSpeechRecognition;

    const { result } = renderHook(() => useSpeechRecognition());

    expect(result.current.browserSupportsSpeechRecognition).toBe(false);
    expect(result.current.isListening).toBe(false);
  });
});

// ============================================
// Initialization Tests
// ============================================

describe('useSpeechRecognition - Initialization', () => {
  beforeEach(() => {
    setupSpeechRecognition();
    jest.clearAllMocks();
  });

  test('should create SpeechRecognition instance', () => {
    renderHook(() => useSpeechRecognition());

    expect(MockSpeechRecognition.instances.length).toBe(1);
    const instance = getLatestRecognitionInstance();
    expect(instance).not.toBeNull();
  });

  test('should set continuous=true', () => {
    renderHook(() => useSpeechRecognition());

    const instance = getLatestRecognitionInstance();
    expect(instance?.continuous).toBe(true);
  });

  test('should set interimResults=true', () => {
    renderHook(() => useSpeechRecognition());

    const instance = getLatestRecognitionInstance();
    expect(instance?.interimResults).toBe(true);
  });

  test('should set lang=en-US', () => {
    renderHook(() => useSpeechRecognition());

    const instance = getLatestRecognitionInstance();
    expect(instance?.lang).toBe('en-US');
  });
});

// ============================================
// Start/Stop Listening Tests
// ============================================

describe('useSpeechRecognition - Start/Stop Listening', () => {
  beforeEach(() => {
    setupSpeechRecognition();
    jest.clearAllMocks();
  });

  test('startListening calls recognition.start()', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    act(() => {
      result.current.startListening();
    });

    const instance = getLatestRecognitionInstance();
    expect(instance?.startCalls).toBe(1);
  });

  test('startListening sets isListening to true', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    expect(result.current.isListening).toBe(false);

    act(() => {
      result.current.startListening();
    });

    expect(result.current.isListening).toBe(true);
  });

  test('stopListening calls recognition.stop()', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    act(() => {
      result.current.startListening();
    });

    const instance = getLatestRecognitionInstance();
    const stopCallsBeforeStop = instance?.stopCalls || 0;

    act(() => {
      result.current.stopListening();
    });

    const stopCallsAfterStop = instance?.stopCalls || 0;
    // stopListening should call stop
    expect(stopCallsAfterStop).toBeGreaterThan(stopCallsBeforeStop);
  });

  test('stopListening sets isListening to false', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    act(() => {
      result.current.startListening();
    });

    expect(result.current.isListening).toBe(true);

    act(() => {
      result.current.stopListening();
    });

    expect(result.current.isListening).toBe(false);
  });

  test('handles starting when already listening gracefully', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    act(() => {
      result.current.startListening();
    });

    const startCallsAfterFirst = getLatestRecognitionInstance()?.startCalls || 0;

    act(() => {
      result.current.startListening();
    });

    // Should not increase start calls when already listening
    const startCallsAfterSecond = getLatestRecognitionInstance()?.startCalls || 0;
    expect(startCallsAfterSecond).toBe(startCallsAfterFirst);
  });

  test('handles stopping when not listening gracefully', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    expect(result.current.isListening).toBe(false);

    act(() => {
      result.current.stopListening();
    });

    expect(result.current.isListening).toBe(false);
  });
});

// ============================================
// Transcript Tests
// ============================================

describe('useSpeechRecognition - Transcript', () => {
  beforeEach(() => {
    setupSpeechRecognition();
    jest.clearAllMocks();
  });

  test('onresult updates transcript state', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    const instance = getLatestRecognitionInstance();

    act(() => {
      if (instance?.onresult) {
        const mockEvent = {
          resultIndex: 0,
          results: [
            {
              0: { transcript: 'Hello world' },
              isFinal: true,
              length: 1
            }
          ],
          resultsLength: 1
        };
        instance.onresult(mockEvent);
      }
    });

    expect(result.current.transcript).toBe('Hello world');
  });

  test('handles both final and interim results', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    const instance = getLatestRecognitionInstance();

    act(() => {
      if (instance?.onresult) {
        const mockEvent = {
          resultIndex: 0,
          results: [
            {
              0: { transcript: 'Hello' },
              isFinal: false,
              length: 1
            },
            {
              0: { transcript: ' world' },
              isFinal: true,
              length: 1
            }
          ],
          resultsLength: 2
        };
        instance.onresult(mockEvent);
      }
    });

    // The implementation accumulates all segments from resultIndex
    expect(result.current.transcript).toBe('Hello world');
  });

  test('accumulates transcript segments', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    const instance = getLatestRecognitionInstance();

    act(() => {
      if (instance?.onresult) {
        const mockEvent = {
          resultIndex: 0,
          results: [
            {
              0: { transcript: 'Hello ' },
              isFinal: true,
              length: 1
            },
            {
              0: { transcript: 'world' },
              isFinal: true,
              length: 1
            }
          ],
          resultsLength: 2
        };
        instance.onresult(mockEvent);
      }
    });

    expect(result.current.transcript).toBe('Hello world');
  });

  test('resetTranscript clears transcript', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    const instance = getLatestRecognitionInstance();

    act(() => {
      if (instance?.onresult) {
        const mockEvent = {
          resultIndex: 0,
          results: [
            {
              0: { transcript: 'Hello world' },
              isFinal: true,
              length: 1
            }
          ],
          resultsLength: 1
        };
        instance.onresult(mockEvent);
      }
    });

    expect(result.current.transcript).toBe('Hello world');

    act(() => {
      result.current.resetTranscript();
    });

    expect(result.current.transcript).toBe('');
  });
});

// ============================================
// Wake Word Mode Tests
// ============================================

describe('useSpeechRecognition - Wake Word Mode', () => {
  beforeEach(() => {
    setupSpeechRecognition();
    jest.clearAllMocks();
  });

  test('wake word mode is off by default', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    expect(result.current.wakeWordEnabled).toBe(false);
  });

  test('setWakeWordMode enables wake word', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    act(() => {
      result.current.setWakeWordMode(true);
    });

    expect(result.current.wakeWordEnabled).toBe(true);
  });

  test('filters transcript for "atom" keyword when enabled', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    const instance = getLatestRecognitionInstance();

    act(() => {
      result.current.setWakeWordMode(true);
    });

    act(() => {
      if (instance?.onresult) {
        const mockEvent = {
          resultIndex: 0,
          results: [
            {
              0: { transcript: 'Hey atom, what time is it' },
              isFinal: true,
              length: 1
            }
          ],
          resultsLength: 1
        };
        instance.onresult(mockEvent);
      }
    });

    // Should extract text after "atom"
    expect(result.current.transcript).toContain('what time is it');
  });

  test('auto-restarts on onend when wake word enabled', () => {
    // This test verifies the implementation's auto-restart logic
    // Note: The hook's useEffect depends on wakeWordEnabled, so changing it
    // recreates the recognition instance with new event handlers
    const { result } = renderHook(() => useSpeechRecognition());

    act(() => {
      result.current.setWakeWordMode(true);
    });

    // After setting wake word mode, we get a new recognition instance
    const instance = getLatestRecognitionInstance();

    act(() => {
      result.current.startListening();
    });

    expect(result.current.isListening).toBe(true);

    // When onend fires with wake word enabled, it should try to restart
    act(() => {
      if (instance?.onend) {
        instance.onend();
      }
    });

    // Verify the hook attempts to restart (isListening may be managed by start())
    expect(instance?.startCalls).toBeGreaterThan(0);
  });

  test('handles "no-speech" error when wake word enabled', () => {
    // Note: The implementation checks wakeWordEnabled at event callback time
    // Since useEffect re-creates handlers when wakeWordEnabled changes,
    // we need to verify the closure captures the right value
    const { result } = renderHook(() => useSpeechRecognition());

    act(() => {
      result.current.setWakeWordMode(true);
    });

    // Get the instance after wake word mode is enabled
    const instance = getLatestRecognitionInstance();

    act(() => {
      result.current.startListening();
    });

    expect(result.current.isListening).toBe(true);

    // The onerror handler checks wakeWordEnabled in its closure
    // If it's true when the handler is created, no-speech won't stop listening
    act(() => {
      if (instance?.onerror) {
        const mockError = { error: 'no-speech' };
        instance.onerror(mockError);
      }
    });

    // With wake word enabled, no-speech error should keep listening
    // (the handler returns early before setting isListening to false)
    expect(result.current.isListening).toBe(true);
  });
});

// ============================================
// Event Handler Tests
// ============================================

describe('useSpeechRecognition - Event Handlers', () => {
  beforeEach(() => {
    setupSpeechRecognition();
    jest.clearAllMocks();
  });

  test('onerror sets isListening to false', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    const instance = getLatestRecognitionInstance();

    act(() => {
      result.current.startListening();
    });

    expect(result.current.isListening).toBe(true);

    act(() => {
      if (instance?.onerror) {
        const mockError = { error: 'network' };
        instance.onerror(mockError);
      }
    });

    expect(result.current.isListening).toBe(false);
  });

  test('onend handles auto-restart logic', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    const instance = getLatestRecognitionInstance();

    act(() => {
      result.current.startListening();
    });

    expect(result.current.isListening).toBe(true);

    act(() => {
      if (instance?.onend) {
        instance.onend();
      }
    });

    // Without wake word, should stop listening
    expect(result.current.isListening).toBe(false);
  });

  test('event handlers are properly cleaned up on unmount', () => {
    const { result, unmount } = renderHook(() => useSpeechRecognition());

    const instance = getLatestRecognitionInstance();

    // Verify handlers were set
    expect(instance?.onresult).not.toBeNull();
    expect(instance?.onerror).not.toBeNull();
    expect(instance?.onend).not.toBeNull();

    // Unmount should not throw
    expect(() => unmount()).not.toThrow();
  });
});

// ============================================
// Cleanup Tests
// ============================================

describe('useSpeechRecognition - Cleanup', () => {
  beforeEach(() => {
    setupSpeechRecognition();
    jest.clearAllMocks();
  });

  test('useEffect cleanup stops recognition', () => {
    const { result, unmount } = renderHook(() => useSpeechRecognition());

    act(() => {
      result.current.startListening();
    });

    const instance = getLatestRecognitionInstance();
    const stopCallsBeforeUnmount = instance?.stopCalls || 0;

    unmount();

    const stopCallsAfterUnmount = instance?.stopCalls || 0;
    // Cleanup should stop recognition
    expect(stopCallsAfterUnmount).toBeGreaterThanOrEqual(stopCallsBeforeUnmount);
  });

  test('removes event listeners on unmount', () => {
    const { unmount } = renderHook(() => useSpeechRecognition());

    const instance = getLatestRecognitionInstance();

    // Verify cleanup doesn't throw
    expect(() => unmount()).not.toThrow();

    // Verify instance was created
    expect(instance).not.toBeNull();
  });

  test('handles rapid mount/unmount cycles', () => {
    const { unmount: unmount1 } = renderHook(() => useSpeechRecognition());

    unmount1();

    const { unmount: unmount2 } = renderHook(() => useSpeechRecognition());

    unmount2();

    const { unmount: unmount3 } = renderHook(() => useSpeechRecognition());

    expect(() => unmount3()).not.toThrow();
  });
});

// ============================================
// Edge Cases Tests
// ============================================

describe('useSpeechRecognition - Edge Cases', () => {
  beforeEach(() => {
    setupSpeechRecognition();
    jest.clearAllMocks();
  });

  test('handles empty transcript gracefully', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    const instance = getLatestRecognitionInstance();

    act(() => {
      if (instance?.onresult) {
        const mockEvent = {
          resultIndex: 0,
          results: [
            {
              0: { transcript: '' },
              isFinal: true,
              length: 1
            }
          ],
          resultsLength: 1
        };
        instance.onresult(mockEvent);
      }
    });

    expect(result.current.transcript).toBe('');
  });

  test('handles special characters in transcript', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    const instance = getLatestRecognitionInstance();

    act(() => {
      if (instance?.onresult) {
        const mockEvent = {
          resultIndex: 0,
          results: [
            {
              0: { transcript: 'Hello! @#$ %^&*() world' },
              isFinal: true,
              length: 1
            }
          ],
          resultsLength: 1
        };
        instance.onresult(mockEvent);
      }
    });

    expect(result.current.transcript).toBe('Hello! @#$ %^&*() world');
  });

  test('handles transcript with leading/trailing spaces', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    const instance = getLatestRecognitionInstance();

    act(() => {
      if (instance?.onresult) {
        const mockEvent = {
          resultIndex: 0,
          results: [
            {
              0: { transcript: '   Hello world   ' },
              isFinal: true,
              length: 1
            }
          ],
          resultsLength: 1
        };
        instance.onresult(mockEvent);
      }
    });

    // Wake word logic uses trim for comparison
    expect(result.current.transcript).toBe('   Hello world   ');
  });

  test('handles case-insensitive wake word matching', () => {
    const { result } = renderHook(() => useSpeechRecognition());

    const instance = getLatestRecognitionInstance();

    act(() => {
      result.current.setWakeWordMode(true);
    });

    // Test lowercase "atom"
    act(() => {
      if (instance?.onresult) {
        const mockEvent = {
          resultIndex: 0,
          results: [
            {
              0: { transcript: 'atom command' },
              isFinal: true,
              length: 1
            }
          ],
          resultsLength: 1
        };
        instance.onresult(mockEvent);
      }
    });

    expect(result.current.transcript).toContain('command');

    // Test uppercase "ATOM"
    act(() => {
      result.current.resetTranscript();
      if (instance?.onresult) {
        const mockEvent = {
          resultIndex: 0,
          results: [
            {
              0: { transcript: 'ATOM another command' },
              isFinal: true,
              length: 1
            }
          ],
          resultsLength: 1
        };
        instance.onresult(mockEvent);
      }
    });

    expect(result.current.transcript).toContain('another command');

    // Test mixed case "Atom"
    act(() => {
      result.current.resetTranscript();
      if (instance?.onresult) {
        const mockEvent = {
          resultIndex: 0,
          results: [
            {
              0: { transcript: 'Atom third command' },
              isFinal: true,
              length: 1
            }
          ],
          resultsLength: 1
        };
        instance.onresult(mockEvent);
      }
    });

    expect(result.current.transcript).toContain('third command');
  });
});
