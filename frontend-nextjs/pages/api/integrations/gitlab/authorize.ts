/**
 * GitLab OAuth Start API
 * Initiate GitLab OAuth flow
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
    const { user_id, scopes = ['read_repository', 'api', 'read_user'] } = req.body;

    if (!user_id) {
      return res.status(400).json({ error: 'User ID is required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/auth/gitlab/authorize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id,
        scopes,
        platform: 'tauri' // Set platform for handling
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        ok: false,
        error: data.error || 'Failed to initiate GitLab OAuth'
      });
    }

    return res.status(200).json({
      ok: true,
      authorization_url: data.authorization_url,
      user_id,
      success: true
    });

  } catch (error) {
    console.error('GitLab OAuth start error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}