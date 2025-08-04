import { GmailMessageSnippet, NotionPageSummary, SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function storeEmailSnippetInLanceDb(userId: string, email: GmailMessageSnippet): Promise<SkillResponse<{
    email_id: string;
    message: string;
} | null>>;
export declare function storeNotionPageSummaryInLanceDb(userId: string, page: NotionPageSummary): Promise<SkillResponse<{
    notion_page_id: string;
    message: string;
} | null>>;
export declare function processAndStoreDocument(userId: string, filePath: string, // Changed from file: File
docType: string, // e.g., 'pdf', 'docx'
title?: string, sourceUri?: string): Promise<SkillResponse<{
    doc_id: string;
    num_chunks_stored: number;
} | null>>;
export interface SemanticSearchFilters {
    date_after?: string;
    date_before?: string;
    source_types?: SearchResultSourceType[];
    doc_type_filter?: string;
}
import { UniversalSearchResultItem, SearchResultSourceType, HybridSearchResultItem, HybridSearchFilters } from '../../atomic-docker/project/functions/atom-agent/types';
export interface HybridSearchOptions {
    semanticLimit?: number;
    keywordLimit?: number;
    filters?: HybridSearchFilters;
}
export declare function hybridSearch(userId: string, queryText: string, options?: HybridSearchOptions): Promise<SkillResponse<HybridSearchResultItem[]>>;
export declare function semanticSearchLanceDb(userId: string, queryText: string, filters?: SemanticSearchFilters, limit?: number): Promise<SkillResponse<UniversalSearchResultItem[]>>;
