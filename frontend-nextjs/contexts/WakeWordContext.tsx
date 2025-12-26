import React, {
  createContext,
  useState,
  useContext,
  ReactNode,
  useCallback,
  useEffect,
  useRef,
} from "react";
import { useRouter } from "next/router";

// Define a global variable to hold the AudioContext instance
let globalAudioContext: AudioContext | null = null;
const getGlobalAudioContext = (): AudioContext => {
  if (!globalAudioContext) {
    globalAudioContext = new AudioContext();
  }
  return globalAudioContext;
};

interface WakeWordContextType {
  isWakeWordEnabled: boolean;
  isListening: boolean;
  wakeWordError: string | null;
  toggleWakeWord: (forceEnable?: boolean) => void;
  startListening: () => void;
  stopListening: () => void;
  refreshConnection: () => void;
  retryConnection: (attempts?: number) => void;
}

const WakeWordContext = createContext<WakeWordContextType | undefined>(
  undefined,
);

export const WakeWordProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const [isWakeWordEnabled, setIsWakeWordEnabled] = useState<boolean>(false);
  const [isListening, setIsListening] = useState<boolean>(false);
  const [wakeWordError, setWakeWordError] = useState<string | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorNodeRef = useRef<ScriptProcessorNode | null>(null);
  const webSocketRef = useRef<WebSocket | null>(null);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const mockTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const AUDIO_PROCESSOR_URL =
    process.env.NEXT_PUBLIC_AUDIO_PROCESSOR_URL || "ws://localhost:8008";
  const MOCK_WAKE_WORD_DETECTION =
    process.env.NEXT_PUBLIC_MOCK_WAKE_WORD_DETECTION === "true";
  const router = useRouter();

  const stopListening = useCallback(() => {
    setIsListening(false);

    if (mockTimeoutRef.current) {
      clearTimeout(mockTimeoutRef.current);
      mockTimeoutRef.current = null;
    }

    if (webSocketRef.current) {
      webSocketRef.current.close();
      webSocketRef.current = null;
    }

    if (processorNodeRef.current) {
      processorNodeRef.current.disconnect();
      processorNodeRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
  }, []);

  const handleWakeWordDetected = useCallback(
    (transcript: string) => {
      console.log("Wake word detected:", transcript);

      // Stop listening temporarily to prevent spam
      stopListening();

      // Cross-platform activation
      if (typeof window !== "undefined") {
        // Desktop app integration via Electron
        if ((window as any).electronAPI) {
          (window as any).electronAPI.handleWakeWordActivation({
            transcript,
            timestamp: Date.now(),
            source: "wake-word-detection",
          });
        }

        // Web app navigation
        if (router.pathname !== "/") {
          router.push("/");
        }

        // Focus chat interface and open panels
        setTimeout(() => {
          const chatInput = document.querySelector(
            '[data-testid="chat-input"]',
          ) as HTMLTextAreaElement;
          chatInput?.focus();

          // Open collapsed chat if necessary
          const chatToggle = document.querySelector(
            '[data-testid="chat-toggle"]',
          );
          if (
            chatToggle &&
            chatToggle.getAttribute("aria-expanded") === "false"
          ) {
            (chatToggle as HTMLElement).click();
          }

          // Broadcast event for integration
          window.dispatchEvent(
            new CustomEvent("wake-word-activated", {
              detail: { transcript, timestamp: Date.now() },
            }),
          );
        }, 300);
      }

      // Resume listening after user interaction
      setTimeout(() => {
        if (isWakeWordEnabled) startAudioProcessing();
      }, 3000);
    },
    [router, stopListening, isWakeWordEnabled], // Removed startAudioProcessing from dependency for now to avoid circular dependency before def
  );

  const initializeWebSocket = useCallback(() => {
    if (webSocketRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(AUDIO_PROCESSOR_URL + "/ws/audio");

    ws.onopen = () => {
      console.log("Connected to Wake Word Service");
      setWakeWordError(null);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "WAKE_WORD_DETECTED") {
          handleWakeWordDetected(message.transcript);
        }
      } catch (e) {
        console.error(e);
      }
    };

    ws.onerror = (e) => {
      console.error("WebSocket error", e);
      setWakeWordError("Wake word service connection failed");
    };

    ws.onclose = () => {
      // Reconnection logic is handled manually or by retryConnection
    };

    webSocketRef.current = ws;
  }, [AUDIO_PROCESSOR_URL, handleWakeWordDetected]);

  const startAudioProcessing = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      // ScriptProcessor is deprecated but easiest for simple inline PCM processing without separate worklet file
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorNodeRef.current = processor;

      source.connect(processor);
      processor.connect(audioContext.destination);

      processor.onaudioprocess = (e: any) => {
        if (!webSocketRef.current || webSocketRef.current.readyState !== WebSocket.OPEN) return;

        const inputData = e.inputBuffer.getChannelData(0);
        // Downsample/Convert Float32 to Int16
        // We forced ctx to 16000, so just convert format
        const buffer = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          let s = Math.max(-1, Math.min(1, inputData[i]));
          buffer[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        webSocketRef.current.send(buffer.buffer);
      };
    } catch (err) {
      console.error("Error accessing microphone", err);
      setWakeWordError("Microphone access denied");
      setIsListening(false);
    }
  }, []);

  // connectWebSocket removed in favor of initializeWebSocket

  const toggleWakeWord = useCallback(
    (forceEnable?: boolean) => {
      const newState =
        forceEnable !== undefined ? forceEnable : !isWakeWordEnabled;
      setIsWakeWordEnabled(newState);

      if (!newState) {
        stopListening();
      }
    },
    [isWakeWordEnabled, stopListening],
  );

  const startListening = useCallback(() => {
    if (!isWakeWordEnabled) {
      setWakeWordError("Wake word detection is disabled");
      return;
    }

    if (isListening) {
      return;
    }

    setIsListening(true);
    setWakeWordError(null);

    if (MOCK_WAKE_WORD_DETECTION) {
      // Simulate wake word detection after a random delay
      const delay = Math.random() * 5000 + 2000; // 2-7 seconds
      mockTimeoutRef.current = setTimeout(() => {
        handleWakeWordDetected("atom");
      }, delay);
    } else {
      // Real WebSocket connection
      initializeWebSocket();
      startAudioProcessing();
    }
  }, [
    isWakeWordEnabled,
    isListening,
    MOCK_WAKE_WORD_DETECTION,
    handleWakeWordDetected,
    initializeWebSocket,
    startAudioProcessing
  ]);

  // Removed stopListening from here

  const refreshConnection = useCallback(() => {
    stopListening();
    if (isWakeWordEnabled) {
      startListening();
    }
  }, [stopListening, isWakeWordEnabled, startListening]);

  const retryConnection = useCallback(
    (attempts: number = 3) => {
      if (attempts <= 0) {
        setWakeWordError(
          "Failed to establish connection after multiple attempts",
        );
        return;
      }

      console.log(`Retrying connection... (${attempts} attempts remaining)`);
      setTimeout(() => {
        refreshConnection();
      }, 2000);
    },
    [refreshConnection],
  );

  useEffect(() => {
    return () => {
      stopListening();
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
    };
  }, [stopListening]);

  const contextValue: WakeWordContextType = {
    isWakeWordEnabled,
    isListening,
    wakeWordError,
    toggleWakeWord,
    startListening,
    stopListening,
    refreshConnection,
    retryConnection,
  };

  return (
    <WakeWordContext.Provider value={contextValue}>
      {children}
    </WakeWordContext.Provider>
  );
};

export const useWakeWord = (): WakeWordContextType => {
  const context = useContext(WakeWordContext);
  if (context === undefined) {
    throw new Error("useWakeWord must be used within a WakeWordProvider");
  }
  return context;
};
