/**
 * GitLab Projects API
 * API endpoint for fetching GitLab projects
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
      visibility = 'all',
      archived = false,
      search,
      sort = 'updated_at',
      order = 'desc',
      include_pipelines = true,
      include_issues = true,
      include_merge_requests = true
    } = req.body;

    if (!user_id) {
      return res.status(400).json({ error: 'User ID is required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/integrations/gitlab/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id,
        limit,
        visibility,
        archived,
        search,
        sort,
        order,
        include_pipelines,
        include_issues,
        include_merge_requests
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        ok: false,
        error: data.error || 'Failed to fetch GitLab projects'
      });
    }

    return res.status(200).json({
      ok: true,
      projects: data.projects || [],
      pipelines: data.pipelines || [],
      issues: data.issues || [],
      merge_requests: data.merge_requests || [],
      total: data.projects?.length || 0
    });

  } catch (error) {
    console.error('GitLab projects fetch error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}