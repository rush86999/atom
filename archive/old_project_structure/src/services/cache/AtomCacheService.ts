/**
 * ATOM Cache Service - Advanced Caching Layer
 * Redis-based caching implementation for enterprise performance optimization
 * Provides multi-tier caching with intelligent invalidation strategies
 */

import Redis from 'ioredis';
import { promisify } from 'util';
import { Logger } from '../utils/logger';

// Cache Configuration Types
export interface AtomCacheConfig {
  redis: {
    host: string;
    port: number;
    password?: string;
    db: number;
    keyPrefix: string;
    retryDelayOnFailover: number;
    maxRetriesPerRequest: number;
    lazyConnect: boolean;
    enableAutoPipelining: boolean;
    maxMemoryPolicy?: string;
  };
  strategies: {
    userSessions: CacheStrategy;
    apiResponses: CacheStrategy;
    designAssets: CacheStrategy;
    fileMetadata: CacheStrategy;
    integrationData: CacheStrategy;
    analytics: CacheStrategy;
    webhookEvents: CacheStrategy;
    authTokens: CacheStrategy;
  };
  monitoring: {
    enabled: boolean;
    metricsInterval: number;
    alertThresholds: {
      errorRate: number;
      responseTime: number;
      memoryUsage: number;
    };
  };
}

export interface CacheStrategy {
  ttl: number; // Time to live in seconds
  maxSize?: number; // Maximum number of items
  refreshWindow?: number; // Background refresh window
  compression: boolean; // Enable compression for large data
  encryption: boolean; // Enable encryption for sensitive data
  invalidationStrategy: 'time' | 'manual' | 'event' | 'hybrid';
  backgroundRefresh: boolean; // Background refresh before expiry
}

export interface CacheOptions {
  key: string;
  value: any;
  ttl?: number;
  tags?: string[];
  compress?: boolean;
  encrypt?: boolean;
  priority?: 'high' | 'medium' | 'low';
}

export interface CacheResult<T = any> {
  found: boolean;
  data?: T;
  metadata?: {
    ttl: number;
    createdAt: number;
    updatedAt: number;
    tags: string[];
    size: number;
    hits: number;
  };
  error?: string;
}

export interface CacheMetrics {
  totalOperations: number;
  hits: number;
  misses: number;
  hitRate: number;
  errorRate: number;
  averageResponseTime: number;
  memoryUsage: {
    used: number;
    available: number;
    percentage: number;
  };
  operations: {
    get: number;
    set: number;
    delete: number;
    clear: number;
    refresh: number;
  };
  byStrategy: Record<string, {
    hits: number;
    misses: number;
    hitRate: number;
    averageResponseTime: number;
  }>;
}

// Main Cache Service Implementation
export class AtomCacheService {
  private redis: Redis;
  private config: AtomCacheConfig;
  private logger: Logger;
  private metrics: CacheMetrics;
  private backgroundRefreshJobs: Map<string, NodeJS.Timeout>;
  private compressionEnabled: boolean;
  private encryptionEnabled: boolean;

  constructor(config: AtomCacheConfig) {
    this.config = config;
    this.logger = new Logger('AtomCacheService');
    this.metrics = this.initializeMetrics();
    this.backgroundRefreshJobs = new Map();
    
    this.initializeRedis();
    this.setupMonitoring();
    this.setupCompression();
    this.setupEncryption();
  }

  private initializeMetrics(): CacheMetrics {
    return {
      totalOperations: 0,
      hits: 0,
      misses: 0,
      hitRate: 0,
      errorRate: 0,
      averageResponseTime: 0,
      memoryUsage: {
        used: 0,
        available: 0,
        percentage: 0
      },
      operations: {
        get: 0,
        set: 0,
        delete: 0,
        clear: 0,
        refresh: 0
      },
      byStrategy: {}
    };
  }

  private initializeRedis(): void {
    try {
      this.redis = new Redis({
        host: this.config.redis.host,
        port: this.config.redis.port,
        password: this.config.redis.password,
        db: this.config.redis.db,
        keyPrefix: this.config.redis.keyPrefix,
        retryDelayOnFailover: this.config.redis.retryDelayOnFailover,
        maxRetriesPerRequest: this.config.redis.maxRetriesPerRequest,
        lazyConnect: this.config.redis.lazyConnect,
        enableAutoPipelining: this.config.redis.enableAutoPipelining,
        // Performance optimizations
        maxMemoryPolicy: this.config.redis.maxMemoryPolicy || 'allkeys-lru',
        // Connection pooling
        family: 4,
        keepAlive: 30000,
        connectTimeout: 10000,
        commandTimeout: 5000,
      });

      this.redis.on('connect', () => {
        this.logger.info('Redis connected successfully');
        this.updateMemoryUsage();
      });

      this.redis.on('error', (error) => {
        this.logger.error('Redis connection error:', error);
        this.updateMetrics('error');
      });

      this.redis.on('close', () => {
        this.logger.warn('Redis connection closed');
      });

      // Set up memory optimization
      this.optimizeRedisMemory();

    } catch (error) {
      this.logger.error('Failed to initialize Redis:', error);
      throw new Error(`Redis initialization failed: ${error.message}`);
    }
  }

