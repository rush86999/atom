import React, { useEffect } from 'react';
import { useVoiceIO } from '@/hooks/useVoiceIO';
import { Button } from '@/components/ui/button';
import { Mic, MicOff, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface VoiceInputProps {
    onTranscriptChange: (transcript: string) => void;
    className?: string;
}

export const VoiceInput: React.FC<VoiceInputProps> = ({ onTranscriptChange, className }) => {
    const {
        isListening,
        transcript,
        startListening,
        stopListening,
        isSupported: browserSupportsSpeechRecognition,
        resetTranscript,
        wakeWordActive: wakeWordEnabled,
        toggleWakeWord: setWakeWordMode
    } = useVoiceIO({
        wakeWord: 'atom',
        onTranscript: onTranscriptChange // Auto-sync
    });

    // Note: useVoiceIO's onTranscript handles the syncing, but we also sync if transcript changes
    useEffect(() => {
        if (transcript) {
            onTranscriptChange(transcript);
        }
    }, [transcript, onTranscriptChange]);

    const toggleListening = () => {
        if (isListening) {
            stopListening();
        } else {
            resetTranscript();
            startListening();
        }
    };

    if (!browserSupportsSpeechRecognition) {
        return (
            <Button variant="ghost" size="icon" disabled className="opacity-50" title="Voice input is not supported in this browser.">
                <MicOff className="w-4 h-4 text-gray-400" />
            </Button>
        );
    }

    return (
        <div className={cn("relative flex items-center", className)}>
            <Button
                type="button"
                variant={isListening ? "destructive" : "ghost"}
                size="icon"
                onClick={toggleListening}
                className={cn(
                    "transition-all duration-300",
                    isListening && "animate-pulse ring-2 ring-red-400 ring-opacity-50"
                )}
                title={isListening ? "Stop Listening" : "Start Voice Input"}
            >
                {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            </Button>

            {/* Wake Word Toggle */}
            <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => {
                    if (wakeWordEnabled) {
                        setWakeWordMode(false);
                    } else {
                        setWakeWordMode(true);
                    }
                }}
                className={cn(
                    "ml-1 transition-all",
                    wakeWordEnabled ? "text-blue-500 bg-blue-50 ring-1 ring-blue-200" : "text-gray-400 hover:text-gray-600"
                )}
                title={wakeWordEnabled ? "Click to Disable Wake Word ('Hey Atom')" : "Click to Enable Wake Word ('Hey Atom')"}
            >
                <span className="text-[10px] font-bold">ATOM</span>
            </Button>

            {isListening && (
                <div className="absolute bottom-full right-0 mb-1 flex items-center gap-1 z-50 pointer-events-none bg-white/90 dark:bg-gray-900/90 border border-red-200 dark:border-red-800 rounded-full px-2 py-0.5 shadow-sm whitespace-nowrap -translate-x-1/4">
                    <span className="w-1.5 h-1.5 bg-red-500 rounded-full animate-pulse" />
                    <span className="text-xs text-red-500 font-medium">Listening...</span>
                </div>
            )}
        </div>
    );
};
