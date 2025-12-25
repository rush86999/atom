import React, { useEffect } from 'react';
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition';
import { Button } from '@/components/ui/button';
import { Mic, MicOff, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

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
        resetTranscript
    } = useSpeechRecognition();

    // Sync transcript to parent
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
            <TooltipProvider>
                <Tooltip>
                    <TooltipTrigger asChild>
                        <Button variant="ghost" size="icon" disabled className="opacity-50">
                            <MicOff className="w-4 h-4 text-gray-400" />
                        </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                        <p>Voice input is not supported in this browser.</p>
                    </TooltipContent>
                </Tooltip>
            </TooltipProvider>
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
