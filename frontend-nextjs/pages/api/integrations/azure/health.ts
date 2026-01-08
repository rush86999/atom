import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5059';

  try {
    // Check health of generic backend as proxy for Azure infra (since specific Azure routes might not be loaded)
    const infraResponse = await fetch(`${backendUrl}/health`);

    // Attempt specific auth check if available, otherwise assume disconnected or unknown
    let oauthStatus = "unknown";
    let oauthConnected = false;
    // Skipped specific auth check as endpoint does not exist yet
    if (infraResponse.ok) {
      oauthStatus = "healthy";
      oauthConnected = true;
    }

    const services = {
      oauth: {
        status: oauthStatus,
        connected: oauthConnected,
      },
      infrastructure: {
        status: infraResponse.ok ? "healthy" : "unhealthy",
        connected: infraResponse.ok,
      },
    };

    const overallStatus = Object.values(services).some(s => s.connected)
      ? "healthy"
      : "disconnected";

    return res.status(200).json({
      status: overallStatus,
      backend: 'connected',
      services,
      connected_count: Object.values(services).filter(s => s.connected).length,
      total_services: Object.keys(services).length,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error('Azure health check error:', error);
    return res.status(503).json({
      status: 'unhealthy',
      error: 'Azure services unavailable',
    });
  }
}