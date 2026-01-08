import { useState, useCallback, useRef, useEffect } from 'react';

interface UseVoiceAgentReturn {
    isPlaying: boolean;
    playAudio: (audioData: string) => void;
    stopAudio: () => void;
}

export const useVoiceAgent = (): UseVoiceAgentReturn => {
    const [isPlaying, setIsPlaying] = useState(false);
    const audioRef = useRef<HTMLAudioElement | null>(null);

    useEffect(() => {
        // Initialize audio element
        audioRef.current = new Audio();

        const handleEnded = () => {
            setIsPlaying(false);
            audioRef.current = null;
        };
        const handleError = (e: any) => {
            console.error("Audio playback error:", e);
            setIsPlaying(false);
            audioRef.current = null;
        };

        audioRef.current.addEventListener('ended', handleEnded);
        audioRef.current.addEventListener('error', handleError);

        return () => {
            if (audioRef.current) {
                audioRef.current.removeEventListener('ended', handleEnded);
                audioRef.current.removeEventListener('error', handleError);
                audioRef.current.pause();
                audioRef.current = null;
            }
        };
    }, []);
    const stopAudio = useCallback(() => {
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.currentTime = 0;

        }
        setIsPlaying(false);
    }, []);

    const playAudio = useCallback((audioData: string) => {
        if (!audioData) return;

        try {
            stopAudio();

            // Determine if it's already a data URI or just base64
            let audioSrc = audioData;
            if (!audioData.startsWith('data:audio')) {
                // Try to create a blob for better performance with large data
                try {
                    const byteCharacters = atob(audioData);
                    const byteNumbers = new Array(byteCharacters.length);
                    for (let i = 0; i < byteCharacters.length; i++) {
                        byteNumbers[i] = byteCharacters.charCodeAt(i);
                    }
                    const byteArray = new Uint8Array(byteNumbers);
                    const blob = new Blob([byteArray], { type: 'audio/mpeg' });
                    audioSrc = URL.createObjectURL(blob);
                } catch (e) {
                    // Fallback to data URI if blob creation fails
                    audioSrc = `data:audio/mp3;base64,${audioData}`;
                }
            }

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
                setIsPlaying(true); // Setting isPlaying to true if it actually started
                // Wait for ending
            });
        } catch (error) {
            console.error("Error creating audio object:", error);
            setIsPlaying(false);
        }
    }
    }, [stopAudio]);

return {
    isPlaying,
    playAudio,
    stopAudio
};
};
