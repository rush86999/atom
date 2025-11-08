import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  try {
    const response = await fetch(`${backendUrl}/api/auth/salesforce/health`, {
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
        error: 'Backend Salesforce service not responding',
      });
    }
  } catch (error) {
    console.error('Salesforce health check error:', error);
    return res.status(503).json({
      status: 'unhealthy',
      error: 'Salesforce service unavailable',
    });
  }
}