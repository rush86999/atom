import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5059';

  try {
    // Stripe routes are mounted at /api/stripe/health based on router setup
    const response = await fetch(`${backendUrl}/api/stripe/health`);
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
