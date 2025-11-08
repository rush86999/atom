import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  try {
    // Check health of Azure services
    const [oauthResponse, infraResponse] = await Promise.all([
      fetch(`${backendUrl}/api/auth/azure/health`),
      fetch(`${backendUrl}/api/azure/health`)
    ]);

    const services = {
      oauth: {
        status: oauthResponse.ok ? "healthy" : "unhealthy",
        connected: oauthResponse.ok,
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