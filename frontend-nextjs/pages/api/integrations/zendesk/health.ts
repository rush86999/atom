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
    const response = await fetch(`${backendUrl}/api/zendesk/status`, {
      method: 'GET',
      headers: { ...fwdAuth,
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