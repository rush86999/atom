/**
 * Next.js OAuth Callback Endpoint
 * Handles OAuth callback from Vercel
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
    const { code, state, platform } = req.body;

    if (!code) {
      return res.status(400).json({ error: 'Authorization code is required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/auth/nextjs/callback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        code,
        state,
        platform: platform || 'web'
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        ok: false,
        error: data.error || 'Failed to complete Next.js OAuth'
      });
    }

    return res.status(200).json({
      ok: true,
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      expires_at: data.expires_at,
      user: data.user,
      projects: data.projects,
      team_id: data.team_id,
    });

  } catch (error) {
    console.error('Next.js OAuth callback error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}