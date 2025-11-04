/**
 * Production Monitoring and Analytics for Outlook Integration
 */

export interface MonitoringMetrics {
  // OAuth Metrics
  oauthSuccessRate: number;
  oauthFailureRate: number;
  oauthResponseTime: number;
  tokenRefreshRate: number;
  tokenExpiryRate: number;
  
  // Email Metrics
  emailSendSuccessRate: number;
  emailSendFailureRate: number;
  emailSendResponseTime: number;
  emailRetrievalSuccessRate: number;
  emailSearchResponseTime: number;
  emailTriageAccuracy: number;
  
  // Calendar Metrics
  calendarCreateSuccessRate: number;
  calendarUpdateSuccessRate: number;
  calendarSearchResponseTime: number;
  calendarEventRetrievalTime: number;
  
  // NLP Metrics
  intentRecognitionAccuracy: number;
  entityExtractionAccuracy: number;
  commandProcessingTime: number;
  
  // System Metrics
  memoryUsage: number;
  cpuUsage: number;
  diskUsage: number;
  networkLatency: number;
  
  // User Metrics
  activeUsers: number;
  sessionDuration: number;
  featureUsage: Record<string, number>;
  errorRate: number;
  userSatisfaction: number;
}

export interface AlertConfig {
  metricName: string;
  threshold: number;
  operator: 'gt' | 'lt' | 'eq';
  severity: 'low' | 'medium' | 'high' | 'critical';
  cooldown: number; // minutes
  enabled: boolean;
}

export interface HealthCheck {
  service: string;
  status: 'healthy' | 'degraded' | 'unhealthy';
  lastCheck: string;
  responseTime: number;
  details?: Record<string, any>;
}

export class OutlookMonitoringService {
  private metrics: MonitoringMetrics;
  private alerts: Map<string, AlertConfig>;
  private healthChecks: Map<string, HealthCheck>;
  private isProduction: boolean;
  private monitoringInterval: NodeJS.Timeout | null = null;

  constructor(isProduction = true) {
    this.isProduction = isProduction;
    this.metrics = this.initializeMetrics();
    this.alerts = this.initializeAlerts();
    this.healthChecks = new Map();
    
    if (isProduction) {
      this.startMonitoring();
    }
  }

  private initializeMetrics(): MonitoringMetrics {
    return {
      // OAuth Metrics
      oauthSuccessRate: 0,
      oauthFailureRate: 0,
      oauthResponseTime: 0,
      tokenRefreshRate: 0,
      tokenExpiryRate: 0,
      
      // Email Metrics
      emailSendSuccessRate: 0,
      emailSendFailureRate: 0,
      emailSendResponseTime: 0,
      emailRetrievalSuccessRate: 0,
      emailSearchResponseTime: 0,
      emailTriageAccuracy: 0,
      
      // Calendar Metrics
      calendarCreateSuccessRate: 0,
      calendarUpdateSuccessRate: 0,
      calendarSearchResponseTime: 0,
      calendarEventRetrievalTime: 0,
      
      // NLP Metrics
      intentRecognitionAccuracy: 0,
      entityExtractionAccuracy: 0,
      commandProcessingTime: 0,
      
      // System Metrics
      memoryUsage: 0,
      cpuUsage: 0,
      diskUsage: 0,
      networkLatency: 0,
      
      // User Metrics
      activeUsers: 0,
      sessionDuration: 0,
      featureUsage: {},
      errorRate: 0,
      userSatisfaction: 0
    };
  }

