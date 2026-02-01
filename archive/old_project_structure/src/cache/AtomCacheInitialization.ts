/**
 * ATOM Cache Initialization Script
 * Sets up Redis cache service and integrates with ATOM platform
 * Provides performance optimization for all integrations and services
 */

import { AtomCacheService, AtomCacheServiceFactory, DEFAULT_CACHE_CONFIG } from './services/cache/AtomCacheService';
import { AtomCacheIntegration, AtomCacheIntegrationFactory } from './services/cache/AtomCacheIntegration';
import AtomCacheMiddleware from './services/cache/AtomCacheMiddleware';
import { Logger } from './utils/logger';

// Express/FastAPI app type (adjust based on your framework)
declare const require: any;
const express = require('express') || null;

interface AtomApp {
  use?: (middleware: any) => void;
  listen?: (port: number, callback?: () => void) => void;
}

export interface CacheInitializationConfig {
  enabled: boolean;
  redis: {
    host: string;
    port: number;
    password?: string;
    db: number;
  };
  middleware: {
    enabled: boolean;
    skipPaths: string[];
    ttl: {
      api: number;
      files: number;
      assets: number;
      sessions: number;
    };
  };
  monitoring: {
    enabled: boolean;
    dashboard: boolean;
    metrics: boolean;
    alerts: boolean;
  };
  optimization: {
    autoOptimize: boolean;
    compression: boolean;
    encryption: boolean;
    backgroundRefresh: boolean;
  };
}

// Default Configuration
export const DEFAULT_INITIALIZATION_CONFIG: CacheInitializationConfig = {
  enabled: true,
  redis: {
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT || '6379'),
    password: process.env.REDIS_PASSWORD,
    db: parseInt(process.env.REDIS_DB || '0')
  },
  middleware: {
    enabled: true,
    skipPaths: ['/health', '/metrics', '/favicon.ico', '/robots.txt'],
    ttl: {
      api: 300, // 5 minutes
      files: 1800, // 30 minutes
      assets: 3600, // 1 hour
      sessions: 7200 // 2 hours
    }
  },
  monitoring: {
    enabled: true,
    dashboard: true,
    metrics: true,
    alerts: true
  },
  optimization: {
    autoOptimize: true,
    compression: true,
    encryption: true,
    backgroundRefresh: true
  }
};

// Cache Initialization Service
export class AtomCacheInitialization {
  private logger: Logger;
  private config: CacheInitializationConfig;
  private cacheService: AtomCacheService | null = null;
  private cacheIntegration: AtomCacheIntegration | null = null;
  private middleware: AtomCacheMiddleware | null = null;

  constructor(config: CacheInitializationConfig = DEFAULT_INITIALIZATION_CONFIG) {
    this.logger = new Logger('AtomCacheInitialization');
    this.config = config;
  }

  // Main initialization method
  async initialize(app?: AtomApp): Promise<boolean> {
    try {
      this.logger.info('Initializing ATOM Cache System...');

      // Step 1: Validate configuration
      await this.validateConfiguration();

      // Step 2: Initialize Redis Cache Service
      await this.initializeCacheService();

      // Step 3: Initialize Cache Integration
      await this.initializeCacheIntegration();

      // Step 4: Initialize Cache Middleware
      if (this.config.middleware.enabled && app) {
        await this.initializeCacheMiddleware(app);
      }

      // Step 5: Setup Monitoring
      await this.setupMonitoring();

      // Step 6: Setup Auto-optimization
      if (this.config.optimization.autoOptimize) {
        await this.setupAutoOptimization();
      }

      // Step 7: Cache Warm-up
      await this.performCacheWarmup();

      this.logger.info('ATOM Cache System initialized successfully');
      return true;

    } catch (error) {
      this.logger.error('Failed to initialize ATOM Cache System:', error);
      return false;
    }
  }

  private async validateConfiguration(): Promise<void> {
    this.logger.info('Validating cache configuration...');

    // Validate Redis configuration
    if (!this.config.redis.host) {
      throw new Error('Redis host is required');
    }

    if (!this.config.redis.port || this.config.redis.port <= 0) {
      throw new Error('Valid Redis port is required');
    }

    // Validate environment variables
    const requiredEnvVars = ['NODE_ENV'];
    for (const envVar of requiredEnvVars) {
      if (!process.env[envVar]) {
        this.logger.warn(`Environment variable ${envVar} is not set`);
      }
    }

    this.logger.info('Cache configuration validated');
  }

