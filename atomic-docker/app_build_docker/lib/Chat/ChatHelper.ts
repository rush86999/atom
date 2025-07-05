import { ChatBrainBodyType, ChatHistoryType, SkillChatHistoryType, SkillMessageHistoryType } from "@lib/dataTypes/Messaging/MessagingTypes"
import { dayjs } from "@lib/date-utils"
import _ from "lodash"
import { chatWSAPIUrl } from "./constants"
import qs from 'qs'
import { v4 as uuid } from 'uuid'

export const createChatSocket = async (token: string) => {
    try {
        const socket = new WebSocket(`${chatWSAPIUrl}?${qs.stringify({Auth: `Bearer ${token}`})}`)
        return socket
    } catch (e) {
        console.log(e, ' unable to create client')
    }
}

export const newSession = (
    setChatHistory: React.Dispatch<React.SetStateAction<ChatHistoryType | []>>,
    setMessageHistory: React.Dispatch<React.SetStateAction<[] | SkillChatHistoryType>>,
    setReconnect: React.Dispatch<React.SetStateAction<boolean>>,
    reconnect: boolean,
) => {
    setChatHistory([{
        role: 'assistant',
        content: 'How can I help you today?',
        id: 0,
        date: dayjs().format(),
    }])
    setMessageHistory([{
        skill: 'pending',
        query: 'pending',
        messages: [],
    }])
    setReconnect(!reconnect)
}

export const sendMessage = async (
    socket: WebSocket,
    body: ChatBrainBodyType,
) => {
    try {
        socket.send(JSON.stringify(body))
    } catch (e) {
        console.log(e, ' unable to send message')
    }
}

export const addMessageToBrain = async (
    socket: WebSocket,
    userMessage: string,
    userId: string,
    timezone: string,
    chatHistory: ChatHistoryType,
    messageHistory: SkillChatHistoryType,
    setChatHistory: React.Dispatch<React.SetStateAction<ChatHistoryType | []>>,
    setMessageHistory: React.Dispatch<React.SetStateAction<[] | SkillChatHistoryType>>,
    setIsLoading:  React.Dispatch<React.SetStateAction<boolean>>,
) => {
    console.log(chatHistory, ' chatHistory inside addNewQuestion')
    const newChatHistory = (chatHistory || [])?.concat([{
        role: 'user',
        content: userMessage,
        id: chatHistory?.length, // old length so matche index
        date: dayjs().format(),
    }])
    try {
        console.log(newChatHistory, ' newChatHistory inside addNewQuestion')
        const newChatHistory2 = (newChatHistory || [])?.concat([{
            role: 'assistant',
            content: 'working ...',
            id: newChatHistory?.length,
            date: dayjs().format(),
        }])

        console.log(newChatHistory2, ' newChatHistory2 inside addNewQuestion')

        setChatHistory(newChatHistory2)

        setIsLoading(true)

        /**{
    skill: SkillType,
    messages: MessageHistoryType,
    query: 'missing_fields' | 'completed' | 'event_not_found' | 'pending' | 'error',
    required?: RequiredFieldsType,
    formData?: ReceiverTimezoneFormDataResponseType,
    prevData?: any,
    prevDataExtra?: any,
}
 */     const index = messageHistory?.length === 0 ? 0 : messageHistory?.length - 1
        const newMessage: SkillMessageHistoryType = {
            ...messageHistory?.[index],
            messages: [
                ...messageHistory?.[index]?.messages,
                {role: 'user', content: userMessage}
            ]
        }
        const body: ChatBrainBodyType = {
            chat: newMessage,
            userId,
            timezone,
            id: uuid(),
        }

        await sendMessage(socket, body)

        const newMessageHistory = messageHistory.concat([newMessage])

        setMessageHistory(newMessageHistory)

    } catch (e) {
        console.log(e, ' unable to add message to brain')
    }
}

