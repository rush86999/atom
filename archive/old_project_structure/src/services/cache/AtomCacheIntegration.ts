/**
 * ATOM Cache Integration Layer
 * Integrates Redis caching with all ATOM services and integrations
 * Provides intelligent caching strategies for different service types
 */

import { AtomCacheService, CacheOptions, CacheResult } from './AtomCacheService';
import { Logger } from '../utils/logger';

// Integration Service Types
export type IntegrationService = 
  | 'figma'
  | 'github'
  | 'slack'
  | 'gmail'
  | 'teams'
  | 'notion'
  | 'jira'
  | 'asana'
  | 'linear'
  | 'microsoft365'
  | 'hubspot'
  | 'zendesk'
  | 'freshdesk'
  | 'xero'
  | 'airtable'
  | 'box'
  | 'dropbox'
  | 'gdrive'
  | 'onedrive';

// Cache Key Builders
export class CacheKeyBuilder {
  static buildIntegrationKey(
    service: IntegrationService, 
    operation: string, 
    params: Record<string, any>
  ): string {
    const sortedParams = Object.keys(params)
      .sort()
      .reduce((result, key) => {
        result[key] = params[key];
        return result;
      }, {} as Record<string, any>);
    
    const paramString = btoa(JSON.stringify(sortedParams));
    return `${service}:${operation}:${paramString}`;
  }

  static buildUserKey(userId: string, operation: string, params?: Record<string, any>): string {
    if (params) {
      const paramString = btoa(JSON.stringify(params));
      return `user:${userId}:${operation}:${paramString}`;
    }
    return `user:${userId}:${operation}`;
  }

  static buildFileKey(fileId: string, operation: string, params?: Record<string, any>): string {
    if (params) {
      const paramString = btoa(JSON.stringify(params));
      return `file:${fileId}:${operation}:${paramString}`;
    }
    return `file:${fileId}:${operation}`;
  }

  static buildAnalyticsKey(reportType: string, params: Record<string, any>): string {
    const sortedParams = Object.keys(params)
      .sort()
      .reduce((result, key) => {
        result[key] = params[key];
        return result;
      }, {} as Record<string, any>);
    
    const paramString = btoa(JSON.stringify(sortedParams));
    return `analytics:${reportType}:${paramString}`;
  }

  static buildWebhookKey(eventType: string, params: Record<string, any>): string {
    const paramString = btoa(JSON.stringify(params));
    return `webhook:${eventType}:${paramString}`;
  }
}

// Integration-specific Cache Strategies
export class IntegrationCacheStrategies {
  // Figma-specific caching
  static figmaCacheStrategy(operation: string): string {
    const strategyMap: Record<string, string> = {
      'getFiles': 'designAssets',
      'getComponents': 'designAssets', 
      'getStyles': 'designAssets',
      'getProjects': 'fileMetadata',
      'getTeams': 'integrationData',
      'getFile': 'designAssets',
      'getVersionHistory': 'apiResponses',
      'getComments': 'apiResponses',
      'search': 'apiResponses'
    };
    
    return strategyMap[operation] || 'apiResponses';
  }

  // GitHub-specific caching
  static githubCacheStrategy(operation: string): string {
    const strategyMap: Record<string, string> = {
      'getRepos': 'fileMetadata',
      'getCommits': 'apiResponses',
      'getIssues': 'apiResponses',
      'getPullRequests': 'apiResponses',
      'getFileContent': 'designAssets',
      'getBranches': 'fileMetadata',
      'getReleases': 'apiResponses',
      'getActions': 'apiResponses'
    };
    
    return strategyMap[operation] || 'apiResponses';
  }

  // Slack-specific caching
  static slackCacheStrategy(operation: string): string {
    const strategyMap: Record<string, string> = {
      'getChannels': 'integrationData',
      'getMessages': 'apiResponses',
      'getUsers': 'integrationData',
      'getFiles': 'fileMetadata',
      'search': 'apiResponses',
      'getConversations': 'apiResponses',
      'getThreads': 'apiResponses'
    };
    
    return strategyMap[operation] || 'apiResponses';
  }

  // Generic strategy fallback
  static getStrategy(service: IntegrationService, operation: string): string {
    const serviceStrategies: Record<IntegrationService, (op: string) => string> = {
      'figma': this.figmaCacheStrategy,
      'github': this.githubCacheStrategy,
      'slack': this.slackCacheStrategy,
      'gmail': () => 'apiResponses',
      'teams': () => 'apiResponses',
      'notion': () => 'fileMetadata',
      'jira': () => 'apiResponses',
      'asana': () => 'apiResponses',
      'linear': () => 'apiResponses',
      'microsoft365': () => 'apiResponses',
      'hubspot': () => 'apiResponses',
      'zendesk': () => 'apiResponses',
      'freshdesk': () => 'apiResponses',
      'xero': () => 'apiResponses',
      'airtable': () => 'fileMetadata',
      'box': () => 'fileMetadata',
      'dropbox': () => 'fileMetadata',
      'gdrive': () => 'fileMetadata',
      'onedrive': () => 'fileMetadata'
    };

    const strategyFunction = serviceStrategies[service];
    return strategyFunction ? strategyFunction(operation) : 'apiResponses';
  }
}

