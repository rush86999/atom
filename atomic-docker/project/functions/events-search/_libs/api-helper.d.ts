import OpenAI from 'openai';
import { CreateChatCompletionRequestMessage } from 'openai/resources/chat';
export declare const convertEventTitleToOpenAIVector: (title: string) => Promise<number[] | undefined>;
export declare const convertQuestionToOpenAIVectors: (question: string, openai: OpenAI) => Promise<number[] | undefined>;
/**
 * response:
 * {
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "\n\nHello there, how may I assist you today?",
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 9,
    "completion_tokens": 12,
    "total_tokens": 21
  }
}

 */
export declare const callOpenAIWithMessageHistory: (openai: OpenAI, messageHistory: CreateChatCompletionRequestMessage[] | undefined, prompt: string, model: "gpt-3.5-turbo" | undefined, userData: string, exampleInput?: string, exampleOutput?: string) => Promise<{
    totalTokenCount: number | undefined;
    response: string | null;
} | undefined>;
export declare const callOpenAI: (openai: OpenAI, prompt: string, model: "gpt-3.5-turbo" | undefined, userData: string, exampleInput?: string, exampleOutput?: string) => Promise<string | null | undefined>;
