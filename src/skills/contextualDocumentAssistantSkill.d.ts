import { LLMServiceInterface } from '../lib/llmUtils';
export interface DocumentContent {
    id: string;
    title: string;
    textContent: string;
    tags?: string[];
    createdAt?: Date;
}
export interface DocumentAssistantInput {
    query: string;
    documentIds?: string[];
    userId: string;
    options?: {
        summarize?: boolean;
        targetSummaryLength?: 'short' | 'medium' | 'long';
        maxResults?: number;
        snippetLength?: number;
    };
}
export interface AnswerObject {
    documentId: string;
    documentTitle?: string;
    relevantSnippets: string[];
    summary?: string;
    relevanceScore?: number;
    pageNumbers?: number[];
}
export interface DocumentAssistantResult {
    originalQuery: string;
    answers: AnswerObject[];
    overallSummary?: string;
    searchPerformedOn?: 'all_accessible' | 'specified_ids';
}
export declare class ContextualDocumentAssistantSkill {
    private readonly llmService;
    constructor(llmService: LLMServiceInterface);
    execute(input: DocumentAssistantInput): Promise<DocumentAssistantResult>;
}
