import { ChatGPTRoleType } from '@/gpt-meeting/_libs/types/ChatGPTTypes';

export type ChatGPTSystemMessageType = {
  role: ChatGPTRoleType; // 'system'
  content: string; // prompt
};

export type ChatGPTUserMessageType = {
  role: ChatGPTRoleType; // 'user'
  content: string; // user input
};

export type ChatGPTAssistantMessageType = {
  role: ChatGPTRoleType; //'assistant',
  content: string; // gpt output
};

export type ChatGPTMessageHistoryType = (
  | ChatGPTAssistantMessageType
  | ChatGPTUserMessageType
  | ChatGPTSystemMessageType
)[];

export type ChatResponseType = {
  totalTokenCount: number;
  messageList: ChatGPTMessageHistoryType;
};
