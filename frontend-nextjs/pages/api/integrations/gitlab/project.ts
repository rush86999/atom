/**
 * GitLab Project Details API
 * Get detailed information about a specific GitLab project
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
      include_pipelines = true,
      include_issues = true,
      include_merge_requests = true,
      include_commits = false,
      include_branches = false,
      pipeline_limit = 10,
      issue_limit = 20,
      mr_limit = 20,
      commit_limit = 10,
      branch_limit = 50
    } = req.body;

    if (!user_id || !project_id) {
      return res.status(400).json({ error: 'User ID and Project ID are required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/integrations/gitlab/project`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id,
        project_id,
        include_pipelines,
        include_issues,
        include_merge_requests,
        include_commits,
        include_branches,
        pipeline_limit,
        issue_limit,
        mr_limit,
        commit_limit,
        branch_limit
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
      pipelines: data.pipelines || [],
      issues: data.issues || [],
      merge_requests: data.merge_requests || [],
      commits: data.commits || [],
      branches: data.branches || [],
      stats: data.stats
    });

  } catch (error) {
    console.error('GitLab project details fetch error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}