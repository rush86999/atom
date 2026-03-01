import { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    if (req.method !== 'GET') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    const authHeader = req.headers.authorization;
    // Hardcode default workspace for now as in the rest of the application
    const workspaceId = 'default';
    const { type } = req.query;

    if (!type || (type !== 'gl' && type !== 'tb')) {
        return res.status(400).json({ error: 'Invalid export type. Must be "gl" or "tb".' });
    }

    try {
        const endpoint = type === 'gl' ? '/api/ai-accounting/export/gl' : '/api/ai-accounting/export/trial-balance';
        const url = `${BACKEND_URL}${endpoint}?workspace_id=${workspaceId}`;

        const response = await fetch(url, {
            headers: {
                ...(authHeader ? { 'Authorization': authHeader } : {}),
            },
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`Backend export error: ${response.status} - ${errorText}`);
            return res.status(response.status).json({ error: `Failed to export ${type}` });
        }

        if (type === 'gl') {
            // CSV Response
            const blob = await response.blob();
            const arrayBuffer = await blob.arrayBuffer();
            const buffer = Buffer.from(arrayBuffer);

            res.setHeader('Content-Type', 'text/csv');
            res.setHeader('Content-Disposition', `attachment; filename=general_ledger_${workspaceId}.csv`);
            return res.status(200).send(buffer);
        } else {
            // JSON Response
            const data = await response.json();
            
            res.setHeader('Content-Type', 'application/json');
            res.setHeader('Content-Disposition', `attachment; filename=trial_balance_${workspaceId}.json`);
            // Send as pretty-printed JSON
            return res.status(200).send(JSON.stringify(data, null, 2));
        }

    } catch (error) {
        console.error('Export proxy error:', error);
        return res.status(500).json({ error: 'Internal server error during export' });
    }
}
