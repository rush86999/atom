import { ChatCompletionMessageParam } from 'openai/resources/chat/completions';
import { ProcessedNLUResponse, LtmQueryResult } from '../../types';
export declare function resetOpenAIClientCache(): void;
export declare function understandMessage(message: string, conversationHistory?: ChatCompletionMessageParam[], ltmContext?: LtmQueryResult[] | null): Promise<ProcessedNLUResponse>;
