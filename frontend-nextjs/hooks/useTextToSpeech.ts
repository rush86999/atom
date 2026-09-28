
import { useState, useCallback, useSyncExternalStore } from 'react';

const EMPTY_VOICES: SpeechSynthesisVoice[] = [];
const subscribeToNothing = () => () => {};
const getServerFalse = () => false;
const hasSpeechSynthesis = () =>
    typeof window !== 'undefined' && 'speechSynthesis' in window;

type VoiceStore = {
    snapshot: SpeechSynthesisVoice[];
    listeners: Set<() => void>;
};

function createVoiceStore(): VoiceStore {
    return {
        snapshot: hasSpeechSynthesis() ? window.speechSynthesis.getVoices() : EMPTY_VOICES,
        listeners: new Set(),
    };
}

function subscribeToVoiceStore(store: VoiceStore, onStoreChange: () => void) {
    if (!hasSpeechSynthesis()) return () => {};
    const synthesis = window.speechSynthesis;
    store.listeners.add(onStoreChange);
    const updateVoices = () => {
        store.snapshot = synthesis.getVoices();
        store.listeners.forEach((listener) => listener());
    };
    if (typeof synthesis.addEventListener === 'function') {
        synthesis.addEventListener('voiceschanged', updateVoices);
        return () => {
            store.listeners.delete(onStoreChange);
            synthesis.removeEventListener('voiceschanged', updateVoices);
        };
    }
    const previous = synthesis.onvoiceschanged;
    synthesis.onvoiceschanged = updateVoices;
    return () => {
        store.listeners.delete(onStoreChange);
        if (synthesis.onvoiceschanged === updateVoices) {
            synthesis.onvoiceschanged = previous;
        }
    };
}

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
    const isSupported = useSyncExternalStore(
        subscribeToNothing,
        hasSpeechSynthesis,
        getServerFalse
    );
    const [voiceStore] = useState(createVoiceStore);
    const voices = useSyncExternalStore(
        useCallback(
            (onStoreChange: () => void) => subscribeToVoiceStore(voiceStore, onStoreChange),
            [voiceStore]
        ),
        useCallback(() => voiceStore.snapshot, [voiceStore]),
        () => EMPTY_VOICES
    );
    const [voiceSelection, setVoiceSelection] = useState<{
        explicit: boolean;
        voice: SpeechSynthesisVoice | null;
    }>({ explicit: false, voice: null });
    const defaultVoice = voices.find(voice => voice.name.includes("Google US English")) ||
        voices.find(voice => voice.lang.startsWith("en-US")) ||
        voices[0] || null;
    const selectedVoice = voiceSelection.explicit
        ? voiceSelection.voice
        : defaultVoice;

    const setVoice = useCallback((voice: SpeechSynthesisVoice | null) => {
        setVoiceSelection({ explicit: true, voice });
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
        setVoice,
    };
};
