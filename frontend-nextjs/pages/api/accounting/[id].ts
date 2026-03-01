import { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    const authHeader = req.headers.authorization;
    const { id } = req.query;

    if (!id || typeof id !== 'string') {
        return res.status(400).json({ error: 'Transaction ID is required' });
    }

    if (req.method === 'PUT') {
        try {
            const body = req.body;
            const response = await fetch(`${BACKEND_URL}/api/ai-accounting/transactions/${id}`, {
                method: 'PUT',
                headers: {
                    ...(authHeader ? { 'Authorization': authHeader } : {}),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(body)
            });

            if (!response.ok) {
                const text = await response.text();
                return res.status(response.status).json({ error: text });
            }

            const data = await response.json();
            return res.status(200).json(data);
        } catch (error) {
            console.error(`Accounting transactions PUT ${id} error:`, error);
            return res.status(500).json({ error: 'Failed to update transaction' });
        }
    }

    if (req.method === 'DELETE') {
        try {
            const response = await fetch(`${BACKEND_URL}/api/ai-accounting/transactions/${id}`, {
                method: 'DELETE',
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
            console.error(`Accounting transactions DELETE ${id} error:`, error);
            return res.status(500).json({ error: 'Failed to delete transaction' });
        }
    }

    return res.status(405).json({ error: 'Method not allowed' });
}
