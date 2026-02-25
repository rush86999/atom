import { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    // Get auth token from header or cookie
    const authHeader = req.headers.authorization;
    const token = authHeader?.replace('Bearer ', '') || '';

    if (req.method === 'GET') {
        try {
            const { user_id, workspace_id } = req.query;
            const queryParams = new URLSearchParams({
                user_id: (user_id as string) || 'default_user',
                workspace_id: (workspace_id as string) || 'default',
            });

            const response = await fetch(
                `${BACKEND_URL}/api/v1/preferences?${queryParams}`,
                {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json',
                    },
                }
            );

            if (!response.ok) {
                const text = await response.text();
                return res.status(response.status).json({ error: text });
            }

            const data = await response.json();
            return res.status(200).json(data);
        } catch (error) {
            console.error('Get preferences error:', error);
            return res.status(500).json({ error: 'Failed to fetch preferences' });
        }
    }

    if (req.method === 'POST') {
        try {
            const response = await fetch(`${BACKEND_URL}/api/v1/preferences`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(req.body),
            });

            if (!response.ok) {
                const text = await response.text();
                return res.status(response.status).json({ error: text });
            }

            const data = await response.json();
            return res.status(200).json(data);
        } catch (error) {
            console.error('Set preference error:', error);
            return res.status(500).json({ error: 'Failed to save preference' });
        }
    }

    return res.status(405).json({ error: 'Method not allowed' });
}
