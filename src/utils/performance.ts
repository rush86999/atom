/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { onCLS, onFCP, onLCP, onTTFB, Metric } from 'web-vitals';

export interface PerformanceMetrics {
  cls?: number;
  fid?: number;
  fcp?: number;
  lcp?: number;
  ttfb?: number;
  customMetrics?: Record<string, number>;
  memoryUsage?: number;
  networkRequests?: number;
  jsHeapSize?: number;
  timestamp?: string;
}

export interface PerformanceConfig {
  enableWebVitals?: boolean;
  enableCustomMetrics?: boolean;
  enableRealTimeMonitoring?: boolean;
  enablePredictiveAnalytics?: boolean;
  reportTo?: string;
  sampleRate?: number; // 0-1, percentage of sessions to track
  alertThresholds?: {
    cls?: number;
    fcp?: number;
    lcp?: number;
    ttfb?: number;
    memoryUsage?: number;
  };
}

export interface PerformanceAlert {
  id: string;
  type: 'warning' | 'error' | 'critical';
  metric: string;
  value: number;
  threshold: number;
  timestamp: string;
  message: string;
}

export interface PredictiveInsight {
  metric: string;
  trend: 'improving' | 'degrading' | 'stable';
  prediction: number;
  confidence: number;
  recommendation: string;
  timestamp: string;
}

class PerformanceMonitor {
  private metrics: PerformanceMetrics = {};
  private config: PerformanceConfig;
  private observers: PerformanceObserver[] = [];
  private customMarks: Map<string, number> = new Map();
  private metricsHistory: PerformanceMetrics[] = [];
  private alerts: PerformanceAlert[] = [];
  private realTimeCallbacks: ((metrics: PerformanceMetrics) => void)[] = [];
  private predictiveInsights: PredictiveInsight[] = [];
  private monitoringInterval?: NodeJS.Timeout;

  constructor(config: PerformanceConfig = {}) {
    this.config = {
      enableWebVitals: true,
      enableCustomMetrics: true,
      enableRealTimeMonitoring: false,
      enablePredictiveAnalytics: false,
      sampleRate: 1,
      ...config,
    };

    if (this.shouldTrack()) {
      this.initialize();
    }
  }

  private shouldTrack(): boolean {
    return Math.random() < (this.config.sampleRate || 1);
  }

  private initialize() {
    if (this.config.enableWebVitals) {
      this.initializeWebVitals();
    }

    if (this.config.enableCustomMetrics) {
      this.initializeCustomMetrics();
    }
  }

  private initializeWebVitals() {
    // Check if Performance API is available (not available in test environments like jsdom)
    if (typeof performance === 'undefined' || !performance.getEntriesByType) {
      console.warn('Web Vitals not available: Performance API not supported');
      return;
    }

    try {
      // Cumulative Layout Shift
      onCLS((metric) => {
        this.metrics.cls = metric.value;
        this.reportMetric('CLS', metric.value);
      });

      // First Input Delay - Note: FID is deprecated in favor of INP in newer versions
      // We'll skip FID for now as it's not available in latest web-vitals

      // First Contentful Paint
      onFCP((metric) => {
        this.metrics.fcp = metric.value;
        this.reportMetric('FCP', metric.value);
      });

      // Largest Contentful Paint
      onLCP((metric) => {
        this.metrics.lcp = metric.value;
        this.reportMetric('LCP', metric.value);
      });

      // Time to First Byte
      onTTFB((metric) => {
        this.metrics.ttfb = metric.value;
        this.reportMetric('TTFB', metric.value);
      });
    } catch (e) {
      console.warn('Web Vitals initialization failed:', e);
    }
  }

