/**
 * ATOM Cache Middleware
 * Express/FastAPI middleware for automatic request/response caching
 * Provides intelligent caching based on HTTP methods, headers, and response patterns
 */

import { Request, Response, NextFunction } from 'express';
import { AtomCacheIntegration } from './AtomCacheIntegration';
import { Logger } from '../utils/logger';

// Middleware Configuration
export interface CacheMiddlewareConfig {
  enabled: boolean;
  cacheIntegration: AtomCacheIntegration;
  strategies: {
    get: CacheStrategy;
    post: CacheStrategy;
    put: CacheStrategy;
    delete: CacheStrategy;
    patch: CacheStrategy;
  };
  rules: CacheRule[];
  skipPaths: string[];
  skipMethods: string[];
  keyGenerator: KeyGenerator;
  ttlGenerator: TTLGenerator;
  cacheHeaders: CacheHeaders;
}

export interface CacheStrategy {
  enabled: boolean;
  defaultTTL: number;
  maxTTL: number;
  cacheCondition: CacheCondition;
  invalidationRule: InvalidationRule;
  compressionThreshold: number; // bytes
  includeHeaders: boolean;
  varyHeaders: string[];
  priority: 'high' | 'medium' | 'low';
}

export interface CacheRule {
  path: string | RegExp;
  methods: string[];
  ttl: number;
  condition?: CacheCondition;
  tags?: string[];
  priority: number;
  enabled: boolean;
}

export interface CacheCondition {
  statusCode?: number | number[];
  headers?: Record<string, string | RegExp>;
  query?: Record<string, boolean>;
  body?: (req: Request) => boolean;
  custom?: (req: Request, res: Response) => boolean;
}

export interface InvalidationRule {
  onMethod: string[];
  paths: string[];
  invalidatePaths: string[];
  tags: string[];
  pattern: RegExp;
}

export interface KeyGenerator {
  generate(req: Request, res?: Response): string;
  includeQuery: boolean;
  includeBody: boolean;
  includeHeaders: string[];
  hashAlgorithm: 'md5' | 'sha1' | 'sha256';
  prefix?: string;
}

export interface TTLGenerator {
  generate(req: Request, res: Response, defaultTTL: number): number;
  rules: TTLRule[];
  fallbackTTL: number;
  maxTTL: number;
}

export interface TTLRule {
  condition: CacheCondition;
  ttl: number;
  priority: number;
}

export interface CacheHeaders {
  enabled: boolean;
  hitHeader: string;
  missHeader: string;
  ttlHeader: string;
  storageHeader: string;
  varyHeader: string;
}

// Cache Middleware Implementation
export class AtomCacheMiddleware {
  private config: CacheMiddlewareConfig;
  private logger: Logger;
  private stats: MiddlewareStats;

  constructor(config: CacheMiddlewareConfig) {
    this.config = config;
    this.logger = new Logger('AtomCacheMiddleware');
    this.stats = this.initializeStats();
  }

  private initializeStats(): MiddlewareStats {
    return {
      totalRequests: 0,
      cacheHits: 0,
      cacheMisses: 0,
      cacheSets: 0,
      skipCache: 0,
      averageResponseTime: 0,
      totalResponseTime: 0,
      byMethod: {},
      byPath: {}
    };
  }

  // Main middleware function
  middleware() {
    return async (req: Request, res: Response, next: NextFunction) => {
      const startTime = Date.now();
      
      try {
        // Check if middleware is enabled
        if (!this.config.enabled) {
          return this.sendRequest(req, res, next, startTime);
        }

        // Update stats
        this.updateStats('totalRequests', req.method, req.path);

        // Check if request should skip cache
        if (this.shouldSkipCache(req)) {
          this.updateStats('skipCache', req.method, req.path);
          return this.sendRequest(req, res, next, startTime);
        }

        // Generate cache key
        const cacheKey = this.generateCacheKey(req);
        
        // Try to get from cache
        const cachedResponse = await this.getCachedResponse(cacheKey, req.method);
        
        if (cachedResponse.found) {
          this.logger.debug(`Cache hit for ${req.method} ${req.path}`);
          this.updateStats('cacheHits', req.method, req.path);
          return this.sendCachedResponse(req, res, cachedResponse, startTime);
        }

        // Store original res methods
        this.patchResponseMethods(res, cacheKey, req, startTime);

        // Continue with request processing
        return this.sendRequest(req, res, next, startTime);

      } catch (error) {
        this.logger.error(`Cache middleware error for ${req.method} ${req.path}:`, error);
        return this.sendRequest(req, res, next, startTime);
      }
    };
  }

