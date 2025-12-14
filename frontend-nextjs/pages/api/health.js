/**
 * Health check endpoint for frontend-backend connectivity
 * This endpoint proxies to the backend health check
 */

export default async function handler(req, res) {
  try {
    // Try to connect to backend health endpoint
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:5059';

    const response = await fetch(`${backendUrl}/health`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    const data = await response.json();

    // Return combined health status
    res.status(200).json({
      status: 'healthy',
      frontend: true,
      backend: response.ok,
      backend_status: response.status,
      timestamp: new Date().toISOString(),
      backend_response: data
    });
  } catch (error) {
    console.error('Health check failed:', error);
    res.status(503).json({
      status: 'unhealthy',
      frontend: true,
      backend: false,
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
}