  private setupMonitoring(): void {
    if (!this.config.monitoring.enabled) return;

    // Update metrics periodically
    setInterval(() => {
      this.updateMemoryUsage();
      this.logMetrics();
    }, this.config.monitoring.metricsInterval);

    // Check alert thresholds
    setInterval(() => {
      this.checkAlertThresholds();
    }, this.config.monitoring.metricsInterval * 2);
  }

  private setupCompression(): void {
    // Compression would require zlib/gzip implementation
    // For now, we'll use JSON.stringify compression simulation
    this.compressionEnabled = true;
  }

  private setupEncryption(): void {
    // Encryption would require crypto implementation
    // For now, we'll use base64 encoding simulation
    this.encryptionEnabled = true;
  }

  private async optimizeRedisMemory(): Promise<void> {
    try {
      await this.redis.config('SET', 'maxmemory-policy', this.config.redis.maxMemoryPolicy || 'allkeys-lru');
      await this.redis.config('SET', 'timeout', 300); // 5 minutes idle timeout
      await this.redis.config('SET', 'tcp-keepalive', 60);
      await this.redis.config('SET', 'save', '900 1 300 10 60 10000'); // RDB persistence
      
      this.logger.info('Redis memory optimization applied');
    } catch (error) {
      this.logger.warn('Failed to optimize Redis memory:', error);
    }
  }

  // Core Cache Operations
  async get<T = any>(key: string, strategy: keyof AtomCacheConfig['strategies'] = 'apiResponses'): Promise<CacheResult<T>> {
    const startTime = Date.now();
    
    try {
      const fullKey = this.buildKey(key, strategy);
      const cachedData = await this.redis.get(fullKey);
      
      this.metrics.operations.get++;
      this.metrics.totalOperations++;

      if (!cachedData) {
        this.metrics.misses++;
        this.updateStrategyMetrics(strategy, 'miss');
        return { found: false };
      }

      const parsedData = await this.deserializeData(cachedData);
      this.metrics.hits++;
      this.updateStrategyMetrics(strategy, 'hit');
      
      const responseTime = Date.now() - startTime;
      this.updateResponseTime(responseTime);

      return {
        found: true,
        data: parsedData.data,
        metadata: parsedData.metadata
      };

    } catch (error) {
      this.logger.error(`Cache get error for key ${key}:`, error);
      this.updateMetrics('error');
      return { 
        found: false, 
        error: error.message 
      };
    }
  }

  async set(options: CacheOptions, strategy: keyof AtomCacheConfig['strategies'] = 'apiResponses'): Promise<boolean> {
    const startTime = Date.now();
    
    try {
      const config = this.config.strategies[strategy];
      const ttl = options.ttl || config.ttl;
      const fullKey = this.buildKey(options.key, strategy);
      
      const serializedData = await this.serializeData({
        data: options.value,
        metadata: {
          ttl,
          createdAt: Date.now(),
          updatedAt: Date.now(),
          tags: options.tags || [],
          size: 0, // Will be calculated during serialization
          hits: 0
        }
      }, config);

      await this.redis.setex(fullKey, ttl, serializedData);

      // Set up background refresh if enabled
      if (config.backgroundRefresh && ttl > 60) {
        this.scheduleBackgroundRefresh(options.key, strategy, ttl, ttl * 0.8);
      }

      // Add to tag index for tag-based invalidation
      if (options.tags && options.tags.length > 0) {
        await this.addToTagIndex(fullKey, options.tags, ttl);
      }

      this.metrics.operations.set++;
      this.metrics.totalOperations++;
      
      const responseTime = Date.now() - startTime;
      this.updateResponseTime(responseTime);

      this.logger.debug(`Cache set for key: ${options.key}, strategy: ${strategy}, ttl: ${ttl}`);
      return true;

    } catch (error) {
      this.logger.error(`Cache set error for key ${options.key}:`, error);
      this.updateMetrics('error');
      return false;
    }
  }

