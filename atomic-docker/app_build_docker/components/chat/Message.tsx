import { UserChatType } from "@lib/dataTypes/Messaging/MessagingTypes";
import { dayjs } from "@lib/date-utils";
import React, { useRef, useEffect, Suspense } from "react"; // Added Suspense
import { useAudioMode } from "@lib/contexts/AudioModeContext"; // Import useAudioMode
import { ChatMessageActions } from "./chat-message-actions";
import { EmailContentCopy } from "./email-content-copy";

// Dynamically import the SearchResultsDisplay component
const SearchResultsDisplay = React.lazy(() => import('./custom/SearchResultsDisplay'));


type Props = {
    message: UserChatType,
    isLoading?: boolean,
    formData?: React.ReactNode,
    htmlEmail?: string,
}

function Message({ message, isLoading, formData, htmlEmail }: Props) {
    const divRef = useRef<HTMLDivElement>(null);
    const { isAudioModeEnabled, triggerReplyListen } = useAudioMode();

    useEffect(() => {
        if (isAudioModeEnabled && message.role === 'assistant' && message.content && !message.audioUrl) {
            const ttsErrorMessages = [
                "Failed to synthesize audio.", // From atom-agent TTS request failed (HTTP error)
                "Error occurred during audio synthesis.", // From atom-agent TTS catch block
                "TTS synthesis succeeded but no audio URL was returned." // From atom-agent if TTS result is missing audio_url
            ];
            // Check if the message content includes any known TTS error substrings
            const isTtsError = ttsErrorMessages.some(errMsg => message.content.includes(errMsg));

            if (isTtsError) {
                console.log("Message.tsx: TTS error detected in Audio Mode, playing error sound for message:", message.content);
                const errorAudio = new Audio('/assets/audio/tts_error.mp3'); // Path to the generic error sound
                errorAudio.play().catch(e => console.error("Error playing TTS error sound:", e));
            }
        }
    }, [message.content, message.role, message.audioUrl, isAudioModeEnabled]);

    return (
        <div className=" px-2">
            {
                message?.role === 'user'
                ? (
                    <div className=" chat chat-end">

                        <div className="chat-header">
                            You
                        </div>

                        <div className="group/item chat-bubble chat-bubble-primary">
                        <ChatMessageActions message={message} />
                            {message.content}
                        </div>
                        <div className="chat-footer opacity-50">
                            <time className="text-xs opacity-50">{dayjs(message.date).fromNow()}</time>
                        </div>
                    </div>
                ) : (
                    <div className="chat chat-start">

                        {isLoading
                        ? (
                            <div className="">
                                <div className="chat-header">
                                    Assistant
                                </div>
                                <div className="chat-bubble chat-bubble-secondary flex items-center justify-center">
                                    <div className="ml-2" />
                                    <div className="dot-elastic" />
                                    <div className="mr-2" />
                                </div>
                                <div className="chat-footer opacity-50">
                                    <time className="text-xs opacity-50">{dayjs(message.date).fromNow()}</time>
                                </div>
                            </div>
                        ) : (
                            <div className="">
                                
                                <div className="chat-header">
                                    Assistant
                                </div>
                                
                                <div className="group/item chat-bubble chat-bubble-secondary">
                                    <ChatMessageActions message={message} />
                                    {message.content}
                                    {message.audioUrl && (
                                        <audio
                                            key={message.audioUrl}
                                            src={message.audioUrl}
                                            autoPlay
                                            controls={false}
                                            style={{ display: 'none' }}
                                            onEnded={() => {
                                                if (isAudioModeEnabled && message.role === 'assistant') {
                                                  console.log("Message.tsx: Audio ended, requesting listen for reply.");
                                                  triggerReplyListen();
                                                }
                                              }}
                                            onError={(e) => console.error('Error playing audio in Message.tsx:', e)}
                                        />
                                    )}
                                </div>
                                <div className="chat-footer opacity-50">
                                    <time className="text-xs opacity-50">{dayjs(message.date).fromNow()}</time>
                                </div>
                                <div className="pb-2">
                                    {
                                        formData ? formData : null
                                    }
                                </div>
                                <div className="pb-2">
                                    {/* Render custom component if type matches */}
                                    {message.customComponentType === 'semantic_search_results' && message.customComponentProps?.results && (
                                        <Suspense fallback={<div>Loading search results...</div>}>
                                            <SearchResultsDisplay results={message.customComponentProps.results} />
                                        </Suspense>
                                    )}
                                    {/* Render HTML email if present */}
                                    {htmlEmail && !message.customComponentType && ( // Avoid rendering if custom component already shown
                                        <div className="group/email">
                                            <EmailContentCopy emailContent={divRef} />
                                            <div ref={divRef} dangerouslySetInnerHTML={{ __html: htmlEmail }} />
                                        </div>
                                    )}
                                    {/* Render generic formData if present and no other custom content took precedence */}
                                    {formData && !message.customComponentType && !htmlEmail && (
                                        <div>{formData}</div>
                                    )}
                                </div>
                            </div>
                            )}
                    </div>
                )
            }
        </div>
    )
}

export default Message


