import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  if (req.method === 'POST') {
    try {
      const { channelId, action } = req.body;

      if (!channelId || !action) {
        return res.status(400).json({
          success: false,
          error: 'channelId and action are required'
        });
      }

      let endpoint = '';
      if (action === 'join') {
        endpoint = `/api/slack/channels/${channelId}/join`;
      } else if (action === 'leave') {
        endpoint = `/api/slack/channels/${channelId}/leave`;
      } else if (action === 'archive') {
        endpoint = `/api/slack/channels/${channelId}/archive`;
      } else if (action === 'unarchive') {
        endpoint = `/api/slack/channels/${channelId}/unarchive`;
      } else {
        return res.status(400).json({
          success: false,
          error: 'action must be one of: join, leave, archive, unarchive'
        });
      }

      const response = await fetch(`${backendUrl}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: 'current',
        }),
      });

      const data = await response.json();
      
      if (response.ok) {
        return res.status(200).json(data);
      } else {
        return res.status(400).json(data);
      }
    } catch (error) {
      console.error(`Error performing channel action:`, error);
      return res.status(500).json({
        success: false,
        error: 'Failed to perform channel action'
      });
    }
  } else {
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}