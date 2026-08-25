import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  // Round 80: forward the caller's Authorization header to the backend
  const fwdAuth = req.headers.authorization
    ? { Authorization: req.headers.authorization as string }
    : {};

  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

  try {
    // Check health of Google Workspace services
    const [driveResponse, gmailResponse, calendarResponse] = await Promise.all([
      fetch(`${backendUrl}/api/google-drive/health`, {
        method: 'HEAD',
      }),
      fetch(`${backendUrl}/api/gmail/health`, {
        method: 'HEAD',
      }),
      fetch(`${backendUrl}/api/calendar/health`, {
        method: 'HEAD',
      }),
    ]);

    // Check new Google Workspace services
    const workspaceResponse = await fetch(`${backendUrl}/api/google-workspace/health`, { headers: { ...fwdAuth } });

    const services = {
      drive: {
        status: driveResponse.ok ? "healthy" : "unhealthy",
        connected: driveResponse.ok,
      },
      gmail: {
        status: gmailResponse.ok ? "healthy" : "unhealthy",
        connected: gmailResponse.ok,
      },
      calendar: {
        status: calendarResponse.ok ? "healthy" : "unhealthy",
        connected: calendarResponse.ok,
      },
      workspace: {
        status: workspaceResponse.ok ? "healthy" : "unhealthy",
        connected: workspaceResponse.ok,
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
    console.error('Google Workspace health check error:', error);
    return res.status(503).json({
      status: 'unhealthy',
      error: 'Google Workspace services unavailable',
    });
  }
}