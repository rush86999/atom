// Google Analytics and Error Handling Service
import { invoke } from '@tauri-apps/api/tauri';
import { writeTextFile, exists, createDir } from '@tauri-apps/api/fs';
import { appDataDir, join } from '@tauri-apps/api/path';

interface AnalyticsEvent {
  id: string;
  type: 'api_call' | 'error' | 'performance' | 'usage' | 'security';
  timestamp: number;
  userId: string;
  service: 'gmail' | 'calendar' | 'drive' | 'oauth';
  action: string;
  data: any;
  metadata: {
    duration?: number;
    success: boolean;
    errorCode?: string;
    errorMessage?: string;
    userAgent?: string;
    platform?: string;
    version?: string;
  };
}

interface PerformanceMetric {
  timestamp: number;
  userId: string;
  service: string;
  action: string;
  duration: number;
  success: boolean;
  cacheHit: boolean;
  batchSize?: number;
  responseSize?: number;
}

interface ErrorReport {
  id: string;
  timestamp: number;
  userId: string;
  error: {
    code: string;
    message: string;
    stack?: string;
    type: 'api_error' | 'network_error' | 'auth_error' | 'validation_error' | 'system_error';
    severity: 'low' | 'medium' | 'high' | 'critical';
  };
  context: {
    service: string;
    action: string;
    parameters: any;
    retryCount: number;
    cacheKey?: string;
  };
  resolution?: {
    attempt: number;
    success: boolean;
    resolutionTime: number;
    resolutionAction: string;
  };
}

interface UsageStatistics {
  userId: string;
  date: string;
  gmail: {
    emailsSent: number;
    emailsRead: number;
    emailsDeleted: number;
    searchesPerformed: number;
  };
  calendar: {
    eventsCreated: number;
    eventsUpdated: number;
    eventsDeleted: number;
    calendarsAccessed: number;
  };
  drive: {
    filesUploaded: number;
    filesDownloaded: number;
    filesShared: number;
    filesDeleted: number;
    searchesPerformed: number;
  };
  totals: {
    apiCalls: number;
    dataTransferred: number;
    errorsEncountered: number;
  };
}

interface AnalyticsConfig {
  enabled: boolean;
  errorReporting: boolean;
  performanceTracking: boolean;
  usageTracking: boolean;
  dataRetention: number; // days
  batchSize: number;
  uploadInterval: number; // minutes
  anonymizeData: boolean;
}

export class GoogleAnalyticsService {
  private static instance: GoogleAnalyticsService;
  private userId: string = '';
  private config: AnalyticsConfig;
  private events: AnalyticsEvent[] = [];
  private errors: ErrorReport[] = [];
  private metrics: PerformanceMetric[] = [];
  private dataDir: string = '';
  private uploadTimer: NodeJS.Timeout | null = null;

  private constructor() {
    this.config = {
      enabled: true,
      errorReporting: true,
      performanceTracking: true,
      usageTracking: true,
      dataRetention: 30, // 30 days
      batchSize: 100,
      uploadInterval: 60, // 1 hour
      anonymizeData: false
    };
  }

  static getInstance(): GoogleAnalyticsService {
    if (!GoogleAnalyticsService.instance) {
      GoogleAnalyticsService.instance = new GoogleAnalyticsService();
    }
    return GoogleAnalyticsService.instance;
  }

  // Initialize analytics service
  async initialize(userId: string): Promise<void> {
    try {
      this.userId = userId;
      this.dataDir = await appDataDir();
      await createDir(this.dataDir);
      
      // Load existing data
      await this.loadAnalyticsData();
      
      // Start upload timer
      this.startUploadTimer();
      
      // Clean up old data
      await this.cleanupOldData();
    } catch (error) {
      console.error('Failed to initialize Google analytics:', error);
    }
  }

