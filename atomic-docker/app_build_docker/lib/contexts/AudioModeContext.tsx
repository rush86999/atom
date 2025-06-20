import React, { createContext, useState, useContext, ReactNode, useCallback } from "react";

// Define the interface for the context value
interface AudioModeContextType {
  isAudioModeEnabled: boolean;
  toggleAudioMode: () => void;
  replyRequestCount: number;    // Incremented to signal a reply listen request
  triggerReplyListen: () => void; // Function to increment replyRequestCount
}

// Create the context with a default undefined value
const AudioModeContext = createContext<AudioModeContextType | undefined>(undefined);

// Create the Provider Component
export const AudioModeProvider = ({ children }: { children: ReactNode }) => {
  const [isAudioModeEnabled, setIsAudioModeEnabled] = useState(false);
  const [replyRequestCount, setReplyRequestCount] = useState(0);

  const toggleAudioMode = useCallback(() => {
    setIsAudioModeEnabled(prev => {
      const newState = !prev;
      if (!newState) {
        // If audio mode is being disabled, reset reply request count as well (optional, but good for consistency)
        setReplyRequestCount(0);
      }
      return newState;
    });
  }, []);

  const triggerReplyListen = useCallback(() => {
    if (isAudioModeEnabled) { // Only trigger if audio mode is actually enabled
        console.log("AudioModeContext: triggerReplyListen called, incrementing replyRequestCount.");
        setReplyRequestCount(prev => prev + 1);
    } else {
        console.log("AudioModeContext: triggerReplyListen called, but Audio Mode is disabled. No action taken.");
    }
  }, [isAudioModeEnabled]); // Depends on isAudioModeEnabled to decide if it should act

  return (
    <AudioModeContext.Provider
      value={{
        isAudioModeEnabled,
        toggleAudioMode,
        replyRequestCount,
        triggerReplyListen,
      }}
    >
      {children}
    </AudioModeContext.Provider>
  );
};

// Create a custom hook for convenience
export const useAudioMode = () => {
  const context = useContext(AudioModeContext);
  if (context === undefined) {
    throw new Error('useAudioMode must be used within an AudioModeProvider');
  }
  return context;
};
