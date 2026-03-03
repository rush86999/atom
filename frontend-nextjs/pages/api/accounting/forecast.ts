import type { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    if (req.method !== 'GET') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    const { workspace_id = 'default' } = req.query;

    try {
        const url = `${BACKEND_URL}/api/ai-accounting/forecast?workspace_id=${workspace_id}`;

        const response = await fetch(url, {
            method: 'GET',
            headers: {
                // 'Authorization': `Bearer ${token}` // Add auth if needed later
            },
        });

        if (!response.ok) {
            console.error(`Backend returned ${response.status}: ${await response.text()}`);
            return res.status(response.status).json({ error: 'Failed to fetch forecast from backend' });
        }

        const data = await response.json();
        return res.status(200).json(data.data); // Return the nested data array/object
    } catch (error) {
        console.error('API Route Error /accounting/forecast:', error);
        return res.status(500).json({ error: 'Internal server error while fetching forecast' });
    }
}