  // Track API call
  trackApiCall(
    service: 'gmail' | 'calendar' | 'drive' | 'oauth',
    action: string,
    data: any,
    success: boolean,
    duration: number
  ): void {
    if (!this.config.enabled) return;

    const event: AnalyticsEvent = {
      id: this.generateId(),
      type: 'api_call',
      timestamp: Date.now(),
      userId: this.userId,
      service,
      action,
      data: this.anonymizeData ? this.anonymize(data) : data,
      metadata: {
        duration,
        success,
        userAgent: this.getUserAgent(),
        platform: this.getPlatform(),
        version: this.getVersion()
      }
    };

    this.events.push(event);
    this.checkBatchSize();
  }

  // Track performance metric
  trackPerformance(
    service: string,
    action: string,
    metric: Omit<PerformanceMetric, 'timestamp' | 'userId'>
  ): void {
    if (!this.config.performanceTracking) return;

    const performanceMetric: PerformanceMetric = {
      timestamp: Date.now(),
      userId: this.userId,
      service,
      action,
      ...metric
    };

    this.metrics.push(performanceMetric);
  }

  // Track error
  async trackError(
    error: Error,
    context: {
      service: string;
      action: string;
      parameters: any;
      retryCount: number;
    },
    resolution?: {
      attempt: number;
      success: boolean;
      resolutionTime: number;
      resolutionAction: string;
    }
  ): Promise<void> {
    if (!this.config.errorReporting) return;

    const errorReport: ErrorReport = {
      id: this.generateId(),
      timestamp: Date.now(),
      userId: this.userId,
      error: {
        code: this.getErrorCode(error),
        message: error.message,
        stack: error.stack,
        type: this.getErrorType(error),
        severity: this.getErrorSeverity(error)
      },
      context,
      resolution
    };

    this.errors.push(errorReport);
    
    // Save critical errors immediately
    if (errorReport.error.severity === 'critical') {
      await this.saveAnalyticsData();
    }
  }

  // Track usage
  trackUsage(
    category: 'gmail' | 'calendar' | 'drive',
    action: string,
    increment: number = 1
  ): void {
    if (!this.config.usageTracking) return;

    const usage: Partial<UsageStatistics> = {
      userId: this.userId,
      date: new Date().toISOString().split('T')[0]
    };

    // Update usage counters
    switch (category) {
      case 'gmail':
        usage.gmail = {
          emailsSent: action === 'send' ? increment : 0,
          emailsRead: action === 'read' ? increment : 0,
          emailsDeleted: action === 'delete' ? increment : 0,
          searchesPerformed: action === 'search' ? increment : 0
        } as any;
        break;
      case 'calendar':
        usage.calendar = {
          eventsCreated: action === 'create' ? increment : 0,
          eventsUpdated: action === 'update' ? increment : 0,
          eventsDeleted: action === 'delete' ? increment : 0,
          calendarsAccessed: action === 'list' ? increment : 0
        } as any;
        break;
      case 'drive':
        usage.drive = {
          filesUploaded: action === 'upload' ? increment : 0,
          filesDownloaded: action === 'download' ? increment : 0,
          filesShared: action === 'share' ? increment : 0,
          filesDeleted: action === 'delete' ? increment : 0,
          searchesPerformed: action === 'search' ? increment : 0
        } as any;
        break;
    }

    // Update totals
    usage.totals = {
      apiCalls: increment,
      dataTransferred: 0, // Would need to calculate from actual API responses
      errorsEncountered: 0
    } as any;

    const event: AnalyticsEvent = {
      id: this.generateId(),
      type: 'usage',
      timestamp: Date.now(),
      userId: this.userId,
      service: category,
      action,
      data: usage,
      metadata: {
        success: true
      }
    };

    this.events.push(event);
  }

