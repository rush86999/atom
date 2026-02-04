/**
 * Enhanced Integration Health Skills
 * Comprehensive health monitoring for all ATOM integrations
 */

import { api } from '../../services/api';

export interface ServiceHealth {
  name: string;
  status: 'healthy' | 'unhealthy' | 'degraded' | 'unknown';
  connected: boolean;
  response_time?: number;
  last_check: string;
  error?: string;
  metadata?: Record<string, any>;
}

export interface IntegrationHealthReport {
  integration_name: string;
  overall_status: 'healthy' | 'unhealthy' | 'degraded' | 'unknown';
  services: ServiceHealth[];
  connected_count: number;
  total_services: number;
  timestamp: string;
  backend_connected: boolean;
}

export interface SystemHealthSummary {
  status: 'healthy' | 'unhealthy' | 'degraded' | 'unknown';
  total_integrations: number;
  healthy_integrations: number;
  degraded_integrations: number;
  unhealthy_integrations: number;
  integrations: Record<string, {
    status: string;
    connected_services: number;
    total_services: number;
  }>;
  timestamp: string;
  version: string;
}

/**
 * Enhanced Integration Health Monitoring Skills
 * Provides comprehensive health checking for all integrations
 */
export class EnhancedIntegrationHealthSkills {
  private static readonly HEALTH_ENDPOINTS = {
    frontend: {
      hubspot: '/api/integrations/hubspot/health',
      slack: '/api/integrations/slack/health',
      jira: '/api/integrations/jira/health',
      linear: '/api/integrations/linear/health',
      salesforce: '/api/integrations/salesforce/health',
      xero: '/api/integrations/xero/health',
    },
    backend: {
      all: '/api/v2/health/health/all',
      hubspot: '/api/v2/health/health/hubspot',
      slack: '/api/v2/health/health/slack',
      jira: '/api/v2/health/health/jira',
      linear: '/api/v2/health/health/linear',
      salesforce: '/api/v2/health/health/salesforce',
      xero: '/api/v2/health/health/xero',
      summary: '/api/v2/health/health/summary',
    }
  };

  /**
   * Get health status from frontend endpoints
   */
  static async getFrontendHealthStatus(integration: keyof typeof EnhancedIntegrationHealthSkills.HEALTH_ENDPOINTS.frontend): Promise<{
    status: string;
    backend: string;
    services: Record<string, ServiceHealth>;
    connected_count: number;
    total_services: number;
    timestamp: string;
    version?: string;
  }> {
    try {
      const endpoint = this.HEALTH_ENDPOINTS.frontend[integration];
      const response = await api.get(endpoint);
      return response.data;
    } catch (error) {
      console.error(`Failed to get frontend health for ${integration}:`, error);
      throw error;
    }
  }

  /**
   * Get comprehensive health status from backend
   */
  static async getBackendHealthStatus(integration?: keyof typeof EnhancedIntegrationHealthSkills.HEALTH_ENDPOINTS.backend): Promise<{
    system_health?: {
      status: string;
      total_integrations: number;
      healthy_integrations: number;
      degraded_integrations: number;
      unhealthy_integrations: number;
    };
    integrations?: Record<string, IntegrationHealthReport>;
    integration?: IntegrationHealthReport;
    summary?: {
      summary: {
        total_integrations: number;
        healthy_count: number;
        degraded_count: number;
        unhealthy_count: number;
        overall_status: string;
      };
      integrations: Record<string, {
        status: string;
        connected_services: number;
        total_services: number;
      }>;
      timestamp: string;
    };
    timestamp: string;
    version: string;
  }> {
    try {
      let endpoint: string;
      
      if (!integration) {
        endpoint = this.HEALTH_ENDPOINTS.backend.all;
      } else if (integration === 'summary') {
        endpoint = this.HEALTH_ENDPOINTS.backend.summary;
      } else {
        endpoint = this.HEALTH_ENDPOINTS.backend[integration];
      }
      
      const response = await api.get(endpoint);
      return response.data;
    } catch (error) {
      console.error(`Failed to get backend health for ${integration || 'all'}:`, error);
      throw error;
    }
  }

  /**
   * Get system health summary
   */
  static async getSystemHealthSummary(): Promise<SystemHealthSummary> {
    try {
      const response = await api.get(this.HEALTH_ENDPOINTS.backend.summary);
      return response.data;
    } catch (error) {
      console.error('Failed to get system health summary:', error);
      throw error;
    }
  }

