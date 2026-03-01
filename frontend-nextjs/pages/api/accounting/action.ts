
import { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    const authHeader = req.headers.authorization;
    const { action, id } = req.query;

    if (req.method === 'POST') {
        try {
            let endpoint = '';
            if (action === 'post' && id) {
                endpoint = `/api/ai-accounting/post/${id}`;
            } else if (action === 'categorize') {
                endpoint = `/api/ai-accounting/categorize`;
            } else {
                return res.status(400).json({ error: 'Invalid action or missing ID' });
            }

            const response = await fetch(`${BACKEND_URL}${endpoint}`, {
                method: 'POST',
                headers: {
                    ...(authHeader ? { 'Authorization': authHeader } : {}),
                    'Content-Type': 'application/json',
                },
                body: req.body ? JSON.stringify(req.body) : undefined,
            });

            if (!response.ok) {
                const text = await response.text();
                return res.status(response.status).json({ error: text });
            }

            const data = await response.json();
            return res.status(200).json(data);
        } catch (error) {
            console.error(`Accounting action ${action} error:`, error);
            return res.status(500).json({ error: `Failed to perform ${action}` });
        }
    }

    return res.status(405).json({ error: 'Method not allowed' });
}
