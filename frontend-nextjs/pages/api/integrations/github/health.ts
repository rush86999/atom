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
        // Comprehensive health checks for GitHub services
        const healthChecks = await Promise.allSettled([
            // API Health Check
            fetch(`${backendUrl}/api/github/health`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                signal: AbortSignal.timeout(5000),
            }),
        ]);

        const [apiResult] = healthChecks;

        // Process results
        const isHealthy = apiResult.status === 'fulfilled' && apiResult.value.ok;

        // Parse error if needed
        let errorMsg: string | undefined;
        if (apiResult.status === 'rejected') {
            errorMsg = apiResult.reason?.message;
        } else if (apiResult.value && !apiResult.value.ok) {
            errorMsg = await getErrorText(apiResult.value);
        }

        const apiHealth: ServiceHealth = {
            status: isHealthy ? 'healthy' : 'unhealthy',
            connected: isHealthy,
            response_time: apiResult.status === 'fulfilled' ? Date.now() - startTime : undefined,
            last_check: new Date().toISOString(),
            error: errorMsg,
        };

        // GitHub doesn't have a separate auth health check exposed, so we mirror API status
        // or we could skip it. For consistency with valid interfaces, we include it.
        const authHealth: ServiceHealth = {
            status: isHealthy ? 'healthy' : 'unhealthy',
            connected: isHealthy,
            last_check: new Date().toISOString(),
        };

        const services = { api: apiHealth, auth: authHealth };
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
        console.error('GitHub health check error:', error);
        return res.status(503).json({
            status: 'unhealthy',
            backend: 'disconnected',
            error: 'GitHub services unavailable',
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
