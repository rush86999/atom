
import { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    const authHeader = req.headers.authorization;

    if (req.method === 'GET') {
        try {
            const response = await fetch(`${BACKEND_URL}/api/ai-accounting/review-queue`, {
                headers: {
                    ...(authHeader ? { 'Authorization': authHeader } : {}),
                    'Content-Type': 'application/json',
                },
            });

            if (!response.ok) {
                const text = await response.text();
                return res.status(response.status).json({ error: text });
            }

            const data = await response.json();
            return res.status(200).json(data);
        } catch (error) {
            console.error('Accounting transactions error:', error);
            return res.status(500).json({ error: 'Failed to fetch transactions' });
        }
    }

    return res.status(405).json({ error: 'Method not allowed' });
}
