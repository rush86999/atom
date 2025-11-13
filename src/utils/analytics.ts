import React from 'react';

/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export interface AnalyticsEvent {
  name: string;
  category: string;
  action: string;
  label?: string;
  value?: number;
  properties?: Record<string, any>;
  timestamp: string;
  sessionId: string;
  userId?: string;
  userAgent: string;
  url: string;
  referrer?: string;
}

export interface AnalyticsConfig {
  enabled?: boolean;
  trackingId?: string;
  endpoint?: string;
  sampleRate?: number; // 0-1, percentage of events to track
  debug?: boolean;
  anonymizeIp?: boolean;
  respectDoNotTrack?: boolean;
}

class AnalyticsTracker {
  private config: AnalyticsConfig;
  private sessionId: string;
  private eventQueue: AnalyticsEvent[] = [];
  private isInitialized = false;

  constructor(config: AnalyticsConfig = {}) {
    this.config = {
      enabled: true,
      sampleRate: 1,
      debug: process.env.NODE_ENV === 'development',
      anonymizeIp: true,
      respectDoNotTrack: true,
      ...config,
    };

    this.sessionId = this.generateSessionId();

    if (this.shouldInitialize()) {
      this.initialize();
    }
  }

  private shouldInitialize(): boolean {
    if (!this.config.enabled) return false;
    if (this.config.respectDoNotTrack && this.isDoNotTrackEnabled()) return false;
    return true;
  }

  private isDoNotTrackEnabled(): boolean {
    return navigator.doNotTrack === '1' || (window as any).doNotTrack === '1';
  }

  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private initialize() {
    this.isInitialized = true;

    // Track initial page view
    this.trackPageView();

    // Track navigation changes
    this.trackNavigation();

    // Track user engagement
    this.trackEngagement();

    if (this.config.debug) {
      console.log('Analytics initialized with config:', this.config);
    }
  }

  // Track page views
  trackPageView(page?: string, title?: string) {
    if (!this.isInitialized) return;

    const event: AnalyticsEvent = {
      name: 'page_view',
      category: 'navigation',
      action: 'view',
      label: page || window.location.pathname,
      properties: {
        title: title || document.title,
        path: window.location.pathname,
        search: window.location.search,
        hash: window.location.hash,
      },
      timestamp: new Date().toISOString(),
      sessionId: this.sessionId,
      userAgent: navigator.userAgent,
      url: window.location.href,
      referrer: document.referrer,
    };

    this.sendEvent(event);
  }

  // Track user interactions
  trackEvent(
    category: string,
    action: string,
    label?: string,
    value?: number,
    properties?: Record<string, any>
  ) {
    if (!this.isInitialized) return;

    const event: AnalyticsEvent = {
      name: `${category}_${action}`,
      category,
      action,
      label,
      value,
      properties,
      timestamp: new Date().toISOString(),
      sessionId: this.sessionId,
      userAgent: navigator.userAgent,
      url: window.location.href,
    };

    this.sendEvent(event);
  }

  // Track button clicks
  trackButtonClick(buttonName: string, properties?: Record<string, any>) {
    this.trackEvent('interaction', 'click', buttonName, undefined, properties);
  }

  // Track form submissions
  trackFormSubmit(formName: string, success: boolean, properties?: Record<string, any>) {
    this.trackEvent(
      'form',
      success ? 'submit_success' : 'submit_error',
      formName,
      undefined,
      properties
    );
  }

  // Track search queries
  trackSearch(query: string, resultsCount?: number, properties?: Record<string, any>) {
    this.trackEvent('search', 'query', query, resultsCount, properties);
  }

  // Track feature usage
  trackFeatureUsage(featureName: string, action: string, properties?: Record<string, any>) {
    this.trackEvent('feature', action, featureName, undefined, properties);
  }

  // Track errors
  trackError(error: Error, context?: Record<string, any>) {
    this.trackEvent('error', 'occurred', error.message, undefined, {
      stack: error.stack,
      name: error.name,
      ...context,
    });
  }

  // Track performance metrics
  trackPerformance(metricName: string, value: number, properties?: Record<string, any>) {
    this.trackEvent('performance', metricName, undefined, value, properties);
  }