export const receiveMessageFromBrain = async (
    skillMessageHistory: SkillMessageHistoryType,
    chatHistory: ChatHistoryType,
import { SemanticSearchResultsPayload } from "../dataTypes/SearchResultsTypes"; // Import the new payload type

// Import for structuredData, assuming it's part of SkillMessageHistoryType or a related type
// For now, we'll assume skillMessageHistory might contain an optional 'structuredData' field.
// Actual type definition for what agent sends over WebSocket for structured data would be:
// interface AgentWebSocketMessage {
//   text: string;
//   audioUrl?: string;
//   structuredData?: { displayType: string; data: any; summaryText?: string; };
//   // Other fields like skill, query, messages for the skill log part
//   skill?: string;
//   query?: string;
//   messages?: {role: string; content: string}[];
//   // etc.
// }
// For receiveMessageFromBrain, skillMessageHistory is used for the skill log part.
// The part that constructs UserChatType for display is now in UserViewChat.tsx.

export const receiveMessageFromBrain = async (
    skillDataForLog: SkillMessageHistoryType, // Renamed to reflect its purpose for logging
    messageHistory: SkillChatHistoryType,
    setMessageHistory: React.Dispatch<React.SetStateAction<[] | SkillChatHistoryType>>,
    // setChatHistory and setIsLoading are removed as they are handled by the caller (UserViewChat.tsx)
) => {
    try {
        // This function now *only* updates messageHistory (the skill log).
        // It does not construct or set the visual chat messages in chatHistory.

        // The existing switch logic was mainly for updating chatHistory's "working..." message
        // and then setting messageHistory.
        // Since chatHistory is handled by the caller, we simplify this.

        // We need to decide how to update messageHistory based on skillDataForLog.
        // The old logic replaced the last item in messageHistory if it was 'pending'
        // and then added a new 'pending' item if the query was 'completed' or 'event_not_found'.

        let updatedMessageHistory = [...messageHistory];

        if (skillDataForLog.query === 'missing_fields') {
            // Replace the last 'pending' message in messageHistory with the new skillDataForLog
            if (updatedMessageHistory.length > 0 && updatedMessageHistory[updatedMessageHistory.length - 1].query === 'pending') {
                updatedMessageHistory[updatedMessageHistory.length - 1] = skillDataForLog;
            } else {
                // This case should ideally not happen if addMessageToBrain correctly sets up a pending state.
                updatedMessageHistory.push(skillDataForLog);
            }
            setMessageHistory(updatedMessageHistory);
        } else if (skillDataForLog.query === 'completed' || skillDataForLog.query === 'event_not_found' || skillDataForLog.query === 'error' ) {
            // Replace the last 'pending' message and add a new 'pending' state for the next interaction.
             if (updatedMessageHistory.length > 0 && updatedMessageHistory[updatedMessageHistory.length - 1].query === 'pending') {
                updatedMessageHistory[updatedMessageHistory.length - 1] = skillDataForLog;
            } else {
                updatedMessageHistory.push(skillDataForLog);
            }
            // Add a new pending state for the next turn
            updatedMessageHistory.push({
                skill: 'pending',
                query: 'pending',
                messages: [],
            });
            setMessageHistory(updatedMessageHistory);
        } else if (skillDataForLog.query === 'pending') {
            // If the incoming data itself is 'pending' (e.g. an ack), update the last item.
            // This might happen if the agent sends multiple updates for a single turn.
            if (updatedMessageHistory.length > 0) {
                 updatedMessageHistory[updatedMessageHistory.length - 1] = skillDataForLog;
                 setMessageHistory(updatedMessageHistory);
            } else {
                 setMessageHistory([skillDataForLog]);
            }
        } else {
            // Default behavior: just append if the query state is unknown or doesn't fit above.
            // This ensures the log captures it.
            console.warn("receiveMessageFromBrain: Unhandled skillDataForLog.query state:", skillDataForLog.query, "Appending to log.");
            setMessageHistory([...updatedMessageHistory, skillDataForLog]);
        }

        // setIsLoading(false) is now handled by the caller (UserViewChat.tsx)

    } catch (e) {
        console.log(e, ' unabl eto receive message from brain')
        
    }
}

