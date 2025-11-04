/**
 * GitLab OAuth Callback API
 * Handle GitLab OAuth callback
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
    const { code, state } = req.body;

    if (!code || !state) {
      return res.status(400).json({ error: 'Code and state are required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/auth/gitlab/callback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        code,
        state
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        ok: false,
        error: data.error || 'OAuth callback failed'
      });
    }

    return res.status(200).json({
      ok: true,
      user_id: data.user_id,
      user: data.user,
      projects: data.projects,
      success: true
    });

  } catch (error) {
    console.error('GitLab OAuth callback error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}