  private async initializeCacheService(): Promise<void> {
    this.logger.info('Initializing Redis Cache Service...');

    const cacheConfig = {
      ...DEFAULT_CACHE_CONFIG,
      redis: {
        ...DEFAULT_CACHE_CONFIG.redis,
        host: this.config.redis.host,
        port: this.config.redis.port,
        password: this.config.redis.password,
        db: this.config.redis.db
      },
      strategies: {
        ...DEFAULT_CACHE_CONFIG.strategies,
        apiResponses: {
          ...DEFAULT_CACHE_CONFIG.strategies.apiResponses,
          ttl: this.config.middleware.ttl.api
        },
        designAssets: {
          ...DEFAULT_CACHE_CONFIG.strategies.designAssets,
          ttl: this.config.middleware.ttl.assets
        },
        fileMetadata: {
          ...DEFAULT_CACHE_CONFIG.strategies.fileMetadata,
          ttl: this.config.middleware.ttl.files
        },
        userSessions: {
          ...DEFAULT_CACHE_CONFIG.strategies.userSessions,
          ttl: this.config.middleware.ttl.sessions,
          compression: this.config.optimization.compression,
          encryption: this.config.optimization.encryption,
          backgroundRefresh: this.config.optimization.backgroundRefresh
        }
      },
      monitoring: {
        ...DEFAULT_CACHE_CONFIG.monitoring,
        enabled: this.config.monitoring.metrics
      }
    };

    this.cacheService = new AtomCacheService(cacheConfig);
    AtomCacheServiceFactory.getInstance(this.cacheService);

    this.logger.info('Redis Cache Service initialized');
  }

  private async initializeCacheIntegration(): Promise<void> {
    this.logger.info('Initializing Cache Integration Layer...');

    if (!this.cacheService) {
      throw new Error('Cache Service must be initialized first');
    }

    this.cacheIntegration = new AtomCacheIntegration(this.cacheService);
    AtomCacheIntegrationFactory.getInstance(this.cacheIntegration);

    this.logger.info('Cache Integration Layer initialized');
  }

  private async initializeCacheMiddleware(app: AtomApp): Promise<void> {
    this.logger.info('Initializing Cache Middleware...');

    if (!this.cacheIntegration) {
      throw new Error('Cache Integration must be initialized first');
    }

    if (!app || !app.use) {
      this.logger.warn('App does not support middleware, skipping cache middleware');
      return;
    }

    const middlewareConfig = {
      ...DEFAULT_CACHE_MIDDLEWARE_CONFIG,
      enabled: true,
      cacheIntegration: this.cacheIntegration,
      skipPaths: this.config.middleware.skipPaths
    };

    this.middleware = new AtomCacheMiddleware(middlewareConfig);
    app.use(this.middleware.middleware());

    this.logger.info('Cache Middleware initialized');
  }

  private async setupMonitoring(): Promise<void> {
    if (!this.config.monitoring.enabled) {
      this.logger.info('Monitoring disabled, skipping setup');
      return;
    }

    this.logger.info('Setting up monitoring...');

    // Setup metrics collection
    if (this.config.monitoring.metrics) {
      await this.setupMetricsCollection();
    }

    // Setup performance dashboard
    if (this.config.monitoring.dashboard) {
      await this.setupPerformanceDashboard();
    }

    // Setup alerts
    if (this.config.monitoring.alerts) {
      await this.setupAlerts();
    }

    this.logger.info('Monitoring setup complete');
  }

  private async setupMetricsCollection(): Promise<void> {
    this.logger.info('Setting up metrics collection...');

    // Setup periodic metrics collection
    setInterval(async () => {
      try {
        if (this.cacheService) {
          const metrics = await this.cacheService.getMetrics();
          
          // Log key metrics
          this.logger.info('Cache Metrics:', {
            hitRate: `${metrics.hitRate.toFixed(2)}%`,
            averageResponseTime: `${metrics.averageResponseTime.toFixed(2)}ms`,
            memoryUsage: `${metrics.memoryUsage.percentage.toFixed(2)}%`,
            errorRate: `${metrics.errorRate.toFixed(2)}%`
          });

          // Store metrics for dashboard
          if (this.config.monitoring.dashboard) {
            // This would store metrics in your monitoring system
            await this.storeMetrics(metrics);
          }
        }
      } catch (error) {
        this.logger.error('Error collecting metrics:', error);
      }
    }, 30000); // Every 30 seconds
  }

