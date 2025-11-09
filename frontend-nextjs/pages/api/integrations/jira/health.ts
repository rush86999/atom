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
    projects: ServiceHealth;
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

  try {
    // Comprehensive health checks for Jira services
    const healthChecks = await Promise.allSettled([
      // API Health Check
      fetch(`${backendUrl}/api/jira/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(5000),
      }),
      // Auth Service Health Check
      fetch(`${backendUrl}/api/oauth/jira/status`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(5000),
      }),
      // Issues Service Health Check
      fetch(`${backendUrl}/api/jira/issues/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(5000),
      }),
      // Projects Service Health Check
      fetch(`${backendUrl}/api/jira/projects/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(5000),
      }),
    ]);

    const [apiResult, authResult, issuesResult, projectsResult] = healthChecks;
    
    // Process results
    const apiHealth: ServiceHealth = {
      status: apiResult.status === 'fulfilled' && apiResult.value.ok ? 'healthy' : 'unhealthy',
      connected: apiResult.status === 'fulfilled' && apiResult.value.ok,
      response_time: apiResult.status === 'fulfilled' ? Date.now() - startTime : undefined,
      last_check: new Date().toISOString(),
      error: apiResult.status === 'rejected' ? apiResult.reason?.message : 
              apiResult.value?.ok ? undefined : await getErrorText(apiResult.value),
    };

    const authHealth: ServiceHealth = {
      status: authResult.status === 'fulfilled' && authResult.value.ok ? 'healthy' : 'unhealthy',
      connected: authResult.status === 'fulfilled' && authResult.value.ok,
      response_time: authResult.status === 'fulfilled' ? Date.now() - startTime : undefined,
      last_check: new Date().toISOString(),
      error: authResult.status === 'rejected' ? authResult.reason?.message : 
              authResult.value?.ok ? undefined : await getErrorText(authResult.value),
    };

    const issuesHealth: ServiceHealth = {
      status: issuesResult.status === 'fulfilled' && issuesResult.value.ok ? 'healthy' : 'degraded',
      connected: issuesResult.status === 'fulfilled' && issuesResult.value.ok,
      response_time: issuesResult.status === 'fulfilled' ? Date.now() - startTime : undefined,
      last_check: new Date().toISOString(),
      error: issuesResult.status === 'rejected' ? issuesResult.reason?.message : 
              issuesResult.value?.ok ? undefined : await getErrorText(issuesResult),
    };

    const projectsHealth: ServiceHealth = {
      status: projectsResult.status === 'fulfilled' && projectsResult.value.ok ? 'healthy' : 'degraded',
      connected: projectsResult.status === 'fulfilled' && projectsResult.value.ok,
      response_time: projectsResult.status === 'fulfilled' ? Date.now() - startTime : undefined,
      last_check: new Date().toISOString(),
      error: projectsResult.status === 'rejected' ? projectsResult.reason?.message : 
              projectsResult.value?.ok ? undefined : await getErrorText(projectsResult),
    };

    const services = { api: apiHealth, auth: authHealth, issues: issuesHealth, projects: projectsHealth };
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
    console.error('Jira health check error:', error);
    return res.status(503).json({
      status: 'unhealthy',
      backend: 'disconnected',
      error: 'Jira services unavailable',
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
