/**
 * GitLab Merge Requests API
 * API endpoint for fetching GitLab merge requests
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
      state = 'opened',
      source_branch,
      target_branch,
      author,
      assignee,
      labels,
      milestone,
      limit = 100
    } = req.body;

    if (!user_id) {
      return res.status(400).json({ error: 'User ID is required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/integrations/gitlab/merge-requests`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id,
        project_id,
        state,
        source_branch,
        target_branch,
        author,
        assignee,
        labels,
        milestone,
        limit
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        ok: false,
        error: data.error || 'Failed to fetch GitLab merge requests'
      });
    }

    return res.status(200).json({
      ok: true,
      merge_requests: data.merge_requests || [],
      total: data.merge_requests?.length || 0
    });

  } catch (error) {
    console.error('GitLab merge requests fetch error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}