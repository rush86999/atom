atom/frontend-nextjs/src/contexts/AudioControlContext.tsx
import React, { createContext, useContext, useReducer, ReactNode } from 'react';

export type AudioRecordingState = {
  isRecording: boolean;
  isProcessing: boolean;
  error: string | null;
  recordingTime: number;
  audioBlob: Blob | null;
  audioUrl: string | null;
};

export type AudioControlAction =
  | { type: 'START_RECORDING' }
  | { type: 'STOP_RECORDING' }
  | { type: 'SET_RECORDING_TIME'; payload: number }
  | { type: 'SET_AUDIO_BLOB'; payload: Blob }
  | { type: 'SET_AUDIO_URL'; payload: string }
  | { type: 'SET_PROCESSING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'RESET' };

const initialState: AudioRecordingState = {
  isRecording: false,
  isProcessing: false,
  error: null,
  recordingTime: 0,
  audioBlob: null,
  audioUrl: null,
};

function audioReducer(state: AudioRecordingState, action: AudioControlAction): AudioRecordingState {
  switch (action.type) {
    case 'START_RECORDING':
      return {
        ...state,
        isRecording: true,
        error: null,
        recordingTime: 0,
      };
    case 'STOP_RECORDING':
      return {
        ...state,
        isRecording: false,
      };
    case 'SET_RECORDING_TIME':
      return {
        ...state,
        recordingTime: action.payload,
      };
    case 'SET_AUDIO_BLOB':
      return {
        ...state,
        audioBlob: action.payload,
      };
    case 'SET_AUDIO_URL':
      return {
        ...state,
        audioUrl: action.payload,
      };
    case 'SET_PROCESSING':
      return {
        ...state,
        isProcessing: action.payload,
      };
    case 'SET_ERROR':
      return {
        ...state,
        error: action.payload,
        isRecording: false,
        isProcessing: false,
      };
    case 'RESET':
      return initialState;
    default:
      return state;
  }
}

interface AudioControlContextType {
  state: AudioRecordingState;
  dispatch: React.Dispatch<AudioControlAction>;
  startRecording: () => void;
  stopRecording: () => void;
  resetRecording: () => void;
}

const AudioControlContext = createContext<AudioControlContextType | undefined>(undefined);

interface AudioControlProviderProps {
  children: ReactNode;
}

export const AudioControlProvider: React.FC<AudioControlProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(audioReducer, initialState);

  const startRecording = () => {
    dispatch({ type: 'START_RECORDING' });
  };

  const stopRecording = () => {
    dispatch({ type: 'STOP_RECORDING' });
  };

  const resetRecording = () => {
    dispatch({ type: 'RESET' });
  };

  const value: AudioControlContextType = {
    state,
    dispatch,
    startRecording,
    stopRecording,
    resetRecording,
  };

  return (
    <AudioControlContext.Provider value={value}>
      {children}
    </AudioControlContext.Provider>
  );
};

export const useAudioControl = (): AudioControlContextType => {
  const context = useContext(AudioControlContext);
  if (context === undefined) {
    throw new Error('useAudioControl must be used within an AudioControlProvider');
  }
  return context;
};
