/**
 * GitLab Create Merge Request API
 * Create a new GitLab merge request
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
      source_branch,
      target_branch,
      title,
      description,
      assignee_ids,
      reviewer_ids,
      labels,
      milestone_id,
      remove_source_branch = false,
      squash = false
    } = req.body;

    if (!user_id || !project_id || !source_branch || !target_branch || !title) {
      return res.status(400).json({ 
        error: 'User ID, Project ID, Source Branch, Target Branch, and Title are required' 
      });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/integrations/gitlab/create-merge-request`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id,
        project_id,
        source_branch,
        target_branch,
        title,
        description,
        assignee_ids,
        reviewer_ids,
        labels,
        milestone_id,
        remove_source_branch,
        squash
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        ok: false,
        error: data.error || 'Failed to create merge request'
      });
    }

    return res.status(200).json({
      ok: true,
      merge_request: data.merge_request,
      url: data.merge_request?.web_url,
      message: `Merge request created: ${data.merge_request?.title || title}`
    });

  } catch (error) {
    console.error('GitLab create merge request error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}