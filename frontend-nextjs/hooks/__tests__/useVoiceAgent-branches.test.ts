/**
 * useVoiceAgent Branch Coverage Tests (wave 119)
 *
 * Closes the remaining gaps in useVoiceAgent.ts:
 * - addEventListener-registered `handleEnded` / `handleError` handlers on the
 *   mount-created Audio element (lines 18-19, 22-24)
 * - `audio.play().catch(...)` rejection path (lines 90-92)
 * - outer try/catch on Audio construction failure (lines 93-96)
 */

import { renderHook, act } from '@testing-library/react';
import { useVoiceAgent } from '../useVoiceAgent';

class MockAudio {
  src = '';
  paused = true;
  ended = false;
  currentTime = 0;
  onplay: (() => void) | null = null;
  onended: (() => void) | null = null;
  onerror: ((event: any) => void) | null = null;

  private eventListeners: Map<string, Set<Function>> = new Map();

  constructor(src?: string) {
    if (src) {
      this.src = src;
    }
  }

  play(): Promise<void> {
    this.paused = false;
    if (this.onplay) {
      this.onplay();
    }
    return Promise.resolve();
  }

  pause(): void {
    this.paused = true;
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

  simulateEnd() {
    this.paused = true;
    this.ended = true;
    if (this.onended) {
      this.onended();
    }
    this.dispatchEvent('ended');
  }

  simulateError(error: Error) {
    (this as any).error = error;
    this.paused = true;
    if (this.onerror) {
      this.onerror(error);
    }
    this.dispatchEvent('error');
  }
}

let mockAudioInstances: MockAudio[] = [];
let failNextPlay = false;
let throwOnNextCreate = false;

describe('useVoiceAgent - Branch Coverage', () => {
  beforeEach(() => {
    mockAudioInstances = [];
    failNextPlay = false;
    throwOnNextCreate = false;
    jest.clearAllMocks();

    global.Audio = jest.fn((src?: string) => {
      if (throwOnNextCreate) {
        throw new Error('Audio creation failed');
      }
      const audio = new MockAudio(src);
      if (failNextPlay) {
        audio.play = () => Promise.reject(new Error('Autoplay blocked'));
      }
      mockAudioInstances.push(audio);
      return audio as any;
    }) as any;
  });

  function getLatestAudioInstance(): MockAudio | null {
    return mockAudioInstances.length > 0
      ? mockAudioInstances[mockAudioInstances.length - 1]
      : null;
  }

  function createBase64AudioData(): string {
    return 'UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=';
  }

  test('ended listener registered via addEventListener resets playing state', () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

    const { result } = renderHook(() => useVoiceAgent());
    expect(result.current.isPlaying).toBe(false);

    // The mount-created audio has handleEnded registered via addEventListener
    act(() => {
      getLatestAudioInstance()!.simulateEnd();
    });

    expect(result.current.isPlaying).toBe(false);
    // A subsequent play still works (audioRef was reset by handleEnded)
    act(() => {
      result.current.playAudio(createBase64AudioData());
    });
    expect(result.current.isPlaying).toBe(true);

    consoleSpy.mockRestore();
  });

  test('error listener registered via addEventListener logs and resets state', () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

    const { result } = renderHook(() => useVoiceAgent());

    act(() => {
      getLatestAudioInstance()!.simulateError(new Error('decode failure'));
    });

    expect(consoleSpy.mock.calls[0][0]).toContain('Audio playback error');
    expect(consoleSpy).toHaveBeenCalledTimes(1);
    expect(result.current.isPlaying).toBe(false);

    consoleSpy.mockRestore();
  });

  test('unmount cleanup removes the addEventListener handlers', () => {
    const { unmount } = renderHook(() => useVoiceAgent());
    const audio = getLatestAudioInstance()!;

    const removeSpy = jest.spyOn(audio, 'removeEventListener');

    unmount();

    expect(removeSpy).toHaveBeenCalledWith('ended', expect.any(Function));
    expect(removeSpy).toHaveBeenCalledWith('error', expect.any(Function));
  });

  test('play() rejection sets isPlaying false and logs', async () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

    const { result } = renderHook(() => useVoiceAgent());

    failNextPlay = true;
    act(() => {
      result.current.playAudio(createBase64AudioData());
    });

    // The play() promise rejection is caught asynchronously
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(consoleSpy).toHaveBeenCalledWith(
      'Failed to play audio:',
      expect.any(Error)
    );
    expect(result.current.isPlaying).toBe(false);

    consoleSpy.mockRestore();
  });

  test('Audio construction failure is caught by outer try/catch', () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

    const { result } = renderHook(() => useVoiceAgent());

    throwOnNextCreate = true;
    act(() => {
      result.current.playAudio(createBase64AudioData());
    });

    expect(consoleSpy).toHaveBeenCalledWith(
      'Error creating audio object:',
      expect.any(Error)
    );
    expect(result.current.isPlaying).toBe(false);

    consoleSpy.mockRestore();
  });
});
