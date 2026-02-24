import { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    const { key, user_id, workspace_id } = req.query;
    const authHeader = req.headers.authorization;
    const token = authHeader?.replace('Bearer ', '') || '';

    if (req.method === 'GET') {
        try {
            const queryParams = new URLSearchParams({
                user_id: (user_id as string) || 'default_user',
                workspace_id: (workspace_id as string) || 'default',
            });

            const response = await fetch(
                `${BACKEND_URL}/api/v1/preferences/${key}?${queryParams}`,
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
            console.error('Get preference error:', error);
            return res.status(500).json({ error: 'Failed to fetch preference' });
        }
    }

    return res.status(405).json({ error: 'Method not allowed' });
}
