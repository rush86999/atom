/**
 * ATOM Search API Integration
 * Connects search UI with backend services
 */

import {
  AtomSearchResult,
  AtomSearchFilters,
  AtomSearchSort,
  AtomVectorConfig,
  AtomEmbeddingModel
} from './searchTypes';

// Search API client
export class AtomSearchAPI {
  private baseUrl: string;
  private apiKey: string;
  private platform: 'web' | 'desktop' | 'mobile';

  constructor(
    baseUrl: string = '/api/search',
    apiKey: string = '',
    platform: 'web' | 'desktop' | 'mobile' = 'web'
  ) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
    this.platform = platform;
  }

  // Traditional keyword search
  async search(
    query: string,
    filters: AtomSearchFilters,
    sort: AtomSearchSort,
    options: {
      offset?: number;
      limit?: number;
      highlight?: boolean;
      aggregations?: string[];
    } = {}
  ): Promise<{ results: AtomSearchResult[]; total: number; aggregations?: any }> {
    const response = await fetch(`${this.baseUrl}/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Platform': this.platform
      },
      body: JSON.stringify({
        query,
        filters,
        sort,
        options: {
          offset: options.offset || 0,
          limit: options.limit || 50,
          highlight: options.highlight !== false,
          aggregations: options.aggregations || ['sources', 'types', 'authors']
        }
      })
    });

    if (!response.ok) {
      throw new Error(`Search API error: ${response.statusText}`);
    }

    return response.json();
  }

  // Vector search (LanceDB)
  async vectorSearch(
    query: string,
    options: {
      model?: string;
      threshold?: number;
      topK?: number;
      filters?: any;
      includeMetadata?: boolean;
    } = {}
  ): Promise<AtomSearchResult[]> {
    const response = await fetch(`${this.baseUrl}/vector/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Platform': this.platform
      },
      body: JSON.stringify({
        query,
        options: {
          model: options.model || 'text-embedding-ada-002',
          threshold: options.threshold || 0.5,
          topK: options.topK || 50,
          filters: options.filters || {},
          includeMetadata: options.includeMetadata !== false
        }
      })
    });

    if (!response.ok) {
      throw new Error(`Vector search error: ${response.statusText}`);
    }

    const data = await response.json();
    return data.results || [];
  }

  // Memory search (ATOM memory)
  async memorySearch(
    query: string,
    options: {
      type?: 'episodic' | 'semantic' | 'working' | 'long-term';
      limit?: number;
      similarityThreshold?: number;
      dateRange?: { from: string; to: string };
      includeContext?: boolean;
    } = {}
  ): Promise<any[]> {
    const response = await fetch(`${this.baseUrl}/memory/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Platform': this.platform
      },
      body: JSON.stringify({
        query,
        options: {
          type: options.type || 'episodic',
          limit: options.limit || 20,
          similarity_threshold: options.similarityThreshold || 0.6,
          date_range: options.dateRange || {},
          include_context: options.includeContext !== false
        }
      })
    });

    if (!response.ok) {
      throw new Error(`Memory search error: ${response.statusText}`);
    }

    const data = await response.json();
    return data.results || [];
  }

  // Hybrid search (combines vector, memory, and keyword)
  async hybridSearch(
    query: string,
    options: {
      weights?: { vector: number; keyword: number; memory: number };
      vector?: any;
      memory?: any;
      keyword?: any;
      reranking?: { enabled: boolean; method: string; topK: number };
    } = {}
  ): Promise<any> {
    const response = await fetch(`${this.baseUrl}/hybrid/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Platform': this.platform
      },
      body: JSON.stringify({
        query,
        options: {
          weights: options.weights || { vector: 0.6, keyword: 0.3, memory: 0.1 },
          vector: options.vector || {},
          memory: options.memory || {},
          keyword: options.keyword || {},
          reranking: options.reranking || {
            enabled: true,
            method: 'cross-encoder',
            topK: 20
          }
        }
      })
    });

    if (!response.ok) {
      throw new Error(`Hybrid search error: ${response.statusText}`);
    }

    return response.json();
  }

  // Generate embeddings
  async generateEmbedding(
    text: string,
    model?: string
  ): Promise<number[]> {
    const response = await fetch(`${this.baseUrl}/embeddings/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Platform': this.platform
      },
      body: JSON.stringify({
        text,
        model: model || 'text-embedding-ada-002',
        normalize: true
      })
    });

    if (!response.ok) {
      throw new Error(`Embedding generation error: ${response.statusText}`);
    }

    const data = await response.json();
    return data.embedding;
  }

  // Rerank results with cross-encoder
  async rerank(
    query: string,
    passages: Array<{ id: string; text: string; meta?: any }>,
    model?: string
  ): Promise<Array<{ id: string; relevance_score: number }>> {
    const response = await fetch(`${this.baseUrl}/rerank`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Platform': this.platform
      },
      body: JSON.stringify({
        query,
        passages,
        model: model || 'cross-encoder/ms-marco-MiniLM-L-6-v2',
        top_k: passages.length
      })
    });

    if (!response.ok) {
      throw new Error(`Reranking error: ${response.statusText}`);
    }

    const data = await response.json();
    return data.results || [];
  }

  // Get search suggestions
  async getSuggestions(
    query: string,
    options: {
      limit?: number;
      includeHistory?: boolean;
      includePopular?: boolean;
    } = {}
  ): Promise<Array<{ text: string; type: string; count?: number }>> {
    const response = await fetch(`${this.baseUrl}/suggestions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Platform': this.platform
      },
      body: JSON.stringify({
        query,
        options: {
          limit: options.limit || 10,
          include_history: options.includeHistory !== false,
          include_popular: options.includePopular !== false
        }
      })
    });

    if (!response.ok) {
      throw new Error(`Suggestions error: ${response.statusText}`);
    }

    const data = await response.json();
    return data.suggestions || [];
  }

  // Get available embedding models
  async getEmbeddingModels(): Promise<AtomEmbeddingModel[]> {
    const response = await fetch(`${this.baseUrl}/embeddings/models`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Platform': this.platform
      }
    });

    if (!response.ok) {
      throw new Error(`Embedding models error: ${response.statusText}`);
    }

    return response.json();
  }

  // Get vector configuration
  async getVectorConfig(): Promise<AtomVectorConfig> {
    const response = await fetch(`${this.baseUrl}/vector/config`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Platform': this.platform
      }
    });

    if (!response.ok) {
      throw new Error(`Vector config error: ${response.statusText}`);
    }

    return response.json();
  }

  // Update vector configuration
  async updateVectorConfig(config: Partial<AtomVectorConfig>): Promise<AtomVectorConfig> {
    const response = await fetch(`${this.baseUrl}/vector/config`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Platform': this.platform
      },
      body: JSON.stringify(config)
    });

    if (!response.ok) {
      throw new Error(`Vector config update error: ${response.statusText}`);
    }

    return response.json();
  }

  // Index new content for vector search
  async indexContent(
    content: Array<{
      id: string;
      text: string;
      metadata: Record<string, any>;
    }>,
    options: {
      model?: string;
      batchSize?: number;
      overwrite?: boolean;
    } = {}
  ): Promise<{ indexed: number; errors: string[] }> {
    const response = await fetch(`${this.baseUrl}/vector/index`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Platform': this.platform
      },
      body: JSON.stringify({
        content,
        options: {
          model: options.model || 'text-embedding-ada-002',
          batch_size: options.batchSize || 32,
          overwrite: options.overwrite || false
        }
      })
    });

    if (!response.ok) {
      throw new Error(`Index content error: ${response.statusText}`);
    }

    return response.json();
  }

  // Delete content from vector index
  async deleteContent(ids: string[]): Promise<{ deleted: number; errors: string[] }> {
    const response = await fetch(`${this.baseUrl}/vector/delete`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Platform': this.platform
      },
      body: JSON.stringify({ ids })
    });

    if (!response.ok) {
      throw new Error(`Delete content error: ${response.statusText}`);
    }

    return response.json();
  }

  // Get search analytics
  async getAnalytics(
    filters: {
      dateFrom?: string;
      dateTo?: string;
      platform?: string;
    } = {}
  ): Promise<any> {
    const params = new URLSearchParams();
    if (filters.dateFrom) params.append('date_from', filters.dateFrom);
    if (filters.dateTo) params.append('date_to', filters.dateTo);
    if (filters.platform) params.append('platform', filters.platform);

    const response = await fetch(`${this.baseUrl}/analytics?${params}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Platform': this.platform
      }
    });

    if (!response.ok) {
      throw new Error(`Analytics error: ${response.statusText}`);
    }

    return response.json();
  }

  // Get search health and status
  async getHealth(): Promise<{
    status: string;
    services: {
      search: boolean;
      vector: boolean;
      memory: boolean;
      embeddings: boolean;
    };
    performance: {
      avgSearchTime: number;
      avgVectorTime: number;
      cacheHitRate: number;
    };
  }> {
    const response = await fetch(`${this.baseUrl}/health`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Platform': this.platform
      }
    });

    if (!response.ok) {
      throw new Error(`Health check error: ${response.statusText}`);
    }

    return response.json();
  }

  // Save search configuration
  async saveSearchConfig(
    config: {
      name: string;
      filters: AtomSearchFilters;
      sort: AtomSearchSort;
      weights: any;
    }
  ): Promise<{ id: string; created: boolean }> {
    const response = await fetch(`${this.baseUrl}/search/config`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Platform': this.platform
      },
      body: JSON.stringify(config)
    });

    if (!response.ok) {
      throw new Error(`Save search config error: ${response.statusText}`);
    }

    return response.json();
  }

  // Load search configuration
  async loadSearchConfig(id: string): Promise<any> {
    const response = await fetch(`${this.baseUrl}/search/config/${id}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Platform': this.platform
      }
    });

    if (!response.ok) {
      throw new Error(`Load search config error: ${response.statusText}`);
    }

    return response.json();
  }

  // Delete search configuration
  async deleteSearchConfig(id: string): Promise<{ deleted: boolean }> {
    const response = await fetch(`${this.baseUrl}/search/config/${id}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Platform': this.platform
      }
    });

    if (!response.ok) {
      throw new Error(`Delete search config error: ${response.statusText}`);
    }

    return response.json();
  }
}

// Create singleton instance
export const atomSearchAPI = new AtomSearchAPI();

export default atomSearchAPI;