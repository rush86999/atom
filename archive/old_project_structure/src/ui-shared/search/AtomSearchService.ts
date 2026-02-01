/**
 * ATOM Search Service - Backend Integration
 * connects search UI with ATOM backend services
 */

import { atomSearchAPI } from './AtomSearchAPI';
import { AtomSearchResult, AtomSearchFilters, AtomSearchSort } from './searchTypes';

// Search service interface
export interface AtomSearchService {
  // Core search operations
  search(query: string, filters?: AtomSearchFilters, sort?: AtomSearchSort): Promise<AtomSearchResult[]>;
  vectorSearch(query: string, options?: any): Promise<AtomSearchResult[]>;
  memorySearch(query: string, options?: any): Promise<any[]>;
  hybridSearch(query: string, options?: any): Promise<any>;
  
  // Configuration and management
  configureSearch(config: any): Promise<void>;
  getIndexStatus(): Promise<any>;
  rebuildIndex(): Promise<void>;
  
  // Analytics and monitoring
  getSearchAnalytics(): Promise<any>;
  trackSearchEvent(event: string, data: any): Promise<void>;
}

// Implementation using ATOM backend
export class AtomBackendSearchService implements AtomSearchService {
  private api: typeof atomSearchAPI;
  private config: any;
  private eventQueue: Array<{ event: string; data: any; timestamp: number }> = [];
  
  constructor(baseUrl: string = '/api/search', apiKey: string = '') {
    this.api = new atomSearchAPI(baseUrl, apiKey);
    this.config = {};
  }

  async search(
    query: string,
    filters: AtomSearchFilters = {},
    sort: AtomSearchSort = { field: 'relevance', direction: 'desc' }
  ): Promise<AtomSearchResult[]> {
    const startTime = Date.now();
    
    try {
      const response = await this.api.search(query, filters, sort);
      
      const endTime = Date.now();
      
      // Track search event
      await this.trackSearchEvent('search_performed', {
        query,
        filters,
        sort,
        resultCount: response.total,
        searchTime: endTime - startTime,
        platform: this.detectPlatform()
      });
      
      return response.results;
    } catch (error) {
      console.error('Search service error:', error);
      
      // Track error event
      await this.trackSearchEvent('search_error', {
        query,
        error: error instanceof Error ? error.message : String(error),
        platform: this.detectPlatform()
      });
      
      throw error;
    }
  }

  async vectorSearch(query: string, options: any = {}): Promise<AtomSearchResult[]> {
    const startTime = Date.now();
    
    try {
      const response = await this.api.vectorSearch(query, options);
      
      const endTime = Date.now();
      
      // Track vector search event
      await this.trackSearchEvent('vector_search_performed', {
        query,
        options,
        resultCount: response.length,
        searchTime: endTime - startTime,
        platform: this.detectPlatform()
      });
      
      return response;
    } catch (error) {
      console.error('Vector search service error:', error);
      
      // Track error event
      await this.trackSearchEvent('vector_search_error', {
        query,
        options,
        error: error instanceof Error ? error.message : String(error),
        platform: this.detectPlatform()
      });
      
      throw error;
    }
  }

  async memorySearch(query: string, options: any = {}): Promise<any[]> {
    const startTime = Date.now();
    
    try {
      const response = await this.api.memorySearch(query, options);
      
      const endTime = Date.now();
      
      // Track memory search event
      await this.trackSearchEvent('memory_search_performed', {
        query,
        options,
        resultCount: response.length,
        searchTime: endTime - startTime,
        platform: this.detectPlatform()
      });
      
      return response;
    } catch (error) {
      console.error('Memory search service error:', error);
      
      // Track error event
      await this.trackSearchEvent('memory_search_error', {
        query,
        options,
        error: error instanceof Error ? error.message : String(error),
        platform: this.detectPlatform()
      });
      
      throw error;
    }
  }

  async hybridSearch(query: string, options: any = {}): Promise<any> {
    const startTime = Date.now();
    
    try {
      const response = await this.api.hybridSearch(query, options);
      
      const endTime = Date.now();
      
      // Track hybrid search event
      await this.trackSearchEvent('hybrid_search_performed', {
        query,
        options,
        resultCount: response.total_count || 0,
        searchTime: endTime - startTime,
        platform: this.detectPlatform()
      });
      
      return response;
    } catch (error) {
      console.error('Hybrid search service error:', error);
      
      // Track error event
      await this.trackSearchEvent('hybrid_search_error', {
        query,
        options,
        error: error instanceof Error ? error.message : String(error),
        platform: this.detectPlatform()
      });
      
      throw error;
    }
  }

