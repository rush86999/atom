import type { NextApiRequest, NextApiResponse } from 'next'

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  const healthData = {
    status: 'healthy',
    service: 'atom-frontend-minimal',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    environment: process.env.NODE_ENV || 'development',
    features: {
      backend: true,
      api: true,
      health: true,
    },
  }

  res.status(200).json(healthData)
}
