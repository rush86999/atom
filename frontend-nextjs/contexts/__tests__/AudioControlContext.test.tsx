/**
 * Tests for AudioControlContext
 *
 * Tests audio recording state management using React Context and useReducer.
 */

import React from 'react';
import { render, renderHook, act } from '@testing-library/react';
import { AudioControlProvider, useAudioControl } from '../AudioControlContext';

describe('AudioControlContext', () => {
  it('should throw error when useAudioControl is used outside provider', () => {
    // Suppress console.error for this test
    const consoleError = console.error;
    console.error = jest.fn();

    expect(() => {
      renderHook(() => useAudioControl());
    }).toThrow('useAudioControl must be used within an AudioControlProvider');

    console.error = consoleError;
  });

  it('should provide context to children', () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <AudioControlProvider>{children}</AudioControlProvider>
    );

    const { result } = renderHook(() => useAudioControl(), { wrapper });

    expect(result.current).toBeDefined();
    expect(result.current.state).toBeDefined();
    expect(result.current.dispatch).toBeDefined();
    expect(result.current.startRecording).toBeDefined();
    expect(result.current.stopRecording).toBeDefined();
    expect(result.current.resetRecording).toBeDefined();
  });

  describe('initial state', () => {
    it('should have correct initial state', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      expect(result.current.state).toEqual({
        isRecording: false,
        isProcessing: false,
        error: null,
        recordingTime: 0,
        audioBlob: null,
        audioUrl: null,
      });
    });
  });

  describe('startRecording', () => {
    it('should start recording', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      act(() => {
        result.current.startRecording();
      });

      expect(result.current.state.isRecording).toBe(true);
      expect(result.current.state.error).toBe(null);
      expect(result.current.state.recordingTime).toBe(0);
    });

    it('should clear error when starting recording', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      // Set error first
      act(() => {
        result.current.dispatch({ type: 'SET_ERROR', payload: 'Test error' });
      });

      expect(result.current.state.error).toBe('Test error');

      // Start recording should clear error
      act(() => {
        result.current.startRecording();
      });

      expect(result.current.state.isRecording).toBe(true);
      expect(result.current.state.error).toBe(null);
    });

    it('should reset recording time to 0', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      // Set recording time
      act(() => {
        result.current.dispatch({ type: 'SET_RECORDING_TIME', payload: 45 });
      });

      expect(result.current.state.recordingTime).toBe(45);

      // Start recording should reset time
      act(() => {
        result.current.startRecording();
      });

      expect(result.current.state.recordingTime).toBe(0);
    });
  });

  describe('stopRecording', () => {
    it('should stop recording', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      // Start recording first
      act(() => {
        result.current.startRecording();
      });

      expect(result.current.state.isRecording).toBe(true);

      // Stop recording
      act(() => {
        result.current.stopRecording();
      });

      expect(result.current.state.isRecording).toBe(false);
    });

    it('should not affect other state when stopping', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      // Setup state
      act(() => {
        result.current.dispatch({ type: 'START_RECORDING' });
        result.current.dispatch({ type: 'SET_RECORDING_TIME', payload: 30 });
        result.current.dispatch({ type: 'SET_PROCESSING', payload: true });
      });

      const { recordingTime, isProcessing } = result.current.state;

      // Stop recording
      act(() => {
        result.current.stopRecording();
      });

      expect(result.current.state.isRecording).toBe(false);
      expect(result.current.state.recordingTime).toBe(recordingTime);
      expect(result.current.state.isProcessing).toBe(isProcessing);
    });
  });

  describe('resetRecording', () => {
    it('should reset all state to initial values', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      // Setup complex state
      act(() => {
        result.current.dispatch({ type: 'START_RECORDING' });
        result.current.dispatch({ type: 'SET_RECORDING_TIME', payload: 60 });
        result.current.dispatch({ type: 'SET_AUDIO_BLOB', payload: new Blob(['audio']) });
        result.current.dispatch({ type: 'SET_AUDIO_URL', payload: 'blob:http://example.com/audio' });
        result.current.dispatch({ type: 'SET_PROCESSING', payload: true });
        result.current.dispatch({ type: 'SET_ERROR', payload: 'Test error' });
      });

      expect(result.current.state.isRecording).toBe(true);
      expect(result.current.state.recordingTime).toBe(60);
      expect(result.current.state.audioBlob).not.toBe(null);
      expect(result.current.state.audioUrl).toBe('blob:http://example.com/audio');
      expect(result.current.state.isProcessing).toBe(true);
      expect(result.current.state.error).toBe('Test error');

      // Reset
      act(() => {
        result.current.resetRecording();
      });

      expect(result.current.state).toEqual({
        isRecording: false,
        isProcessing: false,
        error: null,
        recordingTime: 0,
        audioBlob: null,
        audioUrl: null,
      });
    });
  });

  describe('dispatch - SET_RECORDING_TIME', () => {
    it('should update recording time', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      act(() => {
        result.current.dispatch({ type: 'SET_RECORDING_TIME', payload: 30 });
      });

      expect(result.current.state.recordingTime).toBe(30);
    });

    it('should handle 0 recording time', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      act(() => {
        result.current.dispatch({ type: 'SET_RECORDING_TIME', payload: 0 });
      });

      expect(result.current.state.recordingTime).toBe(0);
    });

    it('should handle large recording time', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      act(() => {
        result.current.dispatch({ type: 'SET_RECORDING_TIME', payload: 3600 });
      });

      expect(result.current.state.recordingTime).toBe(3600);
    });
  });

  describe('dispatch - SET_AUDIO_BLOB', () => {
    it('should set audio blob', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      const blob = new Blob(['audio data'], { type: 'audio/webm' });

      act(() => {
        result.current.dispatch({ type: 'SET_AUDIO_BLOB', payload: blob });
      });

      expect(result.current.state.audioBlob).toBe(blob);
    });

    it('should overwrite existing blob', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      const blob1 = new Blob(['audio1'], { type: 'audio/webm' });
      const blob2 = new Blob(['audio2'], { type: 'audio/webm' });

      act(() => {
        result.current.dispatch({ type: 'SET_AUDIO_BLOB', payload: blob1 });
      });

      expect(result.current.state.audioBlob).toBe(blob1);

      act(() => {
        result.current.dispatch({ type: 'SET_AUDIO_BLOB', payload: blob2 });
      });

      expect(result.current.state.audioBlob).toBe(blob2);
    });
  });

  describe('dispatch - SET_AUDIO_URL', () => {
    it('should set audio URL', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      const url = 'blob:http://example.com/audio123';

      act(() => {
        result.current.dispatch({ type: 'SET_AUDIO_URL', payload: url });
      });

      expect(result.current.state.audioUrl).toBe(url);
    });

    it('should overwrite existing URL', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      const url1 = 'blob:http://example.com/audio1';
      const url2 = 'blob:http://example.com/audio2';

      act(() => {
        result.current.dispatch({ type: 'SET_AUDIO_URL', payload: url1 });
      });

      expect(result.current.state.audioUrl).toBe(url1);

      act(() => {
        result.current.dispatch({ type: 'SET_AUDIO_URL', payload: url2 });
      });

      expect(result.current.state.audioUrl).toBe(url2);
    });
  });

  describe('dispatch - SET_PROCESSING', () => {
    it('should set processing to true', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      act(() => {
        result.current.dispatch({ type: 'SET_PROCESSING', payload: true });
      });

      expect(result.current.state.isProcessing).toBe(true);
    });

    it('should set processing to false', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      act(() => {
        result.current.dispatch({ type: 'SET_PROCESSING', payload: true });
      });

      expect(result.current.state.isProcessing).toBe(true);

      act(() => {
        result.current.dispatch({ type: 'SET_PROCESSING', payload: false });
      });

      expect(result.current.state.isProcessing).toBe(false);
    });
  });

  describe('dispatch - SET_ERROR', () => {
    it('should set error and stop recording/processing', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      // Setup recording state
      act(() => {
        result.current.dispatch({ type: 'START_RECORDING' });
        result.current.dispatch({ type: 'SET_PROCESSING', payload: true });
      });

      expect(result.current.state.isRecording).toBe(true);
      expect(result.current.state.isProcessing).toBe(true);

      // Set error
      act(() => {
        result.current.dispatch({ type: 'SET_ERROR', payload: 'Microphone error' });
      });

      expect(result.current.state.error).toBe('Microphone error');
      expect(result.current.state.isRecording).toBe(false);
      expect(result.current.state.isProcessing).toBe(false);
    });

    it('should clear error when set to null', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      act(() => {
        result.current.dispatch({ type: 'SET_ERROR', payload: 'Error' });
      });

      expect(result.current.state.error).toBe('Error');

      act(() => {
        result.current.dispatch({ type: 'SET_ERROR', payload: null });
      });

      expect(result.current.state.error).toBe(null);
    });
  });

  describe('dispatch - RESET', () => {
    it('should reset state via dispatch', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      // Setup state
      act(() => {
        result.current.dispatch({ type: 'START_RECORDING' });
        result.current.dispatch({ type: 'SET_RECORDING_TIME', payload: 100 });
        result.current.dispatch({ type: 'SET_ERROR', payload: 'Error' });
      });

      expect(result.current.state.isRecording).toBe(true);
      expect(result.current.state.error).toBe('Error');

      // Reset via dispatch
      act(() => {
        result.current.dispatch({ type: 'RESET' });
      });

      expect(result.current.state).toEqual({
        isRecording: false,
        isProcessing: false,
        error: null,
        recordingTime: 0,
        audioBlob: null,
        audioUrl: null,
      });
    });
  });

  describe('dispatch - unknown action', () => {
    it('should return current state for unknown action', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result } = renderHook(() => useAudioControl(), { wrapper });

      const currentState = result.current.state;

      // @ts-expect-error - testing unknown action
      act(() => {
        result.current.dispatch({ type: 'UNKNOWN_ACTION' });
      });

      expect(result.current.state).toEqual(currentState);
    });
  });

  describe('multiple consumers', () => {
    it('should share state between multiple consumers', () => {
      const wrapper = ({ children }: { children: React.ReactNode }) => (
        <AudioControlProvider>{children}</AudioControlProvider>
      );

      const { result: result1 } = renderHook(() => useAudioControl(), { wrapper });
      const { result: result2 } = renderHook(() => useAudioControl(), { wrapper });

      act(() => {
        result1.current.startRecording();
      });

      expect(result1.current.state.isRecording).toBe(true);
      expect(result2.current.state.isRecording).toBe(true);

      act(() => {
        result2.current.stopRecording();
      });

      expect(result1.current.state.isRecording).toBe(false);
      expect(result2.current.state.isRecording).toBe(false);
    });
  });
});