  private shouldSkipCache(req: Request): boolean {
    // Check skip paths
    for (const skipPath of this.config.skipPaths) {
      if (typeof skipPath === 'string' && req.path.startsWith(skipPath)) {
        return true;
      } else if (skipPath instanceof RegExp && skipPath.test(req.path)) {
        return true;
      }
    }

    // Check skip methods
    if (this.config.skipMethods.includes(req.method)) {
      return true;
    }

    // Check authorization headers (don't cache authenticated requests by default)
    if (req.headers.authorization || req.headers['x-api-key']) {
      return true;
    }

    return false;
  }

  private generateCacheKey(req: Request): string {
    const { keyGenerator } = this.config;
    
    let keyParts = [req.method, req.path];
    
    // Include query parameters
    if (keyGenerator.includeQuery && Object.keys(req.query).length > 0) {
      const sortedQuery = Object.keys(req.query)
        .sort()
        .reduce((result, key) => {
          result[key] = req.query[key];
          return result;
        }, {} as any);
      keyParts.push(btoa(JSON.stringify(sortedQuery)));
    }
    
    // Include body for relevant methods
    if (keyGenerator.includeBody && ['POST', 'PUT', 'PATCH'].includes(req.method)) {
      if (req.body) {
        keyParts.push(btoa(JSON.stringify(req.body)));
      }
    }
    
    // Include specified headers
    if (keyGenerator.includeHeaders && keyGenerator.includeHeaders.length > 0) {
      const headerData: any = {};
      for (const header of keyGenerator.includeHeaders) {
        if (req.headers[header]) {
          headerData[header] = req.headers[header];
        }
      }
      keyParts.push(btoa(JSON.stringify(headerData)));
    }
    
    // Add prefix
    let key = keyParts.join(':');
    if (keyGenerator.prefix) {
      key = `${keyGenerator.prefix}:${key}`;
    }
    
    // Hash if needed
    if (keyGenerator.hashAlgorithm) {
      const crypto = require('crypto');
      key = crypto.createHash(keyGenerator.hashAlgorithm).update(key).digest('hex');
    }
    
    return key;
  }

  private async getCachedResponse(cacheKey: string, method: string) {
    const strategy = this.getStrategy(method);
    
    if (!strategy.enabled) {
      return { found: false };
    }
    
    return await this.config.cacheIntegration.getCachedIntegrationData(
      'api', // Using a generic API service
      'middleware',
      { cacheKey, method }
    );
  }

  private getStrategy(method: string): CacheStrategy {
    const methodKey = method.toLowerCase();
    return this.config.strategies[methodKey as keyof typeof this.config.strategies] || 
           this.config.strategies.get;
  }

  private async cacheResponse(
    cacheKey: string, 
    res: Response, 
    req: Request, 
    startTime: number
  ): Promise<void> {
    const strategy = this.getStrategy(req.method);
    
    if (!strategy.enabled) {
      return;
    }

    // Check caching condition
    if (strategy.cacheCondition && !this.checkCacheCondition(strategy.cacheCondition, req, res)) {
      return;
    }

    // Check status code
    if (!this.shouldCacheStatus(res.statusCode)) {
      return;
    }

    // Prepare response data
    const responseData = {
      statusCode: res.statusCode,
      headers: strategy.includeHeaders ? res.getHeaders() : {},
      body: res.locals.responseBody || '',
      metadata: {
        cachedAt: Date.now(),
        responseTime: Date.now() - startTime,
        method: req.method,
        path: req.path
      }
    };

    // Generate TTL
    const ttl = this.generateTTL(req, res, strategy.defaultTTL);

    // Cache the response
    await this.config.cacheIntegration.cacheIntegrationData(
      'api',
      'middleware',
      { cacheKey },
      responseData,
      {
        ttl,
        tags: ['api-response', req.method, req.path],
        priority: strategy.priority,
        compress: (responseData.body?.length || 0) > strategy.compressionThreshold
      }
    );

    this.updateStats('cacheSets', req.method, req.path);
  }

