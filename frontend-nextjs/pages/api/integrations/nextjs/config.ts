/**
 * Next.js Configuration API
 * Manage Next.js integration configuration
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
      config,
      action = 'save' 
    } = req.body;

    if (!user_id) {
      return res.status(400).json({ error: 'User ID is required' });
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    let response;

    if (action === 'save' && config) {
      response = await fetch(`${backendUrl}/api/integrations/nextjs/config`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id,
          config
        })
      });
    } else if (action === 'load') {
      response = await fetch(`${backendUrl}/api/integrations/nextjs/config`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user_id
        }
      });
    } else {
      return res.status(400).json({ error: 'Invalid action' });
    }

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        ok: false,
        error: data.error || 'Failed to manage configuration'
      });
    }

    return res.status(200).json({
      ok: true,
      config: data.config,
      message: `Configuration ${action}d successfully`
    });

  } catch (error) {
    console.error('Configuration management error:', error);
    return res.status(500).json({
      ok: false,
      error: 'Internal server error'
    });
  }
}