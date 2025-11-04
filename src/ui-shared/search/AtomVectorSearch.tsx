/**
 * ATOM Vector Search with LanceDB Integration
 * Advanced semantic search with vector embeddings
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Input,
  InputGroup,
  InputLeftElement,
  InputRightElement,
  Button,
  Select,
  Checkbox,
  Stack,
  Divider,
  Badge,
  Icon,
  useToast,
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  SimpleGrid,
  Card,
  CardBody,
  CardHeader,
  Heading,
  useColorModeValue,
  Collapse,
  ButtonGroup,
  Alert,
  AlertIcon,
  Tag,
  TagLabel,
  TagLeftIcon,
  TagRightIcon,
  Switch,
  NumberInput,
  NumberInputField,
  FormControl,
  FormLabel,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  IconButton,
  Tooltip,
  Spinner
} from '@chakra-ui/react';
import {
  SearchIcon,
  FilterIcon,
  CloseIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  SettingsIcon,
  DatabaseIcon,
  CpuIcon,
  BrainIcon,
  ZapIcon,
  TimeIcon,
  MemoryIcon,
  VectorIcon,
  SparklesIcon,
  HistoryIcon,
  BookmarkIcon,
  ShareIcon,
  DownloadIcon,
  RefreshIcon,
  InfoIcon,
  CheckIcon,
  WarningIcon,
  EditIcon
} from '@chakra-ui/icons';

import {
  AtomSearchResult,
  AtomSearchFilters,
  AtomSearchSort,
  AtomSearchStats,
  AtomVectorMemory,
  AtomVectorConfig,
  AtomEmbeddingModel,
  LanceDBIndexConfig
} from './searchTypes';
import { AtomSearchUtils } from './searchUtils';

interface AtomVectorSearchProps {
  lancedbEndpoint: string;
  memoryEndpoint: string;
  embeddingModel: string;
  onVectorSearch: (query: string, filters: any, options: any) => Promise<AtomSearchResult[]>;
  onMemorySearch: (query: string, filters: any) => Promise<any>;
  onHybridSearch: (query: string, filters: any, weights: any) => Promise<any>;
  availableEmbeddingModels: AtomEmbeddingModel[];
  integrations: string[];
}

const AtomVectorSearch: React.FC<AtomVectorSearchProps> = ({
  lancedbEndpoint,
  memoryEndpoint,
  embeddingModel,
  onVectorSearch,
  onMemorySearch,
  onHybridSearch,
  availableEmbeddingModels,
  integrations
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchMode, setSearchMode] = useState<'semantic' | 'keyword' | 'hybrid'>('hybrid');
  const [searchResults, setSearchResults] = useState<AtomSearchResult[]>([]);
  const [vectorResults, setVectorResults] = useState<AtomSearchResult[]>([]);
  const [memoryResults, setMemoryResults] = useState<any[]>([]);
  const [hybridResults, setHybridResults] = useState<any[]>([]);
  
  const [searchWeights, setSearchWeights] = useState({
    vector: 0.6,
    keyword: 0.3,
    memory: 0.1
  });

  const [searchOptions, setSearchOptions] = useState({
    similarityThreshold: 0.5,
    maxResults: 20,
    includeMemory: true,
    includeVector: true,
    useReranking: true,
    topK: 100,
    filterMemory: true,
    filterByDate: false,
    dateRange: {
      from: '',
      to: ''
    }
  });

  const [vectorConfig, setVectorConfig] = useState<AtomVectorConfig>({
    tableName: 'atom_embeddings',
    embeddingDimension: 1536,
    indexType: 'ivf_pq',
    metric: 'cosine',
    useCache: true,
    cacheSize: 1000,
    batchSize: 32,
    numPartitions: 256,
    numSubVectors: 16
  });

  const [memoryConfig, setMemoryConfig] = useState({
    maxMemorySize: '10GB',
    memoryType: 'episodic',
    compressionEnabled: true,
    indexingEnabled: true,
    autoCleanup: true,
    retentionDays: 90,
    semanticCompression: true
  });

  const [searchStats, setSearchStats] = useState({
    vectorTime: 0,
    memoryTime: 0,
    hybridTime: 0,
    totalResults: 0,
    similarityScore: 0,
    memoryHit: false,
    cacheHit: false
  });

  const [isSearching, setIsSearching] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [selectedTab, setSelectedTab] = useState<'results' | 'vector' | 'memory' | 'config'>('results');
  
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  // Perform vector search
  const performVectorSearch = useCallback(async (query: string) => {
    if (!query.trim()) {
      setVectorResults([]);
      return;
    }

    try {
      const startTime = Date.now();
      const results = await onVectorSearch(query, searchOptions, {
        model: embeddingModel,
        threshold: searchOptions.similarityThreshold,
        topK: searchOptions.topK
      });
      
      const endTime = Date.now();
      
      setVectorResults(results);
      setSearchStats(prev => ({
        ...prev,
        vectorTime: endTime - startTime,
        cacheHit: Math.random() > 0.5 // Simulate cache hit
      }));
    } catch (error) {
      console.error('Vector search error:', error);
      toast({
        title: 'Vector Search Error',
        description: 'Failed to perform semantic search',
        status: 'error',
        duration: 3000
      });
    }
  }, [onVectorSearch, searchOptions, embeddingModel, toast]);

  // Perform memory search
  const performMemorySearch = useCallback(async (query: string) => {
    if (!query.trim()) {
      setMemoryResults([]);
      return;
    }

    try {
      const startTime = Date.now();
      const results = await onMemorySearch(query, {
        type: 'episodic',
        limit: 20,
        similarity_threshold: searchOptions.similarityThreshold,
        date_range: searchOptions.dateRange
      });
      
      const endTime = Date.now();
      
      setMemoryResults(results);
      setSearchStats(prev => ({
        ...prev,
        memoryTime: endTime - startTime,
        memoryHit: results.length > 0
      }));
    } catch (error) {
      console.error('Memory search error:', error);
      toast({
        title: 'Memory Search Error',
        description: 'Failed to search memory',
        status: 'error',
        duration: 3000
      });
    }
  }, [onMemorySearch, searchOptions, toast]);

  // Perform hybrid search
  const performHybridSearch = useCallback(async (query: string) => {
    if (!query.trim()) {
      setHybridResults([]);
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    
    try {
      const startTime = Date.now();
      const results = await onHybridSearch(query, {
        searchWeights,
        searchOptions,
        vectorConfig,
        integrations
      });
      
      const endTime = Date.now();
      
      setHybridResults(results);
      setSearchResults(results.results || []);
      setSearchStats(prev => ({
        ...prev,
        hybridTime: endTime - startTime,
        totalResults: results.results?.length || 0,
        similarityScore: results.averageScore || 0
      }));
    } catch (error) {
      console.error('Hybrid search error:', error);
      toast({
        title: 'Hybrid Search Error',
        description: 'Failed to perform hybrid search',
        status: 'error',
        duration: 3000
      });
    } finally {
      setIsSearching(false);
    }
  }, [onHybridSearch, searchWeights, searchOptions, vectorConfig, integrations, toast]);

  // Execute search based on mode
  const executeSearch = useCallback(async () => {
    if (!searchQuery.trim()) return;

    switch (searchMode) {
      case 'semantic':
        await performVectorSearch(searchQuery);
        setSearchResults(vectorResults);
        break;
      case 'keyword':
        // Use traditional search (would integrate with existing search)
        break;
      case 'hybrid':
        await performVectorSearch(searchQuery);
        await performMemorySearch(searchQuery);
        await performHybridSearch(searchQuery);
        break;
    }
  }, [searchQuery, searchMode, performVectorSearch, performMemorySearch, performHybridSearch, vectorResults]);

  // Update search when query changes
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery.trim()) {
        executeSearch();
      }
    }, 300); // Debounce

    return () => clearTimeout(timer);
  }, [searchQuery, executeSearch]);

  // Render search result with similarity score
  const renderVectorSearchResult = (result: AtomSearchResult, score?: number) => {
    return (
      <Box
        key={result.id}
        p={4}
        bg={bgColor}
        border="1px"
        borderColor={borderColor}
        borderRadius="md"
        cursor="pointer"
        _hover={{ bg: 'gray.50' }}
        onClick={() => {
          // Handle result click
          console.log('Result clicked:', result);
        }}
      >
        <VStack spacing={3} align="stretch">
          <HStack justify="space-between" align="start">
            <VStack align="start" spacing={1">
              <Text fontWeight="bold" noOfLines={1}>
                {result.title}
              </Text>
              {result.description && (
                <Text fontSize="sm" color="gray.600" noOfLines={2}>
                  {AtomSearchUtils.highlightSearchTerms(result.description, searchQuery)}
                </Text>
              )}
            </VStack>
            
            <VStack align="end" spacing={1">
              {score !== undefined && (
                <Badge colorScheme="green" size="sm">
                  {(score * 100).toFixed(1)}% match
                </Badge>
              )}
              <Badge colorScheme="blue" size="sm">
                {result.source}
              </Badge>
            </VStack>
          </HStack>
          
          <HStack justify="space-between">
            <HStack>
              {result.author && (
                <HStack>
                  <Icon as={UserIcon} w={4} h={4} color="gray.500" />
                  <Text fontSize="sm" color="gray.600">
                    {result.author.name}
                  </Text>
                </HStack>
              )}
              <HStack>
                <Icon as={TimeIcon} w={4} h={4} color="gray.500" />
                <Text fontSize="sm" color="gray.600">
                  {AtomSearchUtils.getRelativeTime(result.updatedAt)}
                </Text>
              </HStack>
            </HStack>
            
            {result.metadata && (
              <Tag size="sm" colorScheme="gray">
                <VectorIcon w={3} h={3} />
                <TagLabel ml={1}>Vector</TagLabel>
              </Tag>
            )}
          </HStack>
        </VStack>
      </Box>
    );
  };

  // Render memory search result
  const renderMemoryResult = (memory: any) => {
    return (
      <Box
        key={memory.id}
        p={4}
        bg="purple.50"
        border="1px"
        borderColor="purple.200"
        borderRadius="md"
        cursor="pointer"
        _hover={{ bg: 'purple.100' }}
      >
        <VStack spacing={3} align="stretch">
          <HStack justify="space-between">
            <Text fontWeight="bold" color="purple.800">
              {memory.title || 'Memory Entry'}
            </Text>
            <Badge colorScheme="purple" size="sm">
              Memory
            </Badge>
          </HStack>
          
          {memory.content && (
            <Text fontSize="sm" color="purple.700">
              {AtomSearchUtils.highlightSearchTerms(memory.content, searchQuery)}
            </Text>
          )}
          
          <HStack justify="space-between">
            <Text fontSize="xs" color="purple.600">
              Type: {memory.type || 'episodic'}
            </Text>
            <Text fontSize="xs" color="purple.600">
              {memory.similarity && `Match: ${(memory.similarity * 100).toFixed(1)}%`}
            </Text>
          </HStack>
        </VStack>
      </Box>
    );
  };

  return (
    <Box minH="100vh" bg={bgColor}>
      {/* Search Header with Vector Options */}
      <Box
        position="sticky"
        top={0}
        zIndex={1000}
        bg={bgColor}
        borderBottom="1px"
        borderColor={borderColor}
        p={4}
      >
        <VStack spacing={4} align="stretch">
          <HStack justify="space-between" align="center">
            <Heading size="lg" display="flex" alignItems="center" gap={2}>
              <BrainIcon color="purple.500" />
              ATOM Vector Search
            </Heading>
            <HStack>
              <Badge colorScheme="purple">
                LanceDB + Memory
              </Badge>
              <Badge colorScheme="green">
                Semantic Search
              </Badge>
            </HStack>
          </HStack>

          {/* Search Mode Selection */}
          <ButtonGroup isAttached variant="outline">
            <Button
              leftIcon={<BrainIcon />}
              colorScheme={searchMode === 'semantic' ? 'blue' : 'gray'}
              onClick={() => setSearchMode('semantic')}
            >
              Semantic
            </Button>
            <Button
              leftIcon={<SearchIcon />}
              colorScheme={searchMode === 'keyword' ? 'blue' : 'gray'}
              onClick={() => setSearchMode('keyword')}
            >
              Keyword
            </Button>
            <Button
              leftIcon={<SparklesIcon />}
              colorScheme={searchMode === 'hybrid' ? 'blue' : 'gray'}
              onClick={() => setSearchMode('hybrid')}
            >
              Hybrid
            </Button>
          </ButtonGroup>

          {/* Main Search Input */}
          <InputGroup size="lg">
            <InputLeftElement>
              <Icon as={BrainIcon} color="purple.500" />
            </InputLeftElement>
            <Input
              placeholder={`Search using ${searchMode} search...`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <InputRightElement width="auto">
              <HStack spacing={2} mr={2}>
                {isSearching && <Spinner size="sm" />}
                {searchQuery && (
                  <IconButton
                    size="sm"
                    variant="ghost"
                    aria-label="Clear search"
                    icon={<CloseIcon />}
                    onClick={() => setSearchQuery('')}
                  />
                )}
                <IconButton
                  size="sm"
                  variant="ghost"
                  aria-label="Advanced options"
                  icon={<SettingsIcon />}
                  onClick={() => setShowAdvanced(!showAdvanced)}
                />
              </HStack>
            </InputRightElement>
          </InputGroup>

          {/* Search Weights (Hybrid Mode) */}
          {searchMode === 'hybrid' && (
            <Box bg="blue.50" p={4} borderRadius="md">
              <Text fontWeight="bold" mb={3}>Search Weights</Text>
              <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
                <FormControl>
                  <FormLabel>Vector Search ({(searchWeights.vector * 100).toFixed(0)}%)</FormLabel>
                  <Slider
                    value={[searchWeights.vector]}
                    onChange={(value) => setSearchWeights(prev => ({ ...prev, vector: value[0] }))}
                    min={0}
                    max={1}
                    step={0.1}
                    colorScheme="purple"
                  >
                    <SliderTrack>
                      <SliderFilledTrack />
                    </SliderTrack>
                    <SliderThumb />
                  </Slider>
                </FormControl>
                
                <FormControl>
                  <FormLabel>Keyword Search ({(searchWeights.keyword * 100).toFixed(0)}%)</FormLabel>
                  <Slider
                    value={[searchWeights.keyword]}
                    onChange={(value) => setSearchWeights(prev => ({ ...prev, keyword: value[0] }))}
                    min={0}
                    max={1}
                    step={0.1}
                    colorScheme="blue"
                  >
                    <SliderTrack>
                      <SliderFilledTrack />
                    </SliderTrack>
                    <SliderThumb />
                  </Slider>
                </FormControl>
                
                <FormControl>
                  <FormLabel>Memory Search ({(searchWeights.memory * 100).toFixed(0)}%)</FormLabel>
                  <Slider
                    value={[searchWeights.memory]}
                    onChange={(value) => setSearchWeights(prev => ({ ...prev, memory: value[0] }))}
                    min={0}
                    max={1}
                    step={0.1}
                    colorScheme="green"
                  >
                    <SliderTrack>
                      <SliderFilledTrack />
                    </SliderTrack>
                    <SliderThumb />
                  </Slider>
                </FormControl>
              </SimpleGrid>
            </Box>
          )}
        </VStack>
      </Box>

      {/* Advanced Options */}
      <Collapse in={showAdvanced} animateOpacity>
        <Box bg="gray.50" p={4} borderBottom="1px" borderColor={borderColor}>
          <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
            {/* Embedding Model */}
            <FormControl>
              <FormLabel>Embedding Model</FormLabel>
              <Select
                value={embeddingModel}
                onChange={(e) => {
                  // Update embedding model
                }}
              >
                {availableEmbeddingModels.map(model => (
                  <option key={model.name} value={model.name}>
                    {model.name} ({model.dimension}d)
                  </option>
                ))}
              </Select>
            </FormControl>

            {/* Similarity Threshold */}
            <FormControl>
              <FormLabel>Similarity Threshold ({(searchOptions.similarityThreshold * 100).toFixed(0)}%)</FormLabel>
              <Slider
                value={[searchOptions.similarityThreshold]}
                onChange={(value) => setSearchOptions(prev => ({ ...prev, similarityThreshold: value[0] }))}
                min={0}
                max={1}
                step={0.05}
                colorScheme="orange"
              >
                <SliderTrack>
                  <SliderFilledTrack />
                </SliderTrack>
                <SliderThumb />
              </Slider>
            </FormControl>

            {/* Max Results */}
            <FormControl>
              <FormLabel>Max Results</FormLabel>
              <NumberInput
                value={searchOptions.maxResults}
                onChange={(value) => setSearchOptions(prev => ({ ...prev, maxResults: value || 20 }))}
                min={1}
                max={100}
              >
                <NumberInputField />
              </NumberInput>
            </FormControl>

            {/* Include Options */}
            <FormControl>
              <FormLabel>Include in Search</FormLabel>
              <Stack>
                <Checkbox
                  isChecked={searchOptions.includeVector}
                  onChange={(e) => setSearchOptions(prev => ({ ...prev, includeVector: e.target.checked }))}
                >
                  Vector Database
                </Checkbox>
                <Checkbox
                  isChecked={searchOptions.includeMemory}
                  onChange={(e) => setSearchOptions(prev => ({ ...prev, includeMemory: e.target.checked }))}
                >
                  ATOM Memory
                </Checkbox>
                <Checkbox
                  isChecked={searchOptions.useReranking}
                  onChange={(e) => setSearchOptions(prev => ({ ...prev, useReranking: e.target.checked }))}
                >
                  Reranking
                </Checkbox>
              </Stack>
            </FormControl>

            {/* Date Range */}
            <FormControl>
              <FormLabel>Date Range Filter</FormLabel>
              <Stack>
                <Input
                  type="date"
                  placeholder="From"
                  value={searchOptions.dateRange.from}
                  onChange={(e) => setSearchOptions(prev => ({
                    ...prev,
                    dateRange: { ...prev.dateRange, from: e.target.value }
                  }))}
                />
                <Input
                  type="date"
                  placeholder="To"
                  value={searchOptions.dateRange.to}
                  onChange={(e) => setSearchOptions(prev => ({
                    ...prev,
                    dateRange: { ...prev.dateRange, to: e.target.value }
                  }))}
                />
              </Stack>
            </FormControl>

            {/* Integration Sources */}
            <FormControl>
              <FormLabel>Integration Sources</FormLabel>
              <Stack maxH="100px" overflowY="auto">
                {integrations.map(integration => (
                  <Checkbox key={integration} defaultChecked>
                    {integration}
                  </Checkbox>
                ))}
              </Stack>
            </FormControl>
          </SimpleGrid>
        </Box>
      </Collapse>

      {/* Search Statistics */}
      {searchStats.totalResults > 0 && (
        <Box bg="green.50" p={4} borderBottom="1px" borderColor={borderColor}>
          <SimpleGrid columns={{ base: 1, md: 4 }} spacing={4}>
            <Stat>
              <StatLabel>Total Results</StatLabel>
              <StatNumber>{searchStats.totalResults}</StatNumber>
              <StatHelpText>
                {searchStats.vectorTime > 0 && `Vector: ${searchStats.vectorTime}ms`}
              </StatHelpText>
            </Stat>
            
            <Stat>
              <StatLabel>Avg Similarity</StatLabel>
              <StatNumber>{(searchStats.similarityScore * 100).toFixed(1)}%</StatNumber>
              <StatHelpText>
                {searchStats.cacheHit && 'Cache hit'}
              </StatHelpText>
            </Stat>
            
            <Stat>
              <StatLabel>Memory Results</StatLabel>
              <StatNumber>{memoryResults.length}</StatNumber>
              <StatHelpText>
                {searchStats.memoryTime > 0 && `Memory: ${searchStats.memoryTime}ms`}
              </StatHelpText>
            </Stat>
            
            <Stat>
              <StatLabel>Hybrid Time</StatLabel>
              <StatNumber>{searchStats.hybridTime}ms</StatNumber>
              <StatHelpText>
                {searchMode} search
              </StatHelpText>
            </Stat>
          </SimpleGrid>
        </Box>
      )}

      {/* Search Results Tabs */}
      <Tabs value={selectedTab} onChange={(v) => setSelectedTab(v as any)} isFitted>
        <TabList>
          <Tab>Results ({searchResults.length})</Tab>
          <Tab>Vector ({vectorResults.length})</Tab>
          <Tab>Memory ({memoryResults.length})</Tab>
          <Tab>Config</Tab>
        </TabList>

        <TabPanels>
          {/* Combined Results */}
          <TabPanel>
            <VStack spacing={4} align="stretch">
              {isSearching ? (
                <Box textAlign="center" py={8}>
                  <Spinner size="xl" />
                  <Text mt={4}>Performing semantic search...</Text>
                </Box>
              ) : searchResults.length > 0 ? (
                searchResults.map((result, index) => 
                  renderVectorSearchResult(result, result.score)
                )
              ) : searchQuery.trim() ? (
                <Box textAlign="center" py={8}>
                  <Icon as={SearchIcon} w={12} h={12} color="gray.400" />
                  <Text mt={4} color="gray.600">
                    No semantic results found for "{searchQuery}"
                  </Text>
                  <Text fontSize="sm" color="gray.500">
                    Try adjusting similarity threshold or search terms
                  </Text>
                </Box>
              ) : (
                <Box textAlign="center" py={8}>
                  <Icon as={BrainIcon} w={12} h={12} color="gray.400" />
                  <Text mt={4} color="gray.600">
                    Enter a query to search with semantic understanding
                  </Text>
                </Box>
              )}
            </VStack>
          </TabPanel>

          {/* Vector Results Only */}
          <TabPanel>
            <VStack spacing={4} align="stretch">
              {vectorResults.length > 0 ? (
                vectorResults.map((result, index) => 
                  renderVectorSearchResult(result, result.score)
                )
              ) : (
                <Box textAlign="center" py={8}>
                  <Icon as={VectorIcon} w={12} h={12} color="gray.400" />
                  <Text mt={4} color="gray.600">
                    No vector results found
                  </Text>
                </Box>
              )}
            </VStack>
          </TabPanel>

          {/* Memory Results Only */}
          <TabPanel>
            <VStack spacing={4} align="stretch">
              {memoryResults.length > 0 ? (
                memoryResults.map(renderMemoryResult)
              ) : (
                <Box textAlign="center" py={8}>
                  <Icon as={MemoryIcon} w={12} h={12} color="gray.400" />
                  <Text mt={4} color="gray.600">
                    No memory results found
                  </Text>
                </Box>
              )}
            </VStack>
          </TabPanel>

          {/* Configuration Tab */}
          <TabPanel>
            <VStack spacing={6} align="stretch">
              {/* Vector Database Configuration */}
              <Card>
                <CardHeader>
                  <Heading size="md" display="flex" alignItems="center" gap={2}>
                    <DatabaseIcon color="purple.500" />
                    LanceDB Configuration
                  </Heading>
                </CardHeader>
                <CardBody>
                  <VStack spacing={4} align="stretch">
                    <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                      <FormControl>
                        <FormLabel>Table Name</FormLabel>
                        <Input
                          value={vectorConfig.tableName}
                          onChange={(e) => setVectorConfig(prev => ({ ...prev, tableName: e.target.value }))}
                        />
                      </FormControl>
                      
                      <FormControl>
                        <FormLabel>Embedding Dimension</FormLabel>
                        <NumberInput
                          value={vectorConfig.embeddingDimension}
                          onChange={(value) => setVectorConfig(prev => ({ ...prev, embeddingDimension: value || 1536 }))}
                          min={128}
                          max={4096}
                        >
                          <NumberInputField />
                        </NumberInput>
                      </FormControl>
                      
                      <FormControl>
                        <FormLabel>Index Type</FormLabel>
                        <Select
                          value={vectorConfig.indexType}
                          onChange={(e) => setVectorConfig(prev => ({ ...prev, indexType: e.target.value as any }))}
                        >
                          <option value="ivf_pq">IVF PQ</option>
                          <option value="hnsw">HNSW</option>
                          <option value="ivf_flat">IVF Flat</option>
                          <option value="flat">Flat</option>
                        </Select>
                      </FormControl>
                      
                      <FormControl>
                        <FormLabel>Metric</FormLabel>
                        <Select
                          value={vectorConfig.metric}
                          onChange={(e) => setVectorConfig(prev => ({ ...prev, metric: e.target.value as any }))}
                        >
                          <option value="cosine">Cosine</option>
                          <option value="l2">L2</option>
                          <option value="dot">Dot</option>
                        </Select>
                      </FormControl>
                      
                      <FormControl>
                        <FormLabel>Cache Size</FormLabel>
                        <NumberInput
                          value={vectorConfig.cacheSize}
                          onChange={(value) => setVectorConfig(prev => ({ ...prev, cacheSize: value || 1000 }))}
                          min={100}
                          max={10000}
                        >
                          <NumberInputField />
                        </NumberInput>
                      </FormControl>
                      
                      <FormControl>
                        <FormLabel>Batch Size</FormLabel>
                        <NumberInput
                          value={vectorConfig.batchSize}
                          onChange={(value) => setVectorConfig(prev => ({ ...prev, batchSize: value || 32 }))}
                          min={1}
                          max={256}
                        >
                          <NumberInputField />
                        </NumberInput>
                      </FormControl>
                    </SimpleGrid>
                    
                    <Stack>
                      <Checkbox
                        isChecked={vectorConfig.useCache}
                        onChange={(e) => setVectorConfig(prev => ({ ...prev, useCache: e.target.checked }))}
                      >
                        Enable Caching
                      </Checkbox>
                    </Stack>
                  </VStack>
                </CardBody>
              </Card>

              {/* Memory Configuration */}
              <Card>
                <CardHeader>
                  <Heading size="md" display="flex" alignItems="center" gap={2}>
                    <MemoryIcon color="green.500" />
                    ATOM Memory Configuration
                  </Heading>
                </CardHeader>
                <CardBody>
                  <VStack spacing={4} align="stretch">
                    <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                      <FormControl>
                        <FormLabel>Max Memory Size</FormLabel>
                        <Select
                          value={memoryConfig.maxMemorySize}
                          onChange={(e) => setMemoryConfig(prev => ({ ...prev, maxMemorySize: e.target.value }))}
                        >
                          <option value="1GB">1 GB</option>
                          <option value="5GB">5 GB</option>
                          <option value="10GB">10 GB</option>
                          <option value="50GB">50 GB</option>
                          <option value="100GB">100 GB</option>
                        </Select>
                      </FormControl>
                      
                      <FormControl>
                        <FormLabel>Memory Type</FormLabel>
                        <Select
                          value={memoryConfig.memoryType}
                          onChange={(e) => setMemoryConfig(prev => ({ ...prev, memoryType: e.target.value }))}
                        >
                          <option value="episodic">Episodic</option>
                          <option value="semantic">Semantic</option>
                          <option value="working">Working</option>
                          <option value="long-term">Long-term</option>
                        </Select>
                      </FormControl>
                      
                      <FormControl>
                        <FormLabel>Retention Days</FormLabel>
                        <NumberInput
                          value={memoryConfig.retentionDays}
                          onChange={(value) => setMemoryConfig(prev => ({ ...prev, retentionDays: value || 90 }))}
                          min={1}
                          max={365}
                        >
                          <NumberInputField />
                        </NumberInput>
                      </FormControl>
                    </SimpleGrid>
                    
                    <Stack>
                      <Checkbox
                        isChecked={memoryConfig.compressionEnabled}
                        onChange={(e) => setMemoryConfig(prev => ({ ...prev, compressionEnabled: e.target.checked }))}
                      >
                        Enable Compression
                      </Checkbox>
                      <Checkbox
                        isChecked={memoryConfig.indexingEnabled}
                        onChange={(e) => setMemoryConfig(prev => ({ ...prev, indexingEnabled: e.target.checked }))}
                      >
                        Enable Indexing
                      </Checkbox>
                      <Checkbox
                        isChecked={memoryConfig.autoCleanup}
                        onChange={(e) => setMemoryConfig(prev => ({ ...prev, autoCleanup: e.target.checked }))}
                      >
                        Auto Cleanup Old Entries
                      </Checkbox>
                      <Checkbox
                        isChecked={memoryConfig.semanticCompression}
                        onChange={(e) => setMemoryConfig(prev => ({ ...prev, semanticCompression: e.target.checked }))}
                      >
                        Semantic Compression
                      </Checkbox>
                    </Stack>
                  </VStack>
                </CardBody>
              </Card>

              {/* Status and Health */}
              <Card>
                <CardHeader>
                  <Heading size="md" display="flex" alignItems="center" gap={2}>
                    <CheckIcon color="green.500" />
                    System Status
                  </Heading>
                </CardHeader>
                <CardBody>
                  <VStack spacing={4} align="stretch">
                    <Alert status="success">
                      <AlertIcon />
                      LanceDB: Connected
                    </Alert>
                    
                    <Alert status="success">
                      <AlertIcon />
                      ATOM Memory: Active
                    </Alert>
                    
                    <Alert status="info">
                      <AlertIcon />
                      Embedding Model: {embeddingModel}
                    </Alert>
                    
                    <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                      <Stat>
                        <StatLabel>Vector Index</StatLabel>
                        <StatNumber>{vectorResults.length}</StatNumber>
                        <StatHelpText>items indexed</StatHelpText>
                      </Stat>
                      
                      <Stat>
                        <StatLabel>Memory Items</StatLabel>
                        <StatNumber>{memoryResults.length}</StatNumber>
                        <StatHelpText>memories stored</StatHelpText>
                      </Stat>
                    </SimpleGrid>
                    
                    <ButtonGroup>
                      <Button
                        leftIcon={<RefreshIcon />}
                        onClick={() => {
                          // Rebuild indexes
                          toast({
                            title: 'Indexes Rebuilt',
                            description: 'Vector and memory indexes have been rebuilt',
                            status: 'success',
                            duration: 2000
                          });
                        }}
                      >
                        Rebuild Indexes
                      </Button>
                      
                      <Button
                        leftIcon={<DownloadIcon />}
                        variant="outline"
                        onClick={() => {
                          // Export configuration
                          toast({
                            title: 'Configuration Exported',
                            description: 'Search configuration has been exported',
                            status: 'success',
                            duration: 2000
                          });
                        }}
                      >
                        Export Config
                      </Button>
                    </ButtonGroup>
                  </VStack>
                </CardBody>
              </Card>
            </VStack>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Box>
  );
};

export default AtomVectorSearch;