  // Track user engagement
  private trackEngagement() {
    let lastActivity = Date.now();
    let pageVisible = true;

    // Track mouse movements (throttled)
    let mouseMoveTimeout: NodeJS.Timeout;
    document.addEventListener('mousemove', () => {
      if (mouseMoveTimeout) return;
      mouseMoveTimeout = setTimeout(() => {
        lastActivity = Date.now();
        mouseMoveTimeout = undefined as any;
      }, 1000);
    });

    // Track clicks
    document.addEventListener('click', () => {
      lastActivity = Date.now();
    });

    // Track scrolling
    let scrollTimeout: NodeJS.Timeout;
    document.addEventListener('scroll', () => {
      if (scrollTimeout) return;
      scrollTimeout = setTimeout(() => {
        this.trackEvent('engagement', 'scroll', window.location.pathname);
        scrollTimeout = undefined as any;
      }, 1000);
    });

    // Track page visibility
    document.addEventListener('visibilitychange', () => {
      pageVisible = !document.hidden;
      if (pageVisible) {
        this.trackEvent('engagement', 'page_focus', window.location.pathname);
      } else {
        this.trackEvent('engagement', 'page_blur', window.location.pathname);
      }
    });

    // Track time spent on page
    setInterval(() => {
      if (pageVisible && Date.now() - lastActivity < 30000) { // Active within last 30 seconds
        this.trackEvent('engagement', 'active_time', window.location.pathname, 30);
      }
    }, 30000);
  }

  // Track navigation changes
  private trackNavigation() {
    // Listen for browser navigation
    window.addEventListener('popstate', () => {
      this.trackPageView();
    });

    // For single-page apps, you might want to call trackPageView() manually
    // when routes change
  }

  // Send event to analytics service
  private async sendEvent(event: AnalyticsEvent) {
    if (!this.shouldSendEvent()) return;

    // Add to queue for batching
    this.eventQueue.push(event);

    // Send immediately or batch
    if (this.config.endpoint) {
      await this.flushEvents();
    } else if (this.config.debug) {
      console.log('Analytics event:', event);
    }
  }

  private shouldSendEvent(): boolean {
    return Math.random() < (this.config.sampleRate || 1);
  }

  private async flushEvents() {
    if (this.eventQueue.length === 0 || !this.config.endpoint) return;

    const events = [...this.eventQueue];
    this.eventQueue = [];

    try {
      await fetch(this.config.endpoint!, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          events,
          trackingId: this.config.trackingId,
        }),
      });
    } catch (error) {
      console.warn('Failed to send analytics events:', error);
      // Re-queue events for retry
      this.eventQueue.unshift(...events);
    }
  }

  // Set user properties
  setUserId(userId: string) {
    this.sessionId = `user_${userId}_${Date.now()}`;
  }

  // Get current session info
  getSessionInfo() {
    return {
      sessionId: this.sessionId,
      userAgent: navigator.userAgent,
      url: window.location.href,
      referrer: document.referrer,
      timestamp: new Date().toISOString(),
    };
  }

  // Cleanup
  destroy() {
    this.flushEvents();
    this.isInitialized = false;
  }
}

// Singleton instance
let analyticsTracker: AnalyticsTracker | null = null;

export const initializeAnalytics = (config?: AnalyticsConfig) => {
  if (!analyticsTracker) {
    analyticsTracker = new AnalyticsTracker(config);
  }
  return analyticsTracker;
};

export const getAnalyticsTracker = () => {
  if (!analyticsTracker) {
    analyticsTracker = new AnalyticsTracker();
  }
  return analyticsTracker;
};

// React hook for analytics
export const useAnalytics = () => {
  return getAnalyticsTracker();
};

// Utility functions for common tracking
export const trackButtonClick = (buttonName: string, properties?: Record<string, any>) => {
  getAnalyticsTracker().trackButtonClick(buttonName, properties);
};

export const trackFormSubmit = (formName: string, success: boolean, properties?: Record<string, any>) => {
  getAnalyticsTracker().trackFormSubmit(formName, success, properties);
};

export const trackSearch = (query: string, resultsCount?: number, properties?: Record<string, any>) => {
  getAnalyticsTracker().trackSearch(query, resultsCount, properties);
};

export const trackFeatureUsage = (featureName: string, action: string, properties?: Record<string, any>) => {
  getAnalyticsTracker().trackFeatureUsage(featureName, action, properties);
};

export const trackError = (error: Error, context?: Record<string, any>) => {
  getAnalyticsTracker().trackError(error, context);
};

export const trackPerformance = (metricName: string, value: number, properties?: Record<string, any>) => {
  getAnalyticsTracker().trackPerformance(metricName, value, properties);
};

// Higher-order component for tracking component interactions
export function withAnalyticsTracking<P extends object>(
  Component: React.ComponentType<P>,
  componentName: string
) {
  const TrackedComponent: React.FC<P> = (props: P) => {
    React.useEffect(() => {
      trackFeatureUsage(componentName, 'mount');
      return () => {
        trackFeatureUsage(componentName, 'unmount');
      };
    }, []);

    return React.createElement(Component, props);
  };

  TrackedComponent.displayName = `withAnalyticsTracking(${Component.displayName || Component.name})`;
  return TrackedComponent;
}
