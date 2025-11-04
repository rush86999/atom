/**
 * Next.js Projects Endpoint
 * Fetch Next.js projects from Vercel
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
      limit = 50, 
      status = 'active',
      include_builds = false,
      include_deployments = true 
    } = req.body;

    if (!user_id) {
      return res.status(400).json({ error: 'User ID is required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/integrations/nextjs/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id,
        limit,
        status,
        include_builds,
        include_deployments
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        ok: false,
        error: data.error || 'Failed to fetch Next.js projects'
      });
    }

    return res.status(200).json({
      ok: true,
      projects: data.projects,
      builds: data.builds,
      deployments: data.deployments,
      count: data.projects?.length || 0,
    });

  } catch (error) {
    console.error('Next.js projects fetch error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}