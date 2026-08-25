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

/**
 * Revoke a provider's stored OAuth tokens (disconnect).
 * DELETE /api/v1/auth/oauth/tokens/{provider} (auth-gated)
 * 404 = no stored integration for that provider (treated as already-off).
 */
export const disconnectIntegration = async (
  provider: string
): Promise<{ disconnected: boolean; message: string }> => {
  const response = await apiService.delete<{ status: string; message: string }>(
    `/api/v1/auth/oauth/tokens/${provider}`
  );
  if (response.success && response.data) {
    return { disconnected: true, message: response.data.message || 'Disconnected' };
  }
  // 404 -> nothing to revoke; treat as already-disconnected
  if (
    !response.success &&
    /no integration found/i.test(response.error || '')
  ) {
    return { disconnected: true, message: 'Already disconnected' };
  }
  throw new Error(response.error || 'Failed to disconnect');
};

/**
 * Fetch the OAuth authorization URL for a provider (JSON variant of the
 * initiate endpoint — mobile cannot follow the default 302).
 * GET /api/v1/auth/oauth/{provider}/initiate?format=json (auth-resolved)
 */
export const getOAuthAuthorizeUrl = async (
  provider: string
): Promise<string> => {
  const response = await apiService.get<{ url: string }>(
    `/api/v1/auth/oauth/${provider}/initiate?format=json`
  );
  if (response.success && response.data?.url) {
    return response.data.url;
  }
  throw new Error(response.error || 'Failed to fetch authorization URL');
};
