
import { useState, useEffect, useCallback, useRef } from 'react';

interface UseTextToSpeechReturn {
    speak: (text: string) => void;
    stop: () => void;
    pause: () => void;
    resume: () => void;
    isSpeaking: boolean;
    isPaused: boolean;
    isSupported: boolean;
    voices: SpeechSynthesisVoice[];
    setVoice: (voice: SpeechSynthesisVoice | null) => void;
}

export const useTextToSpeech = (): UseTextToSpeechReturn => {
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [isPaused, setIsPaused] = useState(false);
    const [isSupported, setIsSupported] = useState(false);
    const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
    const [selectedVoice, setSelectedVoice] = useState<SpeechSynthesisVoice | null>(null);

    useEffect(() => {
        if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
            setIsSupported(true);

            const updateVoices = () => {
                const availableVoices = window.speechSynthesis.getVoices();
                setVoices(availableVoices);
                // Try to select a default English voice
                if (!selectedVoice) {
                    const defaultVoice = availableVoices.find(v => v.name.includes("Google US English")) ||
                        availableVoices.find(v => v.lang.startsWith("en-US")) ||
                        availableVoices[0];
                    setSelectedVoice(defaultVoice || null);
                }
            };

            updateVoices();

            // Chrome loads voices asynchronously
            window.speechSynthesis.onvoiceschanged = updateVoices;
        }
    }, []);

    const speak = useCallback((text: string) => {
        if (!isSupported) return;

        // stop any current speech
        window.speechSynthesis.cancel();

        const utterance = new SpeechSynthesisUtterance(text);
        if (selectedVoice) {
            utterance.voice = selectedVoice;
        }

        // Good default settings
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;

        utterance.onstart = () => {
            setIsSpeaking(true);
            setIsPaused(false);
        };

        utterance.onend = () => {
            setIsSpeaking(false);
            setIsPaused(false);
        };

        utterance.onerror = (event) => {
            console.error("Speech synthesis error", event);
            setIsSpeaking(false);
            setIsPaused(false);
        };

        window.speechSynthesis.speak(utterance);
    }, [isSupported, selectedVoice]);

    const stop = useCallback(() => {
        if (!isSupported) return;
        window.speechSynthesis.cancel();
        setIsSpeaking(false);
        setIsPaused(false);
    }, [isSupported]);

    const pause = useCallback(() => {
        if (!isSupported) return;
        window.speechSynthesis.pause();
        setIsPaused(true);
    }, [isSupported]);

    const resume = useCallback(() => {
        if (!isSupported) return;
        window.speechSynthesis.resume();
        setIsPaused(false);
    }, [isSupported]);

    return {
        speak,
        stop,
        pause,
        resume,
        isSpeaking,
        isPaused,
        isSupported,
        voices,
        setVoice: setSelectedVoice
    };
};
