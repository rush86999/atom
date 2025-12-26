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
    auth: ServiceHealth;
    messaging: ServiceHealth;
    events: ServiceHealth;
    webhooks: ServiceHealth;
  };
  connected_count: number;
  total_services: number;
  timestamp: string;
  version?: string;
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';
  const startTime = Date.now();

  try {
    // Comprehensive health checks for Slack services
    const healthChecks = await Promise.allSettled([
      // Auth Service Health Check
      fetch(`${backendUrl}/api/slack/auth/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(5000),
      }),
      // Messaging API Health Check
      fetch(`${backendUrl}/api/slack/messaging/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(5000),
      }),
      // Events API Health Check
      fetch(`${backendUrl}/api/slack/events/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(5000),
      }),
      // Webhooks Health Check
      fetch(`${backendUrl}/api/slack/webhooks/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(5000),
      }),
    ]);

    const [authResult, messagingResult, eventsResult, webhooksResult] = healthChecks;

    // Process results
    const authHealth: ServiceHealth = {
      status: authResult.status === 'fulfilled' && authResult.value.ok ? 'healthy' : 'unhealthy',
      connected: authResult.status === 'fulfilled' && authResult.value.ok,
      response_time: authResult.status === 'fulfilled' ? Date.now() - startTime : undefined,
      last_check: new Date().toISOString(),
      error: authResult.status === 'rejected' ? authResult.reason?.message :
        authResult.value?.ok ? undefined : await getErrorText(authResult.value),
    };

    const messagingHealth: ServiceHealth = {
      status: messagingResult.status === 'fulfilled' && messagingResult.value.ok ? 'healthy' : 'unhealthy',
      connected: messagingResult.status === 'fulfilled' && messagingResult.value.ok,
      response_time: messagingResult.status === 'fulfilled' ? Date.now() - startTime : undefined,
      last_check: new Date().toISOString(),
      error: messagingResult.status === 'rejected' ? messagingResult.reason?.message :
        messagingResult.value?.ok ? undefined : await getErrorText(messagingResult.value),
    };

    const eventsHealth: ServiceHealth = {
      status: eventsResult.status === 'fulfilled' && eventsResult.value.ok ? 'healthy' : 'degraded',
      connected: eventsResult.status === 'fulfilled' && eventsResult.value.ok,
      response_time: eventsResult.status === 'fulfilled' ? Date.now() - startTime : undefined,
      last_check: new Date().toISOString(),
      error: eventsResult.status === 'rejected' ? eventsResult.reason?.message :
        eventsResult.value?.ok ? undefined : await getErrorText(eventsResult.value),
    };

    const webhooksHealth: ServiceHealth = {
      status: webhooksResult.status === 'fulfilled' && webhooksResult.value.ok ? 'healthy' : 'degraded',
      connected: webhooksResult.status === 'fulfilled' && webhooksResult.value.ok,
      response_time: webhooksResult.status === 'fulfilled' ? Date.now() - startTime : undefined,
      last_check: new Date().toISOString(),
      error: webhooksResult.status === 'rejected' ? webhooksResult.reason?.message :
        webhooksResult.value?.ok ? undefined : await getErrorText(webhooksResult.value),
    };

    const services = { auth: authHealth, messaging: messagingHealth, events: eventsHealth, webhooks: webhooksHealth };
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
    console.error('Slack health check error:', error);
    return res.status(503).json({
      status: 'unhealthy',
      backend: 'disconnected',
      error: 'Slack services unavailable',
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