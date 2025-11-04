/**
 * GitLab Branches API
 * API endpoint for fetching GitLab branches
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
      search,
      limit = 100
    } = req.body;

    if (!user_id || !project_id) {
      return res.status(400).json({ error: 'User ID and Project ID are required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/integrations/gitlab/branches`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id,
        project_id,
        search,
        limit
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        ok: false,
        error: data.error || 'Failed to fetch GitLab branches'
      });
    }

    return res.status(200).json({
      ok: true,
      branches: data.branches || [],
      default_branch: data.default_branch,
      total: data.branches?.length || 0
    });

  } catch (error) {
    console.error('GitLab branches fetch error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}