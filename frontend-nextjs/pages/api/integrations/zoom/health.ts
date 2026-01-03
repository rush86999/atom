import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5059';

  try {
    const response = await fetch(`${backendUrl}/api/zoom/v1/health`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (response.ok) {
      const data = await response.json();
      return res.status(200).json(data);
    } else {
      return res.status(response.status).json({
        ok: false,
        status: 'unhealthy',
        error: 'Backend Zoom service not responding'
      });
    }
  } catch (error) {
    console.error('Zoom health check error:', error);
    return res.status(503).json({
      ok: false,
      status: 'unhealthy',
      error: 'Zoom service unavailable'
    });
  }
}
