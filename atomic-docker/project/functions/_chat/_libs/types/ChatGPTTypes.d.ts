import { ChatGPTRoleType } from '@/gpt-meeting/_libs/types/ChatGPTTypes';
export type ChatGPTSystemMessageType = {
    role: ChatGPTRoleType;
    content: string;
};
export type ChatGPTUserMessageType = {
    role: ChatGPTRoleType;
    content: string;
};
export type ChatGPTAssistantMessageType = {
    role: ChatGPTRoleType;
    content: string;
};
export type ChatGPTMessageHistoryType = (ChatGPTAssistantMessageType | ChatGPTUserMessageType | ChatGPTSystemMessageType)[];
export type ChatResponseType = {
    totalTokenCount: number;
    messageList: ChatGPTMessageHistoryType;
};
