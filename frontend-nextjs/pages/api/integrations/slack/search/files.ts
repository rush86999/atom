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

  if (req.method === 'POST') {
    try {
      const { query, count = 50, sort = 'timestamp_desc' } = req.body;

      if (!query) {
        return res.status(400).json({
          success: false,
          error: 'query is required'
        });
      }

      const response = await fetch(`${backendUrl}/api/slack/search/files`, {
        method: 'POST',
        headers: { ...fwdAuth,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: 'current',
          query,
          count,
          sort,
        }),
      });

      const data = await response.json();
      
      if (response.ok) {
        return res.status(200).json(data);
      } else {
        return res.status(400).json(data);
      }
    } catch (error) {
      console.error('Error searching files:', error);
      return res.status(500).json({
        success: false,
        error: 'Failed to search files'
      });
    }
  } else {
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}