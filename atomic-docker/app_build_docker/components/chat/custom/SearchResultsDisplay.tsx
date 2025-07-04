import React from 'react';
// Assuming FrontendMeetingSearchResult and SearchResultsDisplayProps are defined in a shared types location
// For now, let's redefine or assume they will be imported correctly if this file is part of a larger system.
// If not, these definitions would need to be co-located or imported from e.g., '@lib/dataTypes/SearchResultsTypes'

// Define types locally if not importing, ensuring they match the expected structure
export interface FrontendMeetingSearchResult {
  notion_page_id: string;
  notion_page_title: string;
  notion_page_url: string;
  text_preview: string;
  last_edited: string; // ISO date string
  score: number;
}

export interface SearchResultsDisplayProps {
  results: FrontendMeetingSearchResult[];
}

// dayjs is used in Message.tsx, assuming it's available globally or via context/import
// If not, it would need to be imported: import dayjs from 'dayjs';
// For this component, we can try to use browser's built-in Date formatting for simplicity
// or ensure dayjs is properly set up in the project.
// Let's use toLocaleDateString for now if dayjs is not directly importable here.
const formatDate = (isoString: string): string => {
  if (!isoString) return "N/A";
  try {
    // More robust date formatting than just toLocaleDateString if dayjs was used project-wide
    // For example: dayjs(isoString).format("MMM D, YYYY h:mm A");
    return new Date(isoString).toLocaleDateString(undefined, {
      year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  } catch (e) {
    console.error("Error formatting date:", isoString, e);
    return "Invalid Date";
  }
};

const SearchResultItem: React.FC<{ item: FrontendMeetingSearchResult }> = ({ item }) => {
  const displayDate = formatDate(item.last_edited);

  return (
    <div className="mb-3 p-3 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 shadow-sm hover:shadow-md transition-shadow">
      <h4 className="text-md font-semibold mb-1">
        <a
          href={item.notion_page_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-500 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 hover:underline"
          title={item.notion_page_title || "View Notion Page"}
        >
          {item.notion_page_title || "Untitled Note"}
        </a>
      </h4>
      <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
        <span title={item.last_edited}>Edited: {displayDate}</span>
        <span className="ml-2 pl-2 border-l border-gray-300 dark:border-gray-600">
          Relevance: {item.score !== undefined ? item.score.toFixed(2) : 'N/A'}
        </span>
      </div>
      {item.text_preview && (
        <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed text-ellipsis overflow-hidden max-h-24">
          {/* Simple preview, could be more sophisticated with truncation */}
          {item.text_preview}
        </p>
      )}
    </div>
  );
};

const SearchResultsDisplay: React.FC<SearchResultsDisplayProps> = ({ results }) => {
  if (!results || results.length === 0) {
    return <div className="p-3 text-sm text-gray-500 dark:text-gray-400">No relevant meeting notes found for your query.</div>;
  }

  return (
    <div className="mt-1 p-1 bg-gray-50 dark:bg-gray-700/50 rounded-md max-h-80 overflow-y-auto text-left">
      {/* Container for the results, ensuring text alignment is left for content within */}
      {results.map((item, index) => (
        // Using index in key for simplicity IF notion_page_id + preview start isn't guaranteed unique
        // (e.g. multiple chunks from same page with similar starts, though API currently returns 1 result per page)
        // Since API returns one result per page for now, notion_page_id is fine.
        <SearchResultItem key={item.notion_page_id || `search-result-${index}`} item={item} />
      ))}
    </div>
  );
};

export default SearchResultsDisplay;
