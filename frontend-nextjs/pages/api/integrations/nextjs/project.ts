/**
 * Next.js Project Details API
 * Get detailed information about a specific Next.js project
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
      include_environment_variables = false 
    } = req.body;

    if (!user_id || !project_id) {
      return res.status(400).json({ error: 'User ID and Project ID are required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/integrations/nextjs/project`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id,
        project_id,
        include_environment_variables
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        ok: false,
        error: data.error || 'Failed to fetch project details'
      });
    }

    return res.status(200).json({
      ok: true,
      project: data.project,
      environment_variables: data.environment_variables,
      deployments: data.deployments,
      builds: data.builds
    });

  } catch (error) {
    console.error('Project details fetch error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}