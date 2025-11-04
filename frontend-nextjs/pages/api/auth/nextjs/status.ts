/**
 * Next.js Status Check Endpoint
 * Check if Next.js/Vercel integration is connected
 */

import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/auth/nextjs/status`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        connected: false,
        error: data.error || 'Failed to check Next.js status'
      });
    }

    return res.status(200).json({
      connected: data.connected,
      user: data.user,
      team_id: data.team_id,
      last_sync: data.last_sync,
    });

  } catch (error) {
    console.error('Next.js status check error:', error);
    return res.status(500).json({
      connected: false,
      error: 'Internal server error'
    });
  }
}