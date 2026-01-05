
import { useState, useCallback, useRef } from 'react';

interface UseVoiceAgentReturn {
    isPlaying: boolean;
    playAudio: (audioData: string) => void;
    stopAudio: () => void;
}

export const useVoiceAgent = (): UseVoiceAgentReturn => {
    const [isPlaying, setIsPlaying] = useState(false);
    const audioRef = useRef<HTMLAudioElement | null>(null);

    const stopAudio = useCallback(() => {
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.currentTime = 0;
            audioRef.current = null;
        }
        setIsPlaying(false);
    }, []);

    const playAudio = useCallback((audioData: string) => {
        stopAudio(); // Stop any currently playing audio

        if (!audioData) return;

        try {
            // Assume audioData is base64 string provided by the backend response
            // We need to determine if it's already a data URI or just base64
            const audioSrc = audioData.startsWith('data:audio')
                ? audioData
                : `data:audio/mp3;base64,${audioData}`;

            const audio = new Audio(audioSrc);
            audioRef.current = audio;

            audio.onplay = () => setIsPlaying(true);
            audio.onended = () => {
                setIsPlaying(false);
                audioRef.current = null;
            };
            audio.onerror = (e) => {
                console.error("Audio playback error:", e);
                setIsPlaying(false);
                audioRef.current = null;
            };

            audio.play().catch(err => {
                console.error("Failed to play audio:", err);
                setIsPlaying(false);
            });
        } catch (error) {
            console.error("Error creating audio object:", error);
        }
    }, [stopAudio]);

    return {
        isPlaying,
        playAudio,
        stopAudio
    };
};