  private initializeAlerts(): Map<string, AlertConfig> {
    const alerts = new Map<string, AlertConfig>();
    
    // OAuth Alerts
    alerts.set('oauth_failure_rate', {
      metricName: 'oauthFailureRate',
      threshold: 10, // 10%
      operator: 'gt',
      severity: 'high',
      cooldown: 15,
      enabled: true
    });
    
    alerts.set('oauth_response_time', {
      metricName: 'oauthResponseTime',
      threshold: 5000, // 5 seconds
      operator: 'gt',
      severity: 'medium',
      cooldown: 10,
      enabled: true
    });
    
    // Email Alerts
    alerts.set('email_send_failure_rate', {
      metricName: 'emailSendFailureRate',
      threshold: 5, // 5%
      operator: 'gt',
      severity: 'high',
      cooldown: 10,
      enabled: true
    });
    
    alerts.set('email_search_response_time', {
      metricName: 'emailSearchResponseTime',
      threshold: 3000, // 3 seconds
      operator: 'gt',
      severity: 'medium',
      cooldown: 5,
      enabled: true
    });
    
    // Calendar Alerts
    alerts.set('calendar_operation_failure_rate', {
      metricName: 'calendarCreateSuccessRate',
      threshold: 5, // 5%
      operator: 'lt',
      severity: 'medium',
      cooldown: 10,
      enabled: true
    });
    
    // System Alerts
    alerts.set('memory_usage', {
      metricName: 'memoryUsage',
      threshold: 80, // 80%
      operator: 'gt',
      severity: 'high',
      cooldown: 5,
      enabled: true
    });
    
    alerts.set('cpu_usage', {
      metricName: 'cpuUsage',
      threshold: 70, // 70%
      operator: 'gt',
      severity: 'medium',
      cooldown: 5,
      enabled: true
    });
    
    return alerts;
  }

  private startMonitoring(): void {
    // Collect metrics every 30 seconds
    this.monitoringInterval = setInterval(() => {
      this.collectSystemMetrics();
      this.checkAlerts();
      this.healthChecks.forEach((check, service) => {
        this.performHealthCheck(service);
      });
    }, 30000);
    
    // Send metrics to analytics service every 5 minutes
    setInterval(() => {
      this.sendMetricsToAnalytics();
    }, 300000);
    
    // Generate daily reports
    setInterval(() => {
      this.generateDailyReport();
    }, 24 * 60 * 60 * 1000);
  }

  // OAuth Monitoring
  public trackOAuthSuccess(responseTime: number): void {
    this.metrics.oauthResponseTime = this.calculateAverage(
      this.metrics.oauthResponseTime, responseTime
    );
    this.metrics.oauthSuccessRate = this.updateSuccessRate(
      this.metrics.oauthSuccessRate, true
    );
    this.sendEvent('oauth_success', { responseTime });
  }

  public trackOAuthFailure(error: string, responseTime: number): void {
    this.metrics.oauthFailureRate = this.updateSuccessRate(
      this.metrics.oauthFailureRate, true
    );
    this.sendEvent('oauth_failure', { error, responseTime });
  }

  public trackTokenRefresh(success: boolean): void {
    this.metrics.tokenRefreshRate = this.updateSuccessRate(
      this.metrics.tokenRefreshRate, success
    );
  }

  // Email Monitoring
  public trackEmailSend(success: boolean, responseTime: number): void {
    if (success) {
      this.metrics.emailSendSuccessRate = this.updateSuccessRate(
        this.metrics.emailSendSuccessRate, true
      );
      this.metrics.emailSendResponseTime = this.calculateAverage(
        this.metrics.emailSendResponseTime, responseTime
      );
    } else {
      this.metrics.emailSendFailureRate = this.updateSuccessRate(
        this.metrics.emailSendFailureRate, true
      );
    }
    
    this.sendEvent('email_send', { success, responseTime });
  }

  public trackEmailRetrieval(success: boolean, count: number, responseTime: number): void {
    this.metrics.emailRetrievalSuccessRate = this.updateSuccessRate(
      this.metrics.emailRetrievalSuccessRate, success
    );
    
    this.sendEvent('email_retrieval', { success, count, responseTime });
  }

  public trackEmailSearch(responseTime: number, resultCount: number): void {
    this.metrics.emailSearchResponseTime = this.calculateAverage(
      this.metrics.emailSearchResponseTime, responseTime
    );
    
    this.sendEvent('email_search', { responseTime, resultCount });
  }

