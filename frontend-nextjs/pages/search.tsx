import React, { useState, useEffect, useCallback } from "react";
import { Search, ChevronDown, Star } from "lucide-react";
import { Card, CardContent } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Spinner } from "../components/ui/spinner";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Checkbox } from "../components/ui/checkbox";
import { Slider } from "../components/ui/slider";

interface SearchResult {
  id: string;
  title: string;
  content: string;
  doc_type: string;
  source_uri: string;
  similarity_score: number;
  keyword_score?: number;
  combined_score?: number;
  metadata: {
    created_at: string;
    author?: string;
    tags?: string[];
    participants?: string[];
    file_size?: number;
  };
}

interface SearchFilters {
  doc_type: string[];
  tags: string[];
  date_range: {
    start: string;
    end: string;
  };
  min_score: number;
}

const SearchPage: React.FC = () => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchType, setSearchType] = useState<
    "hybrid" | "semantic" | "keyword"
  >("hybrid");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [filters, setFilters] = useState<SearchFilters>({
    doc_type: [],
    tags: [],
    date_range: { start: "", end: "" },
    min_score: 0.5,
  });

  // Mock user ID - in real app this would come from auth context
  const userId = "user-123";

  // Popular search suggestions
  const popularSearches = [
    "project requirements",
    "meeting notes",
    "API documentation",
    "financial reports",
    "customer feedback",
  ];

  // Debounced search function
  const debouncedSearch = useCallback(
    (() => {
      let timeoutId: NodeJS.Timeout;
      return (searchQuery: string) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
          if (searchQuery.trim()) {
            handleSearch(searchQuery);
          }
        }, 300);
      };
    })(),
    [],
  );

  useEffect(() => {
    if (query.length > 2) {
      debouncedSearch(query);
      fetchSuggestions(query);
    } else {
      setResults([]);
      setSuggestions([]);
    }
  }, [query, debouncedSearch]);

  const fetchSuggestions = async (partialQuery: string) => {
    try {
      const response = await fetch(
        `/api/lancedb-search/suggestions?query=${encodeURIComponent(partialQuery)}&user_id=${userId}&limit=5`,
      );
      const data = await response.json();
      if (data.success) {
        setSuggestions(data.suggestions);
      }
    } catch (err) {
      console.error("Failed to fetch suggestions:", err);
    }
  };

  const handleSearch = async (searchQuery?: string) => {
    const searchTerm = searchQuery || query;
    if (!searchTerm.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/lancedb-search/hybrid", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: searchTerm,
          user_id: userId,
          filters: filters,
          limit: 20,
          search_type: searchType,
        }),
      });

      const data = await response.json();

      if (data.success) {
        setResults(data.results);
        setShowSuggestions(false);
      } else {
        setError(data.message || "Search failed");
      }
    } catch (err) {
      setError("Failed to perform search. Please try again.");
      console.error("Search error:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (filterName: string, value: any) => {
    setFilters((prev) => ({
      ...prev,
      [filterName]: value,
    }));
  };

  const handleDocTypeToggle = (type: string) => {
    setFilters((prev) => ({
      ...prev,
      doc_type: prev.doc_type.includes(type)
        ? prev.doc_type.filter((t) => t !== type)
        : [...prev.doc_type, type],
    }));
  };

  const handleSuggestionClick = (suggestion: string) => {
    setQuery(suggestion);
    setShowSuggestions(false);
    handleSearch(suggestion);
  };

  const formatScore = (score: number) => {
    return (score * 100).toFixed(0) + "%";
  };

  const getDocTypeColor = (docType: string) => {
    const colors: Record<string, string> = {
      document: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
      meeting: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
      note: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
      email: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
      pdf: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
    };
    return colors[docType] || "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300";
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="space-y-2">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            AI-Powered Search
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Search across all your documents, meetings, and notes with AI-powered
            hybrid search
          </p>
        </div>

        {/* Search Bar */}
        <div className="relative">
          <div className="flex gap-4">
            <Input
              data-testid="search-input"
              placeholder="Search across documents, meetings, notes..."
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setShowSuggestions(true);
              }}
              onFocus={() => setShowSuggestions(true)}
              className="text-lg shadow-md"

            />
            <select
              className="w-52 h-12 rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={searchType}
              onChange={(e) => setSearchType(e.target.value as any)}
            >
              <option value="hybrid">Hybrid Search</option>
              <option value="semantic">Semantic Search</option>
              <option value="keyword">Keyword Search</option>
            </select>
            <Button
              onClick={() => handleSearch()}
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-700 px-8"
              size="lg"
            >
              {loading ? (
                <>
                  <Spinner className="mr-2 h-4 w-4" />
                  Searching...
                </>
              ) : (
                <>
                  <Search className="mr-2 h-4 w-4" />
                  Search
                </>
              )}
            </Button>
          </div>

          {/* Search Suggestions */}
          {showSuggestions &&
            (suggestions.length > 0 || query.length === 0) && (
              <Card className="absolute top-full left-0 right-0 z-10 mt-2 shadow-xl">
                <CardContent className="pt-4">
                  <div className="space-y-2">
                    {query.length === 0 && (
                      <>
                        <p className="font-bold text-gray-600 dark:text-gray-400 text-sm">
                          Popular Searches
                        </p>
                        {popularSearches.map((search, index) => (
                          <p
                            key={index}
                            className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer text-gray-900 dark:text-gray-100"
                            onClick={() => handleSuggestionClick(search)}
                          >
                            {search}
                          </p>
                        ))}
                      </>
                    )}
                    {suggestions.map((suggestion, index) => (
                      <p
                        key={index}
                        className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer text-gray-900 dark:text-gray-100"
                        onClick={() => handleSuggestionClick(suggestion)}
                      >
                        {suggestion}
                      </p>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
        </div>

        {/* Filters */}
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Filters</h3>
              <div className="flex gap-6 flex-wrap">
                <div className="space-y-2">
                  <p className="font-medium text-gray-900 dark:text-gray-100">Document Type</p>
                  <div className="space-y-2">
                    {["document", "meeting", "note", "email", "pdf"].map((type) => (
                      <div key={type} className="flex items-center space-x-2">
                        <Checkbox
                          id={`type-${type}`}
                          checked={filters.doc_type.includes(type)}
                          onCheckedChange={() => handleDocTypeToggle(type)}
                        />
                        <label
                          htmlFor={`type-${type}`}
                          className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer capitalize text-gray-900 dark:text-gray-100"
                        >
                          {type}
                        </label>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="font-medium text-gray-900 dark:text-gray-100">Minimum Relevance</p>
                  <Slider
                    value={filters.min_score * 100}
                    onValueChange={(value) =>
                      handleFilterChange("min_score", value / 100)
                    }
                    min={0}
                    max={100}
                    step={5}
                    className="w-52"
                  />
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {formatScore(filters.min_score)} and above
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Error Display */}
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Results */}
        <div>
          {loading ? (
            <div className="flex justify-center items-center h-52">
              <Spinner className="h-12 w-12 text-blue-500" />
            </div>
          ) : results.length > 0 ? (
            <div className="space-y-4" data-testid="search-results">
              <div className="flex justify-between items-center">
                <p className="text-gray-600 dark:text-gray-400">
                  Found {results.length} results for &quot;{query}&quot;
                </p>
                <Button variant="outline" size="sm">
                  <ChevronDown className="mr-2 h-4 w-4" />
                  Export Results
                </Button>
              </div>

              {results.map((result) => (
                <Card
                  key={result.id}
                  className="shadow-md hover:shadow-lg transition-shadow"
                  data-testid="search-result-item"
                >
                  <CardContent className="pt-6">
                    <div className="space-y-3">
                      <div className="flex justify-between items-start">
                        <h3 className="text-lg font-semibold text-blue-700 dark:text-blue-400">
                          {result.title}
                        </h3>
                        <Badge className={getDocTypeColor(result.doc_type)}>
                          {result.doc_type}
                        </Badge>
                      </div>

                      <p className="text-gray-700 dark:text-gray-300 line-clamp-3">
                        {result.content}
                      </p>

                      <div className="flex gap-4 flex-wrap">
                        <div className="flex items-center space-x-1">
                          <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                          <p className="text-sm text-gray-600 dark:text-gray-400">
                            Relevance:{" "}
                            {formatScore(
                              result.combined_score || result.similarity_score,
                            )}
                          </p>
                        </div>

                        {result.metadata.author && (
                          <p className="text-sm text-gray-600 dark:text-gray-400">
                            Author: {result.metadata.author}
                          </p>
                        )}

                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          Created:{" "}
                          {new Date(
                            result.metadata.created_at,
                          ).toLocaleDateString()}
                        </p>
                      </div>

                      {result.metadata.tags &&
                        result.metadata.tags.length > 0 && (
                          <div className="flex gap-2 flex-wrap">
                            {result.metadata.tags.map((tag, index) => (
                              <Badge
                                key={index}
                                variant="secondary"
                                className="bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300"
                              >
                                {tag}
                              </Badge>
                            ))}
                          </div>
                        )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : query && !loading ? (
            <div className="flex justify-center items-center h-52">
              <p className="text-gray-500 text-lg">
                No results found for &quot;{query}&quot;
              </p>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};

export default SearchPage;