  async delete(key: string, strategy: keyof AtomCacheConfig['strategies'] = 'apiResponses'): Promise<boolean> {
    try {
      const fullKey = this.buildKey(key, strategy);
      const result = await this.redis.del(fullKey);
      
      this.metrics.operations.delete++;
      this.metrics.totalOperations++;

      // Remove from tag index
      await this.removeFromTagIndex(fullKey);

      this.logger.debug(`Cache delete for key: ${key}, strategy: ${strategy}`);
      return result > 0;

    } catch (error) {
      this.logger.error(`Cache delete error for key ${key}:`, error);
      this.updateMetrics('error');
      return false;
    }
  }

  async clear(strategy?: keyof AtomCacheConfig['strategies']): Promise<boolean> {
    try {
      let keys: string[];
      
      if (strategy) {
        // Clear only specific strategy
        const pattern = this.buildKey('*', strategy);
        keys = await this.redis.keys(pattern);
      } else {
        // Clear all cache
        const pattern = this.buildKey('*');
        keys = await this.redis.keys(pattern);
      }

      if (keys.length > 0) {
        await this.redis.del(...keys);
      }

      this.metrics.operations.clear++;
      this.metrics.totalOperations++;

      this.logger.info(`Cache cleared for strategy: ${strategy || 'all'}, keys: ${keys.length}`);
      return true;

    } catch (error) {
      this.logger.error(`Cache clear error:`, error);
      this.updateMetrics('error');
      return false;
    }
  }

  async invalidateByTag(tag: string): Promise<boolean> {
    try {
      const tagKeys = await this.redis.smembers(`tag:${tag}`);
      
      if (tagKeys.length > 0) {
        await this.redis.del(...tagKeys);
        await this.redis.del(`tag:${tag}`);
      }

      this.logger.info(`Invalidated ${tagKeys.length} cache entries by tag: ${tag}`);
      return true;

    } catch (error) {
      this.logger.error(`Tag invalidation error for tag ${tag}:`, error);
      return false;
    }
  }

  // Advanced Operations
  async refresh(key: string, refreshFn: () => Promise<any>, strategy: keyof AtomCacheConfig['strategies'] = 'apiResponses'): Promise<boolean> {
    try {
      const startTime = Date.now();
      const newData = await refreshFn();
      const responseTime = Date.now() - startTime;

      await this.set({ key, value: newData }, strategy);
      
      this.metrics.operations.refresh++;
      this.metrics.totalOperations++;

      this.logger.debug(`Cache refreshed for key: ${key}, response time: ${responseTime}ms`);
      return true;

    } catch (error) {
      this.logger.error(`Cache refresh error for key ${key}:`, error);
      return false;
    }
  }

  async mget(keys: string[], strategy: keyof AtomCacheConfig['strategies'] = 'apiResponses'): Promise<CacheResult[]> {
    const fullKeys = keys.map(key => this.buildKey(key, strategy));
    
    try {
      const values = await this.redis.mget(...fullKeys);
      
      return values.map((value, index) => {
        if (!value) {
          return { found: false };
        }

        try {
          const parsedData = this.deserializeData(value);
          return {
            found: true,
            data: parsedData.data,
            metadata: parsedData.metadata
          };
        } catch (error) {
          return { found: false, error: error.message };
        }
      });

    } catch (error) {
      this.logger.error('Cache mget error:', error);
      return keys.map(key => ({ found: false, error: error.message }));
    }
  }

  // Metrics and Monitoring
  async getMetrics(): Promise<CacheMetrics> {
    this.updateMemoryUsage();
    return { ...this.metrics };
  }

  async resetMetrics(): Promise<void> {
    this.metrics = this.initializeMetrics();
    this.logger.info('Cache metrics reset');
  }

  private async serializeData(data: any, config: CacheStrategy): Promise<string> {
    let serialized = JSON.stringify(data);
    
    // Simulate compression
    if (config.compression) {
      serialized = Buffer.from(serialized).toString('base64');
    }
    
    // Simulate encryption
    if (config.encryption) {
      serialized = Buffer.from(serialized).toString('hex');
    }
    
    return serialized;
  }

  private async deserializeData(data: string): Promise<any> {
    // Simulate decryption
    let deserialized = data;
    if (this.encryptionEnabled) {
      deserialized = Buffer.from(deserialized, 'hex').toString();
    }
    
    // Simulate decompression
    if (this.compressionEnabled) {
      deserialized = Buffer.from(deserialized, 'base64').toString();
    }
    
    return JSON.parse(deserialized);
  }