  public trackEmailTriage(total: number, highPriority: number, requiresAction: number): void {
    this.metrics.emailTriageAccuracy = (highPriority + requiresAction) / total;
    
    this.sendEvent('email_triage', { total, highPriority, requiresAction });
  }

  // Calendar Monitoring
  public trackCalendarCreate(success: boolean, responseTime: number): void {
    this.metrics.calendarCreateSuccessRate = this.updateSuccessRate(
      this.metrics.calendarCreateSuccessRate, success
    );
    
    this.sendEvent('calendar_create', { success, responseTime });
  }

  public trackCalendarUpdate(success: boolean, responseTime: number): void {
    this.metrics.calendarUpdateSuccessRate = this.updateSuccessRate(
      this.metrics.calendarUpdateSuccessRate, success
    );
    
    this.sendEvent('calendar_update', { success, responseTime });
  }

  public trackCalendarSearch(responseTime: number, resultCount: number): void {
    this.metrics.calendarSearchResponseTime = this.calculateAverage(
      this.metrics.calendarSearchResponseTime, responseTime
    );
    
    this.sendEvent('calendar_search', { responseTime, resultCount });
  }

  public trackCalendarEventRetrieval(responseTime: number, count: number): void {
    this.metrics.calendarEventRetrievalTime = this.calculateAverage(
      this.metrics.calendarEventRetrievalTime, responseTime
    );
    
    this.sendEvent('calendar_retrieval', { responseTime, count });
  }

  // NLP Monitoring
  public trackIntentProcessing(intent: string, confidence: number, processingTime: number): void {
    this.metrics.commandProcessingTime = this.calculateAverage(
      this.metrics.commandProcessingTime, processingTime
    );
    
    if (confidence > 0.8) {
      this.metrics.intentRecognitionAccuracy = this.updateSuccessRate(
        this.metrics.intentRecognitionAccuracy, true
      );
    }
    
    this.sendEvent('intent_processing', { intent, confidence, processingTime });
  }

  public trackEntityExtraction(extracted: number, total: number): void {
    const accuracy = extracted / total;
    this.metrics.entityExtractionAccuracy = this.calculateAverage(
      this.metrics.entityExtractionAccuracy, accuracy
    );
    
    this.sendEvent('entity_extraction', { extracted, total, accuracy });
  }

  // User Metrics
  public trackUserAction(action: string, userId: string): void {
    if (!this.metrics.featureUsage[action]) {
      this.metrics.featureUsage[action] = 0;
    }
    this.metrics.featureUsage[action]++;
    
    this.sendEvent('user_action', { action, userId });
  }

  public trackSessionStart(userId: string): void {
    this.metrics.activeUsers++;
    this.sendEvent('session_start', { userId });
  }

  public trackSessionEnd(userId: string, duration: number): void {
    this.metrics.activeUsers = Math.max(0, this.metrics.activeUsers - 1);
    this.metrics.sessionDuration = this.calculateAverage(
      this.metrics.sessionDuration, duration
    );
    
    this.sendEvent('session_end', { userId, duration });
  }

  // System Metrics
  private async collectSystemMetrics(): Promise<void> {
    try {
      // Memory usage
      const memoryInfo = await this.getMemoryUsage();
      this.metrics.memoryUsage = memoryInfo.usedPercentage;
      
      // CPU usage
      const cpuInfo = await this.getCpuUsage();
      this.metrics.cpuUsage = cpuInfo.usagePercentage;
      
      // Disk usage
      const diskInfo = await this.getDiskUsage();
      this.metrics.diskUsage = diskInfo.usedPercentage;
      
      // Network latency (ping Microsoft Graph API)
      const latency = await this.measureNetworkLatency();
      this.metrics.networkLatency = latency;
      
    } catch (error) {
      console.error('Failed to collect system metrics:', error);
    }
  }

  private async getMemoryUsage(): Promise<{ usedPercentage: number }> {
    // Mock implementation - in production use system APIs
    return { usedPercentage: Math.random() * 100 };
  }

