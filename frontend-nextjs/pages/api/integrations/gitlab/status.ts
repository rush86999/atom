/**
 * GitLab Status API
 * Check GitLab connection status
 */

import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { user_id } = req.body;

    if (!user_id) {
      return res.status(400).json({ error: 'User ID is required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/integrations/gitlab/status`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        ok: false,
        error: data.error || 'Failed to check GitLab status'
      });
    }

    return res.status(200).json({
      ok: true,
      connected: data.connected,
      user: data.user,
      token_status: data.token_status,
      last_check: data.last_check,
      success: true
    });

  } catch (error) {
    console.error('GitLab status check error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}