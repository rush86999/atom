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
}

export interface PerformanceConfig {
  enableWebVitals?: boolean;
  enableCustomMetrics?: boolean;
  reportTo?: string;
  sampleRate?: number; // 0-1, percentage of sessions to track
}

class PerformanceMonitor {
  private metrics: PerformanceMetrics = {};
  private config: PerformanceConfig;
  private observers: PerformanceObserver[] = [];
  private customMarks: Map<string, number> = new Map();

  constructor(config: PerformanceConfig = {}) {
    this.config = {
      enableWebVitals: true,
      enableCustomMetrics: true,
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

  getMetrics(): PerformanceMetrics {
    return { ...this.metrics };
  }

  // Cleanup observers
  destroy() {
    this.observers.forEach(observer => observer.disconnect());
    this.observers = [];
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
