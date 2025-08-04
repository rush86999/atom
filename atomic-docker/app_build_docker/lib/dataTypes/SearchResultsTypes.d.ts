export interface FrontendMeetingSearchResult {
    notion_page_id: string;
    notion_page_title: string;
    notion_page_url: string;
    text_preview: string;
    last_edited: string;
    score: number;
}
export interface SearchResultsDisplayProps {
    results: FrontendMeetingSearchResult[];
}
export interface SemanticSearchResultsPayload {
    type: 'semantic_search_results';
    summaryText: string;
    results: FrontendMeetingSearchResult[];
}