  private async setupPerformanceDashboard(): Promise<void> {
    this.logger.info('Setting up performance dashboard...');

    // Setup dashboard route (if using Express)
    if (express && this.middleware) {
      try {
        const app = express();
        
        // Dashboard route
        app.get('/dashboard/performance', (req: any, res: any) => {
          // This would serve the React dashboard component
          res.json({
            message: 'Performance Dashboard',
            cacheService: !!this.cacheService,
            middleware: !!this.middleware,
            monitoring: this.config.monitoring
          });
        });

        // Metrics API route
        app.get('/api/performance/metrics', async (req: any, res: any) => {
          try {
            if (this.cacheService) {
              const metrics = await this.cacheService.getMetrics();
              res.json(metrics);
            } else {
              res.status(503).json({ error: 'Cache service not available' });
            }
          } catch (error) {
            res.status(500).json({ error: error.message });
          }
        });

        // Health check route
        app.get('/api/performance/health', async (req: any, res: any) => {
          try {
            if (this.cacheService) {
              const metrics = await this.cacheService.getMetrics();
              const isHealthy = metrics.errorRate < 5 && metrics.hitRate > 70;
              
              res.status(isHealthy ? 200 : 503).json({
                status: isHealthy ? 'healthy' : 'degraded',
                metrics: {
                  hitRate: metrics.hitRate,
                  errorRate: metrics.errorRate,
                  memoryUsage: metrics.memoryUsage.percentage
                }
              });
            } else {
              res.status(503).json({ status: 'unavailable', error: 'Cache service not available' });
            }
          } catch (error) {
            res.status(500).json({ status: 'error', error: error.message });
          }
        });

        this.logger.info('Performance dashboard routes configured');

      } catch (error) {
        this.logger.warn('Failed to setup dashboard routes:', error);
      }
    }
  }

  private async setupAlerts(): Promise<void> {
    this.logger.info('Setting up alerts...');

    // Setup alert monitoring
    setInterval(async () => {
      try {
        if (this.cacheService) {
          const metrics = await this.cacheService.getMetrics();
          
          // Check for alert conditions
          const alerts = [];

          // Cache hit rate alert
          if (metrics.hitRate < 70) {
            alerts.push({
              type: 'warning',
              severity: 'medium',
              title: 'Low Cache Hit Rate',
              description: `Cache hit rate is ${metrics.hitRate.toFixed(2)}%, below target of 70%`,
              metric: 'hitRate',
              value: metrics.hitRate,
              threshold: 70
            });
          }

          // Error rate alert
          if (metrics.errorRate > 5) {
            alerts.push({
              type: 'error',
              severity: 'high',
              title: 'High Cache Error Rate',
              description: `Cache error rate is ${metrics.errorRate.toFixed(2)}%, above threshold of 5%`,
              metric: 'errorRate',
              value: metrics.errorRate,
              threshold: 5
            });
          }

          // Memory usage alert
          if (metrics.memoryUsage.percentage > 80) {
            alerts.push({
              type: 'error',
              severity: 'critical',
              title: 'High Memory Usage',
              description: `Cache memory usage is ${metrics.memoryUsage.percentage.toFixed(2)}%, above threshold of 80%`,
              metric: 'memoryUsage',
              value: metrics.memoryUsage.percentage,
              threshold: 80
            });
          }

          // Response time alert
          if (metrics.averageResponseTime > 1000) {
            alerts.push({
              type: 'warning',
              severity: 'medium',
              title: 'High Response Time',
              description: `Cache response time is ${metrics.averageResponseTime.toFixed(2)}ms, above threshold of 1000ms`,
              metric: 'averageResponseTime',
              value: metrics.averageResponseTime,
              threshold: 1000
            });
          }

          // Send alerts (this would integrate with your alerting system)
          for (const alert of alerts) {
            await this.sendAlert(alert);
          }

        }
      } catch (error) {
        this.logger.error('Error checking alerts:', error);
      }
    }, 60000); // Every minute
  }

  private async setupAutoOptimization(): Promise<void> {
    this.logger.info('Setting up auto-optimization...');

    // Setup periodic optimization
    setInterval(async () => {
      try {
        if (this.cacheService) {
          const metrics = await this.cacheService.getMetrics();
          
          // Auto-optimize based on metrics
          await this.performAutoOptimization(metrics);
        }
      } catch (error) {
        this.logger.error('Error performing auto-optimization:', error);
      }
    }, 300000); // Every 5 minutes
  }

  private async performCacheWarmup(): Promise<void> {
    this.logger.info('Performing cache warm-up...');

    try {
      // Warm up frequently accessed data
      const warmupTasks = [
        this.warmupUserSessions(),
        this.warmupIntegrationData(),
        this.warmupSystemSettings()
      ];

      await Promise.allSettled(warmupTasks);
      this.logger.info('Cache warm-up completed');

    } catch (error) {
      this.logger.error('Error during cache warm-up:', error);
    }
  }

