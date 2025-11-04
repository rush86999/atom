/**
 * GitLab Create Issue API
 * Create a new GitLab issue
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
      title,
      description,
      labels,
      assignee_ids,
      milestone_id,
      weight,
      confidential = false
    } = req.body;

    if (!user_id || !project_id || !title) {
      return res.status(400).json({ error: 'User ID, Project ID, and Title are required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/integrations/gitlab/create-issue`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id,
        project_id,
        title,
        description,
        labels,
        assignee_ids,
        milestone_id,
        weight,
        confidential
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        ok: false,
        error: data.error || 'Failed to create issue'
      });
    }

    return res.status(200).json({
      ok: true,
      issue: data.issue,
      url: data.issue?.web_url,
      message: `Issue created: ${data.issue?.title || title}`
    });

  } catch (error) {
    console.error('GitLab create issue error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}