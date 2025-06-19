import { UserChatType } from "@lib/dataTypes/Messaging/MessagingTypes";
import { dayjs } from "@lib/date-utils";
import React, { useRef } from "react";
import { ChatMessageActions } from "./chat-message-actions";
import { EmailContentCopy } from "./email-content-copy";


type Props = {
    message: UserChatType,
    isLoading?: boolean,
    formData?: React.ReactNode,
    htmlEmail?: string,
}

function Message({ message, isLoading, formData, htmlEmail }: Props) {
    const divRef = useRef<HTMLDivElement>(null)
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
                                            onError={(e) => console.error('Error playing audio:', e)}
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
                                    {
                                        htmlEmail ? (
                                            <div className="group/email">
                                                <EmailContentCopy emailContent={divRef} />
                                                <div ref={divRef} dangerouslySetInnerHTML={{ __html: htmlEmail }} />
                                            </div>
                                        ) : null
                                    }
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


