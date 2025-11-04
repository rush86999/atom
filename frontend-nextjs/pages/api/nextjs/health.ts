/**
 * Next.js Health Check Endpoint
 * Check health of Next.js integration services
 */

import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Forward request to backend service
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/nextjs/health`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json({
        services: {
          nextjs: {
            status: 'unhealthy',
            error: data.error || 'Service unavailable'
          }
        }
      });
    }

    return res.status(200).json(data);

  } catch (error) {
    console.error('Next.js health check error:', error);
    return res.status(500).json({
      services: {
        nextjs: {
          status: 'unhealthy',
          error: 'Internal server error'
        }
      }
    });
  }
}