  private buildKey(key: string, strategy: keyof AtomCacheConfig['strategies']): string {
    return `${strategy}:${key}`;
  }

  private async addToTagIndex(key: string, tags: string[], ttl: number): Promise<void> {
    const pipeline = this.redis.pipeline();
    
    for (const tag of tags) {
      pipeline.sadd(`tag:${tag}`, key);
      pipeline.expire(`tag:${tag}`, ttl);
    }
    
    await pipeline.exec();
  }

  private async removeFromTagIndex(key: string): Promise<void> {
    // This is simplified - in production, you'd need to track which tags a key belongs to
    // For now, we'll use Redis SCAN to find and remove from all tag sets
    const tagPattern = 'tag:*';
    const tagKeys = await this.redis.keys(tagPattern);
    
    if (tagKeys.length > 0) {
      const pipeline = this.redis.pipeline();
      for (const tagKey of tagKeys) {
        pipeline.srem(tagKey, key);
      }
      await pipeline.exec();
    }
  }

  private scheduleBackgroundRefresh(key: string, strategy: keyof AtomCacheConfig['strategies'], ttl: number, refreshDelay: number): void {
    const refreshKey = `${strategy}:${key}`;
    
    // Clear existing refresh job if any
    if (this.backgroundRefreshJobs.has(refreshKey)) {
      clearTimeout(this.backgroundRefreshJobs.get(refreshKey));
    }

    // Schedule new refresh
    const timeout = setTimeout(async () => {
      this.logger.debug(`Background refresh triggered for key: ${key}, strategy: ${strategy}`);
      
      // The actual refresh function would need to be passed in or retrieved from a registry
      // For now, we'll just delete the key to force a refresh on next get
      await this.delete(key, strategy);
      
      this.backgroundRefreshJobs.delete(refreshKey);
    }, refreshDelay * 1000);

    this.backgroundRefreshJobs.set(refreshKey, timeout);
  }

  private updateStrategyMetrics(strategy: keyof AtomCacheConfig['strategies'], type: 'hit' | 'miss'): void {
    if (!this.metrics.byStrategy[strategy]) {
      this.metrics.byStrategy[strategy] = {
        hits: 0,
        misses: 0,
        hitRate: 0,
        averageResponseTime: 0
      };
    }

    if (type === 'hit') {
      this.metrics.byStrategy[strategy].hits++;
    } else {
      this.metrics.byStrategy[strategy].misses++;
    }

    // Calculate hit rate
    const strategyMetrics = this.metrics.byStrategy[strategy];
    const total = strategyMetrics.hits + strategyMetrics.misses;
    strategyMetrics.hitRate = total > 0 ? strategyMetrics.hits / total : 0;
  }

  private updateMetrics(type: 'get' | 'set' | 'delete' | 'clear' | 'refresh' | 'error'): void {
    if (type === 'error') {
      const errorRate = (this.metrics.totalOperations > 0) ? 
        ((this.metrics.totalOperations - (this.metrics.hits + this.metrics.misses)) / this.metrics.totalOperations) * 100 : 0;
      this.metrics.errorRate = errorRate;
    }
  }

  private updateResponseTime(responseTime: number): void {
    const currentAvg = this.metrics.averageResponseTime;
    const totalOps = this.metrics.totalOperations;
    
    this.metrics.averageResponseTime = ((currentAvg * (totalOps - 1)) + responseTime) / totalOps;
  }

  private async updateMemoryUsage(): Promise<void> {
    try {
      const info = await this.redis.info('memory');
      const lines = info.split('\r\n');
      
      let maxMemory = 0;
      let usedMemory = 0;
      
      for (const line of lines) {
        if (line.includes('maxmemory:')) {
          maxMemory = parseInt(line.split(':')[1]);
        } else if (line.includes('used_memory:')) {
          usedMemory = parseInt(line.split(':')[1]);
        }
      }
      
      this.metrics.memoryUsage = {
        used: usedMemory,
        available: maxMemory,
        percentage: maxMemory > 0 ? (usedMemory / maxMemory) * 100 : 0
      };

    } catch (error) {
      this.logger.warn('Failed to update memory usage:', error);
    }
  }