  private async warmupUserSessions(): Promise<void> {
    if (!this.cacheIntegration) return;

    try {
      // This would load active user sessions into cache
      this.logger.debug('Warming up user sessions');
      // Implementation would depend on your user system
    } catch (error) {
      this.logger.error('Error warming up user sessions:', error);
    }
  }

  private async warmupIntegrationData(): Promise<void> {
    if (!this.cacheIntegration) return;

    try {
      // This would load frequently accessed integration data
      this.logger.debug('Warming up integration data');
      
      const integrations = ['figma', 'github', 'slack', 'notion'];
      for (const integration of integrations) {
        // Cache basic integration info
        await this.cacheIntegration.cacheIntegrationData(
          integration as any,
          'info',
          {},
          { active: true, lastSync: new Date().toISOString() }
        );
      }
    } catch (error) {
      this.logger.error('Error warming up integration data:', error);
    }
  }

  private async warmupSystemSettings(): Promise<void> {
    if (!this.cacheIntegration) return;

    try {
      // This would load system settings into cache
      this.logger.debug('Warming up system settings');
      
      await this.cacheIntegration.cacheIntegrationData(
        'system',
        'settings',
        {},
        {
          cacheEnabled: this.config.enabled,
          monitoringEnabled: this.config.monitoring.enabled,
          autoOptimizeEnabled: this.config.optimization.autoOptimize
        }
      );
    } catch (error) {
      this.logger.error('Error warming up system settings:', error);
    }
  }

  private async storeMetrics(metrics: any): Promise<void> {
    // This would store metrics in your monitoring system
    // For example: InfluxDB, Prometheus, DataDog, etc.
    this.logger.debug('Storing metrics:', {
      hitRate: metrics.hitRate,
      operations: metrics.totalOperations,
      memoryUsage: metrics.memoryUsage.percentage
    });
  }

  private async sendAlert(alert: any): Promise<void> {
    // This would send alerts through your alerting system
    // For example: Slack, Email, SMS, PagerDuty, etc.
    this.logger.warn('ALERT:', alert);
  }

  private async performAutoOptimization(metrics: any): Promise<void> {
    this.logger.debug('Performing auto-optimization...');

    const optimizations = [];

    // Optimize based on hit rate
    if (metrics.hitRate < 70) {
      optimizations.push({
        type: 'increase_ttl',
        description: 'Increase TTL for better cache utilization',
        target: 'apiResponses'
      });
    }

    // Optimize based on memory usage
    if (metrics.memoryUsage.percentage > 80) {
      optimizations.push({
        type: 'cleanup_cache',
        description: 'Clean up cache to free memory',
        target: 'all'
      });
    }

    // Apply optimizations
    for (const optimization of optimizations) {
      await this.applyOptimization(optimization);
    }
  }

  private async applyOptimization(optimization: any): Promise<void> {
    this.logger.info('Applying optimization:', optimization);
    
    switch (optimization.type) {
      case 'increase_ttl':
        // This would adjust TTL settings
        break;
      case 'cleanup_cache':
        // This would perform cache cleanup
        if (this.cacheService) {
          await this.cacheService.clear();
        }
        break;
      default:
        this.logger.warn('Unknown optimization type:', optimization.type);
    }
  }

  // Shutdown method
  async shutdown(): Promise<void> {
    this.logger.info('Shutting down ATOM Cache System...');

    if (this.cacheService) {
      await this.cacheService.shutdown();
      this.cacheService = null;
    }

    this.cacheIntegration = null;
    this.middleware = null;

    this.logger.info('ATOM Cache System shutdown complete');
  }

  // Get cache service instance
  getCacheService(): AtomCacheService | null {
    return this.cacheService;
  }

  // Get cache integration instance
  getCacheIntegration(): AtomCacheIntegration | null {
    return this.cacheIntegration;
  }

  // Get middleware instance
  getMiddleware(): AtomCacheMiddleware | null {
    return this.middleware;
  }
}

// Factory for easy initialization
export class AtomCacheInitializationFactory {
  private static instance: AtomCacheInitialization;

  static async getInstance(config?: CacheInitializationConfig, app?: AtomApp): Promise<AtomCacheInitialization> {
    if (!this.instance) {
      const initConfig = config || DEFAULT_INITIALIZATION_CONFIG;
      this.instance = new AtomCacheInitialization(initConfig);
      await this.instance.initialize(app);
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

// Export initialization function for easy use
export const initializeAtomCache = async (config?: CacheInitializationConfig, app?: AtomApp): Promise<boolean> => {
  try {
    const cacheInit = new AtomCacheInitialization(config);
    return await cacheInit.initialize(app);
  } catch (error) {
    console.error('Failed to initialize ATOM Cache:', error);
    return false;
  }
};

export default AtomCacheInitialization;