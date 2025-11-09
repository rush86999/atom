import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  if (req.method === 'POST') {
    try {
      const response = await fetch(`${backendUrl}/api/figma/search`, {
        method: 'POST',
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req.body)
      });
      
      const data = await response.json();
      
      if (response.ok) {
        return res.status(200).json(data);
      } else {
        return res.status(400).json(data);
      }
    } catch (error) {
      console.error('Figma search endpoint failed:', error);
      return res.status(500).json({
        success: false,
        error: 'Endpoint failed'
      });
    }
  } else {
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