  private initializeCustomMetrics() {
    // Monitor long tasks
    if ('PerformanceObserver' in window) {
      try {
        const longTaskObserver = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            this.reportMetric('longTask', entry.duration);
          }
        });
        longTaskObserver.observe({ entryTypes: ['longtask'] });
        this.observers.push(longTaskObserver);
      } catch (e) {
        console.warn('Long task monitoring not supported');
      }

      // Monitor navigation timing
      try {
        const navigationObserver = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (entry.entryType === 'navigation') {
              const navEntry = entry as PerformanceNavigationTiming;
              this.reportMetric('domContentLoaded', navEntry.domContentLoadedEventEnd - navEntry.domContentLoadedEventStart);
              this.reportMetric('loadComplete', navEntry.loadEventEnd - navEntry.loadEventStart);
            }
          }
        });
        navigationObserver.observe({ entryTypes: ['navigation'] });
        this.observers.push(navigationObserver);
      } catch (e) {
        console.warn('Navigation timing monitoring not supported');
      }

      // Monitor resource loading
      try {
        const resourceObserver = new PerformanceObserver((list) => {
          let networkRequests = 0;
          for (const entry of list.getEntries()) {
            if (entry.entryType === 'resource') {
              networkRequests++;
            }
          }
          if (networkRequests > 0) {
            this.reportMetric('networkRequests', networkRequests);
          }
        });
        resourceObserver.observe({ entryTypes: ['resource'] });
        this.observers.push(resourceObserver);
      } catch (e) {
        console.warn('Resource monitoring not supported');
      }
    }

    // Initialize real-time monitoring if enabled
    if (this.config.enableRealTimeMonitoring) {
      this.startRealTimeMonitoring();
    }

    // Initialize predictive analytics if enabled
    if (this.config.enablePredictiveAnalytics) {
      this.startPredictiveAnalytics();
    }
  }

  // Custom performance marks and measures
  mark(name: string) {
    if (this.config.enableCustomMetrics && 'performance' in window) {
      performance.mark(name);
      this.customMarks.set(name, performance.now());
    }
  }

  measure(name: string, startMark?: string, endMark?: string) {
    if (this.config.enableCustomMetrics && 'performance' in window) {
      try {
        performance.measure(name, startMark, endMark);
        const measure = performance.getEntriesByName(name)[0];
        if (measure) {
          this.reportMetric(`custom_${name}`, measure.duration);
        }
      } catch (e) {
        console.warn(`Failed to measure ${name}:`, e);
      }
    }
  }

  // Time a function execution
  async timeFunction<T>(
    name: string,
    fn: () => T | Promise<T>
  ): Promise<T> {
    const start = performance.now();
    try {
      const result = await fn();
      const duration = performance.now() - start;
      this.reportMetric(`function_${name}`, duration);
      return result;
    } catch (error) {
      const duration = performance.now() - start;
      this.reportMetric(`function_${name}_error`, duration);
      throw error;
    }
  }

  private async reportMetric(name: string, value: number) {
    // Store locally for debugging
    if (!this.metrics.customMetrics) {
      this.metrics.customMetrics = {};
    }
    this.metrics.customMetrics[name] = value;

    // Update timestamp
    this.metrics.timestamp = new Date().toISOString();

    // Store in history for predictive analytics
    this.metricsHistory.push({ ...this.metrics });

    // Keep only last 100 entries
    if (this.metricsHistory.length > 100) {
      this.metricsHistory.shift();
    }

    // Check for alerts
    this.checkAlerts(name, value);

    // Notify real-time subscribers
    this.notifyRealTimeSubscribers();

    // Report to external service if configured
    if (this.config.reportTo) {
      try {
        await fetch(this.config.reportTo, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            metric: name,
            value,
            timestamp: new Date().toISOString(),
            userAgent: navigator.userAgent,
            url: window.location.href,
          }),
        });
      } catch (e) {
        console.warn('Failed to report performance metric:', e);
      }
    }

    // Log to console in development
    if (process.env.NODE_ENV === 'development') {
      console.log(`Performance: ${name} = ${value.toFixed(2)}ms`);
    }
  }

  private checkAlerts(metricName: string, value: number) {
    const thresholds = this.config.alertThresholds;
    if (!thresholds) return;

    const threshold = thresholds[metricName as keyof typeof thresholds];
    if (threshold !== undefined && value > threshold) {
      const alertType: 'warning' | 'error' | 'critical' =
        value > threshold * 2 ? 'critical' :
        value > threshold * 1.5 ? 'error' : 'warning';

      const alert: PerformanceAlert = {
        id: `${metricName}_${Date.now()}`,
        type: alertType,
        metric: metricName,
        value,
        threshold,
        timestamp: new Date().toISOString(),
        message: `${metricName} exceeded threshold: ${value.toFixed(2)} > ${threshold}`,
      };

      this.alerts.push(alert);

      // Keep only last 50 alerts
      if (this.alerts.length > 50) {
        this.alerts.shift();
      }

      // Log alert
      console.warn(`Performance Alert [${alertType.toUpperCase()}]:`, alert.message);
    }
  }

  private notifyRealTimeSubscribers() {
    this.realTimeCallbacks.forEach(callback => {
      try {
        callback(this.getMetrics());
      } catch (e) {
        console.error('Error in real-time callback:', e);
      }
    });
  }

  private startRealTimeMonitoring() {
    // Monitor memory usage every 30 seconds
    this.monitoringInterval = setInterval(() => {
      if ('memory' in performance) {
        const memory = (performance as any).memory;
        this.reportMetric('memoryUsage', memory.usedJSHeapSize / 1024 / 1024); // MB
        this.reportMetric('jsHeapSize', memory.totalJSHeapSize / 1024 / 1024); // MB
      }
    }, 30000);
  }

  private startPredictiveAnalytics() {
    // Generate insights every 5 minutes
    setInterval(() => {
      this.generatePredictiveInsights();
    }, 300000);
  }

  private generatePredictiveInsights() {
    if (this.metricsHistory.length < 10) return;

    const recentMetrics = this.metricsHistory.slice(-10);
    const metricsToAnalyze = ['fcp', 'lcp', 'cls', 'ttfb'];

    metricsToAnalyze.forEach(metricName => {
      const values = recentMetrics
        .map(m => m[metricName as keyof PerformanceMetrics] as number)
        .filter(v => v !== undefined);

      if (values.length < 5) return;

      const trend = this.calculateTrend(values);
      const prediction = this.predictNextValue(values);
      const confidence = this.calculateConfidence(values);

      let recommendation = '';
      if (trend === 'degrading') {
        recommendation = `Performance is degrading for ${metricName}. Consider optimizing ${this.getOptimizationSuggestion(metricName)}.`;
      } else if (trend === 'improving') {
        recommendation = `Performance is improving for ${metricName}. Keep monitoring.`;
      } else {
        recommendation = `Performance is stable for ${metricName}.`;
      }

      const insight: PredictiveInsight = {
        metric: metricName,
        trend,
        prediction,
        confidence,
        recommendation,
        timestamp: new Date().toISOString(),
      };

      this.predictiveInsights.push(insight);

      // Keep only last 20 insights
      if (this.predictiveInsights.length > 20) {
        this.predictiveInsights.shift();
      }
    });
  }

  private calculateTrend(values: number[]): 'improving' | 'degrading' | 'stable' {
    if (values.length < 3) return 'stable';

    const recent = values.slice(-3);
    const earlier = values.slice(0, 3);

    const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length;
    const earlierAvg = earlier.reduce((a, b) => a + b, 0) / earlier.length;

    const change = (recentAvg - earlierAvg) / earlierAvg;

    if (Math.abs(change) < 0.05) return 'stable'; // Less than 5% change
    return change > 0 ? 'degrading' : 'improving';
  }

  private predictNextValue(values: number[]): number {
    // Simple linear regression for prediction
    const n = values.length;
    const sumX = (n * (n - 1)) / 2;
    const sumY = values.reduce((a, b) => a + b, 0);
    const sumXY = values.reduce((sum, y, x) => sum + x * y, 0);
    const sumXX = (n * (n - 1) * (2 * n - 1)) / 6;

    const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
    const intercept = (sumY - slope * sumX) / n;

    return slope * n + intercept;
  }

  private calculateConfidence(values: number[]): number {
    if (values.length < 2) return 0;

    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    const variance = values.reduce((sum, value) => sum + Math.pow(value - mean, 2), 0) / values.length;
    const stdDev = Math.sqrt(variance);

    // Confidence based on coefficient of variation (lower is better)
    const cv = stdDev / mean;
    return Math.max(0, Math.min(1, 1 - cv));
  }

  private getOptimizationSuggestion(metric: string): string {
    const suggestions: Record<string, string> = {
      fcp: 'images, fonts, or critical CSS',
      lcp: 'the largest content element (usually an image or text block)',
      cls: 'layout shifts by reserving space for dynamic content',
      ttfb: 'server response time or network latency',
    };
    return suggestions[metric] || 'performance bottlenecks';
  }

  getMetrics(): PerformanceMetrics {
    return { ...this.metrics };
  }

  getMetricsHistory(): PerformanceMetrics[] {
    return [...this.metricsHistory];
  }

  getAlerts(): PerformanceAlert[] {
    return [...this.alerts];
  }

  getPredictiveInsights(): PredictiveInsight[] {
    return [...this.predictiveInsights];
  }

  subscribeToRealTimeUpdates(callback: (metrics: PerformanceMetrics) => void): () => void {
    this.realTimeCallbacks.push(callback);
    return () => {
      const index = this.realTimeCallbacks.indexOf(callback);
      if (index > -1) {
        this.realTimeCallbacks.splice(index, 1);
      }
    };
  }

  // Cleanup observers
  destroy() {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
    }
    this.observers.forEach(observer => observer.disconnect());
    this.observers = [];
    this.realTimeCallbacks = [];
  }
}