  private async getCpuUsage(): Promise<{ usagePercentage: number }> {
    // Mock implementation - in production use system APIs
    return { usagePercentage: Math.random() * 100 };
  }

  private async getDiskUsage(): Promise<{ usedPercentage: number }> {
    // Mock implementation - in production use system APIs
    return { usedPercentage: Math.random() * 100 };
  }

  private async measureNetworkLatency(): Promise<number> {
    const start = Date.now();
    try {
      // Ping Microsoft Graph API
      const response = await fetch('https://graph.microsoft.com/v1.0/me', {
        method: 'HEAD',
        cache: 'no-cache'
      });
      return Date.now() - start;
    } catch (error) {
      return Date.now() - start; // Return measured time even on failure
    }
  }

  // Health Checks
  public addHealthCheck(service: string, checker: () => Promise<HealthCheck>): void {
    checker().then(healthCheck => {
      this.healthChecks.set(service, healthCheck);
    });
  }

  private async performHealthCheck(service: string): Promise<void> {
    const healthCheck = this.healthChecks.get(service);
    if (!healthCheck) return;

    try {
      // Perform actual health check based on service
      const result = await this.checkServiceHealth(service);
      this.healthChecks.set(service, {
        ...healthCheck,
        ...result,
        lastCheck: new Date().toISOString()
      });
    } catch (error) {
      this.healthChecks.set(service, {
        service,
        status: 'unhealthy',
        lastCheck: new Date().toISOString(),
        responseTime: -1,
        details: { error: error instanceof Error ? error.message : 'Unknown error' }
      });
    }
  }

  private async checkServiceHealth(service: string): Promise<Partial<HealthCheck>> {
    const start = Date.now();
    
    switch (service) {
      case 'microsoft_graph':
        try {
          const response = await fetch('https://graph.microsoft.com/v1.0/me', {
            method: 'HEAD',
            cache: 'no-cache'
          });
          return {
            status: response.ok ? 'healthy' : 'degraded',
            responseTime: Date.now() - start,
            details: { httpStatus: response.status }
          };
        } catch (error) {
          return {
            status: 'unhealthy',
            responseTime: Date.now() - start,
            details: { error: error instanceof Error ? error.message : 'Network error' }
          };
        }
        
      case 'oauth_service':
        try {
          const response = await fetch('https://login.microsoftonline.com/common/.well-known/openid_configuration', {
            cache: 'no-cache'
          });
          return {
            status: response.ok ? 'healthy' : 'degraded',
            responseTime: Date.now() - start,
            details: { httpStatus: response.status }
          };
        } catch (error) {
          return {
            status: 'unhealthy',
            responseTime: Date.now() - start,
            details: { error: error instanceof Error ? error.message : 'Network error' }
          };
        }
        
      default:
        return {
          status: 'healthy',
          responseTime: Date.now() - start
        };
    }
  }

  // Alert Management
  private checkAlerts(): void {
    this.alerts.forEach((alert, key) => {
      if (!alert.enabled) return;
      
      const metricValue = (this.metrics as any)[alert.metricName];
      let shouldAlert = false;
      
      switch (alert.operator) {
        case 'gt':
          shouldAlert = metricValue > alert.threshold;
          break;
        case 'lt':
          shouldAlert = metricValue < alert.threshold;
          break;
        case 'eq':
          shouldAlert = metricValue === alert.threshold;
          break;
      }
      
      if (shouldAlert) {
        this.triggerAlert(alert, metricValue);
      }
    });
  }

  private triggerAlert(alert: AlertConfig, value: number): void {
    const alertData = {
      alert: alert.metricName,
      severity: alert.severity,
      threshold: alert.threshold,
      actualValue: value,
      timestamp: new Date().toISOString(),
      service: 'outlook_integration'
    };
    
    // Send to monitoring service
    this.sendAlert(alertData);
    
    // Log to console
    console.warn(`🚨 ALERT: ${alert.metricName} is ${value} (threshold: ${alert.threshold})`);
  }