  private checkCacheCondition(condition: CacheCondition, req: Request, res: Response): boolean {
    // Check status code
    if (condition.statusCode) {
      const statusCodes = Array.isArray(condition.statusCode) ? 
        condition.statusCode : [condition.statusCode];
      if (!statusCodes.includes(res.statusCode)) {
        return false;
      }
    }

    // Check headers
    if (condition.headers) {
      for (const [header, expectedValue] of Object.entries(condition.headers)) {
        const headerValue = req.headers[header.toLowerCase()];
        if (expectedValue instanceof RegExp) {
          if (!headerValue || !expectedValue.test(String(headerValue))) {
            return false;
          }
        } else if (String(headerValue) !== String(expectedValue)) {
          return false;
        }
      }
    }

    // Check query parameters
    if (condition.query) {
      for (const [param, expectedValue] of Object.entries(condition.query)) {
        const paramValue = req.query[param];
        if (expectedValue && !paramValue) {
          return false;
        }
        if (!expectedValue && paramValue) {
          return false;
        }
      }
    }

    // Check body condition
    if (condition.body && !condition.body(req)) {
      return false;
    }

    // Check custom condition
    if (condition.custom && !condition.custom(req, res)) {
      return false;
    }

    return true;
  }

  private shouldCacheStatus(statusCode: number): boolean {
    // Don't cache error responses by default
    if (statusCode >= 400) {
      return false;
    }
    
    // Cache successful responses
    return statusCode >= 200 && statusCode < 300;
  }

  private generateTTL(req: Request, res: Response, defaultTTL: number): number {
    const { ttlGenerator } = this.config;
    
    // Check custom TTL rules
    for (const rule of ttlGenerator.rules) {
      if (rule.condition && this.checkCacheCondition(rule.condition, req, res)) {
        return Math.min(rule.ttl, ttlGenerator.maxTTL);
      }
    }
    
    // Use TTL generator function
    if (ttlGenerator.generate) {
      const generatedTTL = ttlGenerator.generate(req, res, defaultTTL);
      return Math.min(generatedTTL, ttlGenerator.maxTTL);
    }
    
    return Math.min(defaultTTL, ttlGenerator.maxTTL);
  }

  private patchResponseMethods(res: Response, cacheKey: string, req: Request, startTime: number): void {
    const originalWrite = res.write.bind(res);
    const originalEnd = res.end.bind(res);
    const chunks: any[] = [];

    // Intercept response data
    res.write = function(chunk: any) {
      chunks.push(chunk);
      return originalWrite(chunk);
    };

    res.end = function(chunk?: any) {
      if (chunk) {
        chunks.push(chunk);
      }
      
      // Store response body
      res.locals.responseBody = Buffer.concat(chunks).toString('utf8');
      
      // Cache the response if conditions are met
      this.cacheResponse(cacheKey, res, req, startTime).catch(error => {
        // Don't throw errors in response middleware
        console.error('Failed to cache response:', error);
      });
      
      // Call original end
      return originalEnd(chunk);
    }.bind(this);
  }

  private sendCachedResponse(
    req: Request, 
    res: Response, 
    cachedResponse: any, 
    startTime: number
  ): void {
    const { data } = cachedResponse;
    
    // Set status code
    res.status(data.statusCode);
    
    // Set headers
    if (data.headers) {
      for (const [key, value] of Object.entries(data.headers)) {
        res.setHeader(key, value);
      }
    }
    
    // Set cache headers
    if (this.config.cacheHeaders.enabled) {
      res.setHeader(this.config.cacheHeaders.hitHeader, 'true');
      res.setHeader(this.config.cacheHeaders.ttlHeader, data.metadata.cachedAt);
      res.setHeader(this.config.cacheHeaders.storageHeader, 'redis');
      
      if (data.headers['vary']) {
        res.setHeader(this.config.cacheHeaders.varyHeader, data.headers['vary']);
      }
    }
    
    // Send response body
    if (data.body) {
      res.send(data.body);
    } else {
      res.end();
    }
    
    // Update stats
    const responseTime = Date.now() - startTime;
    this.updateStats('cacheHits', req.method, req.path, responseTime);
  }

