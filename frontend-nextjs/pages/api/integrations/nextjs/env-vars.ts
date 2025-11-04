/**
 * Next.js Environment Variables API
 * Manage environment variables for Next.js projects
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
      action = 'list',
      key,
      value,
      target = ['production', 'preview'],
      type = 'plain'
    } = req.body;

    if (!user_id || !project_id) {
      return res.status(400).json({ error: 'User ID and Project ID are required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/integrations/nextjs/env-vars`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id,
        project_id,
        action,
        key,
        value,
        target,
        type
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        ok: false,
        error: data.error || 'Failed to manage environment variables'
      });
    }

    return res.status(200).json({
      ok: true,
      action,
      result: data.result,
      environment_variables: data.environment_variables,
      message: `Successfully ${action}ed environment variable${key ? ` ${key}` : 's'}`
    });

  } catch (error) {
    console.error('Environment variables management error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}