// Main Cache Integration Service
export class AtomCacheIntegration {
  private cacheService: AtomCacheService;
  private logger: Logger;

  constructor(cacheService: AtomCacheService) {
    this.cacheService = cacheService;
    this.logger = new Logger('AtomCacheIntegration');
  }

  // Integration-specific cache methods
  async cacheIntegrationData<T>(
    service: IntegrationService,
    operation: string,
    params: Record<string, any>,
    data: T,
    options?: Partial<CacheOptions>
  ): Promise<boolean> {
    try {
      const key = CacheKeyBuilder.buildIntegrationKey(service, operation, params);
      const strategy = IntegrationCacheStrategies.getStrategy(service, operation);
      
      const cacheOptions: CacheOptions = {
        key,
        value: data,
        tags: [service, operation],
        ...options
      };

      return await this.cacheService.set(cacheOptions, strategy as any);
      
    } catch (error) {
      this.logger.error(`Failed to cache ${service} data for operation ${operation}:`, error);
      return false;
    }
  }

  async getCachedIntegrationData<T>(
    service: IntegrationService,
    operation: string,
    params: Record<string, any>
  ): Promise<CacheResult<T>> {
    try {
      const key = CacheKeyBuilder.buildIntegrationKey(service, operation, params);
      const strategy = IntegrationCacheStrategies.getStrategy(service, operation);
      
      return await this.cacheService.get<T>(key, strategy as any);
      
    } catch (error) {
      this.logger.error(`Failed to get cached ${service} data for operation ${operation}:`, error);
      return { found: false, error: error.message };
    }
  }

  async invalidateIntegrationData(
    service: IntegrationService,
    operation?: string,
    params?: Record<string, any>
  ): Promise<boolean> {
    try {
      if (operation && params) {
        const key = CacheKeyBuilder.buildIntegrationKey(service, operation, params);
        const strategy = IntegrationCacheStrategies.getStrategy(service, operation);
        return await this.cacheService.delete(key, strategy as any);
      } else {
        // Invalidate all data for a service
        return await this.cacheService.clear(service as any);
      }
    } catch (error) {
      this.logger.error(`Failed to invalidate ${service} data:`, error);
      return false;
    }
  }

  // User session caching
  async cacheUserData<T>(
    userId: string,
    operation: string,
    data: T,
    params?: Record<string, any>,
    options?: Partial<CacheOptions>
  ): Promise<boolean> {
    try {
      const key = CacheKeyBuilder.buildUserKey(userId, operation, params);
      
      const cacheOptions: CacheOptions = {
        key,
        value: data,
        tags: ['user', operation],
        priority: 'high',
        encrypt: true,
        ...options
      };

      return await this.cacheService.set(cacheOptions, 'userSessions');
      
    } catch (error) {
      this.logger.error(`Failed to cache user data for user ${userId}:`, error);
      return false;
    }
  }

  async getCachedUserData<T>(
    userId: string,
    operation: string,
    params?: Record<string, any>
  ): Promise<CacheResult<T>> {
    try {
      const key = CacheKeyBuilder.buildUserKey(userId, operation, params);
      return await this.cacheService.get<T>(key, 'userSessions');
      
    } catch (error) {
      this.logger.error(`Failed to get cached user data for user ${userId}:`, error);
      return { found: false, error: error.message };
    }
  }

  // File metadata caching
  async cacheFileData<T>(
    fileId: string,
    operation: string,
    data: T,
    params?: Record<string, any>,
    options?: Partial<CacheOptions>
  ): Promise<boolean> {
    try {
      const key = CacheKeyBuilder.buildFileKey(fileId, operation, params);
      
      const cacheOptions: CacheOptions = {
        key,
        value: data,
        tags: ['file', operation],
        compress: true,
        ...options
      };

      return await this.cacheService.set(cacheOptions, 'fileMetadata');
      
    } catch (error) {
      this.logger.error(`Failed to cache file data for file ${fileId}:`, error);
      return false;
    }
  }

  async getCachedFileData<T>(
    fileId: string,
    operation: string,
    params?: Record<string, any>
  ): Promise<CacheResult<T>> {
    try {
      const key = CacheKeyBuilder.buildFileKey(fileId, operation, params);
      return await this.cacheService.get<T>(key, 'fileMetadata');
      
    } catch (error) {
      this.logger.error(`Failed to get cached file data for file ${fileId}:`, error);
      return { found: false, error: error.message };
    }
  }

