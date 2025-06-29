import React, { createContext, useState, useContext, ReactNode, useCallback, useEffect, useRef } from 'react';

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
  startListening: () => void; // Exposed for manual start if needed, but typically auto
  stopListening: () => void;
}

const WakeWordContext = createContext<WakeWordContextType | undefined>(undefined);

export const WakeWordProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isWakeWordEnabled, setIsWakeWordEnabled] = useState<boolean>(false);
  const [isListening, setIsListening] = useState<boolean>(false);
  const [wakeWordError, setWakeWordError] = useState<string | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorNodeRef = useRef<ScriptProcessorNode | null>(null); // Or AudioWorkletNode
  const webSocketRef = useRef<WebSocket | null>(null);

  // TODO: Get this from environment variables via Next.js config
  const AUDIO_PROCESSOR_URL = process.env.NEXT_PUBLIC_AUDIO_PROCESSOR_URL;
  const MOCK_WAKE_WORD_DETECTION = process.env.NEXT_PUBLIC_MOCK_WAKE_WORD_DETECTION === 'true';


  const connectWebSocket = useCallback(() => {
    if (!AUDIO_PROCESSOR_URL) {
      setWakeWordError("Audio processor URL is not configured.");
      console.error("Audio processor URL is not configured.");
      setIsListening(false);
      return null;
    }

    console.log(`Attempting to connect to WebSocket: ${AUDIO_PROCESSOR_URL}`);
    const ws = new WebSocket(AUDIO_PROCESSOR_URL);

    ws.onopen = () => {
      console.log("WakeWord WebSocket connection established.");
      setWakeWordError(null);
      // Optionally send a configuration message if the STT service requires it
      // ws.send(JSON.stringify({ type: 'config', sampleRate: audioContextRef.current?.sampleRate }));
    };

    ws.onmessage = (event) => {
      // Assuming the STT service sends a message upon wake word detection
      const message = JSON.parse(event.data as string);
      console.log("WakeWord WebSocket message received:", message);
      if (message.type === 'WAKE_WORD_DETECTED' || (message.transcript && message.transcript.toLowerCase().includes("atom"))) { // Example detection
        console.log("Wake word detected!");
        // TODO: Trigger action (e.g., open chat, send message to agent)
        // For now, just log and maybe set a state
        alert("Wake word 'Atom' detected! (Simulated)");
        // Potentially stop listening or wait for command
      } else if (message.type === 'ERROR') {
        setWakeWordError(message.error || "Unknown error from audio processor.");
        console.error("Error from audio processor:", message.error);
      }
    };

    ws.onerror = (error) => {
      console.error("WakeWord WebSocket error:", error);
      setWakeWordError("WebSocket connection error. Ensure the audio processor is running.");
      setIsListening(false); // Stop listening on error
    };

    ws.onclose = (event) => {
      console.log("WakeWord WebSocket connection closed.", event.reason);
      if (isWakeWordEnabled && !event.wasClean) { // If enabled and not closed cleanly
        setWakeWordError("WebSocket connection closed unexpectedly. Retrying...");
        // Basic retry logic (consider more robust backoff)
        // setTimeout(connectWebSocket, 5000); // Reconnect after 5s if still enabled
      }
       if (webSocketRef.current === ws) { // Avoid issues if a new WS was created quickly
           webSocketRef.current = null;
       }
       //setIsListening(false); // Already handled by error or explicit stop
    };
    return ws;
  }, [AUDIO_PROCESSOR_URL, isWakeWordEnabled]);


  const startAudioProcessing = useCallback(async () => {
    if (!isWakeWordEnabled || isListening) {
      console.log("Not starting audio processing: disabled or already listening.");
      return;
    }

    setWakeWordError(null);
    setIsListening(true);
    console.log("Attempting to start audio processing for wake word...");

    if (MOCK_WAKE_WORD_DETECTION) {
        console.log("Mock Wake Word Detection is ON. Simulating listening.");
        // Simulate detection after a few seconds for testing
        setTimeout(() => {
            if (isWakeWordEnabled && isListening) { // Check if still relevant
                console.log("Mock Wake Word 'Atom' detected!");
                alert("Mock Wake word 'Atom' detected!");
                // Here you would typically trigger some app action
            }
        }, 5000);
        return;
    }

    if (!AUDIO_PROCESSOR_URL) {
        setWakeWordError("Audio processor URL not configured.");
        setIsListening(false);
        return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setWakeWordError("getUserMedia not supported on this browser.");
      setIsListening(false);
      return;
    }

    try {
      audioContextRef.current = getGlobalAudioContext();
      if (audioContextRef.current.state === 'suspended') {
        await audioContextRef.current.resume();
      }

      mediaStreamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      const source = audioContextRef.current.createMediaStreamSource(mediaStreamRef.current);

      // WebSocket connection
      webSocketRef.current = connectWebSocket();
      if (!webSocketRef.current) {
          setIsListening(false); // connectWebSocket will set error if URL is missing
          return;
      }

      // ScriptProcessorNode for audio processing (legacy, consider AudioWorklet for modern browsers)
      // Buffer size, input channels, output channels
      const bufferSize = 4096;
      processorNodeRef.current = audioContextRef.current.createScriptProcessor(bufferSize, 1, 1);

      processorNodeRef.current.onaudioprocess = (event) => {
        if (webSocketRef.current && webSocketRef.current.readyState === WebSocket.OPEN) {
          const inputData = event.inputBuffer.getChannelData(0);
          // Convert to 16-bit PCM or format expected by STT service
          const pcmData = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            pcmData[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
          }
          webSocketRef.current.send(pcmData.buffer);
        }
      };

      source.connect(processorNodeRef.current);
      processorNodeRef.current.connect(audioContextRef.current.destination); // Connect to destination to avoid suspension

      console.log("Audio processing started for wake word.");

    } catch (err: any) {
      console.error("Error starting audio processing:", err);
      setWakeWordError(`Error accessing microphone: ${err.message}`);
      setIsListening(false);
      stopAudioProcessing(); // Clean up
    }
  }, [isWakeWordEnabled, isListening, AUDIO_PROCESSOR_URL, MOCK_WAKE_WORD_DETECTION, connectWebSocket]);

  const stopAudioProcessing = useCallback(() => {
    console.log("Stopping audio processing for wake word.");
    setIsListening(false);

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }
    if (processorNodeRef.current) {
      processorNodeRef.current.disconnect();
      processorNodeRef.current = null;
    }
    // Do not close globalAudioContext here, it can be reused.
    // If it was created just for this, then:
    // if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
    //   // audioContextRef.current.close(); // This is handled by global context now
    //   // audioContextRef.current = null;
    // }
    if (webSocketRef.current) {
      if (webSocketRef.current.readyState === WebSocket.OPEN || webSocketRef.current.readyState === WebSocket.CONNECTING) {
        webSocketRef.current.close(1000, "Client stopping listening");
      }
      webSocketRef.current = null;
    }
  }, []);

  const toggleWakeWord = useCallback((forceEnable?: boolean) => {
    const targetState = typeof forceEnable === 'boolean' ? forceEnable : !isWakeWordEnabled;
    console.log(`Toggling wake word. Current: ${isWakeWordEnabled}, Target: ${targetState}`);
    setIsWakeWordEnabled(targetState);
    if (!targetState) {
      stopAudioProcessing();
    }
    // startAudioProcessing will be called by useEffect if isWakeWordEnabled becomes true
  }, [isWakeWordEnabled, stopAudioProcessing]);

  useEffect(() => {
    if (isWakeWordEnabled && !isListening && !wakeWordError) {
      // Check for AudioContext resume on user gesture if needed, though getUserMedia often handles this.
      const resumeAudio = async () => {
          const ctx = getGlobalAudioContext();
          if (ctx.state === 'suspended') {
              console.log("AudioContext is suspended, attempting to resume for wake word.");
              try {
                  await ctx.resume();
                  console.log("AudioContext resumed successfully.");
                  startAudioProcessing();
              } catch (e) {
                  console.error("Failed to resume AudioContext:", e);
                  setWakeWordError("Audio system could not be started. Please interact with the page and try again.");
              }
          } else {
              startAudioProcessing();
          }
      };
      resumeAudio();
    } else if (!isWakeWordEnabled && isListening) {
      stopAudioProcessing();
    }
  }, [isWakeWordEnabled, isListening, startAudioProcessing, stopAudioProcessing, wakeWordError]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      console.log("WakeWordProvider unmounting. Cleaning up audio resources.");
      stopAudioProcessing();
      if (globalAudioContext && globalAudioContext.state !== 'closed') {
          // globalAudioContext.close(); // Decide if global context should be closed on app exit
          // globalAudioContext = null;
      }
    };
  }, [stopAudioProcessing]);

  return (
    <WakeWordContext.Provider value={{ isWakeWordEnabled, isListening, wakeWordError, toggleWakeWord, startListening: startAudioProcessing, stopListening: stopAudioProcessing }}>
      {children}
    </WakeWordContext.Provider>
  );
};

export const useWakeWord = (): WakeWordContextType => {
  const context = useContext(WakeWordContext);
  if (context === undefined) {
    throw new Error('useWakeWord must be used within a WakeWordProvider');
  }
  return context;
};
