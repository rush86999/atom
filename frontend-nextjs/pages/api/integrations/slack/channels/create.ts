import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  if (req.method === 'POST') {
    try {
      const { name, isPrivate = false, purpose = '' } = req.body;

      if (!name) {
        return res.status(400).json({
          success: false,
          error: 'name is required'
        });
      }

      const response = await fetch(`${backendUrl}/api/slack/channels`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: 'current',
          name,
          is_private: isPrivate,
          purpose,
        }),
      });

      const data = await response.json();
      
      if (response.ok) {
        return res.status(201).json(data);
      } else {
        return res.status(400).json(data);
      }
    } catch (error) {
      console.error('Error creating channel:', error);
      return res.status(500).json({
        success: false,
        error: 'Failed to create channel'
      });
    }
  } else {
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}