  private sendAlert(alertData: any): void {
    // In production, send to Sentry, PagerDuty, or your alerting service
    if (this.isProduction) {
      // Example: Send to webhook
      fetch(process.env.ALERT_WEBHOOK_URL || '', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(alertData)
      }).catch(error => {
        console.error('Failed to send alert:', error);
      });
    }
  }

  // Analytics and Reporting
  private sendMetricsToAnalytics(): void {
    if (!this.isProduction) return;
    
    // Send to analytics service (Google Analytics, Mixpanel, etc.)
    this.sendEvent('metrics_report', this.metrics);
  }

  private sendEvent(eventType: string, data: any): void {
    if (!this.isProduction) return;
    
    // Send to analytics service
    const eventData = {
      eventType,
      timestamp: new Date().toISOString(),
      service: 'outlook_integration',
      data
    };
    
    // Example: Send to your analytics endpoint
    fetch(process.env.ANALYTICS_ENDPOINT || '', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(eventData)
    }).catch(error => {
      console.error('Failed to send analytics:', error);
    });
  }

  private generateDailyReport(): void {
    const report = {
      date: new Date().toISOString().split('T')[0],
      metrics: this.metrics,
      healthChecks: Object.fromEntries(this.healthChecks),
      summary: {
        totalUsers: this.metrics.activeUsers,
        averageResponseTime: this.calculateAverageResponseTime(),
        overallSuccessRate: this.calculateOverallSuccessRate(),
        topFeatures: this.getTopFeatures()
      }
    };
    
    // Send report via email or webhook
    this.sendEvent('daily_report', report);
    
    // Save to local storage
    localStorage.setItem(`outlook_report_${report.date}`, JSON.stringify(report));
  }

  // Utility Methods
  private calculateAverage(current: number, newValue: number): number {
    return (current + newValue) / 2;
  }

  private updateSuccessRate(current: number, success: boolean): number {
    // Simple exponential moving average for success rate
    const alpha = 0.1;
    return current * (1 - alpha) + (success ? 100 : 0) * alpha;
  }

  private calculateAverageResponseTime(): number {
    const responseTimes = [
      this.metrics.oauthResponseTime,
      this.metrics.emailSendResponseTime,
      this.metrics.emailSearchResponseTime,
      this.metrics.calendarSearchResponseTime
    ].filter(time => time > 0);
    
    return responseTimes.reduce((sum, time) => sum + time, 0) / responseTimes.length;
  }

  private calculateOverallSuccessRate(): number {
    const successRates = [
      this.metrics.oauthSuccessRate,
      this.metrics.emailSendSuccessRate,
      this.metrics.emailRetrievalSuccessRate,
      this.metrics.calendarCreateSuccessRate,
      this.metrics.calendarUpdateSuccessRate
    ].filter(rate => rate > 0);
    
    return successRates.reduce((sum, rate) => sum + rate, 0) / successRates.length;
  }

  private getTopFeatures(): Array<{ feature: string; usage: number }> {
    return Object.entries(this.metrics.featureUsage)
      .map(([feature, usage]) => ({ feature, usage }))
      .sort((a, b) => b.usage - a.usage)
      .slice(0, 10);
  }

  // Public API
  public getMetrics(): MonitoringMetrics {
    return { ...this.metrics };
  }

  public getHealthChecks(): Record<string, HealthCheck> {
    return Object.fromEntries(this.healthChecks);
  }

  public stopMonitoring(): void {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
      this.monitoringInterval = null;
    }
  }
}

// Export singleton instance
export const outlookMonitoringService = new OutlookMonitoringService(
  process.env.NODE_ENV === 'production'
);

// Initialize health checks
outlookMonitoringService.addHealthCheck('microsoft_graph', async () => ({
  service: 'microsoft_graph',
  status: 'healthy',
  lastCheck: new Date().toISOString(),
  responseTime: 0
}));

outlookMonitoringService.addHealthCheck('oauth_service', async () => ({
  service: 'oauth_service',
  status: 'healthy',
  lastCheck: new Date().toISOString(),
  responseTime: 0
}));