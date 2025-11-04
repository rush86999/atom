/**
 * Next.js Deploy API
 * Trigger a new deployment for a Next.js project
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
    const { 
      user_id, 
      project_id,
      branch = 'main',
      force = false 
    } = req.body;

    if (!user_id || !project_id) {
      return res.status(400).json({ error: 'User ID and Project ID are required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/integrations/nextjs/deploy`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id,
        project_id,
        branch,
        force
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        ok: false,
        error: data.error || 'Failed to trigger deployment'
      });
    }

    return res.status(200).json({
      ok: true,
      deployment: data.deployment,
      url: data.deployment_url,
      message: `Deployment triggered for project ${project_id} on branch ${branch}`
    });

  } catch (error) {
    console.error('Deployment trigger error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}