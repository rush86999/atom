export interface EventRecord {
    id: string;
    userId: string;
    vector: number[];
    start_date: string;
    end_date: string;
    raw_event_text?: string;
    eventType?: string;
}
export interface SearchRequest {
    userId: string;
    searchText: string;
    startDate?: string;
    endDate?: string;
    limit?: number;
}
export interface SkillError {
    code: string;
    message: string;
    details?: any;
}
export interface LanceEventMatcherResponse<T> {
    ok: boolean;
    data?: T;
    error?: SkillError;
}
export interface OpenAIInterface {
    apiKey: string;
}
export interface EventSchema {
    id: string;
    userId: string;
    vector: number[];
    start_date: string;
    end_date: string;
    raw_event_text?: string;
}
export interface CategoryType {
    id: string;
    name: string;
    description?: string;
}
export interface AIProcessedEvent {
    eventId: string;
    assignedCategoryId: string;
    relevanceScore: number;
    rationale?: string;
}
export interface AIQueryEnhancementResult {
    refinedQueryText: string;
    suggestedCategoryIds?: string[];
    identifiedDateRange?: {
        start?: string;
        end?: string;
    };
}
