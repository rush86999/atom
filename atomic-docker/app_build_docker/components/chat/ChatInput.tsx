/* eslint-disable react/self-closing-comp */
import React, { useState, useRef, useEffect } from "react";
import cls from 'classnames'
// import {ButtonScrollToBottom} from '@components/chat/button-scroll-to-bottom'
// ButtonScrollToBottom seems unused in the provided code, commenting out for now.
// If it's needed elsewhere or was intended for use, it can be uncommented.
import {Textarea} from '@components/chat/ui/textarea'
import { Tooltip, TooltipContent, TooltipTrigger } from "@components/chat/ui/tooltip";
import { cn } from "@lib/Chat/utils";
import { buttonVariants, Button } from "@components/chat/ui/button";
import { IconPlus, IconArrowElbow, IconMic, IconMicOff } from '@components/chat/ui/icons' // Assuming IconMic and IconMicOff
import { useEnterSubmit } from '@lib/Chat/hooks/use-enter-submit'


type Props = {
    sendMessage: (text: string) => void,
    isNewSession: boolean,
    callNewSession: () => void
}

 const ChatInput = ({ sendMessage, isNewSession, callNewSession }: Props) => {
    const [text, setText] = useState<string>('')
    const [isRecording, setIsRecording] = useState<boolean>(false);
    const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
    const [audioChunks, setAudioChunks] = useState<Blob[]>([]);
    const [isTranscribing, setIsTranscribing] = useState<boolean>(false);

    const { formRef, onKeyDown } = useEnterSubmit()
    const inputRef = useRef<HTMLTextAreaElement>(null)

    useEffect(() => {
        if (inputRef.current) {
          inputRef.current.focus()
        }
      }, [])
    
    // Cleanup media recorder and stream on unmount
    useEffect(() => {
        return () => {
            if (mediaRecorder && mediaRecorder.state === "recording") {
                mediaRecorder.stop();
            }
            mediaRecorder?.stream?.getTracks().forEach(track => track.stop());
        };
    }, [mediaRecorder]);

    const onChangeText = (e: { currentTarget: { value: React.SetStateAction<string>; }; }) => (setText(e.currentTarget.value))

    const onSubmit = (e: { preventDefault: () => void; }) => {
        e?.preventDefault()
        // validate
        if (!text) {
            return
        }
        sendMessage(text)
        setText('')
    }

    const handleToggleRecording = async () => {
        if (isRecording && mediaRecorder) {
            mediaRecorder.stop();
            setIsRecording(false);
            // Note: onstop will handle the transcription
        } else {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                const recorder = new MediaRecorder(stream);
                setMediaRecorder(recorder);

                recorder.ondataavailable = (event) => {
                    setAudioChunks(prev => [...prev, event.data]);
                };

                recorder.onstop = async () => {
                    setIsTranscribing(true);
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' }); // Deepgram supports webm
                    const audioFile = new File([audioBlob], "voice_input.webm", { type: 'audio/webm' });

                    const formData = new FormData();
                    formData.append("audio_file", audioFile);

                    try {
                        // Ensure this endpoint is correct and accessible from your frontend environment
                        const response = await fetch('/api/audio_processor/stt', {
                            method: 'POST',
                            body: formData
                        });

                        if (!response.ok) {
                            const errorBody = await response.json();
                            throw new Error(errorBody.error || 'STT API request failed');
                        }

                        const result = await response.json();
                        if (result.transcription) {
                            setText(prevText => prevText ? `${prevText} ${result.transcription}` : result.transcription);
                            if (inputRef.current) {
                                inputRef.current.focus(); // Refocus after transcription
                            }
                        } else if (result.error) {
                            alert(`Transcription Error: ${result.error}`);
                        } else {
                            alert("Transcription failed or returned empty.");
                        }
                    } catch (error: any) {
                        console.error("STT Error:", error);
                        alert(`Error during transcription: ${error.message || "Unknown error"}`);
                    } finally {
                        setAudioChunks([]);
                        setIsTranscribing(false);
                        // Stop microphone tracks to turn off microphone indicator
                        stream.getTracks().forEach(track => track.stop());
                    }
                };

                recorder.start();
                setAudioChunks([]); // Clear previous chunks
                setIsRecording(true);
            } catch (error) {
                console.error("Error accessing microphone:", error);
                alert("Could not access microphone. Please check permissions.");
                setIsRecording(false); // Ensure isRecording is false if permission denied
            }
        }
    };
    

    return (
        <div className={cls('fixed md:w-1/2 bottom-0 ')}> {/* Consider responsive width: w-full md:w-1/2 */}
            
            <form onSubmit={onSubmit}  ref={formRef} className={cls({ 'opacity-50': isNewSession }, 'space-y-4 border-t px-4 py-2 shadow-lg sm:rounded-t-xl sm:border md:py-4 bg-white')}>
                <label htmlFor="chat" className={cls("sr-only")}>Your message</label>
                <div className="relative flex max-h-60 w-full grow flex-col overflow-hidden px-8 sm:rounded-md sm:border sm:px-12"> {/* Increased padding for mic button */}
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Button
                                variant="outline"
                                size="icon"
                                type="button" // Add type="button" to prevent form submission
                                disabled={isNewSession}
                            onClick={e => {
                                e.preventDefault()
                                callNewSession()
                            }}
                            className={cn(
                                buttonVariants({ size: 'sm', variant: 'outline' }),
                                'absolute left-0 top-4 h-8 w-8 rounded-full bg-background p-0 sm:left-4'
                            )}
                            >
                            <IconPlus />
                            <span className="sr-only">New Chat</span>
                            </button>
                        </TooltipTrigger>
                        <TooltipContent>New Chat</TooltipContent>
                    </Tooltip>
                    <div className={cls("flex items-center px-3 py-2")}>
                        <Textarea 
                            id="chat2" 
                            ref={inputRef}
                            tabIndex={0}
                            onKeyDown={onKeyDown}
                            spellCheck={false}
                            rows={1} 
                            className={cls("min-h-[60px] w-full focus-within:outline-none sm:text-sm focus:ring-0 focus:ring-offset-0 border-none resize-none")} 
                            placeholder="Your message..."
                            value={text}
                            onChange={onChangeText}
                        />
                        <div className="absolute right-0 top-4 sm:right-4">
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <Button size="icon" disabled={isNewSession} type="submit" className={cls("text-white")}>
                                        <IconArrowElbow />
                                        <span className="sr-only">Send message</span>
                                    </Button>
                                </TooltipTrigger>
                            <TooltipContent>Send message</TooltipContent>
                        </Tooltip>
                        </div>
                    </div>
                </div>
            </form>
        </div>
    )

}

export default ChatInput
