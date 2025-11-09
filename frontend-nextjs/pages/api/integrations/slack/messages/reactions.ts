import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  if (req.method === 'POST') {
    try {
      const { channelId, messageId, reaction } = req.body;

      if (!channelId || !messageId || !reaction) {
        return res.status(400).json({
          success: false,
          error: 'channelId, messageId, and reaction are required'
        });
      }

      const response = await fetch(`${backendUrl}/api/slack/messages/${messageId}/reactions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: 'current',
          channel_id: channelId,
          reaction: reaction,
        }),
      });

      const data = await response.json();
      
      if (response.ok) {
        return res.status(200).json(data);
      } else {
        return res.status(400).json(data);
      }
    } catch (error) {
      console.error('Error adding reaction:', error);
      return res.status(500).json({
        success: false,
        error: 'Failed to add reaction'
      });
    }
  } else if (req.method === 'DELETE') {
    try {
      const { channelId, messageId, reaction } = req.body;

      if (!channelId || !messageId || !reaction) {
        return res.status(400).json({
          success: false,
          error: 'channelId, messageId, and reaction are required'
        });
      }

      const response = await fetch(`${backendUrl}/api/slack/messages/${messageId}/reactions/${reaction}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: 'current',
          channel_id: channelId,
        }),
      });

      const data = await response.json();
      
      if (response.ok) {
        return res.status(200).json(data);
      } else {
        return res.status(400).json(data);
      }
    } catch (error) {
      console.error('Error removing reaction:', error);
      return res.status(500).json({
        success: false,
        error: 'Failed to remove reaction'
      });
    }
  } else {
    res.setHeader('Allow', ['POST', 'DELETE']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}