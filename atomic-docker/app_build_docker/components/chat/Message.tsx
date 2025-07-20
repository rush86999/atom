import { UserChatType } from "@lib/dataTypes/Messaging/MessagingTypes";
import { dayjs } from "@lib/date-utils";
import React, { useRef, useEffect, Suspense } from "react";
import { useAudioMode } from "@lib/contexts/AudioModeContext";
import { ChatMessageActions } from "./chat-message-actions";
import { EmailContentCopy } from "./email-content-copy";
import { cn } from "@lib/Chat/utils"; // Import cn for class utility

// Dynamically import the SearchResultsDisplay component
const SearchResultsDisplay = React.lazy(() => import('./custom/SearchResultsDisplay'));
const MeetingPrepDisplay = React.lazy(() => import('./custom/MeetingPrepDisplay'));
const DailyBriefingDisplay = React.lazy(() => import('./custom/DailyBriefingDisplay'));
const ImageDisplay = React.lazy(() => import('./custom/ImageDisplay'));
const ChartDisplay = React.lazy(() => import('./custom/ChartDisplay'));


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
                "Failed to synthesize audio.",
                "Error occurred during audio synthesis.",
                "TTS synthesis succeeded but no audio URL was returned."
            ];
            const isTtsError = ttsErrorMessages.some(errMsg => message.content.includes(errMsg));

            if (isTtsError) {
                console.log("Message.tsx: TTS error detected in Audio Mode, playing error sound for message:", message.content);
                const errorAudio = new Audio('/assets/audio/tts_error.mp3');
                errorAudio.play().catch(e => console.error("Error playing TTS error sound:", e));
            }
        }
    }, [message.content, message.role, message.audioUrl, isAudioModeEnabled]);

    const isUser = message?.role === 'user';

    const bubbleBaseClasses = "group/item relative mb-2 px-4 py-3 max-w-xl lg:max-w-2xl break-words"; // Added break-words
    const userBubbleClasses = "bg-sky-600 text-white dark:bg-sky-500 dark:text-white rounded-2xl rounded-br-none";
    const assistantBubbleClasses = "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-100 rounded-2xl rounded-bl-none";
    const loadingBubbleClasses = "bg-gray-200 dark:bg-gray-600 rounded-2xl";

    return (
        <div className={cn("flex w-full px-2 my-3 font-sans", isUser ? "justify-end" : "justify-start")}>
            <div className={cn("flex flex-col", isUser ? "items-end" : "items-start")}>
                <div className={cn("text-xs mb-1", isUser ? "text-right mr-1" : "text-left ml-1",
                                   "text-gray-600 dark:text-gray-400")}>
                    {isUser ? "You" : "Assistant"}
                </div>

                {isLoading && !isUser ? (
                    <div className={cn(bubbleBaseClasses, loadingBubbleClasses, "flex items-center justify-center h-16 w-24")}> {/* Adjusted loading style */}
                        <div className="dot-elastic"></div> {/* Assuming dot-elastic is defined globally or in a CSS file */}
                    </div>
                ) : (
                    <div className={cn(
                        bubbleBaseClasses,
                        isUser ? userBubbleClasses : assistantBubbleClasses,
                        "text-base" // Ensure base font size for message content
                    )}>
                        <ChatMessageActions message={message} className={isUser ? "text-white dark:text-white" : "text-gray-700 dark:text-gray-200"} />
                        <div className="whitespace-pre-wrap">{message.content}</div> {/* Added whitespace-pre-wrap for text formatting */}
                        {message.audioUrl && !isUser && ( // Only show audio for assistant messages if needed
                            <audio
                                key={message.audioUrl}
                                src={message.audioUrl}
                                autoPlay
                                controls={false} // Keep controls hidden
                                style={{ display: 'none' }}
                                onEnded={() => {
                                    if (isAudioModeEnabled) {
                                        console.log("Message.tsx: Audio ended, requesting listen for reply.");
                                        triggerReplyListen();
                                    }
                                }}
                                onError={(e) => console.error('Error playing audio in Message.tsx:', e)}
                            />
                        )}
                    </div>
                )}
                <div className={cn("text-xs mt-1 opacity-75", isUser ? "text-right mr-1" : "text-left ml-1",
                                   "text-gray-500 dark:text-gray-400")}>
                    <time>{dayjs(message.date).fromNow()}</time>
                </div>

                {/* Custom content display area, ensuring it's outside the main bubble but associated with the message */}
                {!isUser && !isLoading && (htmlEmail || formData || message.customComponentType) && (
                     <div className={cn("mt-2 w-full max-w-xl lg:max-w-2xl", isUser ? "ml-auto" : "mr-auto")}> {/* Ensure custom content also respects max width */}
                        {message.customComponentType === 'semantic_search_results' && message.customComponentProps?.results && (
                            <Suspense fallback={<div className="text-sm text-gray-500 dark:text-gray-400">Loading search results...</div>}>
                                <SearchResultsDisplay results={message.customComponentProps.results} />
                            </Suspense>
                        )}
                        {message.customComponentType === 'meeting_prep_results' && message.customComponentProps?.briefing && (
                            <Suspense fallback={<div className="text-sm text-gray-500 dark:text-gray-400">Loading meeting preparation...</div>}>
                                <MeetingPrepDisplay briefing={message.customComponentProps.briefing} />
                            </Suspense>
                        )}
                        {message.customComponentType === 'daily_briefing_results' && message.customComponentProps?.briefing && (
                            <Suspense fallback={<div className="text-sm text-gray-500 dark:text-gray-400">Loading daily briefing...</div>}>
                                <DailyBriefingDisplay briefing={message.customComponentProps.briefing} />
                            </Suspense>
                        )}
                        {message.customComponentType === 'image_display' && message.customComponentProps?.imageUrl && (
                            <Suspense fallback={<div className="text-sm text-gray-500 dark:text-gray-400">Loading image...</div>}>
                                <ImageDisplay imageUrl={message.customComponentProps.imageUrl} />
                            </Suspense>
                        )}
                        {message.customComponentType === 'chart_display' && message.customComponentProps?.data && (
                            <Suspense fallback={<div className="text-sm text-gray-500 dark:text-gray-400">Loading chart...</div>}>
                                <ChartDisplay data={message.customComponentProps.data} chartType={message.customComponentProps.chartType} />
                            </Suspense>
                        )}
                        {htmlEmail && !message.customComponentType && (
                            <div className="group/email p-2 border rounded-lg bg-white dark:bg-gray-800 shadow">
                                <EmailContentCopy emailContent={divRef} />
                                <div ref={divRef} className="prose dark:prose-invert max-w-none" dangerouslySetInnerHTML={{ __html: htmlEmail }} />
                            </div>
                        )}
                        {formData && !message.customComponentType && !htmlEmail && (
                            <div className="p-2 border rounded-lg bg-white dark:bg-gray-800 shadow">
                                {formData}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

export default Message;
