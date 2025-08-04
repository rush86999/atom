import React from 'react';
import { HybridSearchResultItem } from '../../../lib/dataTypes/SearchResultsTypes';
export interface SearchResultsDisplayProps {
    results: HybridSearchResultItem[];
}
declare const SearchResultsDisplay: React.FC<SearchResultsDisplayProps>;
export default SearchResultsDisplay;
