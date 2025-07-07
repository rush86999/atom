import React from 'react';
import { cn } from '@lib/Chat/utils'; // Assuming cn utility is available

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

const formatDate = (isoString: string): string => {
  if (!isoString) return "N/A";
  try {
    return new Date(isoString).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  } catch (e) {
    console.error("Error formatting date:", isoString, e);
    return "Invalid Date";
  }
};

const SearchResultItem: React.FC<{ item: FrontendMeetingSearchResult }> = ({ item }) => {
  const displayDate = formatDate(item.last_edited);

  return (
    <div className={cn(
      "mb-3 p-3 border rounded-lg shadow-sm transition-shadow",
      "bg-white dark:bg-gray-800",
      "border-gray-200 dark:border-gray-700",
      "hover:shadow-lg" // Slightly larger shadow on hover
    )}>
      <h4 className="text-base font-semibold mb-1 text-gray-800 dark:text-gray-100">
        <a
          href={item.notion_page_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sky-600 hover:text-sky-700 dark:text-sky-400 dark:hover:text-sky-300 hover:underline focus:outline-none focus:ring-1 focus:ring-sky-500 rounded"
          title={item.notion_page_title || "View Notion Page"}
        >
          {item.notion_page_title || "Untitled Note"}
        </a>
      </h4>
      <div className="text-xs text-gray-500 dark:text-gray-400 mb-2 space-x-2">
        <span title={item.last_edited}>Edited: {displayDate}</span>
        <span className="inline-block pl-2 border-l border-gray-300 dark:border-gray-600">
          Relevance: {item.score !== undefined ? item.score.toFixed(2) : 'N/A'}
        </span>
      </div>
      {item.text_preview && (
        <p className={cn(
          "text-sm leading-relaxed",
          "text-gray-700 dark:text-gray-300",
          "max-h-28 overflow-hidden text-ellipsis whitespace-pre-wrap" // Allow more lines, ensure pre-wrap
        )}>
          {item.text_preview}
        </p>
      )}
    </div>
  );
};

const SearchResultsDisplay: React.FC<SearchResultsDisplayProps> = ({ results }) => {
  if (!results || results.length === 0) {
    return <div className="p-3 text-sm text-gray-600 dark:text-gray-400 font-sans">No relevant meeting notes found.</div>;
  }

  return (
    <div className={cn(
      "mt-2 p-2 rounded-lg text-left font-sans",
      "bg-gray-50 dark:bg-gray-700/60", // Slightly more transparent dark bg
      "border border-gray-200 dark:border-gray-700", // Added border to main container
      "max-h-96 overflow-y-auto custom-scrollbar" // Ensure scrollbar is styled if custom-scrollbar class exists
                                                    // or use Tailwind scrollbar utilities if available in project config
    )}>
      {results.map((item) => (
        <SearchResultItem key={item.notion_page_id || item.notion_page_url} item={item} />
      ))}
    </div>
  );
};

export default SearchResultsDisplay;