// Singleton instance
let performanceMonitor: PerformanceMonitor | null = null;

export const initializePerformanceMonitoring = (config?: PerformanceConfig) => {
  if (!performanceMonitor) {
    performanceMonitor = new PerformanceMonitor(config);
  }
  return performanceMonitor;
};

export const getPerformanceMonitor = () => {
  if (!performanceMonitor) {
    performanceMonitor = new PerformanceMonitor();
  }
  return performanceMonitor;
};

// React hook for performance monitoring
export const usePerformanceMonitor = () => {
  return getPerformanceMonitor();
};

// Utility functions for common performance measurements
export const measureRenderTime = (componentName: string) => {
  const monitor = getPerformanceMonitor();
  return {
    start: () => monitor.mark(`${componentName}_render_start`),
    end: () => {
      monitor.mark(`${componentName}_render_end`);
      monitor.measure(`${componentName}_render`, `${componentName}_render_start`, `${componentName}_render_end`);
    },
  };
};

export const measureApiCall = async <T>(
  apiName: string,
  apiCall: () => Promise<T>
): Promise<T> => {
  const monitor = getPerformanceMonitor();
  return monitor.timeFunction(`api_${apiName}`, apiCall);
};

// Performance thresholds for Core Web Vitals
export const PERFORMANCE_THRESHOLDS = {
  CLS: { good: 0.1, needsImprovement: 0.25 },
  FID: { good: 100, needsImprovement: 300 },
  FCP: { good: 1800, needsImprovement: 3000 },
  LCP: { good: 2500, needsImprovement: 4000 },
  TTFB: { good: 800, needsImprovement: 1800 },
} as const;

