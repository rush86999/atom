/**
 * Integration Service
 * Read-only visibility into platform integrations for the mobile app
 * (round 80: mobile had zero integration journeys — this adds v1 status).
 */

import apiService from './api';

export interface IntegrationsCatalog {
  total: number;
  integrations: string[];
  loaded: {
    cached: number;
    max_size: number | null;
    hits: number;
    misses: number;
  };
}

export interface IntegrationHealthStatus {
  service_name: string;
  status: string;
  enabled: boolean;
  configured: boolean;
  endpoint_count?: number;
  error_message?: string | null;
}

export interface AllIntegrationsHealth {
  total_integrations: number;
  healthy_integrations: number;
  configured_integrations: number;
  enabled_integrations: number;
  integration_status: IntegrationHealthStatus[];
  overall_health_percentage: number;
}

/**
 * Fetch the integrations catalog (names + lazy-load stats).
 * GET /api/integrations (auth-gated)
 */
export const getIntegrationsCatalog = async (): Promise<IntegrationsCatalog> => {
  const response = await apiService.get<IntegrationsCatalog>('/api/integrations');
  if (response.success && response.data) {
    return response.data;
  }
  throw new Error(response.error || 'Failed to fetch integrations');
};

/**
 * Fetch aggregate integration health (33+ services).
 * GET /api/v1/integrations/health
 */
export const getIntegrationHealth = async (): Promise<AllIntegrationsHealth> => {
  const response = await apiService.get<AllIntegrationsHealth>(
    '/api/v1/integrations/health'
  );
  if (response.success && response.data) {
    return response.data;
  }
  throw new Error(response.error || 'Failed to fetch integration health');
};
