import { NextApiRequest, NextApiResponse } from 'next';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const healthData = {
      status: 'healthy',
      service: 'atom-frontend',
      version: '1.0.0',
      timestamp: new Date().toISOString(),
      environment: process.env.NODE_ENV || 'development',
      uptime: process.uptime(),
      memory: process.memoryUsage(),
      features: {
        byok: true,
        workflowAutomation: true,
        serviceIntegrations: true,
        voiceCommands: true,
        realTimeUpdates: true
      },
      dependencies: {
        backend: 'http://localhost:8000',
        oauth: 'http://localhost:5058'
      }
    };

    res.status(200).json(healthData);
  } catch (error) {
    console.error('Health check error:', error);
    res.status(500).json({
      status: 'unhealthy',
      error: 'Internal server error',
      timestamp: new Date().toISOString()
    });
  }
}
