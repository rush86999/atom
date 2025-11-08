import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  try {
    // Check health of Tableau services
    const [authResponse, apiResponse] = await Promise.all([
      fetch(`${backendUrl}/api/tableau/health`, {
        method: 'HEAD',
      }),
      fetch(`${backendUrl}/api/tableau/health`, {
        method: 'GET',
      }),
    ]);

    const services = {
      auth: {
        status: authResponse.ok ? "healthy" : "unhealthy",
        connected: authResponse.ok,
      },
      api: {
        status: apiResponse.ok ? "healthy" : "unhealthy",
        connected: apiResponse.ok,
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
    console.error('Tableau health check error:', error);
    return res.status(503).json({
      status: 'unhealthy',
      error: 'Tableau services unavailable',
    });
  }
}