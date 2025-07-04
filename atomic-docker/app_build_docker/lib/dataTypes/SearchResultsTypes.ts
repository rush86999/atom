// Defines the structure for semantic search results on the frontend

export interface FrontendMeetingSearchResult {
  notion_page_id: string;
  notion_page_title: string;
  notion_page_url: string;
  text_preview: string;
  last_edited: string; // ISO date string
  score: number;
}

// Props for the SearchResultsDisplay component
export interface SearchResultsDisplayProps {
  results: FrontendMeetingSearchResult[];
}

// Data structure agent might send for this type of display
export interface SemanticSearchResultsPayload {
  type: 'semantic_search_results';
  summaryText: string; // e.g., "Found 5 results..."
  results: FrontendMeetingSearchResult[];
}
