import { NextApiRequest, NextApiResponse } from "next";

interface ServiceHealth {
  status: 'healthy' | 'unhealthy' | 'degraded';
  connected: boolean;
  response_time?: number;
  last_check: string;
  error?: string;
}

interface HealthResponse {
  status: string;
  backend: 'connected' | 'disconnected';
  services: {
    api: ServiceHealth;
    auth: ServiceHealth;
    webhooks: ServiceHealth;
  };
  connected_count: number;
  total_services: number;
  timestamp: string;
  version?: string;
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';
  const startTime = Date.now();
  const useBridgeSystem = process.env.USE_BRIDGE_SYSTEM === 'true';

  try {
    let apiHealth: ServiceHealth | undefined;
    let authHealth: ServiceHealth | undefined;
    let webhookHealth: ServiceHealth | undefined;

    // Use bridge system if available
    if (useBridgeSystem) {
      // Try bridge system first
      try {
        const bridgeResponse = await fetch(`${backendUrl}/api/bridge/health`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
          signal: AbortSignal.timeout(5000),
        });

        if (bridgeResponse.ok) {
          // Get bridge status which includes all integrations
          const bridgeStatusResponse = await fetch(`${backendUrl}/api/bridge/status`, {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
            },
            signal: AbortSignal.timeout(10000),
          });

          if (bridgeStatusResponse.ok) {
            const bridgeStatus = await bridgeStatusResponse.json();

            // Extract HubSpot-specific information
            const hubspotInfo = bridgeStatus.integrations?.hubspot;

            if (hubspotInfo) {
              apiHealth = {
                status: hubspotInfo.status === 'active' ? 'healthy' : 'unhealthy',
                connected: hubspotInfo.status === 'active',
                response_time: startTime ? Date.now() - startTime : undefined,
                last_check: hubspotInfo.last_check || new Date().toISOString(),
                error: hubspotInfo.error_message,
              };

              // Map bridge services to our structure
              authHealth = {
                status: hubspotInfo.status === 'active' ? 'healthy' : 'unhealthy',
                connected: hubspotInfo.status === 'active',
                response_time: startTime ? Date.now() - startTime : undefined,
                last_check: hubspotInfo.last_check || new Date().toISOString(),
              };

              webhookHealth = {
                status: hubspotInfo.available_endpoints?.includes('webhooks') ? 'healthy' : 'degraded',
                connected: hubspotInfo.available_endpoints?.includes('webhooks') || false,
                response_time: startTime ? Date.now() - startTime : undefined,
                last_check: hubspotInfo.last_check || new Date().toISOString(),
                error: hubspotInfo.available_endpoints?.includes('webhooks') ? undefined : 'Webhook endpoints not configured',
              };
            }
          }
        }
      } catch (bridgeError) {
        console.warn('Bridge system not available, falling back to direct endpoints:', bridgeError);
      }
    }

    // Fallback to direct endpoint checks
    if (!apiHealth || !authHealth || !webhookHealth) {
      const healthChecks = await Promise.allSettled([
        // API Health Check
        fetch(`${backendUrl}/api/hubspot/health`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
          signal: AbortSignal.timeout(5000),
        }),
        // Auth Service Health Check
        fetch(`${backendUrl}/api/oauth/hubspot/status`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
          signal: AbortSignal.timeout(5000),
        }),
        // Webhook Health Check
        fetch(`${backendUrl}/api/hubspot/webhooks/health`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
          signal: AbortSignal.timeout(5000),
        }),
      ]);

      const [apiResult, authResult, webhookResult] = healthChecks;

      // Only override if bridge didn't provide data
      apiHealth = apiHealth || {
        status: apiResult.status === 'fulfilled' && apiResult.value.ok ? 'healthy' : 'unhealthy',
        connected: apiResult.status === 'fulfilled' && apiResult.value.ok,
        response_time: apiResult.status === 'fulfilled' ? Date.now() - startTime : undefined,
        last_check: new Date().toISOString(),
        error: apiResult.status === 'rejected' ? apiResult.reason?.message :
          apiResult.value?.ok ? undefined : await getErrorText(apiResult.value),
      };

      authHealth = authHealth || {
        status: authResult.status === 'fulfilled' && authResult.value.ok ? 'healthy' : 'unhealthy',
        connected: authResult.status === 'fulfilled' && authResult.value.ok,
        response_time: authResult.status === 'fulfilled' ? Date.now() - startTime : undefined,
        last_check: new Date().toISOString(),
        error: authResult.status === 'rejected' ? authResult.reason?.message :
          authResult.value?.ok ? undefined : await getErrorText(authResult.value),
      };

      webhookHealth = webhookHealth || {
        status: webhookResult.status === 'fulfilled' && webhookResult.value.ok ? 'healthy' : 'degraded',
        connected: webhookResult.status === 'fulfilled' && webhookResult.value.ok,
        response_time: webhookResult.status === 'fulfilled' ? Date.now() - startTime : undefined,
        last_check: new Date().toISOString(),
        error: webhookResult.status === 'rejected' ? webhookResult.reason?.message :
          webhookResult.value?.ok ? undefined : await getErrorText(webhookResult.value),
      };
    }

    const services = { api: apiHealth, auth: authHealth, webhooks: webhookHealth };
    const connectedCount = Object.values(services).filter(s => s.connected).length;
    const overallStatus = connectedCount === Object.keys(services).length ? 'healthy' :
      connectedCount > 0 ? 'degraded' : 'unhealthy';

    const response: HealthResponse = {
      status: overallStatus,
      backend: 'connected',
      services,
      connected_count: connectedCount,
      total_services: Object.keys(services).length,
      timestamp: new Date().toISOString(),
      version: '2.0.0',
    };

    return res.status(connectedCount > 0 ? 200 : 503).json(response);
  } catch (error) {
    console.error('HubSpot health check error:', error);
    return res.status(503).json({
      status: 'unhealthy',
      backend: 'disconnected',
      error: 'HubSpot services unavailable',
      timestamp: new Date().toISOString(),
    });
  }
}

async function getErrorText(response: Response): Promise<string> {
  try {
    const text = await response.text();
    return text || response.statusText || 'Unknown error';
  } catch {
    return response.statusText || 'Unknown error';
  }
}