  // Get performance summary
  getPerformanceSummary(timeRange: 'hour' | 'day' | 'week' | 'month' = 'day'): {
    averageResponseTime: number;
    successRate: number;
    cacheHitRate: number;
    totalCalls: number;
    errors: number;
  } {
    const now = Date.now();
    const rangeMs = {
      hour: 60 * 60 * 1000,
      day: 24 * 60 * 60 * 1000,
      week: 7 * 24 * 60 * 60 * 1000,
      month: 30 * 24 * 60 * 60 * 1000
    }[timeRange];

    const recentMetrics = this.metrics.filter(
      m => now - m.timestamp <= rangeMs
    );

    if (recentMetrics.length === 0) {
      return {
        averageResponseTime: 0,
        successRate: 0,
        cacheHitRate: 0,
        totalCalls: 0,
        errors: 0
      };
    }

    const totalDuration = recentMetrics.reduce((sum, m) => sum + m.duration, 0);
    const successfulCalls = recentMetrics.filter(m => m.success).length;
    const cacheHits = recentMetrics.filter(m => m.cacheHit).length;

    return {
      averageResponseTime: totalDuration / recentMetrics.length,
      successRate: (successfulCalls / recentMetrics.length) * 100,
      cacheHitRate: (cacheHits / recentMetrics.length) * 100,
      totalCalls: recentMetrics.length,
      errors: recentMetrics.length - successfulCalls
    };
  }

