import React, { useEffect } from 'react';
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition';
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
        browserSupportsSpeechRecognition,
        resetTranscript,
        wakeWordEnabled,
        setWakeWordMode
    } = useSpeechRecognition();

    // Sync transcript to parent
    useEffect(() => {
        if (transcript) {
            onTranscriptChange(transcript);
        }
    }, [transcript, onTranscriptChange]);

    // Listen for global wake word event
    useEffect(() => {
        const handleWakeWord = (event: CustomEvent) => {
            console.log("Global Wake Word Triggered!", event.detail);
            if (!isListening) {
                resetTranscript();
                startListening();
            }
        };

        window.addEventListener('wake-word-activated' as any, handleWakeWord as any);
        return () => {
            window.removeEventListener('wake-word-activated' as any, handleWakeWord as any);
        };
    }, [isListening, startListening, resetTranscript]);

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
                variant="ghost"
                size="icon"
                onClick={() => {
                    if (wakeWordEnabled) {
                        setWakeWordMode(false);
                        stopListening();
                    } else {
                        setWakeWordMode(true);
                        startListening();
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
                <div className="absolute left-full ml-2 flex space-x-1 items-center h-4">
                    {/* Simple CSS animation for audio wave simulation */}
                    <span className="w-1 h-3 bg-red-500 rounded-full animate-[bounce_1s_infinite_100ms]"></span>
                    <span className="w-1 h-5 bg-red-500 rounded-full animate-[bounce_1s_infinite_200ms]"></span>
                    <span className="w-1 h-4 bg-red-500 rounded-full animate-[bounce_1s_infinite_300ms]"></span>
                    <span className="text-xs text-red-500 font-medium ml-1 whitespace-nowrap">Listening...</span>
                </div>
            )}
        </div>
    );
};
