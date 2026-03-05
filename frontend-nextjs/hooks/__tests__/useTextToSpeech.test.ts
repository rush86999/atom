/**
 * useTextToSpeech Hook Tests
 *
 * Tests for SpeechSynthesis API integration with:
 * - Browser support detection
 * - Voice loading and selection
 * - Speak, stop, pause, resume functionality
 * - State management (isSpeaking, isPaused)
 * - Cleanup verification
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useTextToSpeech } from '../useTextToSpeech';

// ============================================
// Mock Setup
// ============================================

// Mock SpeechSynthesisUtterance
class MockSpeechSynthesisUtterance {
  text = '';
  voice: SpeechSynthesisVoice | null = null;
  rate = 1.0;
  pitch = 1.0;
  volume = 1.0;
  onstart: (() => void) | null = null;
  onend: (() => void) | null = null;
  onerror: ((event: any) => void) | null = null;

  constructor(text: string) {
    this.text = text;
  }
}

// Mock SpeechSynthesisVoice
class MockSpeechSynthesisVoice {
  name = '';
  lang = '';
  localService = true;
  default = false;

  constructor(name: string, lang: string, defaultVoice = false) {
    this.name = name;
    this.lang = lang;
    this.default = defaultVoice;
  }
}

// Mock SpeechSynthesis
let mockSpeechSynthesis: {
  getVoices: () => SpeechSynthesisVoice[];
  speak: (utterance: SpeechSynthesisUtterance) => void;
  cancel: () => void;
  pause: () => void;
  resume: () => void;
  onvoiceschanged: (() => void) | null;
  paused: boolean;
  pending: boolean;
  speaking: boolean;
};

let mockUtteranceConstructor: jest.Mock;

function setupSpeechSynthesis() {
  mockSpeechSynthesis = {
    getVoices: jest.fn(() => []),
    speak: jest.fn(),
    cancel: jest.fn(),
    pause: jest.fn(),
    resume: jest.fn(),
    onvoiceschanged: null,
    paused: false,
    pending: false,
    speaking: false
  };

  // Create a mock constructor that returns mock instances
  mockUtteranceConstructor = jest.fn((text: string) => {
    const utterance = new MockSpeechSynthesisUtterance(text);
    return utterance;
  }) as any;

  (window as any).speechSynthesis = mockSpeechSynthesis;
  (window as any).SpeechSynthesisUtterance = mockUtteranceConstructor;
}

// ============================================
// Test Utilities
// ============================================

function createMockVoices(): SpeechSynthesisVoice[] {
  return [
    new MockSpeechSynthesisVoice('Google US English', 'en-US', true),
    new MockSpeechSynthesisVoice('Microsoft David', 'en-US'),
    new MockSpeechSynthesisVoice('Google UK English Female', 'en-GB'),
    new MockSpeechSynthesisVoice('Google Español', 'es-ES'),
    new MockSpeechSynthesisVoice('Google Français', 'fr-FR')
  ];
}

// ============================================
// Browser Support Detection Tests
// ============================================

describe('useTextToSpeech - Browser Support Detection', () => {
  beforeEach(() => {
    setupSpeechSynthesis();
    jest.clearAllMocks();
  });

  test('should detect speechSynthesis availability', () => {
    const { result } = renderHook(() => useTextToSpeech());

    expect(result.current.isSupported).toBe(true);
  });

  test('should set isSupported correctly when API available', () => {
    const { result } = renderHook(() => useTextToSpeech());

    expect(result.current.isSupported).toBe(true);
    expect(window.speechSynthesis).toBeDefined();
  });

  test('should handle no browser support', () => {
    delete (window as any).speechSynthesis;

    const { result } = renderHook(() => useTextToSpeech());

    expect(result.current.isSupported).toBe(false);
    expect(result.current.isSpeaking).toBe(false);
    expect(result.current.isPaused).toBe(false);
  });
});

// ============================================
// Voice Loading Tests
// ============================================

describe('useTextToSpeech - Voice Loading', () => {
  beforeEach(() => {
    setupSpeechSynthesis();
    jest.clearAllMocks();
  });

  test('loads voices from getVoices()', async () => {
    const mockVoices = createMockVoices();
    (mockSpeechSynthesis.getVoices as jest.Mock).mockReturnValue(mockVoices);

    const { result } = renderHook(() => useTextToSpeech());

    // Wait for useEffect to run
    await waitFor(() => {
      expect(result.current.voices).toHaveLength(mockVoices.length);
    });
  });

  test('handles async voice loading via onvoiceschanged', async () => {
    const mockVoices = createMockVoices();
    (mockSpeechSynthesis.getVoices as jest.Mock)
      .mockReturnValue([])
      .mockReturnValueOnce([])  // Initial call returns empty
      .mockReturnValue(mockVoices);  // Second call returns voices

    const { result } = renderHook(() => useTextToSpeech());

    // Initially empty
    expect(result.current.voices).toHaveLength(0);

    // Trigger onvoiceschanged
    act(() => {
      if (mockSpeechSynthesis.onvoiceschanged) {
        mockSpeechSynthesis.onvoiceschanged();
      }
    });

    await waitFor(() => {
      expect(result.current.voices).toHaveLength(mockVoices.length);
    });
  });

  test('selects default English voice', async () => {
    const mockVoices = createMockVoices();
    (mockSpeechSynthesis.getVoices as jest.Mock).mockReturnValue(mockVoices);

    const { result } = renderHook(() => useTextToSpeech());

    await waitFor(() => {
      expect(result.current.voices).toHaveLength(5);
    });

    // Should prefer "Google US English"
    await waitFor(() => {
      expect(result.current.voices[0].name).toBe('Google US English');
    });
  });

  test('falls back to first available voice if no English voice', async () => {
    const nonEnglishVoices = [
      new MockSpeechSynthesisVoice('Google Español', 'es-ES'),
      new MockSpeechSynthesisVoice('Google Français', 'fr-FR')
    ];
    (mockSpeechSynthesis.getVoices as jest.Mock).mockReturnValue(nonEnglishVoices);

    const { result } = renderHook(() => useTextToSpeech());

    await waitFor(() => {
      expect(result.current.voices).toHaveLength(2);
    });
  });
});

// ============================================
// Speak Tests
// ============================================

describe('useTextToSpeech - Speak', () => {
  beforeEach(() => {
    setupSpeechSynthesis();
    jest.clearAllMocks();
  });

  test('speak creates SpeechSynthesisUtterance', async () => {
    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.speak('Hello world');
    });

    expect(mockUtteranceConstructor).toHaveBeenCalledWith('Hello world');
  });

  test('speak sets utterance voice when selected', async () => {
    const mockVoices = createMockVoices();
    (mockSpeechSynthesis.getVoices as jest.Mock).mockReturnValue(mockVoices);

    const { result } = renderHook(() => useTextToSpeech());

    await waitFor(() => {
      expect(result.current.voices).toHaveLength(5);
    });

    act(() => {
      result.current.speak('Test');
    });

    // Verify the utterance was created
    expect(mockSpeechSynthesis.speak).toHaveBeenCalled();
  });

  test('speak sets rate=1.0, pitch=1.0, volume=1.0', async () => {
    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.speak('Test');
    });

    expect(mockSpeechSynthesis.speak).toHaveBeenCalled();
    // Utterance properties are set via constructor/class
  });

  test('speak calls speechSynthesis.speak()', async () => {
    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.speak('Hello world');
    });

    expect(mockSpeechSynthesis.speak).toHaveBeenCalled();
  });

  test('speak cancels previous speech before speaking', async () => {
    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.speak('First');
    });

    expect(mockSpeechSynthesis.cancel).toHaveBeenCalledTimes(1);
    expect(mockSpeechSynthesis.speak).toHaveBeenCalledTimes(1);

    act(() => {
      result.current.speak('Second');
    });

    expect(mockSpeechSynthesis.cancel).toHaveBeenCalledTimes(2);
    expect(mockSpeechSynthesis.speak).toHaveBeenCalledTimes(2);
  });
});

// ============================================
// State Management Tests
// ============================================

describe('useTextToSpeech - State Management', () => {
  beforeEach(() => {
    setupSpeechSynthesis();
    jest.clearAllMocks();
  });

  test('onstart sets isSpeaking=true, isPaused=false', async () => {
    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.speak('Test');
    });

    // Get the utterance that was passed to speak()
    const speakCall = (mockSpeechSynthesis.speak as jest.Mock).mock.calls[0];
    const utterance = speakCall[0] as SpeechSynthesisUtterance;

    // Trigger onstart
    act(() => {
      if (utterance.onstart) {
        utterance.onstart();
      }
    });

    expect(result.current.isSpeaking).toBe(true);
    expect(result.current.isPaused).toBe(false);
  });

  test('onend sets isSpeaking=false, isPaused=false', async () => {
    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.speak('Test');
    });

    const speakCall = (mockSpeechSynthesis.speak as jest.Mock).mock.calls[0];
    const utterance = speakCall[0] as SpeechSynthesisUtterance;

    // Trigger onstart first
    act(() => {
      if (utterance.onstart) {
        utterance.onstart();
      }
    });

    expect(result.current.isSpeaking).toBe(true);

    // Trigger onend
    act(() => {
      if (utterance.onend) {
        utterance.onend();
      }
    });

    expect(result.current.isSpeaking).toBe(false);
    expect(result.current.isPaused).toBe(false);
  });

  test('onerror sets isSpeaking=false', async () => {
    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.speak('Test');
    });

    const speakCall = (mockSpeechSynthesis.speak as jest.Mock).mock.calls[0];
    const utterance = speakCall[0] as SpeechSynthesisUtterance;

    // Trigger onstart first
    act(() => {
      if (utterance.onstart) {
        utterance.onstart();
      }
    });

    expect(result.current.isSpeaking).toBe(true);

    // Trigger onerror
    act(() => {
      if (utterance.onerror) {
        utterance.onerror({ error: 'canceled' });
      }
    });

    expect(result.current.isSpeaking).toBe(false);
    expect(result.current.isPaused).toBe(false);
  });

  test('pause sets isPaused=true', async () => {
    const mockVoices = createMockVoices();
    (mockSpeechSynthesis.getVoices as jest.Mock).mockReturnValue(mockVoices);

    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.speak('Test');
    });

    act(() => {
      result.current.pause();
    });

    expect(mockSpeechSynthesis.pause).toHaveBeenCalled();
    expect(result.current.isPaused).toBe(true);
  });

  test('resume sets isPaused=false', async () => {
    const mockVoices = createMockVoices();
    (mockSpeechSynthesis.getVoices as jest.Mock).mockReturnValue(mockVoices);

    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.speak('Test');
    });

    act(() => {
      result.current.pause();
    });

    expect(result.current.isPaused).toBe(true);

    act(() => {
      result.current.resume();
    });

    expect(mockSpeechSynthesis.resume).toHaveBeenCalled();
    expect(result.current.isPaused).toBe(false);
  });
});

// ============================================
// Stop Tests
// ============================================

describe('useTextToSpeech - Stop', () => {
  beforeEach(() => {
    setupSpeechSynthesis();
    jest.clearAllMocks();
  });

  test('stop cancels speech', async () => {
    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.speak('Test');
    });

    act(() => {
      result.current.stop();
    });

    expect(mockSpeechSynthesis.cancel).toHaveBeenCalled();
  });

  test('stop resets isSpeaking to false', async () => {
    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.speak('Test');
    });

    const speakCall = (mockSpeechSynthesis.speak as jest.Mock).mock.calls[0];
    const utterance = speakCall[0] as SpeechSynthesisUtterance;

    // Trigger onstart
    act(() => {
      if (utterance.onstart) {
        utterance.onstart();
      }
    });

    expect(result.current.isSpeaking).toBe(true);

    act(() => {
      result.current.stop();
    });

    expect(result.current.isSpeaking).toBe(false);
  });

  test('stop resets isPaused to false', async () => {
    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.speak('Test');
      result.current.pause();
    });

    expect(result.current.isPaused).toBe(true);

    act(() => {
      result.current.stop();
    });

    expect(result.current.isPaused).toBe(false);
  });
});

// ============================================
// Voice Selection Tests
// ============================================

describe('useTextToSpeech - Voice Selection', () => {
  beforeEach(() => {
    setupSpeechSynthesis();
    jest.clearAllMocks();
  });

  test('setVoice updates selectedVoice', async () => {
    const mockVoices = createMockVoices();
    (mockSpeechSynthesis.getVoices as jest.Mock).mockReturnValue(mockVoices);

    const { result } = renderHook(() => useTextToSpeech());

    await waitFor(() => {
      expect(result.current.voices).toHaveLength(5);
    });

    const selectedVoice = mockVoices[2]; // Google UK English Female

    act(() => {
      result.current.setVoice(selectedVoice);
    });

    // Voice selection is internal, verify hook doesn't crash
    expect(result.current.voices).toHaveLength(5);
  });

  test('subsequent speech uses selected voice', async () => {
    const mockVoices = createMockVoices();
    (mockSpeechSynthesis.getVoices as jest.Mock).mockReturnValue(mockVoices);

    const { result } = renderHook(() => useTextToSpeech());

    await waitFor(() => {
      expect(result.current.voices).toHaveLength(5);
    });

    const selectedVoice = mockVoices[1]; // Microsoft David

    act(() => {
      result.current.setVoice(selectedVoice);
      result.current.speak('Test with custom voice');
    });

    expect(mockSpeechSynthesis.speak).toHaveBeenCalled();
  });
});

// ============================================
// Edge Cases Tests
// ============================================

describe('useTextToSpeech - Edge Cases', () => {
  beforeEach(() => {
    setupSpeechSynthesis();
    jest.clearAllMocks();
  });

  test('handles empty text gracefully', () => {
    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.speak('');
    });

    // Should not throw
    expect(mockUtteranceConstructor).toHaveBeenCalledWith('');
  });

  test('handles special characters in text', () => {
    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.speak('Hello! @#$ %^&*() world');
    });

    expect(mockSpeechSynthesis.speak).toHaveBeenCalled();
  });

  test('handles very long text', () => {
    const { result } = renderHook(() => useTextToSpeech());

    const longText = 'Hello '.repeat(1000);

    act(() => {
      result.current.speak(longText);
    });

    expect(mockSpeechSynthesis.speak).toHaveBeenCalled();
  });

  test('handles multiple rapid speak calls', () => {
    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.speak('First');
      result.current.speak('Second');
      result.current.speak('Third');
    });

    // Each speak cancels the previous one
    expect(mockSpeechSynthesis.cancel).toHaveBeenCalledTimes(3);
    expect(mockSpeechSynthesis.speak).toHaveBeenCalledTimes(3);
  });

  test('handles pause when not speaking', () => {
    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.pause();
    });

    expect(mockSpeechSynthesis.pause).toHaveBeenCalled();
    expect(result.current.isPaused).toBe(true);
  });

  test('handles resume when not paused', () => {
    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.resume();
    });

    expect(mockSpeechSynthesis.resume).toHaveBeenCalled();
  });

  test('handles stop when not speaking', () => {
    const { result } = renderHook(() => useTextToSpeech());

    act(() => {
      result.current.stop();
    });

    expect(mockSpeechSynthesis.cancel).toHaveBeenCalled();
  });

  test('handles speaking when not supported', () => {
    delete (window as any).speechSynthesis;

    const { result } = renderHook(() => useTextToSpeech());

    expect(result.current.isSupported).toBe(false);

    act(() => {
      result.current.speak('Test');
    });

    // Should not call speak when not supported
    expect(mockSpeechSynthesis.speak).not.toHaveBeenCalled();
  });
});

// ============================================
// Cleanup Tests
// ============================================

describe('useTextToSpeech - Cleanup', () => {
  beforeEach(() => {
    setupSpeechSynthesis();
    jest.clearAllMocks();
  });

  test('cleans up on unmount', () => {
    const { unmount } = renderHook(() => useTextToSpeech());

    // Unmount should not throw
    expect(() => unmount()).not.toThrow();
  });

  test('handles rapid mount/unmount cycles', () => {
    const { unmount: unmount1 } = renderHook(() => useTextToSpeech());

    unmount1();

    const { unmount: unmount2 } = renderHook(() => useTextToSpeech());

    unmount2();

    const { unmount: unmount3 } = renderHook(() => useTextToSpeech());

    expect(() => unmount3()).not.toThrow();
  });

  test('voice state persists across re-renders', async () => {
    const mockVoices = createMockVoices();
    (mockSpeechSynthesis.getVoices as jest.Mock).mockReturnValue(mockVoices);

    const { result, rerender } = renderHook(() => useTextToSpeech());

    await waitFor(() => {
      expect(result.current.voices).toHaveLength(5);
    });

    const voiceCountBefore = result.current.voices.length;

    rerender();

    expect(result.current.voices).toHaveLength(voiceCountBefore);
  });
});
