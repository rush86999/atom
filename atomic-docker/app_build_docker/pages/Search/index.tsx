import React, { useState, useCallback } from 'react';
import Baseof from '@layouts/Baseof';
import { Button } from '@components/chat/ui/button';
import { IconSearch } from '@components/chat/ui/icons';
import { HybridSearchFilters, HybridSearchResultItem } from '@lib/dataTypes/SearchResultsTypes'; // Adjust path
import { hybridSearch } from '../../../../src/skills/lanceDbStorageSkills'; // Adjust path
import DocTypeFilter from '@components/Search/DocTypeFilter';
import DateRangeFilter from '@components/Search/DateRangeFilter';
import MetadataFilter from '@components/Search/MetadataFilter';
import SearchResultsDisplay from '@components/chat/custom/SearchResultsDisplay';

const SearchPage: React.FC = () => {
  const [userId] = useState<string>("test-user-123"); // Placeholder
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [filters, setFilters] = useState<HybridSearchFilters>({});
  const [results, setResults] = useState<HybridSearchResultItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = useCallback(async () => {
    if (!searchTerm.trim()) {
      setError("Please enter a search term.");
      return;
    }
    setIsLoading(true);
    setError(null);
    setResults([]);

    try {
      const response = await hybridSearch(userId, searchTerm, {
        semanticLimit: 10,
        keywordLimit: 20,
        filters: filters,
      });

      if (response.ok && response.data) {
        setResults(response.data);
      } else {
        setError(response.error?.message || "An unknown error occurred during search.");
      }
    } catch (e: any) {
      setError(e.message || "An unexpected exception occurred.");
    } finally {
      setIsLoading(false);
    }
  }, [userId, searchTerm, filters]);

  const handleFilterChange = (update: Partial<HybridSearchFilters>) => {
    setFilters(prev => ({ ...prev, ...update }));
  };

  return (
    <Baseof title="Advanced Search">
      <div className="container mx-auto p-4 md:p-6 lg:p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl font-bold mb-2 text-gray-800 dark:text-gray-100">
            Advanced Search
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Search and filter your entire knowledge base using keywords and specific criteria.
          </p>

          {/* Search Bar */}
          <div className="flex items-center gap-2 mb-4">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search for keywords..."
              className="flex-grow text-base p-2 rounded-md border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 shadow-sm focus:border-sky-500 focus:ring-sky-500"
            />
            <Button onClick={handleSearch} disabled={isLoading}>
              <IconSearch className="mr-2 h-4 w-4" />
              {isLoading ? 'Searching...' : 'Search'}
            </Button>
          </div>

          {/* Filters Section */}
          <div className="space-y-4 mb-8">
            <DocTypeFilter
              selectedTypes={filters.doc_types || []}
              onChange={(doc_types) => handleFilterChange({ doc_types })}
            />
            <DateRangeFilter
              filters={filters}
              onChange={handleFilterChange}
            />
            <MetadataFilter
              properties={filters.metadata_properties || {}}
              onChange={(metadata_properties) => handleFilterChange({ metadata_properties })}
            />
          </div>

          {/* Results Section */}
          <div>
            <h2 className="text-2xl font-bold border-b pb-2 mb-4 dark:border-gray-600">Results</h2>
            {error && <p className="text-red-500">Error: {error}</p>}
            {isLoading && <p>Loading results...</p>}
            {!isLoading && !error && (
              <SearchResultsDisplay results={results} />
            )}
          </div>
        </div>
      </div>
    </Baseof>
  );
};

export default SearchPage;
