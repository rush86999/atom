import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  try {
    const response = await fetch(`${backendUrl}/api/zendesk/health`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (response.ok) {
      const healthData = await response.json();
      return res.status(200).json({
        status: 'healthy',
        backend: 'connected',
        ...healthData,
      });
    } else {
      return res.status(503).json({
        status: 'unhealthy',
        error: 'Backend Zendesk service not responding',
      });
    }
  } catch (error) {
    console.error('Zendesk health check error:', error);
    return res.status(503).json({
      status: 'unhealthy',
      error: 'Zendesk service unavailable',
    });
  }
}