  /**
   * Check specific integration health from both frontend and backend
   */
  static async checkIntegrationHealth(integration: keyof typeof EnhancedIntegrationHealthSkills.HEALTH_ENDPOINTS.frontend): Promise<{
    frontend: any;
    backend: IntegrationHealthReport;
    correlation: {
      status_match: boolean;
      service_count_match: boolean;
      timestamp_difference: number;
    };
  }> {
    try {
      const [frontend, backend] = await Promise.all([
        this.getFrontendHealthStatus(integration).catch(error => ({ error: error.message })),
        this.getBackendHealthStatus(integration).catch(error => ({ error: error.message }))
      ]);

      const backendReport = backend.integrations?.[integration] || backend.integration || backend;

      // Correlate results
      const correlation = {
        status_match: frontend.status === backendReport.overall_status,
        service_count_match: frontend.connected_count === backendReport.connected_count,
        timestamp_difference: Math.abs(
          new Date(frontend.timestamp).getTime() - new Date(backendReport.timestamp).getTime()
        )
      };

      return {
        frontend,
        backend: backendReport,
        correlation
      };
    } catch (error) {
      console.error(`Failed to check ${integration} health:`, error);
      throw error;
    }
  }

  /**
   * Get health status for all integrations
   */
  static async getAllIntegrationsHealth(): Promise<{
    system_summary: SystemHealthSummary;
    individual_health: Record<string, {
      frontend: any;
      backend: IntegrationHealthReport;
      correlation: {
        status_match: boolean;
        service_count_match: boolean;
        timestamp_difference: number;
      };
    }>;
  }> {
    try {
      const integrations = Object.keys(this.HEALTH_ENDPOINTS.frontend) as Array<keyof typeof EnhancedIntegrationHealthSkills.HEALTH_ENDPOINTS.frontend>;
      
      const [systemSummary, ...individualHealth] = await Promise.all([
        this.getSystemHealthSummary(),
        ...integrations.map(integration => 
          this.checkIntegrationHealth(integration).catch(error => ({
            integration,
            error: error.message
          }))
        )
      ]);

      const healthMap: Record<string, any> = {};
      individualHealth.forEach((health, index) => {
        if ('integration' in health) {
          healthMap[health.integration] = health;
        } else {
          healthMap[integrations[index]] = health;
        }
      });

      return {
        system_summary: systemSummary,
        individual_health: healthMap
      };
    } catch (error) {
      console.error('Failed to get all integrations health:', error);
      throw error;
    }
  }

  /**
   * Monitor integration health over time
   */
  static async startHealthMonitoring(
    integration: keyof typeof EnhancedIntegrationHealthSkills.HEALTH_ENDPOINTS.frontend,
    interval: number = 30000, // 30 seconds
    onHealthChange: (healthData: any) => void
  ): Promise<{ stop: () => void }> {
    let previousHealth: any = null;
    let monitoringInterval: NodeJS.Timeout;

    const checkHealth = async () => {
      try {
        const currentHealth = await this.checkIntegrationHealth(integration);
        
        // Detect changes
        if (previousHealth) {
          const hasChanged = 
            previousHealth.frontend.status !== currentHealth.frontend.status ||
            previousHealth.backend.overall_status !== currentHealth.backend.overall_status ||
            previousHealth.frontend.connected_count !== currentHealth.frontend.connected_count ||
            previousHealth.backend.connected_count !== currentHealth.backend.connected_count;
          
          if (hasChanged) {
            onHealthChange({
              integration,
              previous: previousHealth,
              current: currentHealth,
              change_detected: true,
              timestamp: new Date().toISOString()
            });
          }
        } else {
          // First check
          onHealthChange({
            integration,
            current: currentHealth,
            first_check: true,
            timestamp: new Date().toISOString()
          });
        }
        
        previousHealth = currentHealth;
      } catch (error) {
        console.error(`Health monitoring error for ${integration}:`, error);
        onHealthChange({
          integration,
          error: error.message,
          timestamp: new Date().toISOString()
        });
      }
    };

    // Start monitoring
    await checkHealth(); // Initial check
    monitoringInterval = setInterval(checkHealth, interval);

    return {
      stop: () => {
        if (monitoringInterval) {
          clearInterval(monitoringInterval);
        }
      }
    };
  }