  private sendRequest(
    req: Request, 
    res: Response, 
    next: NextFunction, 
    startTime: number
  ): void {
    // Set cache miss header
    if (this.config.cacheHeaders.enabled) {
      res.setHeader(this.config.cacheHeaders.missHeader, 'true');
    }
    
    // Continue with request processing
    const originalEnd = res.end.bind(res);
    
    res.end = function(chunk?: any) {
      // Update stats and call original end
      const responseTime = Date.now() - startTime;
      this.updateStats('cacheMisses', req.method, req.path, responseTime);
      return originalEnd(chunk);
    }.bind(this);
    
    next();
  }

  private updateStats(
    type: keyof MiddlewareStats,
    method: string,
    path: string,
    responseTime?: number
  ): void {
    // Update general stats
    if (type === 'totalRequests') {
      this.stats.totalRequests++;
    } else if (type === 'cacheHits') {
      this.stats.cacheHits++;
    } else if (type === 'cacheMisses') {
      this.stats.cacheMisses++;
    } else if (type === 'cacheSets') {
      this.stats.cacheSets++;
    } else if (type === 'skipCache') {
      this.stats.skipCache++;
    }

    // Update average response time
    if (responseTime) {
      this.stats.totalResponseTime += responseTime;
      this.stats.averageResponseTime = this.stats.totalResponseTime / 
        (this.stats.cacheHits + this.stats.cacheMisses + this.stats.skipCache);
    }

    // Update method stats
    if (!this.stats.byMethod[method]) {
      this.stats.byMethod[method] = { hits: 0, misses: 0, skips: 0, total: 0 };
    }
    if (type === 'cacheHits') {
      this.stats.byMethod[method].hits++;
    } else if (type === 'cacheMisses') {
      this.stats.byMethod[method].misses++;
    } else if (type === 'skipCache') {
      this.stats.byMethod[method].skips++;
    }
    this.stats.byMethod[method].total++;

    // Update path stats
    if (!this.stats.byPath[path]) {
      this.stats.byPath[path] = { hits: 0, misses: 0, skips: 0, total: 0 };
    }
    if (type === 'cacheHits') {
      this.stats.byPath[path].hits++;
    } else if (type === 'cacheMisses') {
      this.stats.byPath[path].misses++;
    } else if (type === 'skipCache') {
      this.stats.byPath[path].skips++;
    }
    this.stats.byPath[path].total++;
  }

  // Stats and monitoring
  getStats(): MiddlewareStats {
    const hitRate = this.stats.totalRequests > 0 ? 
      (this.stats.cacheHits / this.stats.totalRequests) * 100 : 0;
    
    return {
      ...this.stats,
      hitRate
    };
  }

  resetStats(): void {
    this.stats = this.initializeStats();
  }

  // Cache invalidation
  async invalidateCache(pattern: string | RegExp): Promise<boolean> {
    try {
      // This would need to be implemented based on the specific cache system
      // For now, we'll use tag-based invalidation
      return await this.config.cacheIntegration.invalidateByTag('api-response');
    } catch (error) {
      this.logger.error('Failed to invalidate cache:', error);
      return false;
    }
  }
}

// Stats interface
interface MiddlewareStats {
  totalRequests: number;
  cacheHits: number;
  cacheMisses: number;
  cacheSets: number;
  skipCache: number;
  averageResponseTime: number;
  totalResponseTime: number;
  hitRate?: number;
  byMethod: Record<string, { hits: number; misses: number; skips: number; total: number }>;
  byPath: Record<string, { hits: number; misses: number; skips: number; total: number }>;
}