  // Get error summary
  getErrorSummary(timeRange: 'hour' | 'day' | 'week' | 'month' = 'day'): {
    totalErrors: number;
    errorsByType: Record<string, number>;
    errorsBySeverity: Record<string, number>;
    errorsByService: Record<string, number>;
    mostCommonErrors: Array<{ error: string; count: number }>;
  } {
    const now = Date.now();
    const rangeMs = {
      hour: 60 * 60 * 1000,
      day: 24 * 60 * 60 * 1000,
      week: 7 * 24 * 60 * 60 * 1000,
      month: 30 * 24 * 60 * 60 * 1000
    }[timeRange];

    const recentErrors = this.errors.filter(
      e => now - e.timestamp <= rangeMs
    );

    const errorsByType: Record<string, number> = {};
    const errorsBySeverity: Record<string, number> = {};
    const errorsByService: Record<string, number> = {};
    const errorCounts: Record<string, number> = {};

    for (const error of recentErrors) {
      // Count by type
      errorsByType[error.error.type] = (errorsByType[error.error.type] || 0) + 1;
      
      // Count by severity
      errorsBySeverity[error.error.severity] = (errorsBySeverity[error.error.severity] || 0) + 1;
      
      // Count by service
      errorsByService[error.context.service] = (errorsByService[error.context.service] || 0) + 1;
      
      // Count specific errors
      const errorKey = `${error.error.code}: ${error.error.message}`;
      errorCounts[errorKey] = (errorCounts[errorKey] || 0) + 1;
    }

    const mostCommonErrors = Object.entries(errorCounts)
      .map(([error, count]) => ({ error, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);

    return {
      totalErrors: recentErrors.length,
      errorsByType,
      errorsBySeverity,
      errorsByService,
      mostCommonErrors
    };
  }

  // Get usage statistics
  async getUsageStatistics(timeRange: 'day' | 'week' | 'month' = 'day'): Promise<UsageStatistics[]> {
    const now = new Date();
    const rangeDays = {
      day: 1,
      week: 7,
      month: 30
    }[timeRange];

    const startDate = new Date(now);
    startDate.setDate(startDate.getDate() - rangeDays);

    const usageEvents = this.events.filter(
      e => e.type === 'usage' && 
             e.timestamp >= startDate.getTime()
    );

    // Group by date and aggregate
    const dailyStats: Record<string, UsageStatistics> = {};

    for (const event of usageEvents) {
      const date = new Date(event.timestamp).toISOString().split('T')[0];
      
      if (!dailyStats[date]) {
        dailyStats[date] = {
          userId: this.userId,
          date,
          gmail: { emailsSent: 0, emailsRead: 0, emailsDeleted: 0, searchesPerformed: 0 },
          calendar: { eventsCreated: 0, eventsUpdated: 0, eventsDeleted: 0, calendarsAccessed: 0 },
          drive: { filesUploaded: 0, filesDownloaded: 0, filesShared: 0, filesDeleted: 0, searchesPerformed: 0 },
          totals: { apiCalls: 0, dataTransferred: 0, errorsEncountered: 0 }
        };
      }

      // Merge usage data
      const eventData = event.data as Partial<UsageStatistics>;
      const stats = dailyStats[date];

      if (eventData.gmail) {
        stats.gmail.emailsSent += eventData.gmail.emailsSent;
        stats.gmail.emailsRead += eventData.gmail.emailsRead;
        stats.gmail.emailsDeleted += eventData.gmail.emailsDeleted;
        stats.gmail.searchesPerformed += eventData.gmail.searchesPerformed;
      }

      if (eventData.calendar) {
        stats.calendar.eventsCreated += eventData.calendar.eventsCreated;
        stats.calendar.eventsUpdated += eventData.calendar.eventsUpdated;
        stats.calendar.eventsDeleted += eventData.calendar.eventsDeleted;
        stats.calendar.calendarsAccessed += eventData.calendar.calendarsAccessed;
      }

      if (eventData.drive) {
        stats.drive.filesUploaded += eventData.drive.filesUploaded;
        stats.drive.filesDownloaded += eventData.drive.filesDownloaded;
        stats.drive.filesShared += eventData.drive.filesShared;
        stats.drive.filesDeleted += eventData.drive.filesDeleted;
        stats.drive.searchesPerformed += eventData.drive.searchesPerformed;
      }

      if (eventData.totals) {
        stats.totals.apiCalls += eventData.totals.apiCalls;
        stats.totals.dataTransferred += eventData.totals.dataTransferred;
        stats.totals.errorsEncountered += eventData.totals.errorsEncountered;
      }
    }

    return Object.values(dailyStats)
      .sort((a, b) => a.date.localeCompare(b.date));
  }

  // Export analytics data
  async exportData(format: 'json' | 'csv' = 'json'): Promise<string> {
    const exportData = {
      events: this.events,
      errors: this.errors,
      metrics: this.metrics,
      exportedAt: new Date().toISOString(),
      userId: this.userId,
      config: this.config
    };

    if (format === 'csv') {
      return this.convertToCSV(exportData);
    }

    return JSON.stringify(exportData, null, 2);
  }

  // Save analytics data to file
  private async saveAnalyticsData(): Promise<void> {
    try {
      const analyticsFile = await join(this.dataDir, `google_analytics_${this.userId}.json`);
      const data = {
        events: this.events,
        errors: this.errors,
        metrics: this.metrics,
        lastSaved: Date.now()
      };
      
      await writeTextFile(analyticsFile, JSON.stringify(data, null, 2));
    } catch (error) {
      console.error('Failed to save analytics data:', error);
    }
  }

  // Load analytics data from file
  private async loadAnalyticsData(): Promise<void> {
    try {
      const analyticsFile = await join(this.dataDir, `google_analytics_${this.userId}.json`);
      
      if (await exists(analyticsFile)) {
        const data = await readTextFile(analyticsFile);
        const parsed = JSON.parse(data);
        
        this.events = parsed.events || [];
        this.errors = parsed.errors || [];
        this.metrics = parsed.metrics || [];
      }
    } catch (error) {
      console.error('Failed to load analytics data:', error);
    }
  }

  // Clean up old data
  private async cleanupOldData(): Promise<void> {
    try {
      const cutoffTime = Date.now() - (this.config.dataRetention * 24 * 60 * 60 * 1000);
      
      // Filter out old data
      this.events = this.events.filter(e => e.timestamp > cutoffTime);
      this.errors = this.errors.filter(e => e.timestamp > cutoffTime);
      this.metrics = this.metrics.filter(m => m.timestamp > cutoffTime);
      
      await this.saveAnalyticsData();
    } catch (error) {
      console.error('Failed to cleanup old data:', error);
    }
  }

  // Start upload timer
  private startUploadTimer(): void {
    if (this.uploadTimer) {
      clearInterval(this.uploadTimer);
    }

    this.uploadTimer = setInterval(async () => {
      await this.uploadData();
    }, this.config.uploadInterval * 60 * 1000);
  }

  // Upload data to server
  private async uploadData(): Promise<void> {
    try {
      if (this.events.length === 0) return;

      const uploadData = {
        userId: this.userId,
        events: this.events.slice(0, this.config.batchSize),
        errors: this.errors.slice(0, this.config.batchSize),
        metrics: this.metrics.slice(0, this.config.batchSize),
        timestamp: Date.now()
      };

      await invoke('google_upload_analytics', uploadData);

      // Remove uploaded data
      this.events.splice(0, this.config.batchSize);
      this.errors.splice(0, this.config.batchSize);
      this.metrics.splice(0, this.config.batchSize);

      await this.saveAnalyticsData();
    } catch (error) {
      console.error('Failed to upload analytics data:', error);
    }
  }

  // Check batch size and upload if needed
  private checkBatchSize(): void {
    if (this.events.length >= this.config.batchSize) {
      this.uploadData();
    }
  }

  // Utility methods
  private generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  private getUserAgent(): string {
    return navigator.userAgent || 'Unknown';
  }

  private getPlatform(): string {
    return navigator.platform || 'Unknown';
  }

  private getVersion(): string {
    return '1.0.0'; // Would get from package.json
  }

  private getErrorCode(error: Error): string {
    // Extract error code based on error message or type
    if (error.message.includes('401')) return 'AUTH_401';
    if (error.message.includes('403')) return 'PERMISSION_403';
    if (error.message.includes('404')) return 'NOT_FOUND_404';
    if (error.message.includes('429')) return 'RATE_LIMIT_429';
    if (error.message.includes('500')) return 'SERVER_500';
    return 'UNKNOWN_ERROR';
  }

  private getErrorType(error: Error): 'api_error' | 'network_error' | 'auth_error' | 'validation_error' | 'system_error' {
    const message = error.message.toLowerCase();
    
    if (message.includes('network') || message.includes('fetch')) return 'network_error';
    if (message.includes('auth') || message.includes('unauthorized')) return 'auth_error';
    if (message.includes('validation') || message.includes('invalid')) return 'validation_error';
    if (message.includes('api')) return 'api_error';
    
    return 'system_error';
  }

  private getErrorSeverity(error: Error): 'low' | 'medium' | 'high' | 'critical' {
    const code = this.getErrorCode(error);
    
    if (code.includes('500') || code.includes('503')) return 'critical';
    if (code.includes('401') || code.includes('403')) return 'high';
    if (code.includes('404') || code.includes('429')) return 'medium';
    
    return 'low';
  }

  private anonymize(data: any): any {
    // Remove sensitive data
    const anonymized = JSON.parse(JSON.stringify(data));
    
    // Remove email addresses
    if (anonymized.to) {
      anonymized.to = anonymized.to.map((email: string) => 
        email.replace(/(.{2}).*@/, '$1***@')
      );
    }
    
    // Remove tokens and passwords
    if (anonymized.accessToken) anonymized.accessToken = '***';
    if (anonymized.password) anonymized.password = '***';
    
    return anonymized;
  }

  private convertToCSV(data: any): string {
    // Convert JSON data to CSV format
    // This is a simplified implementation
    const csv = Object.entries(data)
      .map(([key, value]) => {
        const count = Array.isArray(value) ? value.length : 0;
        return `${key},${count}`;
      })
      .join('\n');
    
    return csv;
  }

  // Update configuration
  updateConfig(config: Partial<AnalyticsConfig>): void {
    this.config = { ...this.config, ...config };
  }

  // Get current configuration
  getConfig(): AnalyticsConfig {
    return { ...this.config };
  }

  // Cleanup
  async cleanup(): Promise<void> {
    try {
      if (this.uploadTimer) {
        clearInterval(this.uploadTimer);
        this.uploadTimer = null;
      }
      
      await this.saveAnalyticsData();
    } catch (error) {
      console.error('Analytics cleanup failed:', error);
    }
  }
}

// Export singleton instance
export const googleAnalytics = GoogleAnalyticsService.getInstance();

// Export types
export type { 
  AnalyticsEvent, 
  PerformanceMetric, 
  ErrorReport, 
  UsageStatistics, 
  AnalyticsConfig 
};