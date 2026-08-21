/**
 * Next.js Deployment Status API
 * Get the status of a specific deployment
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
      deployment_id,
      include_build_info = true 
    } = req.body;

    if (!user_id || !deployment_id) {
      return res.status(400).json({ error: 'User ID and Deployment ID are required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
    const response = await fetch(`${backendUrl}/api/integrations/nextjs/deployment/status`, {
      method: 'POST',
      headers: { ...fwdAuth,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id,
        deployment_id,
        include_build_info
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        ok: false,
        error: data.error || 'Failed to fetch deployment status'
      });
    }

    return res.status(200).json({
      ok: true,
      deployment: data.deployment,
      build: data.build,
      status: data.deployment?.status || 'unknown',
      url: data.deployment?.url,
      created_at: data.deployment?.created_at,
      ready_state: data.deployment?.ready
    });

  } catch (error) {
    console.error('Deployment status fetch error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}