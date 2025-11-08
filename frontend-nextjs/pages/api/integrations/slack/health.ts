import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  try {
    // Check health of Slack services
    const [oauthResponse, enhancedResponse] = await Promise.all([
      fetch(`${backendUrl}/api/slack/oauth/start`, {
        method: 'HEAD',
      }),
      fetch(`${backendUrl}/api/slack/health`),
    ]);

    const services = {
      oauth: {
        status: oauthResponse.ok ? "healthy" : "unhealthy",
        connected: oauthResponse.ok,
      },
      enhanced: {
        status: enhancedResponse.ok ? "healthy" : "unhealthy",
        connected: enhancedResponse.ok,
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
    console.error('Slack health check error:', error);
    return res.status(503).json({
      status: 'unhealthy',
      error: 'Slack services unavailable',
    });
  }
}