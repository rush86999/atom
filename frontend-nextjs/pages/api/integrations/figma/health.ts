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

  if (req.method === 'GET') {
    try {
      const response = await fetch(`${backendUrl}/api/integrations/figma/health`, { headers: { ...fwdAuth } });
      const data = await response.json();

      return res.status(200).json(data);
    } catch (error) {
      console.error('Figma health check failed:', error);
      return res.status(500).json({
        success: false,
        error: 'Health check failed'
      });
    }
  } else {
    res.setHeader('Allow', ['GET']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
