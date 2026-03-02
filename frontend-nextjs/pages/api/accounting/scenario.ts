import type { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    const { workspace_id = 'default', scenario_description = '' } = req.query;

    try {
        const url = `${BACKEND_URL}/api/ai-accounting/scenario?workspace_id=${workspace_id}&scenario_description=${encodeURIComponent(scenario_description as str)}`;

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                // 'Authorization': `Bearer ${token}` // Add auth if needed later
            },
        });

        if (!response.ok) {
            console.error(`Backend returned ${response.status}: ${await response.text()}`);
            return res.status(response.status).json({ error: 'Failed to analyze scenario from backend' });
        }

        const data = await response.json();
        return res.status(200).json(data.data); // Return the nested data array/object
    } catch (error) {
        console.error('API Route Error /accounting/scenario:', error);
        return res.status(500).json({ error: 'Internal server error while analyzing scenario' });
    }
}
