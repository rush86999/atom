/**
 * ATOM Vector Search with LanceDB and Memory - Hook
 * Custom React hook for vector search operations
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  AtomSearchResult,
  AtomSearchFilters,
  AtomVectorMemory,
  AtomVectorConfig,
  AtomEmbeddingModel,
  LanceDBIndexConfig
} from './searchTypes';
import { AtomSearchUtils } from './searchUtils';

interface VectorSearchOptions {
  embeddingModel: string;
  threshold: number;
  topK: number;
  includeMetadata: boolean;
  filterByDate: boolean;
  dateRange: {
    from: string;
    to: string;
  };
}

interface MemorySearchOptions {
  type: 'episodic' | 'semantic' | 'working' | 'long-term';
  limit: number;
  similarity_threshold: number;
  date_range: {
    from: string;
    to: string;
  };
  includeContext: boolean;
}

interface HybridSearchOptions {
  vector: {
    weight: number;
    options: VectorSearchOptions;
  };
  keyword: {
    weight: number;
    filters: AtomSearchFilters;
  };
  memory: {
    weight: number;
    options: MemorySearchOptions;
  };
  reranking: {
    enabled: boolean;
    method: 'cross-encoder' | 'rrf' | 'reciprocal';
    topK: number;
  };
}

interface UseVectorSearchConfig {
  lancedbEndpoint: string;
  memoryEndpoint: string;
  embeddingApiEndpoint: string;
  defaultEmbeddingModel: string;
  availableEmbeddingModels: AtomEmbeddingModel[];
  defaultVectorConfig: AtomVectorConfig;
  cacheEnabled: boolean;
  cacheTimeout: number;
  enablePersistence: boolean;
  enableAnalytics: boolean;
}

interface UseVectorSearchParams {
  query: string;
  filters: AtomSearchFilters;
  mode: 'semantic' | 'keyword' | 'hybrid';
  options: {
    vector?: Partial<VectorSearchOptions>;
    memory?: Partial<MemorySearchOptions>;
    hybrid?: Partial<HybridSearchOptions>;
  };
}

interface UseVectorSearchResult {
  // Results
  vectorResults: AtomSearchResult[];
  memoryResults: any[];
  hybridResults: AtomSearchResult[];
  keywordResults: AtomSearchResult[];
  combinedResults: AtomSearchResult[];
  
  // Search state
  isSearching: boolean;
  isEmbedding: boolean;
  isVectorSearching: boolean;
  isMemorySearching: boolean;
  isHybridSearching: boolean;
  
  // Configuration
  searchConfig: UseVectorSearchConfig;
  currentEmbeddingModel: string;
  vectorConfig: AtomVectorConfig;
  
  // Statistics
  searchStats: {
    vectorTime: number;
    memoryTime: number;
    hybridTime: number;
    keywordTime: number;
    embeddingTime: number;
    totalResults: number;
    averageSimilarity: number;
    cacheHit: boolean;
    errorCount: number;
  };
  
  // Error handling
  error: string | null;
  lastError: Error | null;
  
  // Methods
  search: (params: UseVectorSearchParams) => Promise<void>;
  vectorSearch: (query: string, options?: Partial<VectorSearchOptions>) => Promise<AtomSearchResult[]>;
  memorySearch: (query: string, options?: Partial<MemorySearchOptions>) => Promise<any[]>;
  hybridSearch: (query: string, options?: Partial<HybridSearchOptions>) => Promise<any>;
  keywordSearch: (query: string, filters?: AtomSearchFilters) => Promise<AtomSearchResult[]>;
  
  // Configuration methods
  setEmbeddingModel: (model: string) => void;
  updateVectorConfig: (config: Partial<AtomVectorConfig>) => void;
  updateSearchConfig: (config: Partial<UseVectorSearchConfig>) => void;
  
  // Cache methods
  clearCache: () => void;
  warmupCache: (queries: string[]) => Promise<void>;
  
  // Analytics methods
  getSearchAnalytics: () => any;
  exportSearchHistory: () => any;
}

export const useVectorSearch = (initialConfig: UseVectorSearchConfig): UseVectorSearchResult => {
  // State management
  const [searchConfig, setSearchConfig] = useState<UseVectorSearchConfig>(initialConfig);
  const [vectorConfig, setVectorConfig] = useState<AtomVectorConfig>(initialConfig.defaultVectorConfig);
  const [currentEmbeddingModel, setCurrentEmbeddingModel] = useState<string>(initialConfig.defaultEmbeddingModel);
  
  // Results state
  const [vectorResults, setVectorResults] = useState<AtomSearchResult[]>([]);
  const [memoryResults, setMemoryResults] = useState<any[]>([]);
  const [hybridResults, setHybridResults] = useState<any[]>([]);
  const [keywordResults, setKeywordResults] = useState<AtomSearchResult[]>([]);
  const [combinedResults, setCombinedResults] = useState<AtomSearchResult[]>([]);
  
  // Search state
  const [isSearching, setIsSearching] = useState(false);
  const [isEmbedding, setIsEmbedding] = useState(false);
  const [isVectorSearching, setIsVectorSearching] = useState(false);
  const [isMemorySearching, setIsMemorySearching] = useState(false);
  const [isHybridSearching, setIsHybridSearching] = useState(false);
  
  // Error state
  const [error, setError] = useState<string | null>(null);
  const [lastError, setLastError] = useState<Error | null>(null);
  
  // Statistics
  const [searchStats, setSearchStats] = useState({
    vectorTime: 0,
    memoryTime: 0,
    hybridTime: 0,
    keywordTime: 0,
    embeddingTime: 0,
    totalResults: 0,
    averageSimilarity: 0,
    cacheHit: false,
    errorCount: 0
  });
  
  // Cache
  const cache = useRef<Map<string, any>>(new Map());
  const searchHistory = useRef<Array<any>>([]);
  
  // Generate embedding for search query
  const generateEmbedding = useCallback(async (
    query: string,
    model: string
  ): Promise<number[]> => {
    setIsEmbedding(true);
    const startTime = Date.now();
    
    try {
      // Check cache first
      const cacheKey = `embedding:${model}:${query}`;
      if (cache.current.has(cacheKey)) {
        const cached = cache.current.get(cacheKey);
        setSearchStats(prev => ({ ...prev, cacheHit: true }));
        return cached;
      }
      
      // Call embedding API
      const response = await fetch(searchConfig.embeddingApiEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: query,
          model: model,
          normalize: true
        })
      });
      
      if (!response.ok) {
        throw new Error(`Embedding API error: ${response.statusText}`);
      }
      
      const data = await response.json();
      const embedding = data.embedding;
      
      // Cache the embedding
      if (searchConfig.cacheEnabled) {
        cache.current.set(cacheKey, embedding);
        
        // Cleanup old cache entries
        setTimeout(() => {
          cache.current.delete(cacheKey);
        }, searchConfig.cacheTimeout);
      }
      
      const embeddingTime = Date.now() - startTime;
      setSearchStats(prev => ({ ...prev, embeddingTime }));
      
      return embedding;
    } catch (error) {
      console.error('Embedding generation error:', error);
      throw new Error(`Failed to generate embedding: ${error}`);
    } finally {
      setIsEmbedding(false);
    }
  }, [searchConfig]);
  
  // Perform vector search with LanceDB
  const vectorSearch = useCallback(async (
    query: string,
    options: Partial<VectorSearchOptions> = {}
  ): Promise<AtomSearchResult[]> => {
    setIsVectorSearching(true);
    const startTime = Date.now();
    
    try {
      const searchOptions: VectorSearchOptions = {
        embeddingModel: currentEmbeddingModel,
        threshold: 0.5,
        topK: 20,
        includeMetadata: true,
        filterByDate: false,
        dateRange: { from: '', to: '' },
        ...options
      };
      
      // Generate embedding
      const embedding = await generateEmbedding(query, searchOptions.embeddingModel);
      
      // Query LanceDB
      const searchPayload = {
        table_name: vectorConfig.tableName,
        query_vector: embedding,
        limit: searchOptions.topK,
        nprobes: 10,
        filter: searchOptions.filterByDate ? {
          date_range: searchOptions.dateRange
        } : undefined,
        include_metadata: searchOptions.includeMetadata,
        return_type: 'search'
      };
      
      const response = await fetch(`${searchConfig.lancedbEndpoint}/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(searchPayload)
      });
      
      if (!response.ok) {
        throw new Error(`LanceDB search error: ${response.statusText}`);
      }
      
      const data = await response.json();
      const results = data.results || [];
      
      // Convert to AtomSearchResult format
      const atomResults: AtomSearchResult[] = results.map((item: any) => ({
        id: item.id,
        type: item.metadata.type || 'document',
        title: item.metadata.title,
        description: item.metadata.description,
        content: item.metadata.content,
        source: item.metadata.source || 'lancedb',
        sourceIcon: () => '🔍',
        sourceColor: 'purple.500',
        url: item.metadata.url,
        createdAt: item.metadata.created_at,
        updatedAt: item.metadata.updated_at,
        author: item.metadata.author,
        metadata: {
          ...item.metadata,
          similarity_score: item._distance || 0,
          embedding_model: searchOptions.embeddingModel
        },
        score: 1 - (item._distance || 0),
        highlights: [query]
      }));
      
      // Filter by threshold
      const filteredResults = atomResults.filter(result => 
        result.score >= searchOptions.threshold
      );
      
      const vectorTime = Date.now() - startTime;
      setSearchStats(prev => ({
        ...prev,
        vectorTime,
        totalResults: filteredResults.length,
        averageSimilarity: filteredResults.reduce((sum, r) => sum + (r.score || 0), 0) / filteredResults.length || 0
      }));
      
      setVectorResults(filteredResults);
      return filteredResults;
      
    } catch (error) {
      console.error('Vector search error:', error);
      setError(`Vector search failed: ${error}`);
      setSearchStats(prev => ({ ...prev, errorCount: prev.errorCount + 1 }));
      return [];
    } finally {
      setIsVectorSearching(false);
    }
  }, [currentEmbeddingModel, vectorConfig, searchConfig, generateEmbedding]);
  
  // Perform memory search
  const memorySearch = useCallback(async (
    query: string,
    options: Partial<MemorySearchOptions> = {}
  ): Promise<any[]> => {
    setIsMemorySearching(true);
    const startTime = Date.now();
    
    try {
      const searchOptions: MemorySearchOptions = {
        type: 'episodic',
        limit: 20,
        similarity_threshold: 0.5,
        date_range: { from: '', to: '' },
        includeContext: true,
        ...options
      };
      
      // Generate embedding for memory search
      const embedding = await generateEmbedding(query, currentEmbeddingModel);
      
      // Query ATOM memory
      const memoryPayload = {
        query: query,
        query_embedding: embedding,
        memory_type: searchOptions.type,
        limit: searchOptions.limit,
        similarity_threshold: searchOptions.similarity_threshold,
        date_range: searchOptions.date_range,
        include_context: searchOptions.includeContext,
        return_format: 'detailed'
      };
      
      const response = await fetch(`${searchConfig.memoryEndpoint}/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(memoryPayload)
      });
      
      if (!response.ok) {
        throw new Error(`Memory search error: ${response.statusText}`);
      }
      
      const data = await response.json();
      const results = data.results || [];
      
      // Process memory results
      const processedResults = results.map((item: any) => ({
        id: item.id,
        type: 'memory',
        title: item.title || 'Memory Entry',
        content: item.content,
        source: 'atom_memory',
        sourceIcon: () => '🧠',
        sourceColor: 'green.500',
        createdAt: item.created_at,
        updatedAt: item.updated_at,
        metadata: {
          memory_type: item.memory_type,
          context: item.context,
          relevance_score: item.relevance_score,
          tags: item.tags
        },
        score: item.relevance_score || 0,
        highlights: [query]
      }));
      
      const memoryTime = Date.now() - startTime;
      setSearchStats(prev => ({ ...prev, memoryTime }));
      
      setMemoryResults(processedResults);
      return processedResults;
      
    } catch (error) {
      console.error('Memory search error:', error);
      setError(`Memory search failed: ${error}`);
      setSearchStats(prev => ({ ...prev, errorCount: prev.errorCount + 1 }));
      return [];
    } finally {
      setIsMemorySearching(false);
    }
  }, [currentEmbeddingModel, searchConfig, generateEmbedding]);
  
  // Perform hybrid search
  const hybridSearch = useCallback(async (
    query: string,
    options: Partial<HybridSearchOptions> = {}
  ): Promise<any> => {
    setIsHybridSearching(true);
    const startTime = Date.now();
    
    try {
      const searchOptions: HybridSearchOptions = {
        vector: {
          weight: 0.6,
          options: {
            embeddingModel: currentEmbeddingModel,
            threshold: 0.5,
            topK: 100,
            includeMetadata: true,
            filterByDate: false,
            dateRange: { from: '', to: '' }
          }
        },
        keyword: {
          weight: 0.3,
          filters: {}
        },
        memory: {
          weight: 0.1,
          options: {
            type: 'episodic',
            limit: 20,
            similarity_threshold: 0.5,
            date_range: { from: '', to: '' },
            includeContext: true
          }
        },
        reranking: {
          enabled: true,
          method: 'cross-encoder',
          topK: 20
        },
        ...options
      };
      
      // Perform parallel searches
      const [vectorRes, memoryRes, keywordRes] = await Promise.allSettled([
        vectorSearch(query, searchOptions.vector.options),
        memorySearch(query, searchOptions.memory.options),
        // keyword search would go here
        Promise.resolve([])
      ]);
      
      const vectorResults = vectorRes.status === 'fulfilled' ? vectorRes.value : [];
      const memoryResults = memoryRes.status === 'fulfilled' ? memoryRes.value : [];
      const keywordResults = keywordRes.status === 'fulfilled' ? keywordRes.value : [];
      
      // Combine results using weighted scores
      const combinedResults: any[] = [];
      
      // Add vector results
      vectorResults.forEach((result, index) => {
        combinedResults.push({
          ...result,
          score: result.score * searchOptions.vector.weight,
          source_type: 'vector',
          source_rank: index
        });
      });
      
      // Add memory results
      memoryResults.forEach((result, index) => {
        const memoryResult = {
          id: `memory_${result.id}`,
          type: 'memory',
          title: result.title,
          content: result.content,
          source: 'atom_memory',
          sourceIcon: () => '🧠',
          sourceColor: 'green.500',
          createdAt: result.createdAt,
          updatedAt: result.updatedAt,
          metadata: result.metadata,
          score: result.score * searchOptions.memory.weight,
          source_type: 'memory',
          source_rank: index
        };
        combinedResults.push(memoryResult);
      });
      
      // Add keyword results
      keywordResults.forEach((result, index) => {
        combinedResults.push({
          ...result,
          score: (result.score || 0) * searchOptions.keyword.weight,
          source_type: 'keyword',
          source_rank: index
        });
      });
      
      // Reranking if enabled
      if (searchOptions.reranking.enabled) {
        // Apply cross-encoder reranking
        const rerankedResults = await applyCrossEncoderReranking(
          query,
          combinedResults,
          searchOptions.reranking.topK
        );
        
        setHybridResults({
          results: rerankedResults,
          vector_count: vectorResults.length,
          memory_count: memoryResults.length,
          keyword_count: keywordResults.length,
          total_count: rerankedResults.length,
          reranking_method: searchOptions.reranking.method,
          weights: {
            vector: searchOptions.vector.weight,
            keyword: searchOptions.keyword.weight,
            memory: searchOptions.memory.weight
          }
        });
        
        setCombinedResults(rerankedResults);
      } else {
        // Simple score-based ranking
        const rankedResults = combinedResults
          .sort((a, b) => b.score - a.score)
          .slice(0, searchOptions.reranking.topK);
        
        setHybridResults({
          results: rankedResults,
          vector_count: vectorResults.length,
          memory_count: memoryResults.length,
          keyword_count: keywordResults.length,
          total_count: rankedResults.length,
          reranking_method: 'score',
          weights: searchOptions.vector
        });
        
        setCombinedResults(rankedResults);
      }
      
      const hybridTime = Date.now() - startTime;
      setSearchStats(prev => ({ ...prev, hybridTime }));
      
      return hybridResults.current;
      
    } catch (error) {
      console.error('Hybrid search error:', error);
      setError(`Hybrid search failed: ${error}`);
      setSearchStats(prev => ({ ...prev, errorCount: prev.errorCount + 1 }));
      return null;
    } finally {
      setIsHybridSearching(false);
    }
  }, [vectorSearch, memorySearch, currentEmbeddingModel]);
  
  // Apply cross-encoder reranking
  const applyCrossEncoderReranking = useCallback(async (
    query: string,
    results: any[],
    topK: number
  ): Promise<AtomSearchResult[]> => {
    try {
      const response = await fetch(`${searchConfig.embeddingApiEndpoint}/rerank`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query,
          passages: results.map(r => ({
            id: r.id,
            text: r.title + (r.content ? ' ' + r.content : ''),
            meta: r.metadata
          })),
          model: 'cross-encoder',
          top_k: topK
        })
      });
      
      if (!response.ok) {
        throw new Error(`Reranking error: ${response.statusText}`);
      }
      
      const data = await response.json();
      const rerankedResults = data.results || [];
      
      // Map back to AtomSearchResult format with updated scores
      const updatedResults = rerankedResults.map((item: any) => {
        const originalResult = results.find(r => r.id === item.id);
        return {
          ...originalResult,
          score: item.relevance_score,
          metadata: {
            ...originalResult.metadata,
            rerank_score: item.relevance_score
          }
        };
      });
      
      return updatedResults as AtomSearchResult[];
    } catch (error) {
      console.error('Reranking error:', error);
      // Fallback to original order
      return results as AtomSearchResult[];
    }
  }, [searchConfig]);
  
  // Main search function
  const search = useCallback(async (params: UseVectorSearchParams): Promise<void> => {
    setIsSearching(true);
    setError(null);
    
    try {
      const { query, mode, filters, options } = params;
      
      switch (mode) {
        case 'semantic':
          await vectorSearch(query, options.vector);
          setCombinedResults(vectorResults);
          break;
          
        case 'keyword':
          // Would implement keyword search here
          const keywordResults = await keywordSearch(query, filters);
          setCombinedResults(keywordResults);
          break;
          
        case 'hybrid':
        default:
          await hybridSearch(query, options.hybrid);
          break;
      }
      
      // Add to search history
      searchHistory.current.push({
        query,
        mode,
        timestamp: new Date().toISOString(),
        resultCount: combinedResults.length,
        filters,
        options
      });
      
    } catch (error) {
      console.error('Search error:', error);
      setError(`Search failed: ${error}`);
      setLastError(error instanceof Error ? error : new Error(String(error)));
    } finally {
      setIsSearching(false);
    }
  }, [vectorSearch, hybridSearch, vectorResults, combinedResults]);
  
  // Configuration methods
  const setEmbeddingModel = useCallback((model: string) => {
    setCurrentEmbeddingModel(model);
    // Clear cache when model changes
    if (searchConfig.cacheEnabled) {
      cache.current.clear();
    }
  }, [searchConfig]);
  
  const updateVectorConfig = useCallback((config: Partial<AtomVectorConfig>) => {
    setVectorConfig(prev => ({ ...prev, ...config }));
  }, []);
  
  const updateSearchConfig = useCallback((config: Partial<UseVectorSearchConfig>) => {
    setSearchConfig(prev => ({ ...prev, ...config }));
  }, []);
  
  // Cache methods
  const clearCache = useCallback(() => {
    cache.current.clear();
  }, []);
  
  const warmupCache = useCallback(async (queries: string[]): Promise<void> => {
    console.log('Warming up cache with', queries.length, 'queries');
    
    const promises = queries.map(async (query) => {
      try {
        await generateEmbedding(query, currentEmbeddingModel);
      } catch (error) {
        console.warn('Failed to warm up cache for query:', query, error);
      }
    });
    
    await Promise.all(promises);
    console.log('Cache warmup completed');
  }, [generateEmbedding, currentEmbeddingModel]);
  
  // Analytics methods
  const getSearchAnalytics = useCallback(() => {
    return {
      searchStats,
      searchHistory: searchHistory.current,
      cacheSize: cache.current.size,
      searchConfig,
      vectorConfig,
      currentEmbeddingModel
    };
  }, [searchStats, searchConfig, vectorConfig, currentEmbeddingModel]);
  
  const exportSearchHistory = useCallback(() => {
    return {
      history: searchHistory.current,
      stats: searchStats,
      config: searchConfig,
      exported_at: new Date().toISOString()
    };
  }, [searchHistory, searchStats, searchConfig]);
  
  // Initialize
  useEffect(() => {
    // Perform any necessary initialization
    console.log('Vector search hook initialized with config:', initialConfig);
  }, [initialConfig]);
  
  return {
    // Results
    vectorResults,
    memoryResults,
    hybridResults,
    keywordResults,
    combinedResults,
    
    // Search state
    isSearching,
    isEmbedding,
    isVectorSearching,
    isMemorySearching,
    isHybridSearching,
    
    // Configuration
    searchConfig,
    currentEmbeddingModel,
    vectorConfig,
    
    // Statistics
    searchStats,
    
    // Error handling
    error,
    lastError,
    
    // Methods
    search,
    vectorSearch,
    memorySearch,
    hybridSearch,
    keywordSearch,
    
    // Configuration methods
    setEmbeddingModel,
    updateVectorConfig,
    updateSearchConfig,
    
    // Cache methods
    clearCache,
    warmupCache,
    
    // Analytics methods
    getSearchAnalytics,
    exportSearchHistory
  };
};

export default useVectorSearch;