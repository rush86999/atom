/**
 * GitLab OAuth Start API
 * Initiate GitLab OAuth flow
 */

import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  // Round 80: forward the caller's Authorization header to the backend
  const fwdAuth = req.headers.authorization
    ? { Authorization: req.headers.authorization as string }
    : {};

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { user_id, scopes = ['read_repository', 'api', 'read_user'] } = req.body;

    if (!user_id) {
      return res.status(400).json({ error: 'User ID is required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
    const response = await fetch(`${backendUrl}/api/auth/gitlab/authorize`, {
      method: 'POST',
      headers: { ...fwdAuth,
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