export const getPerformanceScore = (metrics: PerformanceMetrics): 'good' | 'needs-improvement' | 'poor' => {
  const scores: ('good' | 'needs-improvement' | 'poor')[] = [];

  if (metrics.cls !== undefined) {
    if (metrics.cls <= PERFORMANCE_THRESHOLDS.CLS.good) scores.push('good');
    else if (metrics.cls <= PERFORMANCE_THRESHOLDS.CLS.needsImprovement) scores.push('needs-improvement');
    else scores.push('poor');
  }

  if (metrics.fid !== undefined) {
    if (metrics.fid <= PERFORMANCE_THRESHOLDS.FID.good) scores.push('good');
    else if (metrics.fid <= PERFORMANCE_THRESHOLDS.FID.needsImprovement) scores.push('needs-improvement');
    else scores.push('poor');
  }

  if (metrics.fcp !== undefined) {
    if (metrics.fcp <= PERFORMANCE_THRESHOLDS.FCP.good) scores.push('good');
    else if (metrics.fcp <= PERFORMANCE_THRESHOLDS.FCP.needsImprovement) scores.push('needs-improvement');
    else scores.push('poor');
  }

  if (metrics.lcp !== undefined) {
    if (metrics.lcp <= PERFORMANCE_THRESHOLDS.LCP.good) scores.push('good');
    else if (metrics.lcp <= PERFORMANCE_THRESHOLDS.LCP.needsImprovement) scores.push('needs-improvement');
    else scores.push('poor');
  }

  if (metrics.ttfb !== undefined) {
    if (metrics.ttfb <= PERFORMANCE_THRESHOLDS.TTFB.good) scores.push('good');
    else if (metrics.ttfb <= PERFORMANCE_THRESHOLDS.TTFB.needsImprovement) scores.push('needs-improvement');
    else scores.push('poor');
  }

  // Return the worst score
  if (scores.includes('poor')) return 'poor';
  if (scores.includes('needs-improvement')) return 'needs-improvement';
  return 'good';
};
