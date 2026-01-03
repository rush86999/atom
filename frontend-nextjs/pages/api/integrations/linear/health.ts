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
    issues: ServiceHealth;
    teams: ServiceHealth;
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

  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5059';
  const startTime = Date.now();

  try {
    // Comprehensive health checks for Linear services
    const healthChecks = await Promise.allSettled([
      // API Health Check
      fetch(`${backendUrl}/api/linear/status`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(5000),
      }),
      // Teams Service Health Check
      fetch(`${backendUrl}/api/linear/teams/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(5000),
      }),
    ]);

    const [statusResult, teamsResult] = healthChecks;

    const isHealthy = statusResult.status === 'fulfilled' && statusResult.value.ok;

    // Process results
    const apiHealth: ServiceHealth = {
      status: isHealthy ? 'healthy' : 'unhealthy',
      connected: isHealthy,
      response_time: statusResult.status === 'fulfilled' ? Date.now() - startTime : undefined,
      last_check: new Date().toISOString(),
      error: statusResult.status === 'rejected' ? statusResult.reason?.message :
        statusResult.value?.ok ? undefined : await getErrorText(statusResult.value),
    };

    const authHealth: ServiceHealth = {
      status: isHealthy ? 'healthy' : 'unhealthy',
      connected: isHealthy,
      last_check: new Date().toISOString(),
    };

    const issuesHealth: ServiceHealth = {
      status: isHealthy ? 'healthy' : 'degraded',
      connected: isHealthy,
      last_check: new Date().toISOString(),
    };

    const teamsHealth: ServiceHealth = {
      status: teamsResult && teamsResult.status === 'fulfilled' && teamsResult.value.ok ? 'healthy' : 'degraded',
      connected: teamsResult && teamsResult.status === 'fulfilled' && teamsResult.value.ok,
      last_check: new Date().toISOString(),
      error: !teamsResult ? 'Check skipped' : teamsResult.status === 'rejected' ? teamsResult.reason?.message :
        teamsResult.value?.ok ? undefined : await getErrorText(teamsResult.value),
    };

    const services = { api: apiHealth, auth: authHealth, issues: issuesHealth, teams: teamsHealth };
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
    console.error('Linear health check error:', error);
    return res.status(503).json({
      status: 'unhealthy',
      backend: 'disconnected',
      error: 'Linear services unavailable',
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
