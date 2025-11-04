/**
 * GitLab Health Check API
 * API endpoint for GitLab service health
 */

import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'GET' && req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // For POST requests, get user_id from body
    let user_id;
    if (req.method === 'POST') {
      user_id = req.body.user_id;
    }

    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/gitlab/health`, {
      method: 'GET',
      headers: user_id ? {
        'X-User-ID': user_id
      } : {}
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        status: 'unhealthy',
        services: {
          gitlab: {
            status: 'unhealthy',
            error: data.error || 'Service unavailable'
          }
        }
      });
    }

    return res.status(200).json({
      status: 'healthy',
      services: {
        gitlab: {
          status: 'healthy',
          error: null
        }
      },
      timestamp: data.timestamp || new Date().toISOString()
    });

  } catch (error) {
    console.error('GitLab health check error:', error);
    return res.status(500).json({
      status: 'unhealthy',
      services: {
        gitlab: {
          status: 'unhealthy',
          error: 'Health check failed'
        }
      }
    });
  }
}