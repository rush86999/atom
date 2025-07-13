import React from 'react';
import { cn } from '@lib/Chat/utils';
// Assuming HybridSearchResultItem is now in a shared types file
// This path might need adjustment based on final project structure.
import { HybridSearchResultItem, HybridMatchSource } from '../../../lib/dataTypes/SearchResultsTypes';

export interface SearchResultsDisplayProps {
  results: HybridSearchResultItem[];
}

const formatDate = (isoString: string | null | undefined): string => {
  if (!isoString) return "N/A";
  try {
    return new Date(isoString).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric'
    });
  } catch (e) {
    console.error("Error formatting date:", isoString, e);
    return "Invalid Date";
  }
};

const MatchTypeTag: React.FC<{ type: HybridMatchSource }> = ({ type }) => {
  const baseClasses = "text-xs font-semibold px-2 py-0.5 rounded-full";
  const typeStyles = {
    semantic: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
    keyword: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
    hybrid: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
  };
  return (
    <span className={cn(baseClasses, typeStyles[type])}>
      {type.charAt(0).toUpperCase() + type.slice(1)}
    </span>
  );
};


const SearchResultItem: React.FC<{ item: HybridSearchResultItem }> = ({ item }) => {
  const displayDate = formatDate(item.last_modified_source || item.created_at_source || item.ingested_at);
  const dateTitle = item.last_modified_source || item.created_at_source || item.ingested_at || "No date available";

  return (
    <div className={cn(
      "mb-3 p-3 border rounded-lg shadow-sm transition-shadow",
      "bg-white dark:bg-gray-800",
      "border-gray-200 dark:border-gray-700",
      "hover:shadow-lg"
    )}>
      <div className="flex justify-between items-start mb-1">
        <h4 className="text-base font-semibold text-gray-800 dark:text-gray-100 flex-grow">
          <a
            href={item.source_uri || '#'}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sky-600 hover:text-sky-700 dark:text-sky-400 dark:hover:text-sky-300 hover:underline focus:outline-none focus:ring-1 focus:ring-sky-500 rounded"
            title={item.title || "View Source"}
          >
            {item.title || "Untitled Document"}
          </a>
        </h4>
        <div className="flex-shrink-0 ml-2">
          <MatchTypeTag type={item.match_type} />
        </div>
      </div>

      <div className="text-xs text-gray-500 dark:text-gray-400 mb-2 space-x-2 flex items-center flex-wrap">
        {item.doc_type &&
          <span className="font-medium bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded">
            {item.doc_type.replace(/_/g, ' ').toUpperCase()}
          </span>
        }
        <span title={dateTitle}>Date: {displayDate}</span>
        <span className="inline-block pl-2 border-l border-gray-300 dark:border-gray-600">
          Score: {item.score !== undefined && item.score !== null ? item.score.toFixed(4) : 'N/A'}
        </span>
      </div>

      {(item.snippet || item.extracted_text_preview) && (
        <p className={cn(
          "text-sm leading-relaxed",
          "text-gray-700 dark:text-gray-300",
          "max-h-28 overflow-hidden text-ellipsis whitespace-pre-wrap"
        )}>
          {item.snippet || item.extracted_text_preview}
        </p>
      )}
    </div>
  );
};

const SearchResultsDisplay: React.FC<SearchResultsDisplayProps> = ({ results }) => {
  if (!results || results.length === 0) {
    return <div className="p-3 text-sm text-gray-600 dark:text-gray-400 font-sans">No relevant documents found.</div>;
  }

  return (
    <div className={cn(
      "mt-2 p-2 rounded-lg text-left font-sans",
      "bg-gray-50 dark:bg-gray-700/60",
      "border border-gray-200 dark:border-gray-700",
      "max-h-96 overflow-y-auto custom-scrollbar"
    )}>
      {results.map((item) => (
        <SearchResultItem key={item.doc_id} item={item} />
      ))}
    </div>
  );
};

export default SearchResultsDisplay;
