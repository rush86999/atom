export const config = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL || process.env.API_BASE_URL || process.env.PYTHON_BACKEND_URL || 'http://localhost:8000',
  wsUrl: process.env.NEXT_PUBLIC_WS_URL || process.env.NEXT_PUBLIC_API_URL?.replace('http', 'ws') || 'ws://localhost:8000'
};