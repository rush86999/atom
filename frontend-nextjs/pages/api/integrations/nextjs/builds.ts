/**
 * Next.js Builds Endpoint
 * Fetch build information for Next.js projects
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
    const { 
      user_id, 
      project_id,
      status = 'all',
      limit = 20,
      include_logs = false
    } = req.body;

    if (!user_id || !project_id) {
      return res.status(400).json({ error: 'User ID and Project ID are required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
    const response = await fetch(`${backendUrl}/api/integrations/nextjs/builds`, {
      method: 'POST',
      headers: { ...fwdAuth,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id,
        project_id,
        status,
        limit,
        include_logs
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        ok: false,
        error: data.error || 'Failed to fetch Next.js builds'
      });
    }

    return res.status(200).json({
      ok: true,
      builds: data.builds,
      count: data.builds?.length || 0,
    });

  } catch (error) {
    console.error('Next.js builds fetch error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}