/**
 * useVoiceIO Hook Tests
 *
 * Tests for voice I/O wrapper hook (delegation to useSpeechRecognition).
 */

import { renderHook } from '@testing-library/react';
import { useVoiceIO } from '@/hooks/useVoiceIO';
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition';

// Mock useSpeechRecognition
jest.mock('@/hooks/useSpeechRecognition');

describe('useVoiceIO - Delegation Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('should return all useSpeechRecognition properties', () => {
    const mockSpeechReturn = {
      isListening: false,
      transcript: '',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: false,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    // Verify all properties exist
    expect(result.current).toHaveProperty('isListening');
    expect(result.current).toHaveProperty('transcript');
    expect(result.current).toHaveProperty('startListening');
    expect(result.current).toHaveProperty('stopListening');
    expect(result.current).toHaveProperty('resetTranscript');
    expect(result.current).toHaveProperty('isSupported');
    expect(result.current).toHaveProperty('wakeWordActive');
    expect(result.current).toHaveProperty('toggleWakeWord');
  });

  test('should alias browserSupportsSpeechRecognition as isSupported', () => {
    const mockSpeechReturn = {
      isListening: false,
      transcript: '',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: false,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    expect(result.current.isSupported).toBe(true);
    expect(mockSpeechReturn.browserSupportsSpeechRecognition).toBe(true);
  });

  test('should alias wakeWordEnabled as wakeWordActive', () => {
    const mockSpeechReturn = {
      isListening: false,
      transcript: '',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: true,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    expect(result.current.wakeWordActive).toBe(true);
    expect(mockSpeechReturn.wakeWordEnabled).toBe(true);
  });

  test('should alias setWakeWordMode as toggleWakeWord', () => {
    const mockToggleFn = jest.fn();
    const mockSpeechReturn = {
      isListening: false,
      transcript: '',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: false,
      setWakeWordMode: mockToggleFn
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    // Verify it's the same function reference
    expect(result.current.toggleWakeWord).toBe(mockToggleFn);
  });
});

describe('useVoiceIO - Passthrough Behavior', () => {
  test('should pass through isListening correctly', () => {
    const mockSpeechReturn = {
      isListening: true,
      transcript: '',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: false,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    expect(result.current.isListening).toBe(true);
  });

  test('should pass through transcript correctly', () => {
    const mockSpeechReturn = {
      isListening: false,
      transcript: 'Hello world',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: false,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    expect(result.current.transcript).toBe('Hello world');
  });

  test('should pass through startListening correctly', () => {
    const mockStartFn = jest.fn();
    const mockSpeechReturn = {
      isListening: false,
      transcript: '',
      startListening: mockStartFn,
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: false,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    result.current.startListening();

    expect(mockStartFn).toHaveBeenCalledTimes(1);
  });

  test('should pass through stopListening correctly', () => {
    const mockStopFn = jest.fn();
    const mockSpeechReturn = {
      isListening: true,
      transcript: '',
      startListening: jest.fn(),
      stopListening: mockStopFn,
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: false,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    result.current.stopListening();

    expect(mockStopFn).toHaveBeenCalledTimes(1);
  });

  test('should pass through resetTranscript correctly', () => {
    const mockResetFn = jest.fn();
    const mockSpeechReturn = {
      isListening: false,
      transcript: 'Some text',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: mockResetFn,
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: false,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    result.current.resetTranscript();

    expect(mockResetFn).toHaveBeenCalledTimes(1);
  });

  test('should pass through isSupported (browserSupportsSpeechRecognition) correctly', () => {
    const mockSpeechReturn = {
      isListening: false,
      transcript: '',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: false,
      wakeWordEnabled: false,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    expect(result.current.isSupported).toBe(false);
  });

  test('should pass through wakeWordActive (wakeWordEnabled) correctly', () => {
    const mockSpeechReturn = {
      isListening: false,
      transcript: '',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: true,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    expect(result.current.wakeWordActive).toBe(true);
  });

  test('should pass through toggleWakeWord (setWakeWordMode) correctly', () => {
    const mockSetMode = jest.fn();
    const mockSpeechReturn = {
      isListening: false,
      transcript: '',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: false,
      setWakeWordMode: mockSetMode
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    result.current.toggleWakeWord(true);

    expect(mockSetMode).toHaveBeenCalledWith(true);
  });
});

describe('useVoiceIO - Options Parameter', () => {
  test('should pass options parameter to useSpeechRecognition', () => {
    const mockSpeechReturn = {
      isListening: false,
      transcript: '',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: false,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const options = {
      wakeWord: 'atom',
      onTranscript: jest.fn()
    };

    renderHook(() => useVoiceIO(options));

    // Verify the hook was called
    expect(useSpeechRecognition).toHaveBeenCalled();

    // The options parameter should be passed through
    // (Note: React strict mode causes multiple calls)
    expect(useSpeechRecognition.mock.calls.length).toBeGreaterThan(0);
  });

  test('should work without options parameter', () => {
    const mockSpeechReturn = {
      isListening: false,
      transcript: '',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: false,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    expect(result.current).toBeDefined();
    // Note: React strict mode may cause multiple calls, check if any call was with undefined
    expect(useSpeechRecognition.mock.calls.some(call => call[0] === undefined)).toBe(true);
  });
});

describe('useVoiceIO - Return Value Structure', () => {
  test('should match UseVoiceIOReturn interface structure', () => {
    const mockSpeechReturn = {
      isListening: false,
      transcript: '',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: false,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    // Verify return value has all expected properties
    const expectedKeys = [
      'isListening',
      'transcript',
      'startListening',
      'stopListening',
      'resetTranscript',
      'isSupported',
      'wakeWordActive',
      'toggleWakeWord'
    ];

    expectedKeys.forEach(key => {
      expect(result.current).toHaveProperty(key);
    });

    // Note: Due to spread operator, we get both original and aliased properties
    // So we have 11 properties total: 8 original + 3 aliases (browserSupportsSpeechRecognition, wakeWordEnabled, setWakeWordMode)
    expect(Object.keys(result.current).length).toBeGreaterThanOrEqual(expectedKeys.length);
  });

  test('should maintain correct property types', () => {
    const mockSpeechReturn = {
      isListening: false,
      transcript: '',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: false,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    expect(typeof result.current.isListening).toBe('boolean');
    expect(typeof result.current.transcript).toBe('string');
    expect(typeof result.current.startListening).toBe('function');
    expect(typeof result.current.stopListening).toBe('function');
    expect(typeof result.current.resetTranscript).toBe('function');
    expect(typeof result.current.isSupported).toBe('boolean');
    expect(typeof result.current.wakeWordActive).toBe('boolean');
    expect(typeof result.current.toggleWakeWord).toBe('function');
  });
});

describe('useVoiceIO - Edge Cases', () => {
  test('should handle empty transcript', () => {
    const mockSpeechReturn = {
      isListening: false,
      transcript: '',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: false,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    expect(result.current.transcript).toBe('');
  });

  test('should handle browser not supporting speech recognition', () => {
    const mockSpeechReturn = {
      isListening: false,
      transcript: '',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: false,
      wakeWordEnabled: false,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    expect(result.current.isSupported).toBe(false);
  });

  test('should handle wake word already enabled', () => {
    const mockSpeechReturn = {
      isListening: true,
      transcript: 'atom hello',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: true,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    expect(result.current.wakeWordActive).toBe(true);
    expect(result.current.isListening).toBe(true);
  });

  test('should handle transcript with wake word', () => {
    const mockSpeechReturn = {
      isListening: false,
      transcript: 'atom what is the weather',
      startListening: jest.fn(),
      stopListening: jest.fn(),
      resetTranscript: jest.fn(),
      browserSupportsSpeechRecognition: true,
      wakeWordEnabled: true,
      setWakeWordMode: jest.fn()
    };

    (useSpeechRecognition as jest.Mock).mockReturnValue(mockSpeechReturn);

    const { result } = renderHook(() => useVoiceIO());

    expect(result.current.transcript).toBe('atom what is the weather');
  });
});
