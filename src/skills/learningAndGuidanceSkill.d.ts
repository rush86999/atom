import { LLMServiceInterface } from '../lib/llmUtils';
export interface KnowledgeBaseArticle {
    id: string;
    title: string;
    contentType: 'tutorial' | 'how-to' | 'faq' | 'workflow_guide' | 'explanation';
    application?: string;
    keywords?: string[];
    content: string;
    steps?: {
        title: string;
        description: string;
    }[];
    difficulty?: 'beginner' | 'intermediate' | 'advanced';
}
export type GuidanceType = 'answer_question' | 'find_tutorial' | 'guide_workflow' | 'general_explanation';
export interface LearningAndGuidanceInput {
    userId: string;
    query: string;
    guidanceTypeHint?: GuidanceType;
    applicationContext?: string;
    options?: {
        preferContentType?: KnowledgeBaseArticle['contentType'];
        maxResults?: number;
    };
}
export interface ProvidedGuidance {
    title: string;
    contentSnippet?: string;
    fullContent?: string;
    steps?: {
        title: string;
        description: string;
    }[];
    sourceArticleId: string;
    relevanceScore?: number;
}
export interface LearningAndGuidanceResult {
    originalQuery: string;
    guidanceProvided: ProvidedGuidance[];
    followUpSuggestions?: string[];
    searchPerformedOn?: string;
}
export declare class LearningAndGuidanceSkill {
    private readonly llmService;
    constructor(llmService: LLMServiceInterface);
    execute(input: LearningAndGuidanceInput): Promise<LearningAndGuidanceResult>;
}
