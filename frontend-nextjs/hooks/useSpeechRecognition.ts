import { useState, useEffect, useCallback, useRef, useSyncExternalStore } from 'react';

const subscribeToNothing = () => () => {};
const getServerFalse = () => false;
const hasSpeechRecognition = () =>
    typeof window !== 'undefined' && Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);

declare global {
    interface Window {
        SpeechRecognition: any;
        webkitSpeechRecognition: any;
    }
}

export interface UseSpeechRecognitionReturn {
    isListening: boolean;
    transcript: string;
    startListening: () => void;
    stopListening: () => void;
    resetTranscript: () => void;
    browserSupportsSpeechRecognition: boolean;
    wakeWordEnabled: boolean;
    setWakeWordMode: (enabled: boolean) => void;
}

export const useSpeechRecognition = (): UseSpeechRecognitionReturn => {
    const [isListening, setIsListening] = useState(false);
    const [transcript, setTranscript] = useState('');
    const browserSupportsSpeechRecognition = useSyncExternalStore(
        subscribeToNothing,
        hasSpeechRecognition,
        getServerFalse
    );
    const recognitionRef = useRef<SpeechRecognition | null>(null);

    const [wakeWordEnabled, setWakeWordEnabled] = useState(false);

    useEffect(() => {
        if (typeof window !== 'undefined') {
            const SpeechRecognitionConstructor = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (SpeechRecognitionConstructor) {
                const recognitionInstance = new SpeechRecognitionConstructor();
                recognitionInstance.continuous = true;
                recognitionInstance.interimResults = true;
                recognitionInstance.lang = 'en-US';

                recognitionInstance.onresult = (event: any) => {
                    let currentTranscript = '';
                    for (let i = event.resultIndex; i < event.results.length; i++) {
                        const transcriptSegment = event.results[i][0].transcript;
                        if (event.results[i].isFinal) {
                            currentTranscript += transcriptSegment;
                        } else {
                            currentTranscript += transcriptSegment;
                        }
                    }

                    const normalize = (s: string) => s.toLowerCase().trim();
                    const normalizedTranscript = normalize(currentTranscript);

                    // Wake word logic
                    if (wakeWordEnabled) {
                        if (normalizedTranscript.includes("atom")) {
                            // Remove everything before "atom" to clean the command
                            const command = currentTranscript.substring(currentTranscript.toLowerCase().indexOf("atom") + 4).trim();
                            setTranscript(command); // Only set transcript AFTER wake word
                        } else {
                            // Keep transcript empty until wake word heard?
                            // Or just let it flow but visualizer shows "Waiting for Atom..."
                            // For now, let's keep it simple: we pass everything but flag if triggered
                            setTranscript(currentTranscript);
                        }
                    } else {
                        setTranscript(currentTranscript);
                    }
                };

                recognitionInstance.onerror = (event: any) => {
                    console.error('Speech recognition error', event.error);
                    // Don't stop on no-speech error if wake word is on
                    if (event.error === 'no-speech' && wakeWordEnabled) {
                        return;
                    }
                    setIsListening(false);
                };

                recognitionInstance.onend = () => {
                    // Auto-restart if wake word enabled and not explicitly stopped
                    if (wakeWordEnabled) {
                        try {
                            recognitionInstance.start();
                        } catch (e) {
                            setIsListening(false);
                        }
                    } else {
                        setIsListening(false);
                    }
                };

                recognitionRef.current = recognitionInstance;

                // Cleanup: stop the recognition instance when the effect
                // re-runs (wakeWordEnabled change) or the component unmounts.
                // Without this, the mic stays active after unmount and old
                // instances pile up on every toggle (BUG-044).
                return () => {
                    if (recognitionRef.current === recognitionInstance) {
                        recognitionRef.current = null;
                    }
                    try {
                        recognitionInstance.onresult = null;
                        recognitionInstance.onerror = null;
                        recognitionInstance.onend = null;
                        recognitionInstance.stop();
                    } catch (e) {
                        // Already stopped — ignore.
                    }
                };
            }
        }
    }, [wakeWordEnabled]);

    const startListening = useCallback(() => {
        const recognition = recognitionRef.current;
        if (recognition && !isListening) {
            try {
                recognition.start();
                setIsListening(true);
            } catch (error) {
                console.error("Error starting speech recognition:", error);
            }
        }
    }, [isListening]);

    const stopListening = useCallback(() => {
        const recognition = recognitionRef.current;
        if (recognition && isListening) {
            recognition.stop();
            setIsListening(false);
            setWakeWordEnabled(false); // Disable wake word loop on manual stop
        }
    }, [isListening]);

    const resetTranscript = useCallback(() => {
        setTranscript('');
    }, []);

    const setWakeWordMode = useCallback((enabled: boolean) => {
        setWakeWordEnabled(enabled);
    }, []);

    return {
        isListening,
        transcript,
        startListening,
        stopListening,
        resetTranscript,
        browserSupportsSpeechRecognition,
        wakeWordEnabled,
        setWakeWordMode
    };
};
