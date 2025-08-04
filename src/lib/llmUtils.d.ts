export type LLMTaskType = 'categorize_email' | 'summarize_email' | 'suggest_reply_email' | 'extract_actions_email' | 'classify_guidance_query' | 'answer_from_text' | 'extract_steps_from_text' | 'summarize_for_explanation' | 'generate_followup_suggestions' | 'extract_document_snippets' | 'custom_lead_agent_synthesis' | 'summarize_document_snippets' | 'summarize_overall_answer' | 'parse_search_query' | 'custom_analytical_analysis' | 'custom_creative_analysis' | 'custom_practical_analysis' | 'custom_synthesis' | 'custom_advanced_research' | 'custom_social_media' | 'custom_content_creation' | 'custom_personalized_shopping' | 'custom_legal_document_analysis' | 'custom_recruitment_recommendation' | 'custom_vibe_hacking';
export interface EmailCategorizationData {
    subject: string;
    bodySnippet: string;
}
export interface SearchQueryParsingData {
    rawQuery: string;
    currentDate: string;
}
export interface EmailSummarizationData {
    subject: string;
    bodySnippet: string;
}
export interface EmailReplySuggestionData {
    category: string;
    subject: string;
    summary: string;
    actionItems?: string[];
}
export interface EmailActionExtractionData {
    emailBody: string;
}
export interface GuidanceQueryClassificationData {
    query: string;
}
export interface AnswerFromTextData {
    query: string;
    textContent: string;
    articleTitle?: string;
}
export interface StepsFromTextData {
    query: string;
    textContent: string;
    articleTitle?: string;
}
export interface ExplanationData {
    query: string;
    textContent: string;
    articleTitle?: string;
}
export interface FollowupSuggestionData {
    query: string;
    articleTitle?: string;
}
export interface DocumentSnippetData {
    query: string;
    documentTitle: string;
    documentText: string;
    snippetLength?: number;
}
export interface DocumentSummaryData {
    query: string;
    documentTitle: string;
    snippets?: string[];
    documentText?: string;
    targetLength?: string;
}
export interface OverallSummaryData {
    query: string;
    individualSummaries: {
        title?: string | undefined;
        summary?: string | undefined;
    }[];
}
export interface StructuredLLMPrompt {
    task: LLMTaskType;
    data: any;
}
export interface LLMServiceResponse {
    success: boolean;
    content?: string;
    error?: string;
    usage?: {
        promptTokens: number;
        completionTokens: number;
        totalTokens: number;
    };
}
export interface LLMServiceInterface {
    generate(prompt: StructuredLLMPrompt, model: string, options?: {
        temperature?: number;
        maxTokens?: number;
        isJsonOutput?: boolean;
    }): Promise<LLMServiceResponse>;
}
export declare class MockLLMService implements LLMServiceInterface {
    generate(structuredPrompt: StructuredLLMPrompt, model: string, options?: {
        temperature?: number;
        maxTokens?: number;
    }): Promise<LLMServiceResponse>;
}
export declare class RealLLMService implements LLMServiceInterface {
    private apiKey;
    private defaultModelName;
    private baseURL;
    private openai;
    constructor(apiKey: string, defaultModelName: string, baseURL?: string);
    private _constructMessages;
    generate(structuredPrompt: StructuredLLMPrompt, modelNameToUse?: string, options?: {
        temperature?: number;
        maxTokens?: number;
        isJsonOutput?: boolean;
    }): Promise<LLMServiceResponse>;
}
