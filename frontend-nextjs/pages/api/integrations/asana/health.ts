import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method === 'GET') {
    return res.status(200).json({
      success: true,
      service: "Asana Health",
      timestamp: new Date().toISOString()
    });
  } else {
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5059';
    return res.status(405).json({ error: 'Method not allowed' });
  }
}
