import { NextApiRequest, NextApiResponse } from 'next';
import axios from 'axios';

const PYTHON_BACKEND_URL = process.env.PYTHON_API_BASE_URL || 'http://localhost:5058';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  try {
    const response = await axios.get(`${PYTHON_BACKEND_URL}/api/financial/budgets/summary`, {
      params: req.query, // Forward query parameters
    });
    res.status(response.status).json(response.data);
  } catch (error) {
    console.error('Error proxying to Python backend:', error.response?.data || error.message);
    if (error.response) {
      res.status(error.response.status).json(error.response.data);
    } else {
      res.status(500).json({ error: 'Internal Server Error while proxying request' });
    }
  }
}
