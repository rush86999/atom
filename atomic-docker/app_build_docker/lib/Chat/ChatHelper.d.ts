import { ChatBrainBodyType, ChatHistoryType, SkillChatHistoryType, SkillMessageHistoryType } from '@lib/dataTypes/Messaging/MessagingTypes';
export declare const createChatSocket: (token: string) => Promise<WebSocket | undefined>;
export declare const newSession: (setChatHistory: React.Dispatch<React.SetStateAction<ChatHistoryType | []>>, setMessageHistory: React.Dispatch<React.SetStateAction<[] | SkillChatHistoryType>>, setReconnect: React.Dispatch<React.SetStateAction<boolean>>, reconnect: boolean) => void;
export declare const sendMessage: (socket: WebSocket, body: ChatBrainBodyType) => Promise<void>;
export declare const addMessageToBrain: (socket: WebSocket, userMessage: string, userId: string, timezone: string, chatHistory: ChatHistoryType, messageHistory: SkillChatHistoryType, setChatHistory: React.Dispatch<React.SetStateAction<ChatHistoryType | []>>, setMessageHistory: React.Dispatch<React.SetStateAction<[] | SkillChatHistoryType>>, setIsLoading: React.Dispatch<React.SetStateAction<boolean>>) => Promise<void>;
export declare const receiveMessageFromBrain: (skillDataForLog: SkillMessageHistoryType, // Renamed to reflect its purpose for logging
messageHistory: SkillChatHistoryType, setMessageHistory: React.Dispatch<React.SetStateAction<[] | SkillChatHistoryType>>) => Promise<void>;