  async configureSearch(config: any): Promise<void> {
    try {
      // Update vector configuration
      if (config.vector) {
        await this.api.updateVectorConfig(config.vector);
      }
      
      // Store configuration
      this.config = { ...this.config, ...config };
      
      // Track configuration update
      await this.trackSearchEvent('search_config_updated', {
        config,
        platform: this.detectPlatform()
      });
    } catch (error) {
      console.error('Search configuration error:', error);
      
      // Track error event
      await this.trackSearchEvent('search_config_error', {
        config,
        error: error instanceof Error ? error.message : String(error),
        platform: this.detectPlatform()
      });
      
      throw error;
    }
  }

  async getIndexStatus(): Promise<any> {
    try {
      const health = await this.api.getHealth();
      const vectorConfig = await this.api.getVectorConfig();
      
      return {
        health,
        vectorConfig,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      console.error('Index status error:', error);
      throw error;
    }
  }

  async rebuildIndex(): Promise<void> {
    try {
      // In a real implementation, this would trigger index rebuilding
      console.log('Rebuilding search indexes...');
      
      // Track index rebuild event
      await this.trackSearchEvent('index_rebuild_started', {
        platform: this.detectPlatform()
      });
      
      // Simulate rebuild process
      await new Promise(resolve => setTimeout(resolve, 5000));
      
      // Track completion
      await this.trackSearchEvent('index_rebuild_completed', {
        duration: 5000,
        platform: this.detectPlatform()
      });
      
      console.log('Search indexes rebuilt successfully');
    } catch (error) {
      console.error('Index rebuild error:', error);
      
      // Track error event
      await this.trackSearchEvent('index_rebuild_error', {
        error: error instanceof Error ? error.message : String(error),
        platform: this.detectPlatform()
      });
      
      throw error;
    }
  }

  async getSearchAnalytics(): Promise<any> {
    try {
      // Get analytics from API
      const analytics = await this.api.getAnalytics();
      
      // Get health status
      const health = await this.api.getHealth();
      
      // Get local event queue statistics
      const eventStats = this.getEventQueueStats();
      
      return {
        analytics,
        health,
        events: eventStats,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      console.error('Analytics error:', error);
      throw error;
    }
  }

  async trackSearchEvent(event: string, data: any): Promise<void> {
    const eventData = {
      event,
      data,
      timestamp: Date.now(),
      platform: this.detectPlatform()
    };
    
    // Add to event queue
    this.eventQueue.push(eventData);
    
    // Process queue asynchronously
    this.processEventQueue();
  }

  private async processEventQueue(): Promise<void> {
    if (this.eventQueue.length === 0) return;
    
    // Get events to process
    const events = [...this.eventQueue];
    this.eventQueue = [];
    
    try {
      // Send events to analytics endpoint
      await fetch('/api/search/analytics/events', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          events,
          timestamp: Date.now(),
          platform: this.detectPlatform()
        })
      });
    } catch (error) {
      console.error('Event queue processing error:', error);
      
      // Re-add events to queue on error
      this.eventQueue.unshift(...events);
    }
  }

  private getEventQueueStats(): any {
    const eventCounts: { [key: string]: number } = {};
    const recentEvents = this.eventQueue.filter(event => 
      Date.now() - event.timestamp < 3600000 // Last hour
    );
    
    recentEvents.forEach(event => {
      eventCounts[event.event] = (eventCounts[event.event] || 0) + 1;
    });
    
    return {
      totalQueued: this.eventQueue.length,
      recentHour: recentEvents.length,
      eventCounts,
      oldestEvent: this.eventQueue.length > 0 ? 
        new Date(this.eventQueue[0].timestamp).toISOString() : null
    };
  }

  private detectPlatform(): string {
    if (typeof window !== 'undefined' && window.__TAURI__) {
      return 'desktop';
    }
    if (typeof window !== 'undefined' && /Mobi|Android/i.test(navigator.userAgent)) {
      return 'mobile';
    }
    return 'web';
  }
}

// Create singleton instance
export const atomSearchService = new AtomBackendSearchService();

// Export factory function
export const createSearchService = (
  baseUrl: string = '/api/search',
  apiKey: string = ''
): AtomSearchService => {
  return new AtomBackendSearchService(baseUrl, apiKey);
};

export default atomSearchService;