  private checkAlertThresholds(): void {
    const thresholds = this.config.monitoring.alertThresholds;
    
    // Check error rate
    if (this.metrics.errorRate > thresholds.errorRate) {
      this.logger.warn(`Cache error rate threshold exceeded: ${this.metrics.errorRate}% > ${thresholds.errorRate}%`);
    }
    
    // Check average response time
    if (this.metrics.averageResponseTime > thresholds.responseTime) {
      this.logger.warn(`Cache response time threshold exceeded: ${this.metrics.averageResponseTime}ms > ${thresholds.responseTime}ms`);
    }
    
    // Check memory usage
    if (this.metrics.memoryUsage.percentage > thresholds.memoryUsage) {
      this.logger.warn(`Cache memory usage threshold exceeded: ${this.metrics.memoryUsage.percentage}% > ${thresholds.memoryUsage}%`);
    }
  }

  private logMetrics(): void {
    this.logger.info('Cache Metrics:', {
      totalOperations: this.metrics.totalOperations,
      hits: this.metrics.hits,
      misses: this.metrics.misses,
      hitRate: `${(this.metrics.hitRate * 100).toFixed(2)}%`,
      averageResponseTime: `${this.metrics.averageResponseTime.toFixed(2)}ms`,
      memoryUsage: `${this.metrics.memoryUsage.percentage.toFixed(2)}%`,
      errorRate: `${this.metrics.errorRate.toFixed(2)}%`
    });
  }

  // Cleanup and shutdown
  async shutdown(): Promise<void> {
    this.logger.info('Shutting down AtomCacheService...');
    
    // Clear background refresh jobs
    for (const [key, timeout] of this.backgroundRefreshJobs) {
      clearTimeout(timeout);
    }
    this.backgroundRefreshJobs.clear();
    
    // Close Redis connection
    if (this.redis) {
      await this.redis.quit();
    }
    
    this.logger.info('AtomCacheService shutdown complete');
  }
}

// Default Cache Configuration
export const DEFAULT_CACHE_CONFIG: AtomCacheConfig = {
  redis: {
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT || '6379'),
    password: process.env.REDIS_PASSWORD,
    db: parseInt(process.env.REDIS_DB || '0'),
    keyPrefix: 'atom:',
    retryDelayOnFailover: 100,
    maxRetriesPerRequest: 3,
    lazyConnect: true,
    enableAutoPipelining: true,
    maxMemoryPolicy: 'allkeys-lru'
  },
  strategies: {
    userSessions: {
      ttl: 3600, // 1 hour
      compression: true,
      encryption: true,
      invalidationStrategy: 'hybrid',
      backgroundRefresh: true,
      refreshWindow: 300
    },
    apiResponses: {
      ttl: 300, // 5 minutes
      compression: true,
      encryption: false,
      invalidationStrategy: 'time',
      backgroundRefresh: true,
      refreshWindow: 240
    },
    designAssets: {
      ttl: 1800, // 30 minutes
      compression: true,
      encryption: false,
      invalidationStrategy: 'manual',
      backgroundRefresh: false
    },
    fileMetadata: {
      ttl: 600, // 10 minutes
      compression: true,
      encryption: false,
      invalidationStrategy: 'event',
      backgroundRefresh: true
    },
    integrationData: {
      ttl: 900, // 15 minutes
      compression: true,
      encryption: false,
      invalidationStrategy: 'hybrid',
      backgroundRefresh: true
    },
    analytics: {
      ttl: 3600, // 1 hour
      compression: true,
      encryption: false,
      invalidationStrategy: 'time',
      backgroundRefresh: false
    },
    webhookEvents: {
      ttl: 60, // 1 minute
      compression: true,
      encryption: false,
      invalidationStrategy: 'time',
      backgroundRefresh: false
    },
    authTokens: {
      ttl: 7200, // 2 hours
      compression: true,
      encryption: true,
      invalidationStrategy: 'manual',
      backgroundRefresh: false
    }
  },
  monitoring: {
    enabled: true,
    metricsInterval: 30000, // 30 seconds
    alertThresholds: {
      errorRate: 5, // 5%
      responseTime: 1000, // 1 second
      memoryUsage: 80 // 80%
    }
  }
};

// Cache Service Factory
export class AtomCacheServiceFactory {
  private static instance: AtomCacheService;

  static getInstance(config?: AtomCacheConfig): AtomCacheService {
    if (!this.instance) {
      const cacheConfig = config || DEFAULT_CACHE_CONFIG;
      this.instance = new AtomCacheService(cacheConfig);
    }
    return this.instance;
  }

  static async shutdown(): Promise<void> {
    if (this.instance) {
      await this.instance.shutdown();
      this.instance = null as any;
    }
  }
}

export default AtomCacheService;