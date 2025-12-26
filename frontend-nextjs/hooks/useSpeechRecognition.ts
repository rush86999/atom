import { useState, useEffect, useCallback } from 'react';

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
    const [recognition, setRecognition] = useState<SpeechRecognition | null>(null);
    const [browserSupportsSpeechRecognition, setBrowserSupportsSpeechRecognition] = useState(false);

    const [wakeWordEnabled, setWakeWordEnabled] = useState(false);

    useEffect(() => {
        if (typeof window !== 'undefined') {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (SpeechRecognition) {
                setBrowserSupportsSpeechRecognition(true);
                const recognitionInstance = new SpeechRecognition();
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
                        }
                        setTranscript(currentTranscript);
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

                setRecognition(recognitionInstance);
            }
        }
    }, [wakeWordEnabled]);

    const startListening = useCallback(() => {
        if (recognition && !isListening) {
            try {
                recognition.start();
                setIsListening(true);
            } catch (error) {
                console.error("Error starting speech recognition:", error);
            }
        }
    }, [recognition, isListening]);

    const stopListening = useCallback(() => {
        if (recognition && isListening) {
            recognition.stop();
            setIsListening(false);
            setWakeWordEnabled(false); // Disable wake word loop on manual stop
        }
    }, [recognition, isListening]);

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
