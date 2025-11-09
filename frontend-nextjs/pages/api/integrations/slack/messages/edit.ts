import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  if (req.method === 'POST') {
    try {
      const { channelId, message } = req.body;

      if (!channelId || !message) {
        return res.status(400).json({
          success: false,
          error: 'channelId and message are required'
        });
      }

      const response = await fetch(`${backendUrl}/api/slack/messages/edit`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: 'current',
          channel_id: channelId,
          text: message,
        }),
      });

      const data = await response.json();
      
      if (response.ok) {
        return res.status(200).json(data);
      } else {
        return res.status(400).json(data);
      }
    } catch (error) {
      console.error('Error editing message:', error);
      return res.status(500).json({
        success: false,
        error: 'Failed to edit message'
      });
    }
  } else {
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}