  // Analytics caching
  async cacheAnalyticsData<T>(
    reportType: string,
    params: Record<string, any>,
    data: T,
    options?: Partial<CacheOptions>
  ): Promise<boolean> {
    try {
      const key = CacheKeyBuilder.buildAnalyticsKey(reportType, params);
      
      const cacheOptions: CacheOptions = {
        key,
        value: data,
        tags: ['analytics', reportType],
        ...options
      };

      return await this.cacheService.set(cacheOptions, 'analytics');
      
    } catch (error) {
      this.logger.error(`Failed to cache analytics data for report ${reportType}:`, error);
      return false;
    }
  }

  async getCachedAnalyticsData<T>(
    reportType: string,
    params: Record<string, any>
  ): Promise<CacheResult<T>> {
    try {
      const key = CacheKeyBuilder.buildAnalyticsKey(reportType, params);
      return await this.cacheService.get<T>(key, 'analytics');
      
    } catch (error) {
      this.logger.error(`Failed to get cached analytics data for report ${reportType}:`, error);
      return { found: false, error: error.message };
    }
  }

  // Webhook event caching
  async cacheWebhookEvent<T>(
    eventType: string,
    params: Record<string, any>,
    data: T,
    options?: Partial<CacheOptions>
  ): Promise<boolean> {
    try {
      const key = CacheKeyBuilder.buildWebhookKey(eventType, params);
      
      const cacheOptions: CacheOptions = {
        key,
        value: data,
        tags: ['webhook', eventType],
        priority: 'low',
        ...options
      };

      return await this.cacheService.set(cacheOptions, 'webhookEvents');
      
    } catch (error) {
      this.logger.error(`Failed to cache webhook event for type ${eventType}:`, error);
      return false;
    }
  }

  async getCachedWebhookEvent<T>(
    eventType: string,
    params: Record<string, any>
  ): Promise<CacheResult<T>> {
    try {
      const key = CacheKeyBuilder.buildWebhookKey(eventType, params);
      return await this.cacheService.get<T>(key, 'webhookEvents');
      
    } catch (error) {
      this.logger.error(`Failed to get cached webhook event for type ${eventType}:`, error);
      return { found: false, error: error.message };
    }
  }

  // Tag-based invalidation
  async invalidateByTag(tag: string): Promise<boolean> {
    try {
      return await this.cacheService.invalidateByTag(tag);
    } catch (error) {
      this.logger.error(`Failed to invalidate by tag ${tag}:`, error);
      return false;
    }
  }

  // Performance monitoring
  async getPerformanceMetrics() {
    try {
      return await this.cacheService.getMetrics();
    } catch (error) {
      this.logger.error('Failed to get performance metrics:', error);
      return null;
    }
  }

  // Refresh cached data
  async refreshCachedData<T>(
    service: IntegrationService,
    operation: string,
    params: Record<string, any>,
    refreshFn: () => Promise<T>
  ): Promise<boolean> {
    try {
      const key = CacheKeyBuilder.buildIntegrationKey(service, operation, params);
      const strategy = IntegrationCacheStrategies.getStrategy(service, operation);
      
      return await this.cacheService.refresh(key, refreshFn, strategy as any);
      
    } catch (error) {
      this.logger.error(`Failed to refresh cached ${service} data:`, error);
      return false;
    }
  }

  // Bulk operations
  async cacheBulkData<T>(
    service: IntegrationService,
    operations: Array<{
      operation: string;
      params: Record<string, any>;
      data: T;
    }>
  ): Promise<boolean[]> {
    const results = await Promise.all(
      operations.map(({ operation, params, data }) =>
        this.cacheIntegrationData(service, operation, params, data)
      )
    );
    
    return results;
  }

  async getBulkCachedData<T>(
    service: IntegrationService,
    operations: Array<{
      operation: string;
      params: Record<string, any>;
    }>
  ): Promise<CacheResult<T>[]> {
    const keys = operations.map(({ operation, params }) =>
      CacheKeyBuilder.buildIntegrationKey(service, operation, params)
    );
    
    try {
      const strategy = 'apiResponses'; // Default for bulk operations
      return await this.cacheService.mget<T>(keys, strategy as any);
    } catch (error) {
      this.logger.error(`Failed to get bulk cached ${service} data:`, error);
      return operations.map(() => ({ found: false, error: error.message }));
    }
  }
}

// Cache Integration Service Factory
export class AtomCacheIntegrationFactory {
  private static instance: AtomCacheIntegration;

  static getInstance(cacheService?: AtomCacheService): AtomCacheIntegration {
    if (!this.instance) {
      if (!cacheService) {
        throw new Error('CacheService instance required for first initialization');
      }
      this.instance = new AtomCacheIntegration(cacheService);
    }
    return this.instance;
  }
}

export default AtomCacheIntegration;