  /**
   * Get health trend analysis
   */
  static async getHealthTrendAnalysis(
    integration: keyof typeof EnhancedIntegrationHealthSkills.HEALTH_ENDPOINTS.frontend,
    timeRange: '1h' | '6h' | '24h' | '7d' = '24h'
  ): Promise<{
    integration: string;
    time_range: string;
    trend: {
      status_stability: number;
      uptime_percentage: number;
      avg_response_time: number;
      error_rate: number;
      status_changes: number;
    };
    recommendations: string[];
  }> {
    try {
      // This would normally query historical health data
      // For now, we'll provide a mock analysis based on current state
      const currentHealth = await this.checkIntegrationHealth(integration);
      
      const isHealthy = currentHealth.backend.overall_status === 'healthy';
      const responseTime = currentHealth.backend.services
        .filter(s => s.response_time)
        .reduce((acc, s) => acc + (s.response_time || 0), 0) / 
        currentHealth.backend.services.filter(s => s.response_time).length || 0;
      
      return {
        integration,
        time_range: timeRange,
        trend: {
          status_stability: isHealthy ? 0.95 : 0.7,
          uptime_percentage: isHealthy ? 0.98 : 0.85,
          avg_response_time: responseTime || 150,
          error_rate: isHealthy ? 0.02 : 0.15,
          status_changes: isHealthy ? 1 : 5
        },
        recommendations: this.generateHealthRecommendations(currentHealth)
      };
    } catch (error) {
      console.error(`Failed to get health trend for ${integration}:`, error);
      throw error;
    }
  }

  /**
   * Generate health recommendations based on current status
   */
  private static generateHealthRecommendations(healthData: any): string[] {
    const recommendations: string[] = [];
    const { frontend, backend } = healthData;

    if (backend.overall_status === 'unhealthy') {
      recommendations.push('Critical: Integration is unhealthy - check authentication and API connectivity');
    } else if (backend.overall_status === 'degraded') {
      recommendations.push('Warning: Integration is degraded - some services may not be functioning properly');
    }

    // Check for slow response times
    const slowServices = backend.services.filter((s: ServiceHealth) => s.response_time && s.response_time > 1000);
    if (slowServices.length > 0) {
      recommendations.push(`${slowServices.length} service(s) showing slow response times (>1s)`);
    }

    // Check for error states
    const errorServices = backend.services.filter((s: ServiceHealth) => s.status === 'unhealthy');
    if (errorServices.length > 0) {
      recommendations.push(`${errorServices.length} service(s) in error state - check logs and configuration`);
    }

    // Check backend-frontend correlation
    if (frontend.status !== backend.overall_status) {
      recommendations.push('Frontend and backend health status do not match - check network connectivity');
    }

    // Add optimization recommendations
    if (backend.connected_count === backend.total_services) {
      recommendations.push('All services are healthy - consider setting up proactive monitoring alerts');
    }

    return recommendations;
  }

  /**
   * Get integration health metrics for dashboard
   */
  static async getDashboardMetrics(): Promise<{
    overview: {
      total_integrations: number;
      healthy_count: number;
      degraded_count: number;
      unhealthy_count: number;
      overall_health_score: number;
    };
    integrations: Array<{
      name: string;
      status: string;
      health_score: number;
      services_connected: number;
      total_services: number;
      last_check: string;
      response_time?: number;
    }>;
    alerts: Array<{
      integration: string;
      severity: 'critical' | 'warning' | 'info';
      message: string;
      timestamp: string;
    }>;
  }> {
    try {
      const systemSummary = await this.getSystemHealthSummary();
      const backendHealth = await this.getBackendHealthStatus();
      
      const overview = {
        total_integrations: systemSummary.total_integrations,
        healthy_count: systemSummary.healthy_integrations,
        degraded_count: systemSummary.degraded_integrations,
        unhealthy_count: systemSummary.unhealthy_integrations,
        overall_health_score: (systemSummary.healthy_integrations / systemSummary.total_integrations) * 100
      };

      const integrations = Object.entries(backendHealth.integrations || {}).map(([name, report]: [string, any]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        status: report.overall_status,
        health_score: (report.connected_count / report.total_services) * 100,
        services_connected: report.connected_count,
        total_services: report.total_services,
        last_check: report.timestamp,
        response_time: report.services
          .filter((s: ServiceHealth) => s.response_time)
          .reduce((acc: number, s: ServiceHealth) => acc + (s.response_time || 0), 0) / 
          report.services.filter((s: ServiceHealth) => s.response_time).length || undefined
      }));

      const alerts: any[] = [];
      integrations.forEach((integration) => {
        if (integration.status === 'unhealthy') {
          alerts.push({
            integration: integration.name,
            severity: 'critical' as const,
            message: `${integration.name} integration is unhealthy`,
            timestamp: integration.last_check
          });
        } else if (integration.status === 'degraded') {
          alerts.push({
            integration: integration.name,
            severity: 'warning' as const,
            message: `${integration.name} integration is degraded`,
            timestamp: integration.last_check
          });
        }
        
        if (integration.response_time && integration.response_time > 1000) {
          alerts.push({
            integration: integration.name,
            severity: 'warning' as const,
            message: `${integration.name} showing slow response times`,
            timestamp: integration.last_check
          });
        }
      });

      return {
        overview,
        integrations,
        alerts
      };
    } catch (error) {
      console.error('Failed to get dashboard metrics:', error);
      throw error;
    }
  }
}