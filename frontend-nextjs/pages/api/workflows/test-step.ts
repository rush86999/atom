import type { NextApiRequest, NextApiResponse } from 'next';

/**
 * API proxy for workflow test-step endpoint
 * 
 * Enables step-by-step testing of individual workflow actions,
 * similar to Activepieces' test functionality.
 */
export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    try {
        const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

        const response = await fetch(`${backendUrl}/workflows/test-step`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(req.body),
        });

        const data = await response.json();

        return res.status(response.ok ? 200 : 400).json(data);
    } catch (error) {
        console.error('Test step API error:', error);
        return res.status(500).json({
            success: false,
            error: 'Failed to test workflow step',
        });
    }
}
