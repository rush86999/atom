import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5059';

  try {
    // Check health of Microsoft 365 service (Unified Endpoint)
    const response = await fetch(`${backendUrl}/api/integrations/microsoft365/health`);

    // Default structure if backend doesn't return detailed breakdown
    // The backend returns { status: "healthy", service: "microsoft365", ... }
    const isHealthy = response.ok;

    const services = {
      outlook: {
        status: isHealthy ? "healthy" : "unhealthy",
        connected: isHealthy,
      },
      teams: {
        status: isHealthy ? "healthy" : "unhealthy",
        connected: isHealthy,
      },
      onedrive: {
        status: isHealthy ? "healthy" : "unhealthy",
        connected: isHealthy,
      },
      // Backend is the source of truth
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