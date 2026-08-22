import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  // Round 80: forward the caller's Authorization header to the backend
  const fwdAuth = req.headers.authorization
    ? { Authorization: req.headers.authorization as string }
    : {};

  if (req.method === 'GET') {
    return res.status(200).json({
      success: true,
      service: "Asana Health",
      timestamp: new Date().toISOString()
    });
  } else {
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
    return res.status(405).json({ error: 'Method not allowed' });
  }
}
