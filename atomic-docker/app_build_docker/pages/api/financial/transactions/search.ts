import { NextApiRequest, NextApiResponse } from 'next';
import axios from 'axios';

// The URL for the Python backend service
const PYTHON_BACKEND_URL = process.env.PYTHON_API_BASE_URL || 'http://localhost:5058';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  try {
    // Forward the request to the Python backend
    const response = await axios.post(`${PYTHON_BACKEND_URL}/api/transactions/search`, req.body, {
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Forward the response from the Python backend to the client
    res.status(response.status).json(response.data);
  } catch (error) {
    console.error('Error proxying to Python backend:', error.response?.data || error.message);

    // Forward the error response from the Python backend if available
    if (error.response) {
      res.status(error.response.status).json(error.response.data);
    } else {
      res.status(500).json({ error: 'Internal Server Error while proxying request' });
    }
  }
}
