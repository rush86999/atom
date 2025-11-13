import React, { useState, useEffect, useCallback } from "react";
import {
  Box,
  Input,
  Button,
  VStack,
  HStack,
  Text,
  Heading,
  Card,
  CardBody,
  Stack,
  Badge,
  Flex,
  Spinner,
  Alert,
  AlertIcon,
  Select,
  Checkbox,
  CheckboxGroup,
  RangeSlider,
  RangeSliderTrack,
  RangeSliderFilledTrack,
  RangeSliderThumb,
  Tooltip,
} from "@chakra-ui/react";
import { SearchIcon, ChevronDownIcon, StarIcon } from "@chakra-ui/icons";

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
        setResults(data.results || []);
      } else {
        setError(data.error || "Search failed");
        setResults([]);
      }
    } catch (err) {
      setError("Failed to perform search");
      console.error("Search error:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setQuery(suggestion);
    setShowSuggestions(false);
    handleSearch(suggestion);
  };

  const handleFilterChange = (key: keyof SearchFilters, value: any) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const formatScore = (score: number) => {
    return (score * 100).toFixed(1) + "%";
  };

  const getDocTypeColor = (docType: string) => {
    const colors: { [key: string]: string } = {
      document: "blue",
      meeting: "green",
      note: "purple",
      email: "orange",
      pdf: "red",
    };
    return colors[docType] || "gray";
  };

  return (
    <Box maxW="1200px" mx="auto" p={6}>
      {/* Header */}
      <VStack spacing={6} align="stretch">
        <Heading size="xl" color="blue.600">
          Advanced Search
        </Heading>
        <Text fontSize="lg" color="gray.600">
          Search across all your documents, meetings, and notes with AI-powered
          hybrid search
        </Text>

        {/* Search Bar */}
        <Box position="relative">
          <HStack spacing={4}>
            <Input
              placeholder="Search across documents, meetings, notes..."
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setShowSuggestions(true);
              }}
              onFocus={() => setShowSuggestions(true)}
              size="lg"
              borderRadius="lg"
              boxShadow="md"
            />
            <Select
              value={searchType}
              onChange={(e) => setSearchType(e.target.value as any)}
              width="200px"
            >
              <option value="hybrid">Hybrid Search</option>
              <option value="semantic">Semantic Search</option>
              <option value="keyword">Keyword Search</option>
            </Select>
            <Button
              leftIcon={<SearchIcon />}
              colorScheme="blue"
              size="lg"
              onClick={() => handleSearch()}
              isLoading={loading}
              loadingText="Searching..."
            >
              Search
            </Button>
          </HStack>

          {/* Search Suggestions */}
          {showSuggestions &&
            (suggestions.length > 0 || query.length === 0) && (
              <Card
                position="absolute"
                top="100%"
                left={0}
                right={0}
                zIndex={10}
                mt={2}
                boxShadow="xl"
              >
                <CardBody>
                  <VStack align="stretch" spacing={2}>
                    {query.length === 0 && (
                      <>
                        <Text fontWeight="bold" color="gray.600">
                          Popular Searches
                        </Text>
                        {popularSearches.map((search, index) => (
                          <Text
                            key={index}
                            p={2}
                            borderRadius="md"
                            _hover={{ bg: "gray.100", cursor: "pointer" }}
                            onClick={() => handleSuggestionClick(search)}
                          >
                            {search}
                          </Text>
                        ))}
                      </>
                    )}
                    {suggestions.map((suggestion, index) => (
                      <Text
                        key={index}
                        p={2}
                        borderRadius="md"
                        _hover={{ bg: "gray.100", cursor: "pointer" }}
                        onClick={() => handleSuggestionClick(suggestion)}
                      >
                        {suggestion}
                      </Text>
                    ))}
                  </VStack>
                </CardBody>
              </Card>
            )}
        </Box>

        {/* Filters */}
        <Card>
          <CardBody>
            <VStack align="stretch" spacing={4}>
              <Heading size="md">Filters</Heading>
              <HStack spacing={6} wrap="wrap">
                <VStack align="start" spacing={2}>
                  <Text fontWeight="medium">Document Type</Text>
                  <CheckboxGroup
                    value={filters.doc_type}
                    onChange={(value) => handleFilterChange("doc_type", value)}
                  >
                    <Stack spacing={2}>
                      {["document", "meeting", "note", "email", "pdf"].map(
                        (type) => (
                          <Checkbox key={type} value={type}>
                            {type.charAt(0).toUpperCase() + type.slice(1)}
                          </Checkbox>
                        ),
                      )}
                    </Stack>
                  </CheckboxGroup>
                </VStack>

                <VStack align="start" spacing={2}>
                  <Text fontWeight="medium">Minimum Relevance</Text>
                  <RangeSlider
                    value={[filters.min_score * 100]}
                    onChange={([value]) =>
                      handleFilterChange("min_score", value / 100)
                    }
                    min={0}
                    max={100}
                    step={5}
                    width="200px"
                  >
                    <RangeSliderTrack>
                      <RangeSliderFilledTrack />
                    </RangeSliderTrack>
                    <Tooltip label={`${(filters.min_score * 100).toFixed(0)}%`}>
                      <RangeSliderThumb boxSize={6} index={0} />
                    </Tooltip>
                  </RangeSlider>
                  <Text fontSize="sm" color="gray.600">
                    {formatScore(filters.min_score)} and above
                  </Text>
                </VStack>
              </HStack>
            </VStack>
          </CardBody>
        </Card>

        {/* Error Display */}
        {error && (
          <Alert status="error" borderRadius="lg">
            <AlertIcon />
            {error}
          </Alert>
        )}

        {/* Results */}
        <Box>
          {loading ? (
            <Flex justify="center" align="center" height="200px">
              <Spinner size="xl" color="blue.500" />
            </Flex>
          ) : results.length > 0 ? (
            <VStack spacing={4} align="stretch">
              <Flex justify="space-between" align="center">
                <Text color="gray.600">
                  Found {results.length} results for "{query}"
                </Text>
                <Button variant="outline" size="sm" leftIcon={<ChevronDownIcon />}>
                  Export Results
                </Button>
              </Flex>

              {results.map((result) => (
                <Card
                  key={result.id}
                  boxShadow="md"
                  _hover={{ boxShadow: "lg" }}
                  transition="all 0.2s"
                >
                  <CardBody>
                    <VStack align="start" spacing={3}>
                      <Flex justify="space-between" width="100%" align="start">
                        <Heading size="md" color="blue.700">
                          {result.title}
                        </Heading>
                        <Badge colorScheme={getDocTypeColor(result.doc_type)}>
                          {result.doc_type}
                        </Badge>
                      </Flex>

                      <Text color="gray.700" noOfLines={3}>
                        {result.content}
                      </Text>

                      <Flex gap={4} wrap="wrap">
                        <HStack>
                          <StarIcon color="yellow.500" />
                          <Text fontSize="sm" color="gray.600">
                            Relevance:{" "}
                            {formatScore(
                              result.combined_score || result.similarity_score,
                            )}
                          </Text>
                        </HStack>

                        {result.metadata.author && (
                          <Text fontSize="sm" color="gray.600">
                            Author: {result.metadata.author}
                          </Text>
                        )}

                        <Text fontSize="sm" color="gray.600">
                          Created:{" "}
                          {new Date(
                            result.metadata.created_at,
                          ).toLocaleDateString()}
                        </Text>
                      </Flex>

                      {result.metadata.tags &&
                        result.metadata.tags.length > 0 && (
                          <Flex gap={2} wrap="wrap">
                            {result.metadata.tags.map((tag, index) => (
                              <Badge
                                key={index}
                                variant="subtle"
                                colorScheme="gray"
                              >
                                {tag}
                              </Badge>
                            ))}
                          </Flex>
                        )}
                    </VStack>
                  </CardBody>
                </Card>
              ))}
            </VStack>
          ) : query && !loading ? (
            <Flex justify="center" align="center" height="200px">
              <Text color="gray.500" fontSize="lg">
                No results found for "{query}"
              </Text>
            </Flex>
          ) : null}
        </Box>
      </VStack>
    </Box>
  );
};

export default SearchPage;