// Default Configuration
export const DEFAULT_CACHE_MIDDLEWARE_CONFIG: CacheMiddlewareConfig = {
  enabled: true,
  cacheIntegration: null as any, // Must be provided
  strategies: {
    get: {
      enabled: true,
      defaultTTL: 300, // 5 minutes
      maxTTL: 3600, // 1 hour
      cacheCondition: {
        statusCode: [200, 301, 302],
        headers: {}
      },
      invalidationRule: {
        onMethod: ['POST', 'PUT', 'PATCH', 'DELETE'],
        paths: [],
        invalidatePaths: [],
        tags: ['api-response'],
        pattern: /.*/
      },
      compressionThreshold: 1024, // 1KB
      includeHeaders: true,
      varyHeaders: ['Accept', 'Accept-Language', 'User-Agent'],
      priority: 'medium'
    },
    post: {
      enabled: false, // Don't cache POST requests by default
      defaultTTL: 0,
      maxTTL: 0,
      cacheCondition: {},
      invalidationRule: {
        onMethod: [],
        paths: [],
        invalidatePaths: [],
        tags: [],
        pattern: /.*/
      },
      compressionThreshold: 0,
      includeHeaders: false,
      varyHeaders: [],
      priority: 'low'
    },
    put: {
      enabled: false,
      defaultTTL: 0,
      maxTTL: 0,
      cacheCondition: {},
      invalidationRule: {
        onMethod: [],
        paths: [],
        invalidatePaths: [],
        tags: [],
        pattern: /.*/
      },
      compressionThreshold: 0,
      includeHeaders: false,
      varyHeaders: [],
      priority: 'low'
    },
    delete: {
      enabled: false,
      defaultTTL: 0,
      maxTTL: 0,
      cacheCondition: {},
      invalidationRule: {
        onMethod: [],
        paths: [],
        invalidatePaths: [],
        tags: [],
        pattern: /.*/
      },
      compressionThreshold: 0,
      includeHeaders: false,
      varyHeaders: [],
      priority: 'low'
    },
    patch: {
      enabled: false,
      defaultTTL: 0,
      maxTTL: 0,
      cacheCondition: {},
      invalidationRule: {
        onMethod: [],
        paths: [],
        invalidatePaths: [],
        tags: [],
        pattern: /.*/
      },
      compressionThreshold: 0,
      includeHeaders: false,
      varyHeaders: [],
      priority: 'low'
    }
  },
  rules: [
    {
      path: '/api/integrations',
      methods: ['GET'],
      ttl: 600, // 10 minutes
      tags: ['integrations'],
      priority: 1,
      enabled: true
    },
    {
      path: '/api/analytics',
      methods: ['GET'],
      ttl: 900, // 15 minutes
      tags: ['analytics'],
      priority: 2,
      enabled: true
    }
  ],
  skipPaths: ['/health', '/metrics', '/favicon.ico', '/robots.txt'],
  skipMethods: ['OPTIONS', 'HEAD'],
  keyGenerator: {
    generate: function(req: Request) {
      return `${req.method}:${req.path}:${JSON.stringify(req.query)}`;
    },
    includeQuery: true,
    includeBody: false,
    includeHeaders: ['Authorization', 'X-API-Key'],
    hashAlgorithm: 'md5',
    prefix: 'atom-api'
  },
  ttlGenerator: {
    generate: function(req: Request, res: Response, defaultTTL: number) {
      // Shorter TTL for frequently changing data
      if (req.path.includes('/realtime') || req.path.includes('/webhooks')) {
        return Math.min(60, defaultTTL); // 1 minute
      }
      return defaultTTL;
    },
    rules: [],
    fallbackTTL: 300,
    maxTTL: 3600
  },
  cacheHeaders: {
    enabled: true,
    hitHeader: 'X-Cache-Status',
    missHeader: 'X-Cache-Miss',
    ttlHeader: 'X-Cache-TTL',
    storageHeader: 'X-Cache-Storage',
    varyHeader: 'X-Cache-Vary'
  }
};

export default AtomCacheMiddleware;