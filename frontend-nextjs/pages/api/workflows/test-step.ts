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
        // FORCE 127.0.0.1 for debugging
        const backendUrl = 'http://127.0.0.1:8000';
        console.log(`[TestStep] Attempting fetch to: ${backendUrl}/workflows/test-step`);

        const response = await fetch(`${backendUrl}/workflows/test-step`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(req.body),
        });

        if (!response.ok) {
            const text = await response.text();
            console.error(`Backend returned ${response.status}: ${text}`);
            return res.status(response.status).json({
                success: false,
                error: `Backend error: ${response.status} - ${text}`,
            });
        }

        const data = await response.json();
        return res.status(200).json(data);
    } catch (error: any) {
        console.error('Test step API error:', error);
        return res.status(500).json({
            success: false,
            error: error.message || 'Failed to test workflow step',
            details: error.cause ? JSON.stringify(error.cause) : undefined
        });
    }
}
