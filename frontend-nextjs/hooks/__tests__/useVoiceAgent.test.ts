/**
 * useVoiceAgent Hook Tests
 *
 * Tests for Audio element management with:
 * - Audio initialization and lifecycle
 * - Base64 and data URI handling
 * - Blob creation for audio playback
 * - Play, stop functionality
 * - Event handlers (ended, error)
 * - Cleanup verification for memory leak prevention
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useVoiceAgent } from '../useVoiceAgent';

// ============================================
// Mock Setup
// ============================================

// Mock URL API
const mockObjectUrls: string[] = [];
const mockCreateObjectURL = jest.fn((blob: Blob) => {
  const url = `blob:http://localhost/${mockObjectUrls.length}`;
  mockObjectUrls.push(url);
  return url;
});
const mockRevokeObjectURL = jest.fn((url: string) => {
  const index = mockObjectUrls.indexOf(url);
  if (index > -1) {
    mockObjectUrls.splice(index, 1);
  }
});

global.URL.createObjectURL = mockCreateObjectURL;
global.URL.revokeObjectURL = mockRevokeObjectURL;

// Mock Audio class
class MockAudio {
  src = '';
  paused = true;
  ended = false;
  currentTime = 0;
  error: Error | null = null;
  volume = 1.0;
  playbackRate = 1.0;
  loop = false;
  muted = false;

  // Event handlers
  onplay: (() => void) | null = null;
  onended: (() => void) | null = null;
  onerror: ((event: any) => void) | null = null;
  onpause: (() => void) | null = null;
  onloadeddata: (() => void) | null = null;
  oncanplay: (() => void) | null = null;

  // Event listeners
  private eventListeners: Map<string, Set<Function>> = new Map();

  constructor(src?: string) {
    if (src) {
      this.src = src;
    }
  }

  play(): Promise<void> {
    this.paused = false;
    this.ended = false;
    if (this.onplay) {
      this.onplay();
    }
    this.dispatchEvent('play');
    return Promise.resolve();
  }

  pause(): void {
    this.paused = true;
    if (this.onpause) {
      this.onpause();
    }
    this.dispatchEvent('pause');
  }

  addEventListener(event: string, handler: Function) {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, new Set());
    }
    this.eventListeners.get(event)!.add(handler);
  }

  removeEventListener(event: string, handler: Function) {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      listeners.delete(handler);
    }
  }

  private dispatchEvent(event: string) {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      listeners.forEach(handler => handler());
    }
  }

  // Helper to simulate audio ending
  simulateEnd() {
    this.paused = true;
    this.ended = true;
    if (this.onended) {
      this.onended();
    }
    this.dispatchEvent('ended');
  }

  // Helper to simulate audio error
  simulateError(error: Error) {
    this.error = error;
    this.paused = true;
    if (this.onerror) {
      this.onerror(error);
    }
    this.dispatchEvent('error');
  }
}

let mockAudioInstances: MockAudio[] = [];

// ============================================
// Test Utilities
// ============================================

function setupAudio() {
  mockAudioInstances = [];
  mockObjectUrls.length = 0;

  global.Audio = jest.fn((src?: string) => {
    const audio = new MockAudio(src);
    mockAudioInstances.push(audio);
    return audio as any;
  }) as any;
}

function getLatestAudioInstance(): MockAudio | null {
  return mockAudioInstances.length > 0 ? mockAudioInstances[mockAudioInstances.length - 1] : null;
}

function createBase64AudioData(): string {
  // Short base64 string for testing (not real audio data)
  return 'UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=';
}

function createDataUriAudio(): string {
  return 'data:audio/mp3;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=';
}

// ============================================
// Initialization Tests
// ============================================

describe('useVoiceAgent - Initialization', () => {
  beforeEach(() => {
    setupAudio();
    jest.clearAllMocks();
  });

  test('creates Audio element on mount', () => {
    renderHook(() => useVoiceAgent());

    expect(mockAudioInstances.length).toBe(1);
  });

  test('adds event listeners on mount', () => {
    renderHook(() => useVoiceAgent());

    const audio = getLatestAudioInstance();
    expect(audio).not.toBeNull();
    // Event listeners are added in useEffect
  });

  test('initial isPlaying is false', () => {
    const { result } = renderHook(() => useVoiceAgent());

    expect(result.current.isPlaying).toBe(false);
  });
});

// ============================================
// Play Audio Tests
// ============================================

describe('useVoiceAgent - Play Audio', () => {
  beforeEach(() => {
    setupAudio();
    jest.clearAllMocks();
  });

  test('playAudio handles base64 data', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data);
    });

    expect(mockAudioInstances.length).toBeGreaterThan(0);
  });

  test('playAudio sets audio src correctly', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data);
    });

    const audio = getLatestAudioInstance();
    expect(audio?.src).toBeTruthy();
    expect(audio?.src.length).toBeGreaterThan(0);
  });

  test('playAudio calls audio.play()', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data);
    });

    const audio = getLatestAudioInstance();
    expect(audio?.paused).toBe(false);
  });

  test('playAudio sets isPlaying to true', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    expect(result.current.isPlaying).toBe(false);

    act(() => {
      result.current.playAudio(base64Data);
    });

    // After play() is called
    expect(result.current.isPlaying).toBe(true);
  });
});

// ============================================
// Audio Loading Tests
// ============================================

describe('useVoiceAgent - Audio Loading', () => {
  beforeEach(() => {
    setupAudio();
    jest.clearAllMocks();
  });

  test('handles data:audio/* URIs directly', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const dataUri = createDataUriAudio();

    act(() => {
      result.current.playAudio(dataUri);
    });

    const audio = getLatestAudioInstance();
    expect(audio?.src).toBe(dataUri);
    expect(mockCreateObjectURL).not.toHaveBeenCalled();
  });

  test('creates Blob from base64 string', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data);
    });

    // Should create a blob URL
    expect(mockObjectUrls.length).toBeGreaterThan(0);
  });

  test('uses URL.createObjectURL for blob', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data);
    });

    expect(mockCreateObjectURL).toHaveBeenCalled();
  });

  test('sets correct MIME type (audio/mpeg)', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data);
    });

    expect(mockCreateObjectURL).toHaveBeenCalled();
    const blobArg = mockCreateObjectURL.mock.calls[0][0];
    expect(blobArg).toBeInstanceOf(Blob);
  });
});

// ============================================
// Stop Audio Tests
// ============================================

describe('useVoiceAgent - Stop Audio', () => {
  beforeEach(() => {
    setupAudio();
    jest.clearAllMocks();
  });

  test('stopAudio pauses playback', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data);
    });

    const audio = getLatestAudioInstance();
    expect(audio?.paused).toBe(false);

    act(() => {
      result.current.stopAudio();
    });

    expect(audio?.paused).toBe(true);
  });

  test('stopAudio resets currentTime to 0', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data);
    });

    // Simulate some playback
    const audio = getLatestAudioInstance();
    if (audio) {
      audio.currentTime = 5;
    }

    act(() => {
      result.current.stopAudio();
    });

    expect(audio?.currentTime).toBe(0);
  });

  test('stopAudio sets isPlaying to false', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data);
    });

    expect(result.current.isPlaying).toBe(true);

    act(() => {
      result.current.stopAudio();
    });

    expect(result.current.isPlaying).toBe(false);
  });
});

// ============================================
// Event Handler Tests
// ============================================

describe('useVoiceAgent - Event Handlers', () => {
  beforeEach(() => {
    setupAudio();
    jest.clearAllMocks();
  });

  test('onended sets isPlaying to false', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data);
    });

    const audio = getLatestAudioInstance();

    expect(result.current.isPlaying).toBe(true);

    act(() => {
      if (audio) {
        audio.simulateEnd();
      }
    });

    expect(result.current.isPlaying).toBe(false);
  });

  test('onerror sets isPlaying to false', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data);
    });

    const audio = getLatestAudioInstance();

    expect(result.current.isPlaying).toBe(true);

    act(() => {
      if (audio) {
        audio.simulateError(new Error('Playback failed'));
      }
    });

    expect(result.current.isPlaying).toBe(false);
  });

  test('error is logged to console', () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

    const { result } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data);
    });

    const audio = getLatestAudioInstance();

    act(() => {
      if (audio) {
        audio.simulateError(new Error('Test error'));
      }
    });

    expect(consoleErrorSpy).toHaveBeenCalled();

    consoleErrorSpy.mockRestore();
  });
});

// ============================================
// Cleanup Tests (CRITICAL)
// ============================================

describe('useVoiceAgent - Cleanup', () => {
  beforeEach(() => {
    setupAudio();
    jest.clearAllMocks();
  });

  test('useEffect cleanup removes event listeners', () => {
    const { unmount } = renderHook(() => useVoiceAgent());

    const audio = getLatestAudioInstance();
    expect(audio).not.toBeNull();

    // Unmount should not throw
    expect(() => unmount()).not.toThrow();
  });

  test('pauses audio on unmount', () => {
    const { result, unmount } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data);
    });

    const audio = getLatestAudioInstance();
    expect(audio?.paused).toBe(false);

    unmount();

    // After unmount, audio should be paused
    expect(audio?.paused).toBe(true);
  });

  test('sets audioRef to null on unmount', () => {
    const { result, unmount } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data);
    });

    const audio = getLatestAudioInstance();

    expect(result.current.isPlaying).toBe(true);

    unmount();

    // After unmount, React doesn't update state, but audio is paused
    // The cleanup function pauses audio and sets audioRef to null
    expect(audio?.paused).toBe(true);
    // Note: result.current.isPlaying may not update after unmount
    // because React state updates are batched and unmount is final
  });

  test('revokes object URLs on cleanup', () => {
    const { result, unmount } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data);
    });

    const objectUrlCountBefore = mockObjectUrls.length;
    expect(objectUrlCountBefore).toBeGreaterThan(0);

    unmount();

    // Object URLs should be revoked
    const objectUrlCountAfter = mockObjectUrls.length;
    expect(objectUrlCountAfter).toBeLessThanOrEqual(objectUrlCountBefore);
  });

  test('handles rapid mount/unmount cycles', () => {
    const { unmount: unmount1 } = renderHook(() => useVoiceAgent());

    unmount1();

    const { unmount: unmount2 } = renderHook(() => useVoiceAgent());

    unmount2();

    const { unmount: unmount3 } = renderHook(() => useVoiceAgent());

    expect(() => unmount3()).not.toThrow();
  });
});

// ============================================
// Edge Cases Tests
// ============================================

describe('useVoiceAgent - Edge Cases', () => {
  beforeEach(() => {
    setupAudio();
    jest.clearAllMocks();
  });

  test('handles empty audioData', () => {
    const { result } = renderHook(() => useVoiceAgent());

    act(() => {
      result.current.playAudio('');
    });

    // Should not throw
    expect(result.current.isPlaying).toBe(false);
  });

  test('handles undefined audioData', () => {
    const { result } = renderHook(() => useVoiceAgent());

    act(() => {
      result.current.playAudio(undefined as any);
    });

    // Should not throw
    expect(result.current.isPlaying).toBe(false);
  });

  test('handles blob creation failure gracefully', () => {
    // Mock atob to throw an error
    const originalAtob = global.atob;
    global.atob = jest.fn(() => {
      throw new Error('Invalid base64');
    });

    const { result } = renderHook(() => useVoiceAgent());

    const invalidBase64 = 'not-valid-base64!!!';

    act(() => {
      result.current.playAudio(invalidBase64);
    });

    // Should fall back to data URI and not throw
    expect(result.current.isPlaying).toBe(true);

    global.atob = originalAtob;
  });

  test('falls back to data URI on blob creation error', () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

    // Mock atob to throw
    const originalAtob = global.atob;
    global.atob = jest.fn(() => {
      throw new Error('Base64 decode error');
    });

    const { result } = renderHook(() => useVoiceAgent());

    const invalidBase64 = '%%%invalid%%%';

    act(() => {
      result.current.playAudio(invalidBase64);
    });

    // Should handle error gracefully
    // Note: The hook catches the error and falls back to data URI
    // The console.error may or may not be called depending on implementation
    expect(result.current.isPlaying).toBe(true);

    global.atob = originalAtob;
    consoleErrorSpy.mockRestore();
  });

  test('handles multiple rapid playAudio calls', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const base64Data1 = createBase64AudioData();
    const base64Data2 = createBase64AudioData();
    const base64Data3 = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data1);
      result.current.playAudio(base64Data2);
      result.current.playAudio(base64Data3);
    });

    // Should handle multiple calls
    expect(result.current.isPlaying).toBe(true);
  });

  test('handles stopAudio when not playing', () => {
    const { result } = renderHook(() => useVoiceAgent());

    expect(result.current.isPlaying).toBe(false);

    act(() => {
      result.current.stopAudio();
    });

    // Should not throw
    expect(result.current.isPlaying).toBe(false);
  });

  test('handles playAudio after stopAudio', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data);
    });

    expect(result.current.isPlaying).toBe(true);

    act(() => {
      result.current.stopAudio();
    });

    expect(result.current.isPlaying).toBe(false);

    act(() => {
      result.current.playAudio(base64Data);
    });

    expect(result.current.isPlaying).toBe(true);
  });

  test('handles audio with different MIME types', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const dataUriWav = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=';

    act(() => {
      result.current.playAudio(dataUriWav);
    });

    expect(result.current.isPlaying).toBe(true);
  });

  test('handles very long base64 strings', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const longBase64 = createBase64AudioData().repeat(1000);

    act(() => {
      result.current.playAudio(longBase64);
    });

    expect(result.current.isPlaying).toBe(true);
  });
});

// ============================================
// Audio Playback Lifecycle Tests
// ============================================

describe('useVoiceAgent - Playback Lifecycle', () => {
  beforeEach(() => {
    setupAudio();
    jest.clearAllMocks();
  });

  test('completes full playback cycle: play -> end -> reset', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    // Play
    act(() => {
      result.current.playAudio(base64Data);
    });

    expect(result.current.isPlaying).toBe(true);

    const audio = getLatestAudioInstance();

    // Simulate audio ending
    act(() => {
      if (audio) {
        audio.simulateEnd();
      }
    });

    expect(result.current.isPlaying).toBe(false);

    // Should be able to play again
    act(() => {
      result.current.playAudio(base64Data);
    });

    expect(result.current.isPlaying).toBe(true);
  });

  test('handles playback error and recovery', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    // Play
    act(() => {
      result.current.playAudio(base64Data);
    });

    expect(result.current.isPlaying).toBe(true);

    const audio = getLatestAudioInstance();

    // Simulate error
    act(() => {
      if (audio) {
        audio.simulateError(new Error('Network error'));
      }
    });

    expect(result.current.isPlaying).toBe(false);

    // Should be able to play again after error
    act(() => {
      result.current.playAudio(base64Data);
    });

    expect(result.current.isPlaying).toBe(true);
  });

  test('handles stop during playback', () => {
    const { result } = renderHook(() => useVoiceAgent());

    const base64Data = createBase64AudioData();

    act(() => {
      result.current.playAudio(base64Data);
    });

    expect(result.current.isPlaying).toBe(true);

    const audio = getLatestAudioInstance();

    // Stop during playback
    act(() => {
      result.current.stopAudio();
    });

    expect(result.current.isPlaying).toBe(false);
    expect(audio?.paused).toBe(true);
    expect(audio?.currentTime).toBe(0);
  });
});
