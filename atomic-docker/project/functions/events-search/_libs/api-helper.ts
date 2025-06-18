
import { hasuraGraphUrl, hasuraAdminSecret, openAIPassKey, openAIChatGPTModel, defaultOpenAIAPIKey } from './constants'
// EmailKnwSourceType, AgentKnwSourceType might be needed if OpenAI functions use them, otherwise remove
// For now, assume they are not needed by remaining OpenAI functions.
// import { EmailKnwSourceType, AgentKnwSourceType } from './types' // Keep if callOpenAI* uses these types indirectly.

import OpenAI from "openai"
import { CreateChatCompletionRequestMessage } from 'openai/resources/chat'
import { ChatGPTRoleType } from '@/gpt-meeting/_libs/types/ChatGPTTypes'



const openai = new OpenAI({
    apiKey: defaultOpenAIAPIKey,
});

export const convertEventTitleToOpenAIVector = async (
    title: string,
) => {
    try {
        const embeddingRequest: OpenAI.Embeddings.EmbeddingCreateParams = {
            model: 'text-embedding-3-small',
            input: title,
        }

        const res = await openai.embeddings.create(embeddingRequest)
        console.log(res, ' res inside convertEventTitleToOpenAIVectors')
        return res?.data?.[0]?.embedding
    } catch (e) {
        console.log(e, ' unable to convert event title to openaivectors')
    }
}

export const convertQuestionToOpenAIVectors = async (
    question: string,
    openai: OpenAI,
) => {
    try {
        const embeddingRequest: OpenAI.Embeddings.EmbeddingCreateParams = {
            model: 'text-embedding-3-small',
            input: question,
        }

        const res = await openai.embeddings.create(embeddingRequest)
        console.log(res, ' res inside convertQuestionToOpenAIVectors')
        return res?.data?.[0]?.embedding
    } catch (e) {
        console.log(e, ' unable to convert question to openaivectors')
    }
}


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
export const callOpenAIWithMessageHistory = async (
    openai: OpenAI,
    messageHistory: CreateChatCompletionRequestMessage[] = [],
    prompt: string,
    model: 'gpt-3.5-turbo' = 'gpt-3.5-turbo',
    userData: string,
    exampleInput?: string,
    exampleOutput?: string,
) => {
    try {
        // assistant
        const completion = await openai.chat.completions.create({
            model,
            messages: messageHistory.concat([
                { role: 'system' as ChatGPTRoleType, content: prompt },
                exampleInput && { role: 'user' as ChatGPTRoleType, content: exampleInput },
                exampleOutput && { role: 'assistant' as ChatGPTRoleType, content: exampleOutput },
                { role: 'user' as ChatGPTRoleType, content: userData }
            ])
            ?.filter(m => !!m),
        });
        console.log(completion.choices[0]?.message?.content, ' response from openaiapi');

        return { totalTokenCount: completion?.usage?.total_tokens, response: completion?.choices?.[0]?.message?.content}
    } catch (error) {
        if (error.response) {
            console.log(error.response.status, ' openai error status');
            console.log(error.response.data, ' openai error data');
        } else {
            console.log(error.message, ' openai error message');
        }
    }
}
export const callOpenAI = async (
    openai: OpenAI,
    prompt: string,
    model: 'gpt-3.5-turbo' = 'gpt-3.5-turbo',
    userData: string,
    exampleInput?: string,
    exampleOutput?: string,
) => {
    try {
        // assistant
        const completion = await openai.chat.completions.create({
            model,
            messages: [
                { role: 'system' as ChatGPTRoleType, content: prompt },
                exampleInput && { role: 'user' as ChatGPTRoleType, content: exampleInput },
                exampleOutput && { role: 'assistant' as ChatGPTRoleType, content: exampleOutput },
                { role: 'user' as ChatGPTRoleType, content: userData }
            ]?.filter(m => !!m),
        });
        console.log(completion.choices[0]?.message?.content, ' response from openaiapi');

        return completion?.choices?.[0]?.message?.content
    } catch (error) {
        if (error.response) {
            console.log(error.response.status, ' openai error status');
            console.log(error.response.data, ' openai error data');
        } else {
            console.log(error.message, ' openai error message');
        }
    }
}




