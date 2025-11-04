/**
 * GitLab Trigger Pipeline API
 * Trigger a new GitLab CI/CD pipeline
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
      ref,
      variables = []
    } = req.body;

    if (!user_id || !project_id || !ref) {
      return res.status(400).json({ error: 'User ID, Project ID, and Ref are required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/integrations/gitlab/trigger-pipeline`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id,
        project_id,
        ref,
        variables
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        ok: false,
        error: data.error || 'Failed to trigger pipeline'
      });
    }

    return res.status(200).json({
      ok: true,
      pipeline: data.pipeline,
      url: data.pipeline?.web_url,
      status: data.pipeline?.status,
      message: `Pipeline triggered for project ${project_id} on branch ${ref}`
    });

  } catch (error) {
    console.error('GitLab trigger pipeline error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}