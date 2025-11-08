import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  try {
    // Check health of all Microsoft services
    const [outlookResponse, teamsResponse, onedriveResponse] = await Promise.all([
      fetch(`${backendUrl}/api/integrations/microsoft/health`),
      fetch(`${backendUrl}/api/integrations/teams/health`),
      fetch(`${backendUrl}/api/onedrive/health`),
    ]);

    const services = {
      outlook: {
        status: outlookResponse.ok ? "healthy" : "unhealthy",
        connected: outlookResponse.ok,
      },
      teams: {
        status: teamsResponse.ok ? "healthy" : "unhealthy", 
        connected: teamsResponse.ok,
      },
      onedrive: {
        status: onedriveResponse.ok ? "healthy" : "unhealthy",
        connected: onedriveResponse.ok,
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
    console.error('Microsoft 365 health check error:', error);
    return res.status(503).json({
      status: 'unhealthy',
      error: 'Microsoft 365 services unavailable',
    });
  }
}