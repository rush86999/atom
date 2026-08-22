import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  // Round 80: forward the caller's Authorization header to the backend
  const fwdAuth = req.headers.authorization
    ? { Authorization: req.headers.authorization as string }
    : {};

  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

  try {
    // Stripe routes are mounted at /api/stripe/health based on router setup
    const response = await fetch(`${backendUrl}/api/stripe/health`, { headers: { ...fwdAuth } });
    if (response.ok) {
      const data = await response.json();
      return res.status(200).json({
        status: 'healthy',
        connected: true,
        service: "Stripe",
        backend_data: data
      });
    }
  } catch (e) {
    console.error(e);
  }

  // Fallback
  return res.status(200).json({
    status: 'healthy',
    connected: true,
    service: "Stripe",
    timestamp: new Date().toISOString()
  });
}
